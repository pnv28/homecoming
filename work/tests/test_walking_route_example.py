"""Coordinate routing must preserve interior positions, direction and lift costs."""
import math
from pathlib import Path
import sys
import tempfile
import unittest

from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from walking_route import coordinates, find_route, render_png
from estate_ranking.graph import build_physical_graph
from estate_ranking.graph_costs import tobler_seconds
from test_step_2 import network


def physical(paths):
    return build_physical_graph(network(paths), audit_crossings=False)


class WalkingRouteTests(unittest.TestCase):
    def test_estimated_network_time_is_visible_in_route_and_summary(self):
        from test_time_fallback import reviewed
        graph,_=reviewed([[(-1,0,0),(0,0,0)],[(0,0,0),(0,0,2)],[(0,0,2),(1,0,2)]])
        result,route,_=find_route(graph,Point(-.8,0),Point(.8,0))
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['estimated_network_sections'],1)
        section=route.loc[route.time_model=='distance_height_estimate'].iloc[0]
        self.assertAlmostEqual(section.time_s,12)
        self.assertTrue(section.fallback_review_ids)
        self.assertIn('original_geometry_uncertain',section.time_model_warning)

    def test_two_interior_positions_same_edge_are_directly_connected(self):
        graph = physical([[(0, 0, 0), (10, 0, 0)]])
        result, legs, attachments = find_route(graph, Point(2, 1), Point(8, 2))
        self.assertEqual(result['status'], 'ok')
        self.assertAlmostEqual(result['distance_m'], 9.)
        self.assertAlmostEqual(result['time_s'], tobler_seconds(9., 0.))
        self.assertAlmostEqual(legs.loc[legs.kind == 'network', 'distance_m'].sum(), 6.)
        self.assertEqual(result['subdivision_validation']['new_nodes'], 2)
        self.assertEqual(len(graph.edges), 1)  # Original graph remains intact.
        self.assertFalse(attachments.reused_node.any())

    def test_one_way_edge_allows_forward_and_rejects_reverse(self):
        graph = physical([([(0, 0, 0), (10, 0, 0)], {'direction': 1})])
        forward, _, _ = find_route(graph, Point(2, 1), Point(8, 1))
        reverse, legs, _ = find_route(graph, Point(8, 1), Point(2, 1))
        self.assertEqual(forward['status'], 'ok')
        self.assertEqual(reverse['status'], 'unreachable')
        self.assertIsNone(reverse['time_s'])
        self.assertTrue(legs.empty)

    def test_shared_attachment_and_zero_connector_have_no_degenerate_geometry(self):
        graph = physical([[(0, 0, 0), (10, 0, 0)]])
        result, legs, attachments = find_route(graph, Point(2, 0), Point(2, 1))
        self.assertEqual(result['status'], 'ok')
        self.assertAlmostEqual(result['distance_m'], 1.)
        self.assertEqual(result['subdivision_validation']['new_nodes'], 1)
        self.assertEqual(attachments.node_index.nunique(), 1)
        zero = legs.loc[legs.kind == 'start_connector'].iloc[0]
        self.assertEqual(zero.time_s, 0.)
        self.assertIsNone(zero.geometry)

    def test_two_lifts_charge_twice_but_same_split_lift_charges_once(self):
        ends = [[(-1, 0, 0), (0, 0, 0)], [(0, 0, 10), (1, 0, 10)]]
        two_lifts = physical([ends[0],
            ([(0, 0, 0), (0, 0, 5)], {'kind': 'Lift', 'id': 20}),
            ([(0, 0, 5), (0, 0, 10)], {'kind': 'Lift', 'id': 21}), ends[1]])
        result, _, _ = find_route(two_lifts, Point(-.8, 0), Point(.8, 0))
        self.assertAlmostEqual(result['time_s'], 60. + tobler_seconds(1.6, 0.))
        same_lift = physical([ends[0],
            ([(0, 0, 0), (0, 0, 5), (0, 0, 10)], {'kind': 'Lift', 'id': 20}),
            [(0, 0, 5), (.2, 0, 5)], ends[1]])
        result, legs, _ = find_route(same_lift, Point(-.8, 0), Point(.8, 0))
        self.assertAlmostEqual(result['time_s'], 30. + tobler_seconds(1.6, 0.))
        self.assertEqual(legs.loc[legs.lift_id.notna(), 'time_s'].tolist(), [30., 0.])

    def test_wheelchair_excludes_required_stairs_and_png_reports_no_route(self):
        graph = physical([[(0, 0, 0), (1, 0, 0)],
            ([(1, 0, 0), (2, 0, 1)], {'kind': 'Staircase'}), [(2, 0, 1), (3, 0, 1)]])
        start, end = Point(0, 0), Point(3, 0)
        general, _, _ = find_route(graph, start, end)
        result, route, _ = find_route(graph, start, end, wheelchair=True)
        self.assertEqual(general['status'], 'ok')
        self.assertEqual(result['status'], 'unreachable')
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'no_route.png'
            render_png(graph, start, end, route, result, output, wheelchair=True)
            self.assertEqual(output.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_unattached_point_and_identical_points(self):
        graph = physical([[(0, 0, 0), (10, 0, 0)]])
        result, route, attachments = find_route(graph, Point(2, 0), Point(500, 500))
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(attachments.warnings.str.contains('connector_above_threshold').any())
        self.assertFalse(route.empty)
        result, route, _ = find_route(graph, Point(2, 1), Point(2, 1))
        self.assertEqual(result['distance_m'], 0.)
        self.assertEqual(result['time_s'], 0.)
        self.assertTrue(route.empty)

    def test_coordinate_validation(self):
        self.assertEqual(coordinates(['22.28', '114.13']), (22.28, 114.13))
        for pair in [(91, 114), (22, 181), (math.nan, 114), (22, math.inf)]:
            with self.assertRaises(ValueError):
                coordinates(pair)


if __name__ == '__main__':
    unittest.main()
