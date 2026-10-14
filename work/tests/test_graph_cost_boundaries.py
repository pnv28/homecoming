"""Invalid source intervals cannot swallow usable adjacent geometry."""
import tempfile
import unittest

import numpy as np
from pandas.testing import assert_frame_equal

from estate_ranking.graph import (build_physical_graph, routing_graph, read_graph,
                                  save_physical, save_routing, validate_physical)
from estate_ranking.graph_costs import tobler_seconds
from test_step_2 import network, node_at


class CostBoundaryTests(unittest.TestCase):
    def test_healthy_sides_remain_usable_without_external_endpoint(self):
        original = network([([(0,0,0),(5,0,1),(5,0,6),(10,0,7)],
                             {'id':100,'gradient':.1})])
        physical = build_physical_graph(original)
        pieces = physical.edges.sort_values('start_position')
        self.assertEqual(pieces.time_forward_status.tolist(),
                         ['available','non_lift_vertical_without_horizontal_run','available'])
        self.assertEqual(physical.sources.geometry.iloc[0].wkb, original.geometry.iloc[0].wkb)
        self.assertEqual(physical.sources.time_forward_status.iloc[0],
                         'non_lift_vertical_without_horizontal_run')
        self.assertEqual(validate_physical(physical)['healthy_piece_directions_from_unavailable_sources'],4)
        for wheelchair in (False,True):
            graph = routing_graph(physical,wheelchair,'time')
            a,b,c,d = [node_at(graph,p) for p in [(0,0,0),(5,0,1),(5,0,6),(10,0,7)]]
            self.assertAlmostEqual(graph.costs_from(a)[b],tobler_seconds(5,.1))
            self.assertAlmostEqual(graph.costs_from(b)[a],tobler_seconds(5,-.1))
            self.assertAlmostEqual(graph.costs_from(c)[d],tobler_seconds(5,.1))
            self.assertTrue(np.isinf(graph.costs_from(a)[d]))
            distance = routing_graph(physical,wheelchair,'distance')
            self.assertAlmostEqual(distance.costs_from(a)[d],10)

    def test_cost_node_does_not_create_middle_crossing_connection(self):
        physical = build_physical_graph(network([
            ([(0,0,0),(0,0,5),(10,0,6)],{'id':100,'gradient':.1}),
            ([(-5,0,5),(5,0,5)],{'id':200})]))
        graph = routing_graph(physical)
        boundary = physical.memberships.loc[(physical.memberships.source_id=='100') &
                                             (physical.memberships.position==1)].node_index.iloc[0]
        self.assertEqual(set(physical.memberships.loc[physical.memberships.node_index==boundary].source_id),{'100'})
        self.assertTrue(np.isinf(graph.costs_from(node_at(graph,(10,0,6)))[node_at(graph,(-5,0,5))]))

    def test_existing_supported_cut_is_reused(self):
        physical = build_physical_graph(network([
            ([(0,0,0),(0,0,5),(10,0,6)],{'id':100,'gradient':.1}),
            ([(0,-2,5),(0,0,5)],{'id':200})]))
        self.assertEqual(len(physical.edges.loc[physical.edges.source_id=='100']),2)
        self.assertFalse(any(r['kind']=='cost_boundary_split' for r in physical.review))
        node = physical.memberships.loc[(physical.memberships.source_id=='100') &
                                        (physical.memberships.position==1)].node_index.iloc[0]
        self.assertEqual(set(physical.memberships.loc[physical.memberships.node_index==node].source_id),{'100','200'})

    def test_overflow_boundaries_preserve_level_interval_and_direction(self):
        physical = build_physical_graph(network([
            ([(0,0,0),(1,0,1),(2,0,1),(3,0,2)],
             {'id':100,'gradient':1.56705634,'direction':1})]))
        pieces = physical.edges.sort_values('start_position')
        self.assertEqual(pieces.time_forward_status.tolist(),
                         ['unrepresentable_tobler_time','available','unrepresentable_tobler_time'])
        graph = routing_graph(physical)
        a,b = node_at(graph,(1,0,1)),node_at(graph,(2,0,1))
        self.assertAlmostEqual(graph.costs_from(a)[b],tobler_seconds(1,0))
        self.assertTrue(np.isinf(graph.costs_from(b)[a]))

    def test_valid_profile_does_not_gain_cost_boundary_nodes(self):
        physical = build_physical_graph(network([
            ([(0,0,0),(1,0,1),(2,0,0)],{'id':100,'gradient':.1}),
            ([(3,0,0),(3,0,5)],{'id':200,'kind':'Lift','gradient':1.57})]))
        self.assertEqual(len(physical.edges),2)
        self.assertFalse(any(r['kind']=='cost_boundary_split' for r in physical.review))

    def test_determinism_and_save_reopen(self):
        original = network([
            ([(0,0,0),(0,0,5),(10,0,6)],{'id':100,'gradient':.1}),
            ([(20,0,0),(21,0,0)],{'id':200})])
        physical = build_physical_graph(original)
        shuffled = build_physical_graph(original.iloc[::-1])
        assert_frame_equal(physical.nodes,shuffled.nodes)
        assert_frame_equal(physical.edges,shuffled.edges)
        assert_frame_equal(physical.memberships,shuffled.memberships)
        with tempfile.TemporaryDirectory() as directory:
            save_physical(directory,physical)
            graph = routing_graph(physical)
            save_routing(directory,graph)
            reopened = read_graph(directory)
            a,b = node_at(graph,(0,0,5)),node_at(graph,(10,0,6))
            self.assertAlmostEqual(reopened.costs_from(a)[b],10.154640788407857)
            self.assertTrue(np.isinf(reopened.costs_from(node_at(graph,(0,0,0)))[b]))


if __name__=='__main__':
    unittest.main()
