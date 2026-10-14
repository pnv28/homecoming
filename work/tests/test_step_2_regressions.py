"""Joint XYZ projections, traversal visits and local piece-cost regressions."""
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pyogrio
from scipy.sparse.csgraph import dijkstra

from estate_ranking.graph import (build_graph, build_physical_graph, routing_graph,
                                  save_physical, save_routing, read_graph, validate_physical)
from estate_ranking.graph_costs import build_profile, tobler_seconds
from estate_ranking.graph_topology import projections, projection_visits, separate_interior_visits
from estate_ranking.graph_regressions import check_lift_connections
from test_step_2 import network, node_at


WORK = Path(__file__).resolve().parents[1]


class JointProjectionTests(unittest.TestCase):
    def test_slanted_segment_minimises_xy_inside_height_band_in_both_orders(self):
        coords=np.array([(0,0,0),(.2,0,10.)])
        point=np.array((0.,0.,5.))
        for vertices in (coords,coords[::-1]):
            candidates=projections(vertices,point)
            self.assertEqual(len(candidates),1)
            _,xyz,distance=candidates[0]
            self.assertAlmostEqual(xyz[2],4.975)
            self.assertAlmostEqual(distance,.0995)
            self.assertGreater(xyz[2],0)

    def test_vertical_near_vertical_constant_height_and_degenerate_segments(self):
        for dx in (0.,1e-12,1e-180):
            coords=np.array([(0,0,0),(dx,0,10)])
            for vertices in (coords,coords[::-1]):
                matches=projections(vertices,np.array((.01,0,5)))
                self.assertEqual(len(matches),1)
                self.assertLessEqual(matches[0][2],.10)
                z=matches[0][1][2]
                self.assertTrue(z<=5+.025 and 5<=z+.025)
        level=np.array([(0,0,2.),(10,0,2.)])
        self.assertEqual(projections(level,np.array((5,0,2.1))),[])
        self.assertAlmostEqual(projections(level,np.array((5,.1,2.025)))[0][0],.5)
        zero=np.array([(0,0,2.),(0,0,2.)])
        self.assertEqual(len(projections(zero,np.array((.1,0,2.025)))),1)

    def test_joint_projection_inclusive_boundaries_and_nextafter_rejection(self):
        # The only height-compatible point is the shared end of this segment.
        coords=np.array([(0,0,-2.),(0,0,0.)])
        for dx,dz,accepted in [(.10,.025,True),
                                (np.nextafter(.10,np.inf),.025,False),
                                (.10,np.nextafter(.025,np.inf),False)]:
            for vertices in (coords,coords[::-1]):
                self.assertEqual(bool(projections(vertices,np.array((dx,0,dz)))),accepted)
        # XY-only projection is at z=0; constrained solution meets both limits.
        coords=np.array([(0,0,0.),(.2,0,10.)])
        self.assertEqual(len(projections(coords,np.array((0,0,5.025)))),1)
        self.assertEqual(projections(coords,np.array((0,0,5.0250001))),[])
        self.assertEqual(projections(coords,np.array((0,0,np.nextafter(5.025,np.inf)))),[])

    def test_new_cut_near_lift_base_does_not_invent_an_endpoint_merge(self):
        g=build_graph(network([([(0,0,0),(.7,0,6)],{'id':100,'kind':'Lift'}),
                               ([(-1,0,.043),(0,0,.043)],{'id':200})]))
        self.assertEqual(len(g.edges.loc[g.edges.source_id=='100']),2)
        start=node_at(g,(0,0,.043)); end=node_at(g,(.7,0,6))
        self.assertAlmostEqual(g.costs_from(start)[end],30)
        self.assertFalse(any(r['kind']=='ambiguous_cluster' for r in g.physical.review))
        self.assertLessEqual(g.nodes.max_horizontal_m.max(),.10)
        self.assertLessEqual(g.nodes.max_height_m.max(),.025)

    def test_joint_candidate_still_respects_floor_conflicts(self):
        n=network([([(0,0,0),(.2,0,10)],{'id':100,'floor':1,'building':1}),
                   ([(0,-1,5),(0,0,5)],{'id':200,'floor':2,'building':1})])
        g=build_graph(n,metric='distance')
        self.assertEqual(len(g.edges),2)
        self.assertTrue(any(r['kind']=='floor_conflict_rejected' for r in g.physical.review))


