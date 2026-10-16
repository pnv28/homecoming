"""Reviewed fallback, baseline comparisons and subdivision provenance contracts."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.sparse.csgraph import dijkstra

from estate_ranking.graph import (build_physical_graph, routing_graph, save_physical,
                                  save_routing, read_graph)
from estate_ranking.graph_costs import tobler_seconds
from estate_ranking.policy import load_policy
from estate_ranking.time_fallback import profile_digest, derived_policy
from estate_ranking.attachments import attach_points, attached_routing_graph
from estate_ranking.step_3 import validate_attachments, validate_terminals
from test_step_2 import network
from test_step_3 import points

WORK = Path(__file__).resolve().parents[1]


def reviewed(paths, uphill=6., downhill=2., decision='allow_estimated_time'):
    policy = load_policy(WORK/'config/routing_policy.json')
    policy['transport_time']['fallback']['enabled'] = False
    frame = network(paths)
    frame['Location_label'] = 'Outdoor'
    baseline = build_physical_graph(frame, policy, audit_crossings=False)
    original = {p.source_id: copy.deepcopy(p.evidence()) for p in baseline.profiles}
    sources = baseline.sources.set_index(baseline.sources.PedestrianRouteID.astype(str))
    entries = {}
    for p in baseline.profiles:
        intervals = []
        for i, (reason, f, r) in enumerate(zip(p.interval_reasons, p.forward, p.reverse)):
            if reason or f is None or r is None:
                intervals.append(dict(review_id=p.source_id+':'+str(i),interval_index=i,
                    start_position=float(p.positions[i]),end_position=float(p.positions[i+1]),
                    horizontal_m=float(p.lengths[i]),height_change_m=float(p.heights[i+1]-p.heights[i]),
                    decision=decision,original_reason=reason or 'unrepresentable_tobler_time'))
        if not intervals:
            continue
        row = sources.loc[p.source_id]
        entries[p.source_id] = dict(feature_type=row.FeatureType_label,direction=int(row.Direction),
            enabled=bool(row.Enabled_bool),wheelchair_barrier=bool(row.WheelchairBarrier_bool),
            allow_general=bool(row.allow_general),allow_wheelchair=bool(row.allow_wheelchair),
            original_profile_sha256=profile_digest(p.evidence()),intervals=intervals)
    policy['transport_time']['fallback'].update(enabled=True,uphill_seconds_per_metre=uphill,
        downhill_seconds_per_metre=downhill,review={'sources':entries})
    primary = build_physical_graph(frame, policy, audit_crossings=False)
    return primary, original


class TimeFallbackTests(unittest.TestCase):
    def test_height_cost_reverse_and_original_evidence(self):
        g, originals = reviewed([[(-10,0,0),(0,0,0),(0,0,2),(10,0,2)]])
        p = g.profiles[0]
        self.assertEqual(p.evidence(), originals[p.source_id])
        self.assertIsNone(p.piece_costs(0,3,'baseline').forward_seconds)
        self.assertAlmostEqual(p.piece_costs(0,3).forward_seconds, tobler_seconds(20,0)+12)
        self.assertAlmostEqual(p.piece_costs(0,3).reverse_seconds, tobler_seconds(20,0)+4)
        self.assertEqual(int(g.edges.uses_estimated_time.sum()),1)
        self.assertEqual(g.sources.time_forward_status.iloc[0],'non_lift_vertical_without_horizontal_run')

    def test_split_vertical_estimate_conserves_both_directions(self):
        g,_=reviewed([[(0,0,0),(0,0,2)]])
        p=g.profiles[0]
        a,b=p.piece_costs(0,.3),p.piece_costs(.3,1)
        self.assertAlmostEqual(a.forward_seconds+b.forward_seconds,12)
        self.assertAlmostEqual(a.reverse_seconds+b.reverse_seconds,4)
        self.assertEqual(a.distance_m+b.distance_m,0)

    def test_rise_and_fall_do_not_cancel(self):
        g,_=reviewed([[(0,0,0),(0,0,2),(0,0,0)]])
        p=g.profiles[0]
        self.assertAlmostEqual(p.piece_costs(0,2).forward_seconds,16)
        self.assertAlmostEqual(p.piece_costs(0,2).reverse_seconds,16)

    def test_overflow_receives_distance_and_height_estimate(self):
        g,_=reviewed([([(0,0,0),(.008,0,-2.1)],{'gradient':math.pi/2})])
        p=g.profiles[0]
        self.assertAlmostEqual(p.piece_costs(0,1).forward_seconds,tobler_seconds(.008,0)+4.2)
        self.assertAlmostEqual(p.piece_costs(0,1).reverse_seconds,tobler_seconds(.008,0)+12.6)
        self.assertIsNone(p.piece_costs(0,1,'baseline').forward_seconds)

    def test_rejected_and_unreviewed_failures_stay_unavailable(self):
        g,_=reviewed([[(0,0,0),(0,0,2)]],decision='unresolved')
        self.assertIsNone(g.profiles[0].piece_costs(0,1).forward_seconds)
        self.assertFalse(g.edges.uses_estimated_time.any())
        raw=build_physical_graph(network([[(-1,0,0),(0,0,0),(0,0,2)]]),audit_crossings=False)
        self.assertIsNone(raw.profiles[0].piece_costs(0,2).forward_seconds)

    def test_stale_review_and_missing_coefficients_fail(self):
        g,_=reviewed([[(0,0,0),(0,0,2)]])
        frame=network([[(0,0,0),(0,0,3)]])
        with self.assertRaises(ValueError):
            build_physical_graph(frame,g.policy,audit_crossings=False)
        policy=copy.deepcopy(g.policy)
        policy['transport_time']['fallback']['uphill_seconds_per_metre']=None
        with self.assertRaises(ValueError):
            derived_policy(policy,policy)
        policy=copy.deepcopy(g.policy)
        policy['modes']['general']['bus_operators']=[]
        with self.assertRaises(ValueError):
            derived_policy(g.policy,policy)

    def test_a_to_d_primary_direct_or_detour_and_baseline(self):
        paths=[[(0,0,0),(10,0,0)],[(10,0,0),(10,0,2)],
               [(10,0,2),(20,0,2)],([(10,0,0),(10,40,1),(10,0,2)],{'gradient':.025})]
        for uphill,prefer_direct in [(6,True),(60,False)]:
            g,_=reviewed(paths,uphill=uphill)
            from shapely import get_coordinates
            coords=get_coordinates(g.nodes.geometry,include_z=True)
            a=int(np.argmin(np.linalg.norm(coords-[0,0,0],axis=1)))
            d=int(np.argmin(np.linalg.norm(coords-[20,0,2],axis=1)))
            main=routing_graph(g).costs_from(a)[d]
            base=routing_graph(g,scenario='baseline').costs_from(a)[d]
            expected=tobler_seconds(20,0)+uphill*2
            if prefer_direct:self.assertAlmostEqual(main,expected)
            else:self.assertAlmostEqual(main,base)
            self.assertLessEqual(main,base)

    def test_wheelchair_barrier_and_stairs_not_overridden(self):
        g,_=reviewed([([(0,0,0),(0,0,2)],{'kind':'Staircase','barrier':True})])
        self.assertGreater(routing_graph(g).matrix.nnz,0)
        self.assertEqual(routing_graph(g,wheelchair=True).matrix.nnz,0)

    def test_scenario_specific_attachments_and_no_vertical_snap(self):
        g,_=reviewed([([(0,0,0),(.008,0,2)],{'gradient':math.pi/2}),
                      [(0,10,0),(10,10,0)]])
        a=attach_points(g,{'estate':points('estate',[(.004,0)])})
        rows=a.attachments[(a.attachments['mode']=='general')&(a.attachments.metric=='time')]
        self.assertEqual(rows.loc[rows.scenario=='primary','source_id'].iloc[0],'1')
        self.assertEqual(rows.loc[rows.scenario=='baseline','source_id'].iloc[0],'2')
        validate_attachments(a)
        for scenario in ['primary','baseline']:
            validate_terminals(attached_routing_graph(a,scenario=scenario))
        g,_=reviewed([[(0,0,0),(0,0,2)]])
        a=attach_points(g,{'estate':points('estate',[(0,0)])})
        self.assertTrue(a.attachments.status.eq('unattached').all())

    def test_multiple_estimated_sources_and_no_baseline_route(self):
        g,_=reviewed([[(-1,0,0),(0,0,0)],[(0,0,0),(0,0,2)],
                      [(0,0,2),(1,0,2)],[(1,0,2),(1,0,5)],[(1,0,5),(2,0,5)]])
        from shapely import get_coordinates
        coords=get_coordinates(g.nodes.geometry,include_z=True)
        a=int(np.argmin(np.linalg.norm(coords-[-1,0,0],axis=1)))
        d=int(np.argmin(np.linalg.norm(coords-[2,0,5],axis=1)))
        self.assertAlmostEqual(routing_graph(g).costs_from(a)[d],tobler_seconds(3,0)+30)
        self.assertAlmostEqual(routing_graph(g).costs_from(d)[a],tobler_seconds(3,0)+10)
        self.assertTrue(np.isinf(routing_graph(g,scenario='baseline').costs_from(a)[d]))
        self.assertEqual(int(g.edges.uses_estimated_time.sum()),2)

    def test_save_reopen_original_and_primary_matrices(self):
        g,original=reviewed([[(-1,0,0),(0,0,0),(0,0,2),(1,0,2)]])
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary)
            save_physical(p,g)
            self.assertEqual(json.loads((p/'profiles.jsonl').read_text()),original['1'])
            self.assertEqual(json.loads((p/'derived_profiles.jsonl').read_text())['source_id'],'1')
            for scenario in ['primary','baseline']:
                before=routing_graph(g,scenario=scenario);save_routing(p,before)
                after=read_graph(p,scenario=scenario)
                np.testing.assert_array_equal(before.matrix.data,after.matrix.data)
                self.assertEqual(after.scenario,scenario)


if __name__=='__main__':unittest.main()
