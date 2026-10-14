"""Declined merge diagnostics must distinguish real connectivity and uncertainty."""
import json
import unittest

from estate_ranking.graph import build_physical_graph, routing_graph
from estate_ranking.graph_cluster_audit import audit_cluster_geometry, audit_cluster_routing
from test_step_2 import network


class ClusterAuditTests(unittest.TestCase):
    def chain(self, middle_options=None):
        return build_physical_graph(network([
            ([(-1, 0, 0), (0, 0, 0)], {'id': 100}),
            ([(0, 0, 0), (.075, 0, 0)], {'id': 101}),
            ([(.075, 0, 0), (.15, 0, 0)], dict({'id': 102}, **(middle_options or {}))),
            ([(.15, 0, 0), (1, 0, 0)], {'id': 103}),
        ]), audit_crossings=False)

    def test_original_short_paths_connect_a_declined_chain(self):
        physical = self.chain()
        geometry = audit_cluster_geometry(physical)
        self.assertEqual(geometry['summary']['cluster_count'], 1)
        self.assertEqual(geometry['summary']['horizontal_limit_clusters'], 1)
        self.assertAlmostEqual(geometry['clusters'][0]['max_pair_horizontal_m'], .15)
        for wheelchair in (False, True):
            for metric in ('distance', 'time'):
                report = audit_cluster_routing(routing_graph(physical, wheelchair, metric), geometry)
                cluster = report['clusters'][0]
                self.assertEqual(cluster['classification'],
                                 'original_source_paths_connect_all_endpoint_sites')
                widest = max(cluster['directed_pairs'], key=lambda pair: pair['cost'])
                self.assertEqual({leg['source_id'] for leg in widest['path']}, {'101', '102'})
                json.dumps(report, allow_nan=False)
        # Audit is read-only: the deliberately separate nodes remain separate.
        self.assertEqual(len(physical.nodes), 5)

    def test_wheelchair_exclusion_is_not_reported_as_a_merge_fix(self):
        physical = self.chain({'barrier': True})
        geometry = audit_cluster_geometry(physical)
        general = audit_cluster_routing(routing_graph(physical, False, 'time'), geometry)
        wheelchair = audit_cluster_routing(routing_graph(physical, True, 'time'), geometry)
        self.assertEqual(general['clusters'][0]['classification'],
                         'original_source_paths_connect_all_endpoint_sites')
        self.assertEqual(wheelchair['clusters'][0]['classification'],
                         'some_endpoint_directions_unreachable')
        self.assertEqual(wheelchair['clusters'][0]['pair_status_counts']['unreachable'], 4)

    def test_direction_and_global_detours_are_distinguished(self):
        physical = self.chain({'direction': 1})
        geometry = audit_cluster_geometry(physical)
        report = audit_cluster_routing(routing_graph(physical), geometry)
        self.assertEqual(report['clusters'][0]['pair_status_counts']['unreachable'], 2)
        # Add a genuine alternative path outside the cluster's source records.
        with_detour = build_physical_graph(network([
            ([(-1, 0, 0), (0, 0, 0)], {'id': 100}),
            ([(0, 0, 0), (.075, 0, 0)], {'id': 101}),
            ([(.075, 0, 0), (.15, 0, 0)], {'id': 102, 'direction': 1}),
            ([(.15, 0, 0), (1, 0, 0)], {'id': 103}),
            ([(1, 0, 0), (1, 1, 0), (-1, 1, 0), (-1, 0, 0)], {'id': 200}),
        ]), audit_crossings=False)
        geometry = audit_cluster_geometry(with_detour)
        report = audit_cluster_routing(routing_graph(with_detour, metric='distance'), geometry)
        cluster = report['clusters'][0]
        self.assertEqual(cluster['classification'], 'some_endpoint_directions_require_other_sources')
        alternatives = [pair for pair in cluster['directed_pairs']
                        if pair['status'] == 'connected_by_other_sources']
        self.assertEqual(len(alternatives), 2)
        self.assertTrue(all('200' in {leg['source_id'] for leg in pair['path']} for pair in alternatives))

    def test_unaccepted_interior_candidates_are_not_endpoint_nodes(self):
        physical = self.chain()
        # A review-only interior candidate did not become a graph cut.
        review = [dict(physical.review[0])]
        review[0]['sites'] = list(review[0]['sites']) + [
            {'xyz': [.02, 0, 0], 'members': [('101', .02/.075)]}]
        geometry = audit_cluster_geometry(physical, review)
        candidate = geometry['clusters'][0]['sites'][-1]
        self.assertFalse(candidate['original_endpoint_site'])
        self.assertIsNone(candidate['endpoint_node_id'])
        report = audit_cluster_routing(routing_graph(physical), geometry)
        self.assertNotIn(candidate['site_index'], report['clusters'][0]['eligible_endpoint_sites'])
        self.assertEqual(len(report['clusters'][0]['directed_pairs']), 6)

    def test_cluster_identity_does_not_depend_on_numeric_node_indices(self):
        physical = self.chain()
        geometry = audit_cluster_geometry(physical)
        physical.memberships = physical.memberships.sample(frac=1, random_state=42)
        self.assertEqual(geometry, audit_cluster_geometry(physical))

    def test_eligible_existing_endpoint_preferred_over_same_visit_interior(self):
        # Real source 250015300 and endpoint of 250011610. XY-minimum C
        # qualifies, as does existing endpoint A, but A-C exceeds .025 m Z.
        coordinates = [(834012.8628000002, 815590.8873999994, 50.87390000000596),
                       (834012.3295, 815590.5930000003, 51.21480000000156),
                       (834012.2463999996, 815590.5471000001, 51.26790000000619)]
        incoming = (834012.3323999997, 815590.5866, 51.24899999999616)
        far = (incoming[0]+1, incoming[1]+1, incoming[2])
        for reverse, direction in ((False, 0), (True, 0), (False, 1), (True, -1)):
            with self.subTest(reverse=reverse, direction=direction):
                receive = coordinates[::-1] if reverse else coordinates
                physical = build_physical_graph(network([
                    (receive, {'id': 250015300, 'direction': direction, 'gradient': .5}),
                    ([far, incoming], {'id': 250011610}),
                ]), audit_crossings=False)
                receiving = physical.memberships.loc[physical.memberships.source_id == '250015300']
                arriving = physical.memberships.loc[(physical.memberships.source_id == '250011610') &
                                                   (physical.memberships.position == 1.)]
                endpoint = receiving.loc[receiving.position == (0. if reverse else 2.)]
                self.assertEqual(endpoint.iloc[0].node_id, arriving.iloc[0].node_id)
                self.assertEqual(len(receiving), 2)
                self.assertEqual(len(physical.edges.loc[physical.edges.source_id == '250015300']), 1)
                self.assertFalse(any(r['kind'].startswith('ambiguous') for r in physical.review))
                self.assertLessEqual(physical.nodes.max_horizontal_m.max(), .10)
                self.assertLessEqual(physical.nodes.max_height_m.max(), .025)

    def test_eligible_endpoints_do_not_hide_separate_traversal_visits(self):
        physical = build_physical_graph(network([
            ([(-.04, 0, 0), (-10, 0, 0), (0, 0, 0)], {'id': 100}),
            ([(.05, 1, 0), (.05, 0, 0)], {'id': 101}),
        ]), audit_crossings=False)
        self.assertTrue(any(r['kind'] == 'ambiguous_interior_projection' for r in physical.review))
        memberships = physical.memberships
        incoming = memberships.loc[(memberships.source_id == '101') & (memberships.position == 1.)]
        receiver = memberships.loc[memberships.source_id == '100']
        self.assertNotIn(incoming.iloc[0].node_id, receiver.node_id.tolist())


if __name__ == '__main__':
    unittest.main()
