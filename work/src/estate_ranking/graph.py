"""Public pedestrian graph API, physical edges and lift-identity routing states."""
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.sparse import csr_matrix, save_npz, load_npz
from scipy.sparse.csgraph import connected_components, dijkstra

from .export import read_geodataframe, write_json
from .graph_costs import build_profile, total_or_none
from .graph_topology import build_topology, report_crossings, stable_id
from .policy import load_policy


WORK = Path(__file__).resolve().parents[2]
KNOWN_TYPES = {'Footway','Footbridge','Subway','Service Lane','Traffic Island','RunIn',
    'Escalator','Travelator','Lift','Ramp','Staircase','Stairlift','Other','M_Footway',
    'M_Escalator','M_Travelator','M_Lift','M_Ramp','M_Staircase','M_Stairlift','M_Others',
    'Generalized Walkway inside Park','Footpath','Village','Track','Crossing - Signalized',
    'Crossing - Zebra','Crossing - Cautionary','Crossing - Others'}


@dataclass
class PhysicalGraph:
    nodes: gpd.GeoDataFrame
    edges: gpd.GeoDataFrame
    sources: gpd.GeoDataFrame
    memberships: pd.DataFrame
    profiles: list
    review: list
    policy: dict


@dataclass
class RoutingGraph:
    nodes: gpd.GeoDataFrame
    edges: gpd.GeoDataFrame
    matrix: csr_matrix
    states: pd.DataFrame
    transitions: pd.DataFrame
    wheelchair: bool
    metric: str
    physical: PhysicalGraph

    @property
    def edge_mapping(self):
        """One row per CSR entry, in CSR data order (including stored zeros)."""
        return self.transitions

    def costs_from(self, node_index):
        """Start outside a lift; reduce destination states to physical nodes."""
        base = int(self.states.index[(self.states.node_index == node_index) &
                                     self.states.lift_id.isna()][0])
        costs = dijkstra(self.matrix, indices=base, directed=True)
        reduced = np.full(len(self.nodes), np.inf)
        np.minimum.at(reduced, self.states.node_index.to_numpy(dtype=int), costs)
        return reduced


def _source_reasons(row, policy, wheelchair):
    reasons = []
    if pd.isna(row.Enabled_bool):
        reasons.append('unsupported_enabled_code')
    elif not row.Enabled_bool:
        reasons.append('enabled_false')
    if pd.isna(row.Direction) or row.Direction not in (-1,0,1):
        reasons.append('unsupported_direction_code')
    kind = row.FeatureType_label
    if pd.isna(kind) or kind not in KNOWN_TYPES:
        reasons.append('unsupported_feature_type')
    elif kind in policy['modes']['wheelchair' if wheelchair else 'general']['excluded_path_types']:
        reasons.append('excluded_path_type')
    if wheelchair:
        if pd.isna(row.WheelchairBarrier_bool):
            reasons.append('unsupported_wheelchair_barrier_code')
        elif row.WheelchairBarrier_bool:
            reasons.append('wheelchair_barrier')
    return reasons