class TraversalVisitTests(unittest.TestCase):
    def test_adjacent_retraced_segments_are_ambiguous(self):
        for coords in ([(-10,0,0),(0,0,0),(-10,0,0)],
                       [(-10,0,0),(-5,0,0),(0,0,0),(-5,0,0),(-10,0,0)]):
            n=network([(coords,{'id':100}),([(-4.9,-2,0),(-4.9,0,0)],{'id':200})])
            g=build_graph(n,metric='distance')
            reviews=[r for r in g.physical.review if r['kind']=='ambiguous_interior_projection' and r['receiving_source']=='100']
            self.assertTrue(reviews)
            self.assertEqual(len(reviews[0]['visits']),2)
            self.assertEqual(len(g.edges.loc[g.edges.source_id=='100']),1)
            self.assertFalse(np.isfinite(g.costs_from(node_at(g,(-4.9,-2,0)))[node_at(g,(-10,0,0))]))
        coords=np.array([(-10,0,0),(0,0,0),(-10,0,0)])
        matches=projections(coords,np.array((-4.9,0,0)))
        self.assertTrue(np.allclose([t for t,_,_ in matches],[.51,1.49]))
        self.assertTrue(separate_interior_visits(coords,[.51,1.49]))

    def test_bends_shared_vertices_and_dense_vertices_are_one_visit(self):
        for coords,point in [([(-2,0,0),(0,0,0),(0,2,0)],(-.02,.02,0)),
                              ([(-2,0,0),(0,0,0),(2,0,0)],(0,0,0)),
                              ([(x,0,0) for x in np.linspace(-.2,.2,41)],(0,0,0))]:
            c=np.array(coords,dtype=float); p=np.array(point,dtype=float)
            self.assertEqual(len(projection_visits(c,p,projections(c,p))),1)
            g=build_graph(network([(coords,{'id':100}),([(point[0],point[1]-2,0),point],{'id':200})]),metric='distance')
            self.assertEqual(len(g.edges.loc[g.edges.source_id=='100']),2)
            self.assertFalse(any(r['kind']=='ambiguous_interior_projection' for r in g.physical.review))
            self.assertTrue(np.isfinite(g.costs_from(node_at(g,(point[0],point[1]-2,0)))[node_at(g,coords[-1])]))

    def test_repeated_visits_at_projection_sites_cannot_collapse_in_cluster(self):
        c=np.array([(-10,0,0),(0,0,0),(-10,0,0)])
        self.assertTrue(separate_interior_visits(c,[.51,1.49]))
        c=np.array([(-.05,0,0),(0,0,0),(.05,0,0)])
        self.assertFalse(separate_interior_visits(c,[.1,1.9]))
        # A drawing seam of a closed triangle remains one supported junction.
        c=np.array([(0,0,0),(2,0,0),(2,2,0),(0,0,0)])
        p=np.array((.01,.01,0))
        self.assertEqual(len(projection_visits(c,p,projections(c,p))),1)
        self.assertFalse(separate_interior_visits(c,[0.,3.]))

    def test_endpoint_match_does_not_hide_a_separate_interior_visit(self):
        g=build_graph(network([([(0,0,0),(2,0,0),(-2,0,0)],{'id':100}),
                               ([(0,-2,0),(0,.01,0)],{'id':200})]),metric='distance')
        self.assertTrue(any(r['kind']=='ambiguous_interior_projection' for r in g.physical.review))
        # The incoming endpoint must not attach to either receiving visit.
        members=g.physical.memberships
        incoming=members.loc[(members.source_id=='200') & (members.position==1)].node_index.iloc[0]
        self.assertFalse(((members.node_index==incoming)&(members.source_id=='100')).any())


