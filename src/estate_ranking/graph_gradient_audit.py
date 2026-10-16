"""Read-only evidence for extreme gradients and unavailable piece routing.

Geometry-derived angles are diagnostic comparisons only. The provider gradient
and the agreed cost policy are never replaced by this audit.
"""
import math

import numpy as np
from scipy.sparse.csgraph import dijkstra

from .graph_costs import MAX_LOG, build_profile, interpolate_xyz


def _source(physical, source_id):
    rows = physical.sources.loc[
        physical.sources.PedestrianRouteID.astype(str) == str(source_id)]
    if len(rows) != 1:
        raise ValueError('Expected exactly one source: ' + str(source_id))
    source = rows.iloc[0]
    geometry = source.geometry
    if geometry.geom_type == 'MultiLineString':
        if len(geometry.geoms) != 1:
            raise ValueError('Multipart traversal is unsupported')
        geometry = geometry.geoms[0]
    return source, np.asarray(geometry.coords, dtype=float)


def audit_extreme_gradient(physical, source_id='150021876'):
    """Reproduce source/interval costs safely without evaluating exp(overflow)."""
    source, coords = _source(physical, source_id)
    gradient = float(source.Gradient)
    profile = build_profile(str(source_id), coords, gradient,
                            source.FeatureType_label in {'Lift', 'M_Lift'})
    run = float(math.fsum(np.linalg.norm(np.diff(coords[:, :2], axis=0), axis=1)))
    rise = float(coords[-1, 2] - coords[0, 2])
    geometric_angle = math.atan2(abs(rise), run)
    intervals = []
    for i, (length, angle) in enumerate(zip(profile.lengths, profile.signed_angles)):
        directions = {}
        for direction, signed, value in [('forward', float(angle), profile.forward[i]),
                                          ('reverse', -float(angle), profile.reverse[i])]:
            log_seconds = (math.log(float(length)) + math.log(.6)
                           + 3.5 * abs(math.tan(signed) + .05)) if length > 0 else None
            reason = profile.interval_reasons[i]
            directions[direction] = {
                'signed_gradient_radians': signed,
                'log_seconds': log_seconds,
                'log10_seconds': log_seconds / math.log(10) if log_seconds is not None else None,
                'exceeds_float64_range': bool(log_seconds is not None and log_seconds > MAX_LOG),
                'seconds': value,
                'status': reason or ('available' if value is not None else 'unrepresentable_tobler_time')}
        intervals.append({'start_position': float(profile.positions[i]),
                          'end_position': float(profile.positions[i+1]),
                          'start_xyz': interpolate_xyz(coords, profile.positions[i]).tolist(),
                          'end_xyz': interpolate_xyz(coords, profile.positions[i+1]).tolist(),
                          'horizontal_length_m': float(length), **directions})
    return {
        'source_id': str(source_id), 'source_xyz': coords.tolist(),
        'feature_type': str(source.FeatureType_label),
        'gradient_radians': gradient, 'gradient_degrees': math.degrees(gradient),
        'horizontal_length_m': run, 'endpoint_height_change_m': rise,
        'endpoint_geometry_angle_radians': geometric_angle,
        'provider_minus_endpoint_angle_radians': gradient-geometric_angle,
        'geometry_angle_use': 'diagnostic comparison only; source gradient retained',
        'forward_status': profile.forward_status, 'reverse_status': profile.reverse_status,
        'float64_max_log_seconds': MAX_LOG, 'intervals': intervals,
        'provider_definition': {'file': 'original_data/3DPN_DataDictionary_v2.2.pdf',
                                'pdf_page': 12, 'field': 'Gradient', 'unit': 'radian',
                                'sign_and_aggregation_method': 'not specified in field definition'},
        'correction': None,
        'decision': 'retain original gradient and existing time exclusions; no demonstrated interpretation defect'}


def gradient_routing_impact(graph, source_id='150021876'):
    """Measure saved routes between each source piece's ends in both directions.

    Works for any source, including a source with multiple physical pieces.
    Targets accept any lift state, exactly as RoutingGraph.costs_from does.
    The unavailable edge is not added or assigned an invented counterfactual
    cost. Thus these are available alternative routes, not measured detours.
    """
    source, coords = _source(graph.physical, source_id)
    pieces = graph.edges.loc[graph.edges.source_id.astype(str) == str(source_id)]
    if pieces.empty:
        raise ValueError('Source has no eligible physical pieces: ' + str(source_id))
    wanted_nodes = set(pieces.from_node) | set(pieces.to_node)
    endpoint_states = graph.states.loc[graph.states.node_index.isin(wanted_nodes)]
    base = endpoint_states.loc[endpoint_states.lift_id.isna()].set_index('node_index').state_index
    targets = endpoint_states.groupby('node_index').state_index.apply(list).to_dict()
    cache = {}

    def route(start, end):
        if start not in cache:
            cache[start] = dijkstra(graph.matrix, indices=int(base.loc[start]),
                                    return_predecessors=True, directed=True)
        costs, predecessor = cache[start]
        destination_states = targets[end]
        target = min(destination_states, key=lambda i: costs[i])
        if not math.isfinite(costs[target]):
            return {'reachable': False, 'cost': None, 'route_source_ids': [],
                    'route_uses_audited_source': False}
        origin, current, identities = int(base.loc[start]), int(target), []
        while current != origin:
            previous = int(predecessor[current])
            if previous < 0:
                raise AssertionError('Finite route has no predecessor')
            lower, upper = graph.matrix.indptr[previous:previous+2]
            index = int(lower + np.searchsorted(graph.matrix.indices[lower:upper], current))
            if index >= upper or graph.matrix.indices[index] != current:
                raise AssertionError('Routing predecessor is absent from matrix')
            identities.append(str(graph.transitions.iloc[index].source_id))
            current = previous
        identities.reverse()
        collapsed = [identity for i, identity in enumerate(identities)
                     if i == 0 or identity != identities[i-1]]
        return {'reachable': True, 'cost': float(costs[target]), 'route_source_ids': collapsed,
                'route_uses_audited_source': str(source_id) in identities}

    results = []
    for piece in pieces.sort_values('start_position').itertuples():
        results.append({'edge_id': str(piece.edge_id),
                        'start_position': float(piece.start_position),
                        'end_position': float(piece.end_position),
                        'start_xyz': interpolate_xyz(coords, piece.start_position).tolist(),
                        'end_xyz': interpolate_xyz(coords, piece.end_position).tolist(),
                        'time_forward_status': piece.time_forward_status,
                        'time_reverse_status': piece.time_reverse_status,
                        'forward': route(int(piece.from_node), int(piece.to_node)),
                        'reverse': route(int(piece.to_node), int(piece.from_node))})
    return {'source_id': str(source_id), 'mode': 'wheelchair' if graph.wheelchair else 'general',
            'metric': graph.metric, 'unit': 'seconds' if graph.metric == 'time' else 'metres',
            'source_mode_eligible': bool(source['allow_wheelchair' if graph.wheelchair else 'allow_general']),
            'interpretation': 'available endpoint routes; no hypothetical replacement cost is assigned',
            'pieces': results}
