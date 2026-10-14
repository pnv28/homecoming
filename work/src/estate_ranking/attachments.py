"""Facility attachments, source-position subdivisions and one-way terminals.

X/Y connectors are accepted map-point approximations. Entity Z remains unknown;
only attachment points carry the original path's interpolated HKPD height.
"""
from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point
from scipy.sparse import load_npz

from .export import read_geodataframe, write_json
from .graph import (WORK, PhysicalGraph, RoutingGraph, minimum_matrix, read_physical,
                    routing_graph, save_routing)
from .graph_costs import build_profile, interpolate_xyz, tobler_seconds
from .graph_topology import height_ok, stable_id


ORDINARY_TYPES = {'Footway', 'M_Footway', 'Ramp', 'M_Ramp', 'Service Lane',
    'Traffic Island', 'RunIn', 'Generalized Walkway inside Park', 'Footpath',
    'Village', 'Track', 'Crossing - Signalized', 'Crossing - Zebra',
    'Crossing - Cautionary', 'Crossing - Others'}
ATTACHMENT_POLICY = {
    'version': 1, 'maximum_connector_m': {'estate': 200., 'hospital': 200.,
                                         'mtr_access': 200., 'bus_stop': 50.},
    'ordinary_feature_types': sorted(ORDINARY_TYPES),
    'location_preference': ['Outdoor', 'Indoor'],
    'unknown_location': 'exclude', 'unknown_entity_height': 'preserve_unknown',
    'level_selection': 'nearest_horizontal_then_lower_height_then_source_position',
    'alternative_distance_window_m': 1., 'alternative_height_difference_m': 2.,
    'long_connector_warning_m': 50., 'connector_speed_kmh': 6 * math.exp(-3.5 * .05),
    'connector_model': 'horizontal_straight_line_flat_tobler',
    'reuse_horizontal_m': .10, 'reuse_height_m': .025,
    'estate_terminal': 'outgoing_only_no_current_lift',
    'destination_terminal': 'incoming_only_all_attachment_lift_states',
    'zero_distance': 'explicit_zero_cost_transition_no_line_geometry'}
LAYERS = {'estate': 'estates', 'hospital': 'hospitals',
          'mtr_access': 'mtr_exits', 'bus_stop': 'bus_stops'}


@dataclass
class AttachedPoints:
    physical: PhysicalGraph
    entities: dict
    attachments: gpd.GeoDataFrame
    connectors: gpd.GeoDataFrame
    candidates: pd.DataFrame
    validation: dict


@dataclass
class AttachedGraph(RoutingGraph):
    entities: dict
    attachments: gpd.GeoDataFrame
    connectors: gpd.GeoDataFrame
    terminals: pd.DataFrame

    def costs_from_entity(self, entity_id):
        row = self.terminals.loc[self.terminals.entity_id == entity_id]
        if len(row) != 1 or row.iloc[0].role != 'departure':
            raise ValueError('Expected one estate departure terminal')
        from scipy.sparse.csgraph import dijkstra
        return dijkstra(self.matrix, indices=int(row.iloc[0].state_index), directed=True)

    def costs_from(self, node_index):
        """Physical-node reduction excludes facility terminals with unknown Z."""
        from scipy.sparse.csgraph import dijkstra
        network = self.states.loc[self.states.state_kind == 'physical']
        base = network.loc[(network.node_index == node_index) & network.lift_id.isna()]
        costs = dijkstra(self.matrix, indices=int(base.iloc[0].state_index), directed=True)
        reduced = np.full(len(self.nodes), np.inf)
        np.minimum.at(reduced, network.node_index.to_numpy(dtype=int),
                      costs[network.state_index.to_numpy(dtype=int)])
        return reduced


def load_entities(directory):
    return {kind: read_geodataframe(directory, layer) for kind, layer in LAYERS.items()}


def _eligible(entity, kind, wheelchair):
    if kind == 'mtr_access':
        value = entity['wheelchair_mode_candidate' if wheelchair else 'general_mode_candidate']
    elif kind == 'bus_stop':
        value = entity['wheelchair_boarding_candidate' if wheelchair else 'general_boarding_candidate']
    else:
        return True
    return bool(value) if pd.notna(value) else False