class LocalPieceCostTests(unittest.TestCase):
    def test_healthy_piece_survives_invalid_vertical_interval_in_both_directions(self):
        profile=build_profile('100',[(0,0,0),(0,0,5),(10,0,6)],.1)
        self.assertEqual(profile.forward_status,'non_lift_vertical_without_horizontal_run')
        bad=profile.piece_costs(0,1); good=profile.piece_costs(1,2)
        self.assertIsNone(bad.forward_seconds); self.assertIsNone(bad.reverse_seconds)
        self.assertAlmostEqual(good.forward_seconds,10.1546408,places=7)
        expected_reverse=10*.6*math.exp(3.5*abs(math.tan(-.1)+.05))
        self.assertAlmostEqual(good.reverse_seconds,expected_reverse)
        self.assertEqual((good.forward_status,good.reverse_status),('available','available'))
        self.assertIsNone(profile.piece_costs(.9,1.5).forward_seconds)
        self.assertEqual(profile.piece_costs(1,1).forward_seconds,0)
        self.assertAlmostEqual(profile.piece_costs(1,1.5).forward_seconds,good.forward_seconds/2)
        backwards=build_profile('100',profile.coords[::-1],.1)
        self.assertAlmostEqual(backwards.piece_costs(0,1).forward_seconds,good.reverse_seconds)

    def test_graph_piece_statuses_routing_conservation_and_storage(self):
        n=network([([(0,0,0),(0,0,5),(10,0,6)],{'id':100,'gradient':.1}),
                   ([(0,-2,5),(0,0,5)],{'id':200})])
        physical=build_physical_graph(n)
        edges=physical.edges.loc[physical.edges.source_id=='100'].sort_values('start_position')
        self.assertEqual(len(edges),2)
        self.assertEqual(edges.time_forward_status.tolist(),['non_lift_vertical_without_horizontal_run','available'])
        self.assertEqual(edges.time_reverse_status.tolist(),['non_lift_vertical_without_horizontal_run','available'])
        checks=validate_physical(physical)
        self.assertEqual(checks['healthy_piece_directions_from_unavailable_sources'],2)
        for wheelchair in (False,True):
            graph=routing_graph(physical,wheelchair)
            a,b=node_at(graph,(0,0,5)),node_at(graph,(10,0,6))
            self.assertAlmostEqual(graph.costs_from(a)[b],10.1546408,places=7)
            self.assertAlmostEqual(graph.costs_from(b)[a],tobler_seconds(10,-.1))
            self.assertTrue(np.isinf(graph.costs_from(node_at(graph,(0,0,0)))[b]))
            with tempfile.TemporaryDirectory() as tmp:
                save_physical(tmp,physical); save_routing(tmp,graph)
                reopened=read_graph(tmp,wheelchair)
                self.assertEqual(reopened.edges.time_forward_status.tolist(),graph.edges.time_forward_status.tolist())
                self.assertTrue(np.array_equal(graph.costs_from(a),reopened.costs_from(a)))

    def test_own_sum_overflow_does_not_invalidate_small_pieces(self):
        n=math.atan((math.log(1e308)-math.log(.6))/3.5-.05)
        profile=build_profile('100',[(0,0,0),(1,0,1),(2,0,2)],n)
        self.assertTrue(all(v is not None for v in profile.forward))
        self.assertEqual(profile.forward_status,'unrepresentable_tobler_time')
        self.assertEqual(profile.piece_costs(0,1).forward_status,'available')
        self.assertIsNone(profile.piece_costs(0,2).forward_seconds)
        # An overlapping interval that is itself unavailable stays unavailable.
        extreme=build_profile('100',[(0,0,0),(1,0,1)],math.pi/2)
        self.assertIsNone(extreme.piece_costs(0,.5).forward_seconds)

    def test_piece_status_tampering_fails_validation(self):
        p=build_physical_graph(network([([(0,0,0),(0,0,5),(10,0,6)],{'id':100,'gradient':.1}),
                                        ([(0,-2,5),(0,0,5)],{'id':200})]))
        healthy=p.edges.index[(p.edges.source_id=='100') & (p.edges.start_position==1)][0]
        p.edges.loc[healthy,'time_forward_status']='non_lift_vertical_without_horizontal_run'
        with self.assertRaisesRegex(AssertionError,'status'):
            validate_physical(p)


class RealLiftRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=WORK/'precomputed/outputs/runs/20261014T090829Z-20d0139c/harmonised.gpkg'
        cls.records=pyogrio.read_dataframe(path,layer='network',where=
            'PedestrianRouteID IN (290063550,260001786,290064373,280005280)')

    def test_both_source_identified_lifts_are_direct_30_second_uses_in_both_modes(self):
        physical=build_physical_graph(self.records)
        self.assertEqual(len(physical.edges),6)
        for wheelchair in (False,True):
            graph=routing_graph(physical,wheelchair)
            checked=check_lift_connections(graph)
            self.assertEqual(len(checked),2)
            for result in checked:
                self.assertEqual(result['forward_lift_state_seconds'],30)
                self.assertEqual(result['reverse_lift_state_seconds'],30)
                self.assertTrue(result['direct_connection'])
                self.assertEqual(len(result['accepted_lift_parameters']),1)
        reordered=build_physical_graph(self.records.iloc[::-1])
        self.assertEqual(physical.nodes.node_id.tolist(),reordered.nodes.node_id.tolist())
        self.assertEqual(physical.edges.edge_id.tolist(),reordered.edges.edge_id.tolist())
