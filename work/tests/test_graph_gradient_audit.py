"""Diagnostic evidence must not mutate routing or invent gradient corrections."""
import json
import math
import unittest

from estate_ranking.graph import build_physical_graph, routing_graph
from estate_ranking.graph_gradient_audit import audit_extreme_gradient, gradient_routing_impact
from test_step_2 import network


class GradientAuditTests(unittest.TestCase):
    def test_entirely_vertical_unavailable_graph_validates_and_preserves_distance(self):
        physical = build_physical_graph(network([
            ([(0, 0, 0), (0, 0, 5)], {'id': 100, 'gradient': .1})]))
        time = routing_graph(physical)
        self.assertEqual(time.matrix.nnz, 0)
        result = gradient_routing_impact(time, '100')['pieces'][0]
        self.assertFalse(result['forward']['reachable'])
        self.assertFalse(result['reverse']['reachable'])
        distance = gradient_routing_impact(routing_graph(physical, metric='distance'), '100')
        self.assertEqual(distance['pieces'][0]['forward']['cost'], 0)
        self.assertTrue(distance['pieces'][0]['forward']['route_uses_audited_source'])

    def test_real_gradient_is_correlated_with_xyz_and_overflows_in_both_directions(self):
        coords = [(838471.9702000003, 826101.7000999991, 64.90769999999611),
                  (838471.9652000004, 826101.7061000001, 62.81939999999304)]
        physical = build_physical_graph(network([(coords, {'id': 150021876, 'gradient': 1.56705634})]))
        original = physical.sources.geometry.iloc[0].wkb
        result = audit_extreme_gradient(physical)
        self.assertAlmostEqual(result['horizontal_length_m'], .007810250359888187)
        self.assertAlmostEqual(result['endpoint_height_change_m'], -2.0883000000030734)
        self.assertLess(abs(result['provider_minus_endpoint_angle_radians']), 3e-10)
        for direction in ('forward', 'reverse'):
            interval = result['intervals'][0][direction]
            self.assertGreater(interval['log10_seconds'], 404)
            self.assertTrue(interval['exceeds_float64_range'])
            self.assertIsNone(interval['seconds'])
        self.assertIsNone(result['correction'])
        self.assertEqual(original, physical.sources.geometry.iloc[0].wkb)
        self.assertEqual(physical.sources.Gradient.iloc[0], 1.56705634)
        json.dumps(result, allow_nan=False)

    def test_unavailable_piece_alternatives_and_distance_retention(self):
        physical = build_physical_graph(network([
            ([(0, 0, 0), (1, 0, 2)], {'id': 100, 'gradient': math.pi/2}),
            ([(0, 0, 0), (0, 3, 1), (1, 0, 2)], {'id': 200, 'gradient': .1})]))
        for wheelchair in (False, True):
            graph = routing_graph(physical, wheelchair, 'time')
            original = graph.matrix.copy()
            result = gradient_routing_impact(graph, '100')['pieces'][0]
            for direction in ('forward', 'reverse'):
                self.assertTrue(result[direction]['reachable'])
                self.assertEqual(result[direction]['route_source_ids'], ['200'])
                self.assertFalse(result[direction]['route_uses_audited_source'])
            self.assertNotEqual(result['forward']['cost'], result['reverse']['cost'])
            self.assertEqual((original != graph.matrix).nnz, 0)
            distance = gradient_routing_impact(routing_graph(physical, wheelchair, 'distance'), '100')
            self.assertEqual(distance['pieces'][0]['forward']['cost'], 1)
            self.assertTrue(distance['pieces'][0]['forward']['route_uses_audited_source'])

    def test_all_split_piece_routes_and_unreachable_status(self):
        physical = build_physical_graph(network([
            ([(0, 0, 0), (0, 0, 5), (10, 0, 6)], {'id': 100, 'gradient': .1}),
            ([(0, 0, 5), (-2, 0, 5)], {'id': 200})]))
        result = gradient_routing_impact(routing_graph(physical), '100')
        self.assertEqual(len(result['pieces']), 2)
        invalid, healthy = result['pieces']
        self.assertFalse(invalid['forward']['reachable'])
        self.assertFalse(invalid['reverse']['reachable'])
        self.assertIsNone(invalid['forward']['cost'])
        self.assertAlmostEqual(healthy['forward']['cost'], 10.154640788407857)
        self.assertAlmostEqual(healthy['reverse']['cost'], 7.155854418962862)
        self.assertTrue(healthy['forward']['route_uses_audited_source'])
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