def _can_use(edge, position, role, metric):
    """At a one-way endpoint the selected piece must allow the terminal's role."""
    for direction in (1, -1):
        if edge.direction not in (0, direction):
            continue
        cost = edge.distance_m if metric == 'distance' else getattr(
            edge, 'time_forward_s' if direction == 1 else 'time_reverse_s')
        if pd.isna(cost) or not np.isfinite(cost):
            continue
        departure_end = edge.end_position if direction == 1 else edge.start_position
        arrival_end = edge.start_position if direction == 1 else edge.end_position
        if position != (departure_end if role == 'departure' else arrival_end):
            return True
        # A physical self-loop has a permitted transition even at its endpoint.
        if edge.from_node == edge.to_node:
            return True
    return False


class SegmentIndex:
    """Index original segments of eligible pieces; never collapse repeated visits."""
    def __init__(self, physical, wheelchair, metric):
        self.edges = {int(r.edge_index): r for r in physical.edges.itertuples()}
        sources = physical.sources.set_index(physical.sources.PedestrianRouteID.astype(str))
        ordinary = sources.loc[sources.FeatureType_label.isin(ORDINARY_TYPES)]
        self.context = {}
        for row in ordinary.itertuples():
            sid = str(row.PedestrianRouteID)
            self.context[sid] = {'location': getattr(row, 'Location_label', 'Outdoor'),
                'floor': None if pd.isna(row.FloorID) else str(row.FloorID),
                'buildings': [str(getattr(row, k)) for k in ('BuildingID_1', 'BuildingID_2')
                              if pd.notna(getattr(row, k))], 'kind': row.FeatureType_label}
        geometry, records = [], []
        for edge in physical.edges.itertuples():
            context = self.context.get(edge.source_id)
            if not context or context['location'] not in ('Outdoor', 'Indoor'):
                continue
            if not getattr(edge, 'allow_wheelchair' if wheelchair else 'allow_general'):
                continue
            if not _can_use(edge, (edge.start_position + edge.end_position) / 2,
                            'departure', metric):
                continue
            coords = np.asarray(edge.geometry.coords)
            positions = np.r_[edge.start_position,
                np.arange(math.floor(edge.start_position) + 1, math.ceil(edge.end_position)),
                edge.end_position]
            if len(positions) != len(coords):
                raise AssertionError('Piece geometry/source parameter mismatch')
            for a, b, start, end in zip(coords[:-1], coords[1:], positions[:-1], positions[1:]):
                if np.array_equal(a[:2], b[:2]):
                    continue  # No facility level inferred on vertical/zero-run segments.
                geometry.append(LineString([a[:2], b[:2]]))
                records.append((int(edge.edge_index), float(start), float(end), a, b))
        self.geometry = np.array(geometry, dtype=object)
        self.records = records
        self.tree = shapely.STRtree(self.geometry)
        self.metric = metric

    def candidates(self, point, limit, role):
        indices = self.tree.query(point, predicate='dwithin', distance=limit)
        if not len(indices):
            return []
        segments = self.geometry[indices]
        along = shapely.line_locate_point(segments, point, normalized=True)
        xy = shapely.get_coordinates(shapely.line_interpolate_point(segments, along, normalized=True))
        distances = np.linalg.norm(xy - np.array([point.x, point.y]), axis=1)
        result = {}
        for idx, f, distance in zip(indices, along, distances):
            if distance > limit:
                continue
            edge_index, start, end, a, b = self.records[int(idx)]
            edge = self.edges[edge_index]
            position = float(start + f * (end - start))
            if not _can_use(edge, position, role, self.metric):
                continue
            xyz = a + f * (b - a)
            context = self.context[edge.source_id]
            item = dict(source_id=edge.source_id, parent_edge_index=edge_index,
                parent_edge_id=edge.edge_id, source_position=position, distance_m=float(distance),
                x=float(xyz[0]), y=float(xyz[1]), height_m=float(xyz[2]), **context)
            # Shared vertices of adjacent segments/pieces are one source position.
            key = (edge.source_id, position)
            if key not in result or edge.edge_id < result[key]['parent_edge_id']:
                result[key] = item
        return list(result.values())


def _different_floor(a, b):
    return (a['floor'] is not None and b['floor'] is not None and a['floor'] != b['floor']
            and bool(set(a['buildings']) & set(b['buildings'])))


