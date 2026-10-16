"""Explain declined junction merges using immutable source and routing evidence.

This audit never repairs coordinates or adds graph transitions. A declined merge
can be harmless when the original short source paths already join its endpoints.
Unaccepted interior candidates are evidence, not automatically routing nodes.
"""
from collections import Counter, defaultdict
from dataclasses import replace
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra

from .graph import read_physical, _read_routing, routing_graph
from .graph_topology import HORIZONTAL, HEIGHT, height_ok, stable_id


def _coords(geometry):
    if geometry.geom_type == 'MultiLineString':
        geometry = geometry.geoms[0]
    return np.asarray(geometry.coords, dtype=float)


def audit_cluster_geometry(physical, review=None):
    """Return stable source/XYZ evidence and exact original endpoint anchors."""
    records = physical.review if review is None else review
    clusters = [record for record in records if record['kind'] == 'ambiguous_cluster']
    wanted = {str(source) for r in clusters for site in r['sites'] for source, _ in site['members']}
    sources = {str(row.PedestrianRouteID): row for row in physical.sources.itertuples()
               if str(row.PedestrianRouteID) in wanted}
    memberships = {(str(row.source_id), float(row.position)): str(row.node_id)
                   for row in physical.memberships.itertuples() if str(row.source_id) in wanted}
    result = []
    for record in clusters:
        sites = []
        for index, site in enumerate(record['sites']):
            members, endpoint = [], False
            for source, position in site['members']:
                source, position = str(source), float(position)
                coordinates = _coords(sources[source].geometry)
                is_endpoint = position in (0., float(len(coordinates)-1))
                endpoint |= is_endpoint
                members.append({'source_id': source, 'position': position,
                                'original_endpoint': is_endpoint,
                                'accepted_node_id': memberships.get((source, position))})
            nodes = sorted({m['accepted_node_id'] for m in members
                            if m['accepted_node_id'] is not None and m['original_endpoint']})
            if endpoint and len(nodes) != 1:
                raise ValueError('An exact original endpoint site must retain one node')
            sites.append({'site_index': index, 'xyz': site['xyz'], 'members': members,
                          'original_endpoint_site': endpoint,
                          'endpoint_node_id': nodes[0] if nodes else None})
        rejected, max_xy, max_z = [], 0., 0.
        for index, left in enumerate(sites):
            for right in sites[index+1:]:
                a, b = left['xyz'], right['xyz']
                horizontal = math.hypot(a[0]-b[0], a[1]-b[1])
                height = abs(a[2]-b[2])
                max_xy, max_z = max(max_xy, horizontal), max(max_z, height)
                failures = []
                if horizontal > HORIZONTAL:
                    failures.append('horizontal_tolerance_exceeded')
                if not height_ok(a[2], b[2]):
                    failures.append('height_tolerance_exceeded')
                if failures:
                    rejected.append({'left_site': left['site_index'], 'right_site': right['site_index'],
                                     'horizontal_m': horizontal, 'height_m': height, 'reasons': failures})
        source_ids = sorted({m['source_id'] for site in sites for m in site['members']})
        source_context = []
        for source in source_ids:
            row = sources[source]
            coordinates = _coords(row.geometry)
            source_context.append({'source_id': source, 'feature_type': row.FeatureType_label,
                'direction': int(row.Direction), 'allow_general': bool(row.allow_general),
                'allow_wheelchair': bool(row.allow_wheelchair),
                'general_exclusion': row.general_exclusion, 'wheelchair_exclusion': row.wheelchair_exclusion,
                'floor_id': None if pd.isna(row.FloorID) else int(row.FloorID),
                'building_ids': sorted({int(value) for value in (row.BuildingID_1, row.BuildingID_2)
                                        if pd.notna(value)}),
                'vertex_count': len(coordinates), 'start_xyz': coordinates[0].tolist(),
                'end_xyz': coordinates[-1].tolist(),
                'horizontal_length_m': float(np.hypot(*np.diff(coordinates[:, :2], axis=0).T).sum())})
        result.append({'cluster_id': stable_id('C-', [(m['source_id'], m['position'])
                            for site in sites for m in site['members']]),
                       'original_reason': record['reason'], 'source_ids': source_ids,
                       'sites': sites, 'sources': source_context,
                       'max_pair_horizontal_m': max_xy, 'max_pair_height_m': max_z,
                       'geometric_failure_pairs': rejected})
    summary = {'cluster_count': len(result),
               'horizontal_limit_clusters': sum(c['max_pair_horizontal_m'] > HORIZONTAL for c in result),
               'height_limit_clusters': sum(any('height_tolerance_exceeded' in p['reasons']
                                              for p in c['geometric_failure_pairs']) for c in result)}
    return {'summary': summary, 'clusters': sorted(result, key=lambda c: c['cluster_id'])}


