"""Route a supplied hall map point to every eligible MTR target in saved Step 3.

Run from the repository root with .venv/bin/python work/examples/lee_shau_kee_hall_mtr_demo.py.
Adds temporary departure states in memory; published graphs remain unchanged.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
import shapely
from shapely.geometry import LineString, Point, box
from scipy.sparse import csr_matrix, hstack, vstack
from scipy.sparse.csgraph import dijkstra

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'src'))
from estate_ranking.attachments import (AttachedPoints, read_attached_graph,
    select_attachments, split_attachments)
from estate_ranking.graph import PhysicalGraph
from estate_ranking.ingest import read_json, sha256
from estate_ranking.step_3 import verify_hashes

LATITUDE, LONGITUDE = 22.280111, 114.130386
OUTPUT = WORK / 'precomputed/demos/lee_shau_kee_hall_mtr'


def base_states(graph):
    rows = graph.states.loc[(graph.states.state_kind == 'physical') & graph.states.lift_id.isna()]
    return dict(zip(rows.node_index.astype(int), rows.state_index.astype(int)))


def origin_matrix(graph, attachment, profile, point):
    """An interior origin can depart along either permitted original interval.

    This is equivalent to subdividing the chosen ordinary piece for one outgoing
    origin. Existing transitions remain intact: traversing through that position
    still has the same original cost, and the origin cannot be an intermediate
    destination. A separate physical state keeps facility height unknown.
    """
    n = graph.matrix.shape[0]
    base = base_states(graph)
    connector = dict(kind='origin_connector', source_id=None, direction=1,
        distance_m=float(attachment.distance_m), time_s=float(attachment.time_s),
        geometry=LineString([point, shapely.force_2d(attachment.geometry)]))
    if attachment.reused_node:
        links = {base[int(attachment.node_index)]: connector}
        row = csr_matrix(([connector['time_s' if graph.metric == 'time' else 'distance_m']],
                          ([0], list(links))), shape=(1, n + 1))
        return vstack([hstack([graph.matrix, csr_matrix((n, 1))]), row], format='csr'), n, {(n, next(iter(links))): connector}
    edge = graph.edges.loc[graph.edges.edge_id == attachment.parent_edge_id].iloc[0]
    links = {}
    for direction, target, start, end in [
        (1, int(edge.to_node), attachment.source_position, edge.end_position),
        (-1, int(edge.from_node), edge.start_position, attachment.source_position)]:
        if edge.direction not in (0, direction):
            continue
        cost = profile.piece_costs(start, end)
        seconds = cost.forward_seconds if direction == 1 else cost.reverse_seconds
        if graph.metric == 'time' and seconds is None:
            continue
        geom = profile.geometry(start, end)
        if direction == -1:
            geom = shapely.reverse(geom)
        leg = dict(kind='origin_path_fragment', source_id=edge.source_id, direction=direction,
            distance_m=cost.distance_m, time_s=seconds, start_position=float(start),
            end_position=float(end), geometry=shapely.force_2d(geom))
        state = base[target]
        weight = leg['time_s' if graph.metric == 'time' else 'distance_m']
        if state not in links or weight < links[state]['time_s' if graph.metric == 'time' else 'distance_m']:
            links[state] = leg
    assert links
    partial = csr_matrix(([v['time_s' if graph.metric == 'time' else 'distance_m'] for v in links.values()],
                          ([0] * len(links), list(links))), shape=(1, n + 2))
    terminal = csr_matrix(([connector['time_s' if graph.metric == 'time' else 'distance_m']],
                           ([0], [n])), shape=(1, n + 2))
    matrix = vstack([hstack([graph.matrix, csr_matrix((n, 2))]), partial, terminal], format='csr')
    extras = {(n, state): leg for state, leg in links.items()}
    extras[(n + 1, n)] = connector
    return matrix, n + 1, extras


def route_legs(graph, matrix, predecessors, start, target, extras, targets, mtr):
    rows, current = [], int(target)
    destination_by_state = {int(v['state_index']): k for k, v in targets.items()}
    while current != start:
        previous = int(predecessors[current])
        if previous < 0:
            raise AssertionError('Missing predecessor witness')
        if (previous, current) in extras:
            leg = extras[(previous, current)].copy()
        elif current in destination_by_state and graph.metric == 'distance':
            aid = destination_by_state[current]
            attachment = graph.attachments.loc[graph.attachments.attachment_id == aid].iloc[0]
            destination = mtr.loc[attachment.entity_id].geometry
            leg = dict(kind='destination_connector', source_id=None, direction=1,
                distance_m=float(attachment.distance_m), time_s=float(attachment.time_s),
                geometry=LineString([shapely.force_2d(attachment.geometry), destination]))
        else:
            lo, hi = graph.matrix.indptr[previous:previous + 2]
            offset = int(lo + np.searchsorted(graph.matrix.indices[lo:hi], current))
            transition = graph.transitions.iloc[offset]
            if transition.edge_index < 0:
                attachment = graph.attachments.loc[graph.attachments.attachment_id == transition.source_id].iloc[0]
                leg = dict(kind='destination_connector', source_id=None, direction=1,
                    distance_m=float(attachment.distance_m), time_s=float(transition.cost),
                    geometry=LineString([shapely.force_2d(attachment.geometry), mtr.loc[attachment.entity_id].geometry]))
            else:
                edge = graph.edges.iloc[int(transition.edge_index)]
                geom = edge.geometry if transition.direction == 1 else shapely.reverse(edge.geometry)
                seconds = (float(transition.cost) if graph.metric == 'time' else
                           edge.time_forward_s if transition.direction == 1 else edge.time_reverse_s)
                leg = dict(kind='network', source_id=edge.source_id, direction=int(transition.direction),
                    lift_id=None if pd.isna(edge.lift_id) else str(edge.lift_id),
                    distance_m=float(edge.distance_m), time_s=seconds, geometry=shapely.force_2d(geom))
        rows.append(leg)
        current = previous
        if len(rows) > matrix.shape[0]:
            raise AssertionError('Predecessor cycle')
    rows.reverse()
    if graph.metric == 'distance':
        last_lift = None
        for leg in rows:
            lift = leg.get('lift_id')
            if lift:
                leg['time_s'] = 0. if last_lift == lift else 30.
            last_lift = lift
    for i, leg in enumerate(rows):
        leg['sequence'] = i
    return gpd.GeoDataFrame(rows, crs=2326)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    directory = (WORK / 'precomputed/outputs/step_3/current').resolve()
    manifest = read_json(directory / 'manifest.json')
    print('Verify selected Step 3 artifacts', flush=True)
    verify_hashes(directory, manifest['artifacts'])
    print('Read general time graph', flush=True)
    time_graph = read_attached_graph(directory)
    x, y = Transformer.from_crs(4326, 2326, always_xy=True).transform(LONGITUDE, LATITUDE)
    point = Point(x, y)
    indices = time_graph.edges.sindex.query(point, predicate='dwithin', distance=200.)
    local_edges = time_graph.edges.iloc[indices].copy()
    sources = time_graph.physical.sources
    local_sources = sources.loc[sources.PedestrianRouteID.astype(str).isin(local_edges.source_id)].copy()
    local = PhysicalGraph(time_graph.nodes, local_edges, local_sources,
                          time_graph.physical.memberships, [], [], time_graph.physical.policy)
    origin = gpd.GeoDataFrame([dict(id='demo:lee_shau_kee_hall', geometry=point)], crs=2326)
    selections, candidates = select_attachments(local, {'estate': origin})
    selected = selections.loc[(selections['mode'] == 'general')].copy()
    assert (selected.status == 'attached').all()
    print('Verify original origin profile and Step 3 node reuse/subdivision', flush=True)
    upstream = WORK / manifest['frozen_inputs']['step_2']['directory']
    verify_hashes(upstream, {name: manifest['frozen_inputs']['step_2']['files'][name]
                           for name in ['graph.gpkg', 'profiles.jsonl', 'model_policy.json']})
    augmented, split_validation = split_attachments(time_graph.physical, selected, upstream)
    profiles = {p.source_id: p for p in augmented.profiles}
    time_attachment = selected.loc[selected.metric == 'time'].iloc[0]
    distance_attachment = selected.loc[selected.metric == 'distance'].iloc[0]
    mtr = time_graph.entities['mtr_access'].set_index('id')
    terminals = time_graph.terminals.loc[(time_graph.terminals.entity_type == 'mtr_access') &
                                       (time_graph.terminals.status == 'attached')]
    assert len(terminals) == 598
    time_targets = {r.attachment_id: {'state_index': int(r.state_index), 'entity_id': r.entity_id}
                    for r in terminals.itertuples()}
    print('Route to all 598 eligible MTR targets by walking time', flush=True)
    time_matrix, time_start, time_extras = origin_matrix(time_graph, time_attachment,
        profiles[time_attachment.source_id], point)
    seconds, time_predecessors = dijkstra(time_matrix, indices=time_start, directed=True, return_predecessors=True)
    shared = AttachedPoints(time_graph.physical, time_graph.entities, time_graph.attachments,
                             time_graph.connectors, candidates, {})
    distance_graph = read_attached_graph(directory, metric='distance', attached=shared)
    distance_matrix, distance_start, distance_extras = origin_matrix(distance_graph,
        distance_attachment, profiles[distance_attachment.source_id], point)
    # MTR attachments were already included in physical subdivision in Step 3.
    # Add arrival-only metre-cost terminals at those existing attachment nodes.
    base = base_states(distance_graph)
    targets = time_graph.attachments.set_index('attachment_id').loc[list(time_targets)]
    count, n = len(targets), distance_matrix.shape[0]
    incoming = csr_matrix((targets.distance_m.to_numpy(),
        ([base[int(v)] for v in targets.node_index], np.arange(count))), shape=(n, count))
    distance_matrix = vstack([hstack([distance_matrix, incoming]), csr_matrix((count, n + count))], format='csr')
    distance_targets = {aid: {'state_index': n + i, 'entity_id': row.entity_id}
                        for i, (aid, row) in enumerate(targets.iterrows())}
    print('Route to the same targets by walking distance', flush=True)
    metres, distance_predecessors = dijkstra(distance_matrix, indices=distance_start,
                                             directed=True, return_predecessors=True)
    records = []
    for aid, target in time_targets.items():
        entity = mtr.loc[target['entity_id']]
        seconds_value = float(seconds[target['state_index']])
        metres_value = float(metres[distance_targets[aid]['state_index']])
        record = dict(entity_id=target['entity_id'], attachment_id=aid, name=entity['name'],
            exit_code=entity.exit_code, latitude=float(entity.latitude), longitude=float(entity.longitude),
            fastest_time_seconds=seconds_value, shortest_distance_metres=metres_value,
            straight_line_metres=float(point.distance(entity.geometry)))
        records.append(record)
    comparisons = pd.DataFrame(records).sort_values(['fastest_time_seconds', 'entity_id']).reset_index(drop=True)
    winner = comparisons.loc[np.isfinite(comparisons.fastest_time_seconds)].iloc[0]
    shortest = comparisons.loc[np.isfinite(comparisons.shortest_distance_metres)].sort_values(
        ['shortest_distance_metres', 'entity_id']).iloc[0]
    best = route_legs(time_graph, time_matrix, time_predecessors, time_start,
        time_targets[winner.attachment_id]['state_index'], time_extras, time_targets, mtr)
    shortest_legs = route_legs(distance_graph, distance_matrix, distance_predecessors, distance_start,
        distance_targets[shortest.attachment_id]['state_index'], distance_extras, distance_targets, mtr)
    assert np.isclose(best.time_s.sum(), winner.fastest_time_seconds, rtol=2e-12, atol=1e-8)
    assert np.isclose(shortest_legs.distance_m.sum(), shortest.shortest_distance_metres, rtol=2e-12, atol=1e-8)
    # Collect route lengths for the leading time candidates using their actual
    # predecessor witnesses, rather than substituting shortest-distance routes.
    comparisons['fastest_route_distance_metres'] = np.nan
    for index, r in comparisons.head(12).iterrows():
        if not np.isfinite(r.fastest_time_seconds):
            continue
        legs = route_legs(time_graph, time_matrix, time_predecessors, time_start,
            time_targets[r.attachment_id]['state_index'], time_extras, time_targets, mtr)
        comparisons.at[index, 'fastest_route_distance_metres'] = float(legs.distance_m.sum())
    comparisons.to_csv(OUTPUT / 'mtr_comparison.csv', index=False)
    candidates.to_csv(OUTPUT / 'origin_candidates.csv', index=False)
    selected.to_file(OUTPUT / 'routes.gpkg', layer='origin_attachments', driver='GPKG', engine='pyogrio')
    origin.to_file(OUTPUT / 'routes.gpkg', layer='original_origin', driver='GPKG', engine='pyogrio')
    best.to_file(OUTPUT / 'routes.gpkg', layer='fastest_route', driver='GPKG', engine='pyogrio')
    shortest_legs.to_file(OUTPUT / 'routes.gpkg', layer='shortest_route', driver='GPKG', engine='pyogrio')
    for label, legs in [('fastest', best), ('shortest', shortest_legs)]:
        details = legs.drop(columns='geometry').copy()
        source_metadata = sources.set_index(sources.PedestrianRouteID.astype(str))
        for field in ['FeatureType_label', 'StreetNameEN', 'AliasNameEN']:
            details[field] = details.source_id.map(source_metadata[field])
        details.to_csv(OUTPUT / (label + '_route_legs.csv'), index=False)
    result = {'origin': {'name': 'Lee Shau Kee Hall, HKU', 'latitude': LATITUDE,
        'longitude': LONGITUDE, 'coordinate_source': 'user supplied', 'height': 'unknown',
        'attachment_source_id': time_attachment.source_id,
        'connector_metres': float(time_attachment.distance_m), 'connector_seconds': float(time_attachment.time_s),
        'attachment_height_hkpd_metres': float(time_attachment.height_m),
        'warnings': time_attachment.warnings, 'reused_node': bool(time_attachment.reused_node)},
        'mode': 'general', 'step_3_run': directory.name, 'eligible_mtr_records_compared': len(comparisons),
        'time_reachable_records': int(np.isfinite(comparisons.fastest_time_seconds).sum()),
        'fastest': {**winner.to_dict(), 'route_metres': float(best.distance_m.sum())},
        'shortest': {**shortest.to_dict(), 'route_seconds': float(shortest_legs.time_s.sum())},
        'origin_subdivision_validation': split_validation,
        'validation': {'all_target_records_compared': True, 'directional_original_piece_costs': True,
            'original_profile_evidence_verified': True, 'predecessor_route_cost_sums_verified': True,
            'published_graphs_unchanged': True},
        'limitations': ['Supplied origin and MTR coordinates are map points; connectors are assumed flat walks.',
            'Origin height is unknown; the nearest suitable path level is assumed.',
            'Times use the fixed Tobler and lift model, with no traffic-light waits or real-time access checks.'],
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'example_sha256': sha256(Path(__file__))}
    (OUTPUT / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    render_map(time_graph, point, mtr, comparisons, best, winner)
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)
    print(comparisons.head(10).to_string(index=False), flush=True)


def render_map(graph, point, mtr, comparisons, route, winner):
    os.environ['MPLCONFIGDIR'] = str(WORK / 'cache/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    bound = np.array(route.total_bounds)
    margin = 150.
    extent = box(bound[0] - margin, bound[1] - margin, bound[2] + margin, bound[3] + margin)
    background = graph.edges.iloc[graph.edges.sindex.query(extent, predicate='intersects')]
    background = background.loc[background.allow_general]
    fig, ax = plt.subplots(figsize=(10, 9))
    background.plot(ax=ax, color='#d6dce1', linewidth=.7, zorder=1)
    route.loc[route.kind.isin(['network', 'origin_path_fragment'])].plot(
        ax=ax, color='#0969da', linewidth=3, zorder=3)
    route.loc[route.kind.str.contains('connector')].plot(
        ax=ax, color='#d97706', linewidth=2.5, linestyle='--', zorder=4)
    ax.scatter([point.x], [point.y], color='#111827', s=70, zorder=6)
    ax.annotate('Lee Shau Kee Hall\nUser-supplied point', (point.x, point.y),
                xytext=(10, -30), textcoords='offset points', fontsize=10)
    for record in comparisons.head(10).itertuples():
        target = mtr.loc[record.entity_id].geometry
        if not extent.covers(target):
            continue
        selected = record.entity_id == winner.entity_id
        ax.scatter([target.x], [target.y], s=65, color='#16803c' if selected else '#64748b', zorder=6)
        label = record.name.replace('Mass Transit Railway ', '').replace(' Station-', ' ').replace(' Access', '')
        ax.annotate(label, (target.x, target.y), xytext=(8, 8), textcoords='offset points', fontsize=9)
    ax.set_xlim(extent.bounds[0], extent.bounds[2])
    ax.set_ylim(extent.bounds[1], extent.bounds[3])
    ax.set_aspect('equal')
    ax.set_xlabel('HK1980 easting (metres)')
    ax.set_ylabel('HK1980 northing (metres)')
    label = winner['name'].replace('Mass Transit Railway ', '').replace(' Access', '')
    ax.set_title('Lee Shau Kee Hall to ' + label + '\n'
        + f'{winner.fastest_time_seconds / 60:.1f} min; {route.distance_m.sum():.0f} m — general walking model', fontsize=13)
    fig.text(.5, .02, 'Blue: network route   Orange dashed: assumed connectors   Grey: supplied pedestrian paths',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .035, 1, 1))
    fig.savefig(OUTPUT / 'route_map.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    main()