def select_attachments(physical, entities, progress=lambda message: None):
    rows, reviews = [], []
    for wheelchair in (False, True):
        mode = 'wheelchair' if wheelchair else 'general'
        progress('Index ordinary horizontal segments: ' + mode)
        # Distance eligibility includes time-unavailable pieces. The per-query
        # role/cost filter removes those from time searches, allowing one spatial
        # index to serve both metrics without changing candidate selection.
        index = SegmentIndex(physical, wheelchair, 'distance')
        for metric in ('time', 'distance'):
            progress('Select attachments: ' + mode + '_' + metric)
            index.metric = metric
            for kind, frame in entities.items():
                if kind != 'estate' and metric != ('distance' if kind == 'hospital' else 'time'):
                    continue
                role = 'departure' if kind == 'estate' else 'arrival'
                limit = ATTACHMENT_POLICY['maximum_connector_m'][kind]
                for entity_number, entity in enumerate(frame.to_dict('records')):
                    if entity_number and entity_number % 2000 == 0:
                        progress('{} {} {}: {}/{}'.format(mode, metric, kind, entity_number, len(frame)))
                    aid = '{}:{}:{}'.format(entity['id'], mode, metric)
                    row = dict(attachment_id=aid, entity_id=entity['id'], entity_type=kind,
                        mode=mode, metric=metric, role=role, maximum_distance_m=limit,
                        status='excluded', reason='mode_excluded', warnings='', geometry=None,
                        source_id=None, parent_edge_id=None, parent_edge_index=None,
                        source_position=None, distance_m=None, time_s=None, height_m=None,
                        node_index=None, reused_node=False, zero_distance=False,
                        candidate_count=0, tied_count=0, alternative_level=False)
                    if not _eligible(entity, kind, wheelchair):
                        rows.append(row)
                        continue
                    candidates = index.candidates(entity['geometry'], limit, role)
                    outdoor = [c for c in candidates if c['location'] == 'Outdoor']
                    pool = outdoor or [c for c in candidates if c['location'] == 'Indoor']
                    row['candidate_count'] = len(candidates)
                    if not pool:
                        row.update(status='unattached', reason='no_suitable_path_within_limit')
                        rows.append(row)
                        continue
                    pool.sort(key=lambda c: (c['distance_m'], c['height_m'],
                                             c['source_id'], c['source_position']))
                    chosen = pool[0]
                    tied = [c for c in pool if c['distance_m'] == chosen['distance_m']]
                    nearby = sorted([c for c in candidates
                        if abs(c['distance_m'] - chosen['distance_m']) <= 1.],
                        key=lambda c: (c['distance_m'], c['height_m'], c['source_id'], c['source_position']))
                    levels = [c for c in nearby if abs(c['height_m'] - chosen['height_m']) > 2.
                              or _different_floor(c, chosen)]
                    warnings = ['level_uncertain']
                    if not outdoor:
                        warnings.append('indoor_fallback')
                    if len(tied) > 1:
                        warnings.append('distance_tie_lower_height_assumption')
                    if levels:
                        warnings.append('alternative_level')
                    if kind != 'bus_stop' and chosen['distance_m'] > 50.:
                        warnings.append('long_connector')
                    row.update({k: chosen[k] for k in ('source_id', 'parent_edge_id',
                        'parent_edge_index', 'source_position', 'distance_m', 'height_m')})
                    row.update(status='attached', reason='', warnings=';'.join(warnings),
                        tied_count=len(tied), alternative_level=bool(levels),
                        time_s=tobler_seconds(chosen['distance_m'], 0.),
                        zero_distance=chosen['distance_m'] == 0.,
                        geometry=Point(chosen['x'], chosen['y'], chosen['height_m']))
                    rows.append(row)
                    for c in nearby:
                        review = {k: v for k, v in c.items() if k != 'buildings'}
                        review.update(attachment_id=aid, buildings_json=json.dumps(c['buildings']),
                            selected=c is chosen, exact_distance_tie=c in tied,
                            alternative_level=c in levels)
                        reviews.append(review)
        del index
    attachments = gpd.GeoDataFrame(rows, crs=2326)
    for column in ('parent_edge_index', 'node_index'):
        attachments[column] = attachments[column].astype('Int64')
    for column in ('source_position', 'distance_m', 'time_s', 'height_m'):
        attachments[column] = attachments[column].astype(float)
    attachments.attrs['vertical_crs'] = 'EPSG:5738'
    return attachments, pd.DataFrame(reviews, columns=['source_id', 'parent_edge_index',
        'parent_edge_id', 'source_position', 'distance_m', 'x', 'y', 'height_m',
        'location', 'floor', 'kind', 'attachment_id', 'buildings_json', 'selected',
        'exact_distance_tie', 'alternative_level'])