def build_physical_graph(network, policy=None, progress=lambda message: None, audit_crossings=True):
    policy = policy or load_policy(WORK / 'config/routing_policy.json')
    # Do not silently accept a policy different from the tested executable rules.
    if policy.get('always_open') is not True:
        raise ValueError('Step 2 requires the agreed always-open policy')
    transport = policy['transport_time']
    constants = {'walking_model':'standard_tobler','maximum_speed_kmh':6.,
                 'exponential_coefficient':3.5,'slope_offset':.05}
    if any(transport.get(k) != v for k,v in constants.items()):
        raise ValueError('Unsupported Tobler policy')
    sample = policy['gradient']['equal_height']
    if sample['points_per_round'] != 4 or sample['maximum_rounds'] != 2:
        raise ValueError('Unsupported sampling policy')
    topology = policy['topology']
    if topology['horizontal_tolerance_metres'] != .10 or topology['height_tolerance_metres'] != .025:
        raise ValueError('Unsupported topology tolerances')
    if (policy['transport_time']['lift_travel_seconds'] != 30 or
        policy['transport_time']['lift_wait_seconds'] != 0 or
        policy['transport_time']['wheelchair_speed_model'] != 'standard_tobler' or
        policy['transport_time']['other_equipment_time_model'] != 'standard_tobler' or
        policy['gradient']['equal_height']['random_seed'] != 20261013 or
        policy['gradient']['equal_height']['height_tolerance_metres'] != 0):
        raise ValueError('Unsupported Step 2 cost policy')
    if not isinstance(network, gpd.GeoDataFrame):
        network = read_geodataframe(Path(network).resolve(), 'network')
    if network.crs is None or network.crs.to_epsg() != 2326:
        raise ValueError('Network must use EPSG:2326')
    required = {'PedestrianRouteID','FeatureType_label','Direction','Enabled_bool',
                'WheelchairBarrier_bool','Gradient','FloorID','BuildingID_1','BuildingID_2'}
    if required - set(network):
        raise ValueError('Missing graph fields: ' + str(sorted(required-set(network))))
    if network.attrs.get('vertical_crs') not in (None,'EPSG:5738'):
        raise ValueError('Network heights must use HKPD (EPSG:5738)')
    sources = network.copy()
    sources.attrs['vertical_crs'] = 'EPSG:5738'
    if sources.PedestrianRouteID.isna().any() or sources.PedestrianRouteID.duplicated().any():
        raise ValueError('Missing/duplicate PedestrianRouteID')
    sources = sources.sort_values('PedestrianRouteID').reset_index(drop=True)
    for mode,wheelchair in [('general',False),('wheelchair',True)]:
        reasons = [_source_reasons(row,policy,wheelchair) for row in sources.itertuples()]
        sources[mode+'_exclusion'] = [';'.join(r) for r in reasons]
        sources['allow_'+mode] = [not r for r in reasons]
    review = []
    union = sources.allow_general | sources.allow_wheelchair
    selected = sources.loc[union].copy().reset_index(drop=True)
    source_profiles, eligible_profiles = [], []
    for i,row in enumerate(sources.itertuples()):
        geom = row.geometry
        if geom is None or geom.is_empty or not geom.has_z:
            raise ValueError('Missing XYZ geometry: ' + str(row.PedestrianRouteID))
        if geom.geom_type == 'MultiLineString':
            if len(geom.geoms) != 1:
                raise ValueError('Multipart routing order unsupported: ' + str(row.PedestrianRouteID))
            geom = geom.geoms[0]
        if geom.geom_type != 'LineString':
            raise ValueError('Unsupported geometry: ' + str(row.PedestrianRouteID))
        coords = np.asarray(geom.coords, dtype=float)
        if coords.shape[1] != 3 or not np.isfinite(coords).all():
            raise ValueError('Invalid XYZ: ' + str(row.PedestrianRouteID))
        if pd.isna(row.Gradient) or not np.isfinite(row.Gradient):
            raise ValueError('Missing or nonfinite Gradient: ' + str(row.PedestrianRouteID))
        profile = build_profile(str(row.PedestrianRouteID),coords,float(row.Gradient),
                                row.FeatureType_label in {'Lift','M_Lift'})
        source_profiles.append(profile)
        if union.iloc[i]:
            eligible_profiles.append(profile)
        if i % 100000 == 0:
            progress('Source profiles: {}/{}'.format(i,len(sources)))
    sources['time_forward_status'] = [p.forward_status for p in source_profiles]
    sources['time_reverse_status'] = [p.reverse_status for p in source_profiles]
    sources['sample_rounds'] = [p.rounds for p in source_profiles]
    sources['cost_classification'] = [p.classification for p in source_profiles]
    nodes,memberships,cuts = build_topology(selected,eligible_profiles,review,progress)
    progress('Creating physical pieces')
    rows = []
    for i,(row,profile) in enumerate(zip(selected.itertuples(),eligible_profiles)):
        ordered = sorted(cuts[i])
        for start,end in zip(ordered,ordered[1:]):
            cost = profile.piece_costs(start,end)
            rows.append({'edge_id': stable_id('E-', [(str(row.PedestrianRouteID),start),
                                                    (str(row.PedestrianRouteID),end)]),
                'source_id':str(row.PedestrianRouteID),'start_position':start,'end_position':end,
                'from_node':cuts[i][start],'to_node':cuts[i][end], 'direction':int(row.Direction),
                'allow_general':bool(row.allow_general),'allow_wheelchair':bool(row.allow_wheelchair),
                'lift_id':str(row.PedestrianRouteID) if profile.lift else None,
                'distance_m':cost.distance_m,'time_forward_s':cost.forward_seconds,'time_reverse_s':cost.reverse_seconds,
                'time_forward_status':cost.forward_status,'time_reverse_status':cost.reverse_status,
                'gradient_radians':profile.gradient,'geometry':profile.geometry(start,end)})
    columns = ['edge_id','source_id','start_position','end_position','from_node','to_node','direction',
               'allow_general','allow_wheelchair','lift_id','distance_m','time_forward_s','time_reverse_s',
               'time_forward_status','time_reverse_status','gradient_radians','geometry']
    edges = gpd.GeoDataFrame(rows,columns=columns,crs=2326).sort_values('edge_id').reset_index(drop=True)
    edges['edge_index'] = np.arange(len(edges))
    for frame in (nodes,edges,sources):
        frame.attrs.update(vertical_crs='EPSG:5738',height_datum='Hong Kong Principal Datum',
                           alignment_cost='none; original horizontal run retained')
    if audit_crossings:
        report_crossings(selected,eligible_profiles,review,progress)
    physical = PhysicalGraph(nodes,edges,sources,memberships,source_profiles,review,policy)
    validate_physical(physical)
    return physical