def _local_graph(graph, source_ids):
    """Rebuild local minima from physical alternatives, including parallel edges."""
    physical = graph.physical
    edges = physical.edges.loc[physical.edges.source_id.astype(str).isin(source_ids)].copy()
    indices = sorted(set(edges.from_node) | set(edges.to_node))
    nodes = physical.nodes.iloc[indices].copy().reset_index(drop=True)
    lookup = {old: new for new, old in enumerate(indices)}
    nodes['node_index'] = np.arange(len(nodes))
    edges['from_node'] = edges.from_node.map(lookup)
    edges['to_node'] = edges.to_node.map(lookup)
    local = replace(physical, nodes=nodes, edges=edges)
    return routing_graph(local, wheelchair=graph.wheelchair, metric=graph.metric)


def _route_evidence(graph, predecessors, start, target):
    legs, state = [], int(target)
    while state != start:
        previous = int(predecessors[state])
        if previous < 0:
            raise ValueError('Reachable route has no predecessor witness')
        lo, hi = graph.matrix.indptr[previous:previous+2]
        offset = int(np.searchsorted(graph.matrix.indices[lo:hi], state)) + int(lo)
        transition = graph.transitions.iloc[offset]
        edge_index = int(transition.edge_index)
        if edge_index < len(graph.edges) and int(graph.edges.iloc[edge_index].edge_index) == edge_index:
            edge = graph.edges.iloc[edge_index]
        else:
            edge = graph.edges.loc[graph.edges.edge_index == edge_index].iloc[0]
        legs.append({'source_id': str(transition.source_id), 'edge_id': str(edge.edge_id),
                     'direction': int(transition.direction), 'cost': float(transition.cost)})
        state = previous
        if len(legs) > graph.matrix.shape[0]:
            raise ValueError('Route predecessor cycle')
    return list(reversed(legs))


def audit_cluster_routing(graph, geometry_audit):
    """Measure actual directed connectivity without proposing invalid merges.

    A local graph includes every physical edge from the cluster's original
    source IDs. Global searches run one start at a time only for failed local
    routes, bounding memory independently of the number of clusters.
    """
    mode = 'wheelchair' if graph.wheelchair else 'general'
    full_nodes = dict(zip(graph.nodes.node_id.astype(str), graph.nodes.node_index.astype(int)))
    full_base = {int(row.node_index): int(row.Index) for row in graph.states.itertuples()
                 if pd.isna(row.lift_id)}
    results = []
    for cluster in geometry_audit['clusters']:
        local = _local_graph(graph, set(cluster['source_ids']))
        local_nodes = dict(zip(local.nodes.node_id.astype(str), local.nodes.node_index.astype(int)))
        local_base = {int(row.node_index): int(row.Index) for row in local.states.itertuples()
                      if pd.isna(row.lift_id)}
        contexts = {source['source_id']: source for source in cluster['sources']}
        endpoints = [site for site in cluster['sites'] if site['original_endpoint_site'] and
                     any(contexts[m['source_id']]['allow_'+mode] for m in site['members'])]
        pairs = []
        for start in endpoints:
            start_node = local_nodes[start['endpoint_node_id']]
            start_state = local_base[start_node]
            costs, predecessors = dijkstra(local.matrix, directed=True, indices=start_state,
                                           return_predecessors=True)
            global_costs, global_predecessors = None, None
            for target in endpoints:
                if start['site_index'] == target['site_index']:
                    continue
                node = local_nodes[target['endpoint_node_id']]
                states = local.states.index[local.states.node_index == node].to_numpy(dtype=int)
                target_state = int(states[np.argmin(costs[states])])
                pair = {'from_site': start['site_index'], 'to_site': target['site_index']}
                if np.isfinite(costs[target_state]):
                    pair.update(status='connected_by_cluster_sources',
                                cost=float(costs[target_state]),
                                path=_route_evidence(local, predecessors, start_state, target_state))
                else:
                    if global_costs is None:
                        global_start = full_base[full_nodes[start['endpoint_node_id']]]
                        global_costs, global_predecessors = dijkstra(graph.matrix, directed=True,
                            indices=global_start, return_predecessors=True)
                    global_node = full_nodes[target['endpoint_node_id']]
                    states = graph.states.index[graph.states.node_index == global_node].to_numpy(dtype=int)
                    target_state = int(states[np.argmin(global_costs[states])])
                    if np.isfinite(global_costs[target_state]):
                        pair.update(status='connected_by_other_sources',
                            cost=float(global_costs[target_state]),
                            path=_route_evidence(graph, global_predecessors, global_start, target_state))
                    else:
                        pair.update(status='unreachable', cost=None, path=[])
                pairs.append(pair)
        statuses = Counter(pair['status'] for pair in pairs)
        if not pairs:
            classification = 'fewer_than_two_mode_eligible_endpoint_sites'
        elif statuses['connected_by_cluster_sources'] == len(pairs):
            classification = 'original_source_paths_connect_all_endpoint_sites'
        elif statuses['unreachable']:
            classification = 'some_endpoint_directions_unreachable'
        else:
            classification = 'some_endpoint_directions_require_other_sources'
        results.append({'cluster_id': cluster['cluster_id'], 'classification': classification,
                        'eligible_endpoint_sites': [site['site_index'] for site in endpoints],
                        'pair_status_counts': dict(sorted(statuses.items())), 'directed_pairs': pairs})
    return {'mode': mode, 'metric': graph.metric,
            'cost_unit': 'seconds' if graph.metric == 'time' else 'metres',
            'scope': 'Original endpoint sites only; unaccepted interior candidates remain evidence. '
                     'Connectivity is measured, not an assertion that every direction should be permitted.',
            'summary': dict(sorted(Counter(c['classification'] for c in results).items())),
            'clusters': results}