def recover_profiles(physical, source_ids, evidence_directory=None):
    """Rebuild affected original profiles and compare every saved evidence value."""
    profiles = {p.source_id: p for p in physical.profiles if p.source_id in source_ids}
    if evidence_directory is None:
        if set(profiles) != set(source_ids):
            raise ValueError('Original cost profiles or frozen evidence directory required')
        return profiles
    source_rows = physical.sources.set_index(physical.sources.PedestrianRouteID.astype(str))
    for sid in sorted(source_ids):
        row = source_rows.loc[sid]
        geometry = row.geometry.geoms[0] if row.geometry.geom_type == 'MultiLineString' else row.geometry
        profiles[sid] = build_profile(sid, np.asarray(geometry.coords), float(row.Gradient),
                                      row.FeatureType_label in {'Lift', 'M_Lift'})
        profile = profiles[sid]
        if (profile.classification != row.cost_classification or profile.rounds != row.sample_rounds
                or profile.forward_status != row.time_forward_status
                or profile.reverse_status != row.time_reverse_status):
            raise AssertionError('Original source cost classification changed: ' + sid)
    checked = set()
    with (Path(evidence_directory) / 'profiles.jsonl').open() as stream:
        for line in stream:
            # Parse only profiles being modified; all evidence files are hash-checked.
            sid = json.loads(line)['source_id']
            if sid in profiles:
                evidence = json.loads(line)
                wanted = json.loads(json.dumps(profiles[sid].evidence(), allow_nan=False))
                if wanted != evidence:
                    raise AssertionError('Original profile evidence changed: ' + sid)
                checked.add(sid)
    if checked != set(source_ids):
        raise AssertionError('Missing original source evidence')
    return profiles