def build_graph(network, wheelchair=False, metric='time', policy=None):
    """Build from an EPSG:2326 XYZ GeoDataFrame or a frozen Step 1 directory."""
    return routing_graph(build_physical_graph(network,policy),wheelchair,metric)


def minimum_matrix(transitions, state_count):
    """Choose one minimum alternative; never sum parallel edge costs in COO."""
    columns = ['from_state','to_state','cost','edge_index','direction','source_id']
    table = pd.DataFrame(transitions,columns=columns)
    if len(table):
        table = (table.sort_values(['from_state','to_state','cost','edge_index','direction'], kind='stable')
                 .drop_duplicates(['from_state','to_state']).reset_index(drop=True))
        if not np.isfinite(table.cost).all() or (table.cost < 0).any():
            raise ValueError('Routing costs must be finite and nonnegative')
    # Construct directly from unique, sorted pairs. Stored zeros are deliberate.
    rows = table.from_state.to_numpy(dtype=int)
    columns_index = table.to_state.to_numpy(dtype=int)
    counts = np.bincount(rows,minlength=state_count)
    matrix = csr_matrix((table.cost.to_numpy(dtype=float),columns_index,
                         np.r_[0,np.cumsum(counts)]), shape=(state_count,state_count))
    return matrix,table


def routing_graph(physical, wheelchair=False, metric='time'):
    if metric not in {'time','distance'}:
        raise ValueError('metric must be time or distance')
    edges = physical.edges
    allowed = edges.loc[edges['allow_wheelchair' if wheelchair else 'allow_general']]
    state_keys = [(i,None) for i in range(len(physical.nodes))]
    if metric == 'time':
        lifts = set()
        for row in allowed.loc[allowed.lift_id.notna()].itertuples():
            lifts.add((row.from_node,str(row.lift_id)))
            lifts.add((row.to_node,str(row.lift_id)))
        state_keys.extend(sorted(lifts))
    states = pd.DataFrame(state_keys,columns=['node_index','lift_id'])
    states['state_index'] = np.arange(len(states))
    lookup = {key:i for i,key in enumerate(state_keys)}
    by_node = {}
    for i,(node,lift) in enumerate(state_keys):
        by_node.setdefault(node,[]).append((i,lift))
    transitions = []
    for edge in allowed.itertuples():
        for direction in (1,-1):
            if edge.direction not in (0,direction):
                continue
            a,b = (edge.from_node,edge.to_node) if direction==1 else (edge.to_node,edge.from_node)
            cost = edge.distance_m if metric=='distance' else (edge.time_forward_s if direction==1 else edge.time_reverse_s)
            if pd.isna(cost) or not np.isfinite(cost):
                continue
            lift = str(edge.lift_id) if pd.notna(edge.lift_id) and metric=='time' else None
            target = lookup[(b,lift)]
            for current,last_lift in by_node[a]:
                weight = (0. if last_lift==lift else 30.) if lift else float(cost)
                transitions.append((current,target,weight,int(edge.edge_index),direction,str(edge.source_id)))
    matrix,mapping = minimum_matrix(transitions,len(states))
    return RoutingGraph(physical.nodes,physical.edges,matrix,states,mapping,bool(wheelchair),metric,physical)


