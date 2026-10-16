"""Endpoint selection and reference full-graph calculation adapted from the original example.

The web app uses fast_coordinate.py; the reference is retained for parity tests.
"""
import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString
from scipy.sparse.csgraph import dijkstra
from estate_ranking.attachments import (AttachedPoints, attached_routing_graph, select_attachments, split_attachments)
from estate_ranking.graph import PhysicalGraph
from estate_ranking.step_3 import validate_terminals
from estate_ranking.routes import path_transitions, ordered_sections, check_cost

ROUTE_COLUMNS = ["sequence", "kind", "source_id", "direction", "distance_m", "time_s", "lift_id", "time_model", "time_model_warning", "fallback_review_ids", "geometry"]


def empty_route():
    return gpd.GeoDataFrame(columns=ROUTE_COLUMNS, crs=2326)


def connector_geometry(start, end):
    """Keep exact zero-cost connections as mappings, not degenerate lines."""
    return None if start.equals(end) else LineString([start, end])


def endpoint_attachments(physical, start, end, wheelchair=False):
    indices = np.unique(np.r_[
        physical.edges.sindex.query(start, predicate='dwithin', distance=200.),
        physical.edges.sindex.query(end, predicate='dwithin', distance=200.)]).astype(int)
    edges = physical.edges.iloc[indices].copy()
    sources = physical.sources.loc[physical.sources.PedestrianRouteID.astype(str).isin(edges.source_id)]
    local = PhysicalGraph(physical.nodes, edges, sources, physical.memberships,
                          physical.profiles, [], physical.policy)
    origin = gpd.GeoDataFrame([dict(id='point:start', geometry=start)], crs=2326)
    destination = gpd.GeoDataFrame([dict(id='point:end', geometry=end,
        general_mode_candidate=True, wheelchair_mode_candidate=True)], crs=2326)
    # Reuse the existing departure/arrival selectors. The MTR selector supplies
    # a time-based arrival role here; the destination remains an arbitrary point.
    selections, candidates = select_attachments(local, {'estate': origin, 'mtr_access': destination})
    mode = 'wheelchair' if wheelchair else 'general'
    selected = selections.loc[(selections['mode'] == mode) & (selections.metric == 'time')].copy()
    # The precomputed facility attachment builder permits expanded connections.
    # Arbitrary clicked endpoints use a deliberate 200 m limit instead.
    too_far = selected.distance_m.gt(200.)
    selected.loc[too_far, 'status'] = 'unattached'
    selected.loc[too_far, 'reason'] = 'no_suitable_path_within_200m'
    selected['entity_type'] = selected.entity_id.map({'point:start': 'start', 'point:end': 'destination'})
    return selected, candidates.loc[candidates.attachment_id.isin(selected.attachment_id)].copy()


def find_route(physical, start, end, wheelchair=False, evidence_directory=None):
    """Subdivide both selected positions together, then run directed Dijkstra.

    No source elevations are assigned to the supplied 2D points. Both terminal
    roles are one-way, and the original physical graph is left unchanged.
    """
    empty_attachments = gpd.GeoDataFrame(columns=['entity_id', 'status', 'geometry'], crs=2326)
    if start.equals(end):
        return {'status': 'ok', 'message': 'Start and destination are the same coordinate.',
                'distance_m': 0., 'time_s': 0.}, empty_route(), empty_attachments
    selected, candidates = endpoint_attachments(physical, start, end, wheelchair)
    if not (selected.status == 'attached').all():
        missing = ['start' if row.entity_id == 'point:start' else 'destination'
                   for row in selected.loc[selected.status != 'attached'].itertuples()]
        return {'status': 'unattached', 'message': 'No suitable path in the dataset for ' +
                ' and '.join(missing) + '.', 'distance_m': None, 'time_s': None}, empty_route(), selected
    augmented, validation = split_attachments(physical, selected, evidence_directory)
    points = {'point:start': start, 'point:end': end}
    connectors = []
    for row in selected.itertuples():
        geometry = connector_geometry(points[row.entity_id], shapely.force_2d(row.geometry))
        if geometry is not None:
            connectors.append(dict(attachment_id=row.attachment_id, geometry=geometry))
    attached = AttachedPoints(augmented, {}, selected,
        gpd.GeoDataFrame(connectors, columns=['attachment_id', 'geometry'], crs=2326), candidates, validation)
    graph = attached_routing_graph(attached, wheelchair, 'time')
    validate_terminals(graph)
    terminals = graph.terminals.set_index('entity_id')
    start_state = int(terminals.loc['point:start', 'state_index'])
    end_state = int(terminals.loc['point:end', 'state_index'])
    costs, predecessors = dijkstra(graph.matrix, directed=True, indices=start_state,
                                   return_predecessors=True)
    if not np.isfinite(costs[end_state]):
        return {'status': 'unreachable', 'message': 'Both points attached, but no permitted walking route connects them.',
                'distance_m': None, 'time_s': None, 'subdivision_validation': validation}, empty_route(), selected
    indices = path_transitions(graph, predecessors, start_state, end_state)
    route = ordered_sections(graph, indices, points)
    check_cost(route.time_s, costs[end_state])
    return {'status': 'ok', 'message': 'Fastest route under the saved walking model.',
            'distance_m': float(route.distance_m.sum()), 'time_s': float(costs[end_state]),
            'estimated_network_sections': int(route.time_model.eq('distance_height_estimate').sum()),
            'subdivision_validation': validation, 'route_cost_sum_verified': True}, route, selected