def split_attachments(physical, attachments, evidence_directory=None):
    """Append single-source nodes; preserve upstream node indexes and all costs."""
    affected = set(attachments.loc[attachments.status == 'attached', 'source_id'])
    profiles = recover_profiles(physical, affected, evidence_directory)
    nodes = physical.nodes.copy()
    edge_rows = {int(r.edge_index): r for r in physical.edges.itertuples()}
    cuts, new_nodes, new_members = defaultdict(dict), [], []
    memberships = {sid: f for sid, f in physical.memberships.loc[
        physical.memberships.source_id.isin(affected)].groupby('source_id', sort=False)}
    source_indexes = dict(zip(physical.sources.loc[physical.sources.allow_general |
        physical.sources.allow_wheelchair, 'PedestrianRouteID'].astype(str),
        range(int((physical.sources.allow_general | physical.sources.allow_wheelchair).sum()))))
    for idx in attachments.index[attachments.status == 'attached']:
        row = attachments.loc[idx]
        edge = edge_rows[int(row.parent_edge_index)]
        position = row.source_position
        xyz = np.array(row.geometry.coords[0])
        reusable = []
        profile = profiles[row.source_id]
        # Only memberships of this source within this physical piece. Repeated
        # visits farther along the same source cannot create a shortcut.
        for member in memberships[row.source_id].itertuples():
            if not edge.start_position <= member.position <= edge.end_position:
                continue
            if not _can_use(edge, member.position, row.role, row.metric):
                continue
            original = interpolate_xyz(profile.coords, member.position)
            canonical = np.array(nodes.iloc[int(member.node_index)].geometry.coords[0])
            if (np.linalg.norm(original[:2] - xyz[:2]) <= .10 and height_ok(original[2], xyz[2])
                    and np.linalg.norm(canonical[:2] - xyz[:2]) <= .10
                    and height_ok(canonical[2], xyz[2])):
                lo, hi = sorted([position, member.position])
                # Require a short traversal, not merely coincident coordinates.
                if profile.piece_costs(lo, hi).distance_m <= .10:
                    reusable.append((abs(position - member.position), int(member.node_index)))
        if reusable:
            node_index = min(reusable)[1]
            attachments.at[idx, 'reused_node'] = True
        else:
            key = (row.source_id, float(position))
            node_index = cuts[int(row.parent_edge_index)].get(position)
            if node_index is None:
                # Identical source position from adjacent pieces must already
                # be a membership; fresh positions are confined to one piece.
                node_index = len(nodes) + len(new_nodes)
                node_id = stable_id('A-N-', [key])
                new_nodes.append(dict(node_id=node_id, node_index=node_index, member_count=1,
                    max_horizontal_m=0., max_height_m=0., geometry=row.geometry))
                new_members.append(dict(node_id=node_id, node_index=node_index,
                    source_index=source_indexes[row.source_id], source_id=row.source_id,
                    position=position, alignment_xy_m=0., alignment_z_m=0.))
                cuts[int(row.parent_edge_index)][position] = node_index
        attachments.at[idx, 'node_index'] = node_index
    pieces, conservation = [], []
    for edge_index, interior in cuts.items():
        edge = edge_rows[edge_index]
        profile = profiles[edge.source_id]
        positions = {edge.start_position: int(edge.from_node),
                     edge.end_position: int(edge.to_node), **interior}
        ordered = sorted(positions)
        values = []
        for start, end in zip(ordered, ordered[1:]):
            if end <= start:
                raise AssertionError('Nonpositive subdivision interval')
            cost = profile.piece_costs(start, end)
            item = edge._asdict()
            item.pop('Index', None)
            item.update(edge_id=stable_id('A-E-', [(edge.source_id, start), (edge.source_id, end)]),
                parent_edge_id=edge.edge_id, start_position=start, end_position=end,
                from_node=positions[start], to_node=positions[end], distance_m=cost.distance_m,
                time_forward_s=cost.forward_seconds, time_reverse_s=cost.reverse_seconds,
                time_forward_status=cost.forward_status, time_reverse_status=cost.reverse_status,
                geometry=profile.geometry(start, end))
            pieces.append(item)
            values.append(cost)
        for column, attr in [('distance_m', 'distance_m'),
                ('time_forward_s', 'forward_seconds'), ('time_reverse_s', 'reverse_seconds')]:
            original = getattr(edge, column)
            parts = [getattr(v, attr) for v in values]
            if pd.notna(original):
                if any(v is None for v in parts) or not np.isclose(math.fsum(parts), original,
                        rtol=2e-12, atol=1e-8):
                    raise AssertionError('Subdivision cost conservation failed: ' + edge.edge_id)
            elif all(v is not None for v in parts):
                raise AssertionError('Unavailable parent became wholly available')
        conservation.append(edge.edge_id)
    edges = physical.edges.loc[~physical.edges.edge_index.isin(cuts)].copy()
    edges['parent_edge_id'] = edges.edge_id
    if pieces:
        edges = gpd.GeoDataFrame(pd.concat([edges, gpd.GeoDataFrame(pieces, crs=2326)],
                                          ignore_index=True), crs=2326)
    edges = edges.sort_values('edge_id').reset_index(drop=True)
    edges['edge_index'] = np.arange(len(edges))
    if new_nodes:
        nodes = gpd.GeoDataFrame(pd.concat([nodes, gpd.GeoDataFrame(new_nodes, crs=2326)],
                                          ignore_index=True), crs=2326)
    members = pd.concat([physical.memberships, pd.DataFrame(new_members)], ignore_index=True)
    for frame in (nodes, edges):
        frame.attrs['vertical_crs'] = 'EPSG:5738'
    augmented = PhysicalGraph(nodes, edges, physical.sources, members, list(profiles.values()),
                              [], physical.policy)
    return augmented, {'profiles_verified': len(profiles), 'split_parent_edges': len(conservation),
        'new_nodes': len(new_nodes), 'added_pieces': len(edges) - len(physical.edges),
        'directional_cost_conservation': True, 'original_profiles_preserved': True,
        'single_source_subdivisions': True}