def validate_physical(physical):
    edges,sources = physical.edges,physical.sources
    if physical.nodes.node_id.duplicated().any() or edges.edge_id.duplicated().any():
        raise AssertionError('Duplicate derived identities')
    union = sources.allow_general | sources.allow_wheelchair
    expected = set(sources.loc[union].PedestrianRouteID.astype(str))
    if set(edges.source_id) != expected:
        raise AssertionError('Every eligible source must have physical pieces')
    ordered = edges.sort_values(['source_id','start_position'])
    previous = ordered.groupby('source_id',sort=False).end_position.shift()
    first = previous.isna()
    if not (ordered.loc[first,'start_position'] == 0).all():
        raise AssertionError('Missing source starts')
    if not np.array_equal(previous[~first],ordered.loc[~first,'start_position']):
        raise AssertionError('Gap/overlap in source pieces')
    grouped = edges.groupby('source_id',sort=False)
    # An entirely time-unavailable graph has object columns containing only
    # None. Convert aggregate missing values to numeric NaN before isfinite.
    sums = grouped[['distance_m','time_forward_s','time_reverse_s']].sum(min_count=1).astype(float)
    for column in ('time_forward_s','time_reverse_s'):
        sums.loc[(grouped[column].count() != grouped.size()) | ~np.isfinite(sums[column]), column] = np.nan
    ends = grouped.end_position.max()
    profiles = [p for p in physical.profiles if p.source_id in expected]
    values = [p.piece(0,len(p.coords)-1) for p in profiles]
    wanted = pd.DataFrame(values,index=[p.source_id for p in profiles],
                          columns=['distance_m','time_forward_s','time_reverse_s']).reindex(sums.index)
    if not np.allclose(sums.to_numpy(dtype=float),wanted.to_numpy(dtype=float),
                       rtol=2e-12,atol=1e-8,equal_nan=True):
        raise AssertionError('Splitting changed source distance/time')
    by_source = {p.source_id:p for p in profiles}
    # Check each stored piece against its overlapping original intervals,
    # including healthy pieces from sources whose overall time is unavailable.
    for row in edges.itertuples():
        expected_piece = by_source[row.source_id].piece_costs(row.start_position,row.end_position)
        for value,wanted_value,status,wanted_status in (
            (row.time_forward_s,expected_piece.forward_seconds,row.time_forward_status,expected_piece.forward_status),
            (row.time_reverse_s,expected_piece.reverse_seconds,row.time_reverse_status,expected_piece.reverse_status)):
            if status != wanted_status or (pd.isna(value) != (wanted_value is None)):
                raise AssertionError('Piece directional status does not match overlapping intervals')
            if wanted_value is not None and not np.isclose(value,wanted_value,rtol=2e-12,atol=1e-8):
                raise AssertionError('Piece time does not match overlapping intervals')
    final_positions = pd.Series({p.source_id:len(p.coords)-1 for p in profiles}).reindex(ends.index)
    if not np.array_equal(final_positions,ends):
        raise AssertionError('Missing source ends')
    return {'source_rows':len(sources),'general_eligible_sources':int(sources.allow_general.sum()),
            'wheelchair_eligible_sources':int(sources.allow_wheelchair.sum()),
            'union_eligible_sources':int(union.sum()), 'physical_pieces':len(edges),'nodes':len(physical.nodes),
            'all_sources_accounted_for':True, 'piece_coverage_and_cost_conservation':True,
            'general_exclusions':dict(Counter(sources.general_exclusion)),
            'wheelchair_exclusions':dict(Counter(sources.wheelchair_exclusion)),
            'time_forward_status':dict(Counter(sources.time_forward_status)),
            'time_reverse_status':dict(Counter(sources.time_reverse_status)),
            'piece_time_forward_status':dict(Counter(edges.time_forward_status)),
            'piece_time_reverse_status':dict(Counter(edges.time_reverse_status)),
            'healthy_piece_directions_from_unavailable_sources':int(sum(
                ((edges['time_'+d+'_status']=='available') &
                 edges.source_id.isin(sources.loc[sources['time_'+d+'_status']!='available',
                                                  'PedestrianRouteID'].astype(str))).sum()
                for d in ('forward','reverse'))),
            'piece_local_costs_and_statuses_checked':True,
            'review_counts':dict(Counter(r['kind'] for r in physical.review))}


def connectivity(graph):
    active = np.unique(np.r_[graph.transitions.from_state,graph.transitions.to_state]).astype(int)
    subgraph = graph.matrix[active][:,active]
    result = {'states':len(graph.states),'active_states':len(active),'stored_entries':graph.matrix.nnz,
              'stored_zero_cost_entries':int((graph.matrix.data==0).sum())}
    for connection in ('weak','strong'):
        count,labels = connected_components(subgraph,directed=True,connection=connection)
        sizes = np.bincount(labels)
        result[connection+'_components'] = int(count)
        result[connection+'_largest_sizes'] = sorted(sizes.tolist(),reverse=True)[:20]
    return result


