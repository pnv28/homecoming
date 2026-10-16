"""Shared directed predecessor traversal and lossless route reconstruction."""
import math

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString


def predecessor_states(predecessors, root, endpoint):
    """Return endpoint-to-root states, rejecting missing links and cycles."""
    states, seen = [], set()
    state = int(endpoint)
    while state != root:
        if state < 0 or state in seen or len(seen) >= len(predecessors):
            raise ValueError('Missing or cyclic shortest-path predecessor chain')
        seen.add(state)
        states.append(state)
        state = int(predecessors[state])
    return states


def transition_index(matrix, start, end):
    lo, hi = matrix.indptr[start:start + 2]
    offset = int(lo + np.searchsorted(matrix.indices[lo:hi], end))
    if offset >= hi or matrix.indices[offset] != end:
        raise ValueError('Cached path contains a forbidden transition')
    return offset


def path_transitions(graph, predecessors, root, endpoint, reverse=False):
    states = predecessor_states(predecessors, root, endpoint)
    links = [transition_index(graph.matrix, s, int(predecessors[s])) if reverse else
             transition_index(graph.matrix, int(predecessors[s]), s) for s in states]
    return links if reverse else links[::-1]


def check_cost(costs, expected):
    total = math.fsum(costs)
    if not np.isclose(total, expected, rtol=2e-12, atol=1e-8):
        raise ValueError('Route sections do not conserve shortest-path cost')
    return total


def ordered_sections(graph, indices, points=None, origin_override=None):
    """Preserve network XYZ, 2D connectors, zero movements and actual costs."""
    attachments = graph.attachments.set_index('attachment_id', drop=False)
    points = points or {r.id: r.geometry for f in graph.entities.values() for r in f.itertuples()}
    rows = []
    if origin_override is not None:
        if graph.metric != 'distance' or graph.wheelchair:
            raise ValueError('Hospital override requires the shared general-distance graph')
        a = origin_override['attachment']
        point = points[origin_override['estate_id']]
        network = shapely.Point(a['position'][:2])
        rows.append(dict(sequence=0, transition_index=None, from_state=None,
            to_state=int(origin_override['state_index']), source_id=a['source_id'], direction=1,
            cost=float(a['distance_m']), unit='metres', time_s=None,
            connector_id=a['attachment_id'], lift_id=None, uses_estimated_time=False,
            time_model_warning='', fallback_review_ids='', original_failure_reason='',
            connector_warnings=';'.join(a['warnings']), source_position=a['source_position'],
            kind='start_connector', edge_id=None, distance_m=float(a['distance_m']),
            geometry=None if point.equals(network) else LineString([point, network]),
            time_model='distance', hospital_origin_override=True))
    for index in indices:
        t = graph.transitions.iloc[int(index)]
        row = dict(sequence=len(rows), transition_index=int(index), from_state=int(t.from_state),
                   to_state=int(t.to_state), source_id=str(t.source_id), direction=int(t.direction),
                   cost=float(t.cost), unit='metres' if graph.metric == 'distance' else 'seconds',
                   time_s=float(t.cost) if graph.metric == 'time' else None,
                   connector_id=None, lift_id=None, uses_estimated_time=False,
                   time_model_warning='', fallback_review_ids='', original_failure_reason='',
                   connector_warnings='', source_position=None)
        if t.edge_index < 0:
            a = attachments.loc[t.source_id]
            point, network = points[a.entity_id], shapely.force_2d(a.geometry)
            start, end = (point, network) if a.role == 'departure' else (network, point)
            row.update(source_id=str(a.source_id), kind='start_connector' if a.role == 'departure' else 'end_connector',
                       edge_id=None, distance_m=float(a.distance_m),
                       geometry=None if start.equals(end) else LineString([start, end]),
                       connector_id=a.attachment_id, source_position=float(a.source_position),
                       connector_warnings=a.warnings, time_model='distance' if graph.metric == 'distance' else 'flat_connector')
        else:
            e = graph.edges.iloc[int(t.edge_index)]
            suffix = 'forward' if t.direction == 1 else 'reverse'
            estimated = (graph.metric == 'time' and getattr(graph, 'scenario', 'primary') == 'primary'
                         and e.get('time_' + suffix + '_status') == 'estimated_distance_height')
            lift = None if pd.isna(e.lift_id) else str(e.lift_id)
            row.update(kind='network', edge_id=e.edge_id, source_id=str(e.source_id),
                distance_m=float(e.distance_m), lift_id=lift,
                geometry=e.geometry if t.direction == 1 else shapely.reverse(e.geometry),
                uses_estimated_time=estimated,
                time_model=('distance' if graph.metric == 'distance' else
                    'lift_continuation' if lift and t.cost == 0 else 'lift_entry' if lift else
                    'distance_height_estimate' if estimated else 'tobler'),
                time_model_warning=e.get('time_model_warning', '') if estimated else '',
                fallback_review_ids=e.get('fallback_review_ids', ''),
                original_failure_reason=e.get('original_time_' + suffix + '_status',
                                               e.get('time_' + suffix + '_status', '')),
                start_position=float(e.start_position if t.direction == 1 else e.end_position),
                end_position=float(e.end_position if t.direction == 1 else e.start_position))
        rows.append(row)
    if not rows:
        return gpd.GeoDataFrame(columns=['sequence', 'kind', 'cost', 'time_s', 'distance_m', 'geometry'], crs=2326)
    result = gpd.GeoDataFrame(rows, crs=2326)
    result.attrs.update(network_vertical_crs='EPSG:5738', connector_vertical_crs=None)
    return result