def attach_points(physical, entities, evidence_directory=None, progress=lambda message: None):
    """Attach all entities for both modes/relevant metrics, then split once.

    `entities` maps estate/hospital/mtr_access/bus_stop to EPSG:2326 point
    GeoDataFrames with original Step 1 candidate flags and distinct `id` values.
    A reopened Step 2 PhysicalGraph needs its frozen evidence_directory.
    """
    ids = []
    for kind, frame in entities.items():
        if kind not in LAYERS or not isinstance(frame, gpd.GeoDataFrame) or frame.crs.to_epsg() != 2326:
            raise ValueError('Expected recognised entity GeoDataFrames in EPSG:2326')
        if frame.id.isna().any() or frame.id.duplicated().any() or not (frame.geom_type == 'Point').all():
            raise ValueError('Expected unique entity identities and point geometry')
        if shapely.has_z(frame.geometry).any() or frame.geometry.is_empty.any():
            raise ValueError('Facility heights must remain unknown (2D nonempty points)')
        ids.extend(frame.id)
    if len(ids) != len(set(ids)):
        raise ValueError('Entity IDs must be distinct across layers')
    attachments, candidates = select_attachments(physical, entities, progress)
    progress('Recover original profiles and subdivide attachment pieces')
    augmented, validation = split_attachments(physical, attachments, evidence_directory)
    original = {r.id: r.geometry for f in entities.values() for r in f.itertuples()}
    lines = []
    for row in attachments.loc[(attachments.status == 'attached') & ~attachments.zero_distance].itertuples():
        point = original[row.entity_id]
        lines.append(dict(attachment_id=row.attachment_id, entity_id=row.entity_id,
            mode=row.mode, metric=row.metric, role=row.role, distance_m=row.distance_m,
            time_s=row.time_s, geometry=LineString([(point.x, point.y),
                                        (row.geometry.x, row.geometry.y)])))
    connectors = gpd.GeoDataFrame(lines, columns=['attachment_id', 'entity_id', 'mode', 'metric',
        'role', 'distance_m', 'time_s', 'geometry'], crs=2326)
    return AttachedPoints(augmented, entities, attachments, connectors, candidates, validation)


def attached_routing_graph(attached, wheelchair=False, metric='time'):
    graph = routing_graph(attached.physical, wheelchair, metric)
    states = graph.states.copy()
    states['state_kind'] = 'physical'
    states['entity_id'] = None
    mode = 'wheelchair' if wheelchair else 'general'
    selected = attached.attachments.loc[(attached.attachments['mode'] == mode) &
                                       (attached.attachments.metric == metric)]
    selected = selected.sort_values('attachment_id').reset_index(drop=True)
    network_states = defaultdict(list)
    for row in states.itertuples():
        network_states[int(row.node_index)].append((int(row.state_index), row.lift_id))
    transitions = list(graph.transitions.itertuples(index=False, name=None))
    terminal_rows, state_rows = [], []
    for i, row in enumerate(selected.itertuples()):
        state = len(states) + i
        terminal_rows.append(dict(entity_id=row.entity_id, entity_type=row.entity_type,
            attachment_id=row.attachment_id, role=row.role, state_index=state,
            node_index=row.node_index, status=row.status, reason=row.reason))
        state_rows.append(dict(node_index=np.nan, lift_id=None, state_index=state,
                               state_kind='terminal', entity_id=row.entity_id))
        if row.status != 'attached':
            continue
        cost = row.distance_m if metric == 'distance' else row.time_s
        for network_state, lift in network_states[int(row.node_index)]:
            if row.role == 'departure' and pd.notna(lift):
                continue
            a, b = (state, network_state) if row.role == 'departure' else (network_state, state)
            transitions.append((a, b, cost, -1 - i, 1, row.attachment_id))
    states = pd.concat([states, pd.DataFrame(state_rows)], ignore_index=True)
    matrix, mappings = minimum_matrix(transitions, len(states))
    terminals = pd.DataFrame(terminal_rows, columns=['entity_id', 'entity_type', 'attachment_id', 'role',
        'state_index', 'node_index', 'status', 'reason'])
    terminals['node_index'] = terminals.node_index.astype('Int64')
    return AttachedGraph(graph.nodes, graph.edges, matrix, states, mappings, wheelchair, metric,
        attached.physical, attached.entities, attached.attachments, attached.connectors,
        terminals)