def _write_frame(directory,name,frame):
    # CSV is sufficient for nonspatial states/mappings. GeoPackage retains XYZ.
    if isinstance(frame,gpd.GeoDataFrame):
        frame.to_file(directory/'graph.gpkg',layer=name,driver='GPKG',engine='pyogrio')
    else:
        frame.to_csv(directory/(name+'.csv'),index=False)


def save_physical(directory,physical):
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    schema = {}
    for name in ('nodes','edges','sources'):
        frame = getattr(physical,name)
        _write_frame(directory,name,frame)
        schema[name] = {k:str(frame[k].dtype) for k in frame.columns if k!='geometry'}
    _write_frame(directory,'memberships',physical.memberships)
    write_json(directory/'schema.json',{'spatial_dtypes':schema,'horizontal_crs':'EPSG:2326',
               'vertical_crs':'EPSG:5738','distance_unit':'metres','time_unit':'seconds',
               'piece_parameter':'original_vertex_index_plus_fraction',
               'source_geometry':'unaltered original XYZ; derived edges retain original interpolated XYZ',
               'node_geometry':'canonical member; corrections in memberships, no added cost'})
    write_json(directory/'model_policy.json',physical.policy)
    for name,values in [('profiles', (p.evidence() for p in physical.profiles)),('review',physical.review)]:
        with (directory/(name+'.jsonl')).open('w') as f:
            for value in values:
                f.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')


def save_routing(directory,graph):
    prefix = ('wheelchair' if graph.wheelchair else 'general')+'_'+graph.metric
    save_npz(Path(directory)/(prefix+'.npz'),graph.matrix)
    graph.states.to_csv(Path(directory)/(prefix+'_states.csv'),index=False)
    graph.transitions.to_csv(Path(directory)/(prefix+'_transitions.csv'),index=False)


def read_physical(directory):
    directory = Path(directory).resolve()
    schema = json.loads((directory/'schema.json').read_text())
    frames = {}
    for name,dtypes in schema['spatial_dtypes'].items():
        frame = gpd.read_file(directory/'graph.gpkg',layer=name,engine='pyogrio',datetime_as_string=True)
        for col,dtype in dtypes.items():
            # Empty exclusion text must not become a null on GeoPackage reopen.
            if dtype == 'object' and col.endswith('_exclusion'):
                frame[col] = frame[col].fillna('')
            frame[col] = frame[col].astype(dtype)
        frame.attrs.update(vertical_crs=schema['vertical_crs'],height_datum='Hong Kong Principal Datum')
        frames[name] = frame
    return PhysicalGraph(frames['nodes'],frames['edges'],frames['sources'],
                         pd.read_csv(directory/'memberships.csv',dtype={'source_id':str,'node_id':str},float_precision='round_trip'),[],[],
                         json.loads((directory/'model_policy.json').read_text()))


def read_graph(directory=None, wheelchair=False, metric='time'):
    """Reopen physical GeoDataFrames and persisted CSR with source-edge mapping.

    Start at the node's lift_id=None state. A destination accepts the minimum
    across all its lift states; costs_from implements this convention.
    """
    if metric not in {'time','distance'}:
        raise ValueError('metric must be time or distance')
    directory = Path(directory or WORK/'precomputed/outputs/step_2/current').resolve()
    return _read_routing(directory, read_physical(directory), wheelchair, metric)


def _read_routing(directory, physical, wheelchair, metric):
    directory = Path(directory)
    prefix = ('wheelchair' if wheelchair else 'general')+'_'+metric
    states = pd.read_csv(directory/(prefix+'_states.csv'),dtype={'lift_id':str})
    transitions = pd.read_csv(directory/(prefix+'_transitions.csv'),dtype={'source_id':str},float_precision='round_trip')
    matrix = load_npz(directory/(prefix+'.npz'))
    if matrix.shape != (len(states),len(states)) or matrix.nnz != len(transitions):
        raise ValueError('Saved state/matrix/mapping mismatch')
    rows = np.repeat(np.arange(matrix.shape[0]),np.diff(matrix.indptr))
    if (not np.array_equal(rows,transitions.from_state) or
        not np.array_equal(matrix.indices,transitions.to_state) or
        not np.array_equal(matrix.data,transitions.cost)):
        raise ValueError('Saved matrix/source mapping changed')
    return RoutingGraph(physical.nodes,physical.edges,matrix,states,transitions,bool(wheelchair),metric,physical)