def audit_saved_clusters(directory):
    """Audit one immutable saved run, loading one routing matrix at a time."""
    directory = Path(directory).resolve()
    physical = read_physical(directory)
    with (directory/'review.jsonl').open() as handle:
        review = [json.loads(line) for line in handle]
    geometry = audit_cluster_geometry(physical, review)
    reports = []
    for wheelchair in (False, True):
        for metric in ('distance', 'time'):
            graph = _read_routing(directory, physical, wheelchair, metric)
            reports.append(audit_cluster_routing(graph, geometry))
            del graph
    return {'geometry': geometry, 'routing': reports,
            'changes_applied': False,
            'interpretation': 'No tolerance changes or inferred merges. Local source paths, '
                              'other-source routes and unreachable directions are distinguished.'}


def check_repaired_endpoint_cluster(graph):
    """Verify the real height-cluster repair by source IDs and original XYZ."""
    expected = {'250015300': (834012.2463999996, 815590.5471000001, 51.26790000000619),
                '250011610': (834012.3323999997, 815590.5866, 51.24899999999616)}
    sources = {str(row.PedestrianRouteID): row for row in graph.physical.sources.itertuples()
               if str(row.PedestrianRouteID) in expected}
    anchors = []
    for source, xyz in expected.items():
        coordinates = _coords(sources[source].geometry)
        positions = [float(index) for index in (0, len(coordinates)-1)
                     if np.array_equal(coordinates[index], np.asarray(xyz))]
        if len(positions) != 1:
            raise ValueError('Expected source endpoint XYZ changed: '+source)
        membership = graph.physical.memberships.loc[
            (graph.physical.memberships.source_id.astype(str) == source) &
            (graph.physical.memberships.position == positions[0])]
        if len(membership) != 1:
            raise ValueError('Expected original endpoint membership missing: '+source)
        anchors.append({'source_id': source, 'position': positions[0], 'xyz': list(xyz),
                        'node_id': str(membership.iloc[0].node_id)})
    if anchors[0]['node_id'] != anchors[1]['node_id']:
        raise ValueError('Eligible original endpoints were not joined')
    return {'status': 'passed', 'anchors': anchors,
            'horizontal_m': math.hypot(expected['250015300'][0]-expected['250011610'][0],
                                       expected['250015300'][1]-expected['250011610'][1]),
            'height_m': abs(expected['250015300'][2]-expected['250011610'][2]),
            'alignment_cost': 0.,
            'evidence': 'Same accepted physical node; no stored numeric node indices are assumed.'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit_saved_clusters(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'geometry': report['geometry']['summary'],
                      'routing': [{k: r[k] for k in ('mode', 'metric', 'summary')}
                                  for r in report['routing']]}, indent=2))