def save_attached(directory, attached, upstream):
    """Store derived geometry; unchanged sources/profiles stay in frozen Step 2."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    frames = {'nodes': attached.physical.nodes, 'edges': attached.physical.edges,
              'attachments': attached.attachments, 'connectors': attached.connectors,
              **{LAYERS[k]: f for k, f in attached.entities.items()}}
    schema = {}
    for name, frame in frames.items():
        frame.to_file(directory / 'attachments.gpkg', layer=name, driver='GPKG', engine='pyogrio')
        schema[name] = {c: str(frame[c].dtype) for c in frame if c != 'geometry'}
    attached.physical.memberships.to_csv(directory / 'memberships.csv', index=False)
    attached.candidates.to_csv(directory / 'candidate_reviews.csv', index=False)
    write_json(directory / 'schema.json', {'spatial_dtypes': schema,
        'horizontal_crs': 'EPSG:2326', 'attachment_vertical_crs': 'EPSG:5738',
        'entity_height': 'unknown_2D', 'connector_geometry': '2D_positive_length_only',
        'terminal_node_index': 'null_in_states_reference_only_in_terminals',
        'source_position': 'original_vertex_index_plus_fraction',
        'upstream_step_2': str(Path(upstream).resolve().relative_to(WORK))
            if Path(upstream).resolve().is_relative_to(WORK) else str(Path(upstream).resolve())})


def read_attached_points(directory):
    directory = Path(directory).resolve()
    schema = json.loads((directory / 'schema.json').read_text())
    frames = {}
    for name, dtypes in schema['spatial_dtypes'].items():
        frame = gpd.read_file(directory / 'attachments.gpkg', layer=name,
                             engine='pyogrio', datetime_as_string=True)
        for col, dtype in dtypes.items():
            frame[col] = frame[col].astype(dtype)
        if name in ('nodes', 'edges', 'attachments'):
            frame.attrs['vertical_crs'] = 'EPSG:5738'
        else:
            frame.attrs['vertical_crs'] = None
        frames[name] = frame
    upstream = Path(schema['upstream_step_2'])
    # Resolve relative references after publication; portable with the repository.
    if not upstream.is_absolute():
        upstream = (WORK / upstream).resolve()
    source_schema = json.loads((upstream / 'schema.json').read_text())
    sources = gpd.read_file(upstream / 'graph.gpkg', layer='sources', engine='pyogrio',
                           datetime_as_string=True)
    for col, dtype in source_schema['spatial_dtypes']['sources'].items():
        if dtype == 'object' and col.endswith('_exclusion'):
            sources[col] = sources[col].fillna('')
        sources[col] = sources[col].astype(dtype)
    sources.attrs['vertical_crs'] = 'EPSG:5738'
    members = pd.read_csv(directory / 'memberships.csv', dtype={'source_id': str, 'node_id': str},
                          float_precision='round_trip')
    physical = PhysicalGraph(frames['nodes'], frames['edges'], sources, members, [], [],
                             json.loads((upstream / 'model_policy.json').read_text()))
    entities = {kind: frames[layer] for kind, layer in LAYERS.items() if layer in frames}
    candidates = pd.read_csv(directory / 'candidate_reviews.csv', float_precision='round_trip',
                             dtype={'source_id': str, 'floor': str})
    return AttachedPoints(physical, entities, frames['attachments'], frames['connectors'],
                          candidates, {})


def save_attached_routing(directory, graph):
    save_routing(directory, graph)
    prefix = ('wheelchair' if graph.wheelchair else 'general') + '_' + graph.metric
    graph.terminals.to_csv(Path(directory) / (prefix + '_terminals.csv'), index=False)


def read_attached_graph(directory=None, wheelchair=False, metric='time', attached=None):
    """Reopen GeoDataFrames, terminal mappings and a directed SciPy CSR matrix."""
    if metric not in ('time', 'distance'):
        raise ValueError('metric must be time or distance')
    directory = Path(directory or WORK / 'precomputed/outputs/step_3/current').resolve()
    attached = attached or read_attached_points(directory)
    prefix = ('wheelchair' if wheelchair else 'general') + '_' + metric
    states = pd.read_csv(directory / (prefix + '_states.csv'), dtype={'lift_id': str, 'entity_id': str},
                         float_precision='round_trip')
    transitions = pd.read_csv(directory / (prefix + '_transitions.csv'), dtype={'source_id': str},
                              float_precision='round_trip')
    terminals = pd.read_csv(directory / (prefix + '_terminals.csv'),
                            dtype={'node_index': 'Int64'}, float_precision='round_trip')
    terminals['reason'] = terminals.reason.fillna('')
    matrix = load_npz(directory / (prefix + '.npz'))
    rows = np.repeat(np.arange(matrix.shape[0]), np.diff(matrix.indptr))
    if (matrix.shape != (len(states), len(states)) or
            not np.array_equal(rows, transitions.from_state) or
            not np.array_equal(matrix.indices, transitions.to_state) or
            not np.array_equal(matrix.data, transitions.cost)):
        raise ValueError('Saved terminal matrix/mapping mismatch')
    return AttachedGraph(attached.physical.nodes, attached.physical.edges, matrix, states,
        transitions, wheelchair, metric, attached.physical, attached.entities,
        attached.attachments, attached.connectors, terminals)
