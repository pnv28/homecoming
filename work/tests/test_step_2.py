"""Step 2 contracts: topology, conservation, eligibility, stateful lifts and persistence."""
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import shapely
from shapely.geometry import LineString, MultiLineString
from scipy.sparse.csgraph import dijkstra

from estate_ranking.graph import (build_graph, build_physical_graph, routing_graph,
    minimum_matrix, read_graph, read_physical, save_physical, save_routing)
from estate_ranking.graph_costs import build_profile, tobler_seconds
from estate_ranking.policy import load_policy, canonical_sites
from estate_ranking.models import Table
from estate_ranking.validate import ValidationReport


WORK = Path(__file__).resolve().parents[1]


def network(paths):
    rows = []
    for i,item in enumerate(paths):
        options = item[1] if isinstance(item,tuple) else {}
        coords = item[0] if isinstance(item,tuple) else item
        rows.append(dict(PedestrianRouteID=options.get('id',i+1),
            FeatureType_label=options.get('kind','Footway'),Direction=options.get('direction',0),
            Enabled_bool=options.get('enabled',True),WheelchairBarrier_bool=options.get('barrier',False),
            Gradient=options.get('gradient',0.),FloorID=options.get('floor',None),
            BuildingID_1=options.get('building',None),BuildingID_2=None,
            geometry=MultiLineString([coords])))
    return gpd.GeoDataFrame(rows,crs=2326)


def node_at(graph, xyz):
    coords = shapely.get_coordinates(graph.nodes.geometry,include_z=True)
    return int(np.argmin(np.linalg.norm(coords-np.array(xyz),axis=1)))


class CostTests(unittest.TestCase):
    def test_signed_vertices_reverse_and_conservation(self):
        p = build_profile('123',[(0,0,10),(3,0,12),(7,0,9),(10,0,11)],.1)
        self.assertEqual(list(np.sign(p.signed_angles)),[1,-1,1])
        expected = tobler_seconds(3,.1)+tobler_seconds(4,-.1)+tobler_seconds(3,.1)
        self.assertAlmostEqual(sum(p.forward),expected)
        reverse = build_profile('123',p.coords[::-1],.1)
        self.assertAlmostEqual(sum(p.reverse),sum(reverse.forward))
        pieces = [p.piece(0,.4),p.piece(.4,1.8),p.piece(1.8,3)]
        self.assertAlmostEqual(sum(x[1] for x in pieces),sum(p.forward))
        self.assertAlmostEqual(sum(x[2] for x in pieces),sum(p.reverse))
        self.assertAlmostEqual(sum(x[0] for x in pieces),10)

    def test_bounded_repeatable_sampling_and_exact_equality(self):
        coords = [(0,0,2),(5,0,2),(10,0,2)]
        p = build_profile('flat',coords,.2)
        q = build_profile('flat',coords,.2)
        self.assertEqual(p.samples,q.samples)
        self.assertEqual(p.rounds,2)
        self.assertEqual(len(p.samples),8)
        self.assertEqual(len({s['position'] for s in p.samples}),8)
        self.assertEqual(p.classification,'relatively_flat')
        self.assertTrue(all(a==0 for a in p.signed_angles))
        tiny = build_profile('tiny',[(0,0,2),(5,0,2+1e-12),(10,0,2)],.2)
        self.assertEqual(tiny.rounds,1)
        self.assertEqual(tiny.classification,'sampled_nonflat')
        self.assertEqual(len(tiny.samples),4)
        # The same profile is reversed for traversal; topology never resamples.
        self.assertEqual(p.samples, q.samples)
        a,b = p.piece(0,.8),p.piece(.8,2)
        self.assertAlmostEqual(a[1]+b[1],p.piece(0,2)[1])

    def test_extreme_slopes_and_vertical_time_unavailable(self):
        p = build_profile('huge',[(0,0,0),(1,0,1)],math.pi/2)
        self.assertIsNone(p.piece(0,1)[1])
        self.assertEqual(p.forward_status,'unrepresentable_tobler_time')
        vertical = build_profile('vertical',[(0,0,0),(0,0,5)],.3)
        self.assertEqual(vertical.forward_status,'non_lift_vertical_without_horizontal_run')
        lift = build_profile('lift',[(0,0,0),(0,0,5)],math.pi/2,True)
        self.assertEqual(lift.piece(0,1),(0.,0.,0.))


class TopologyTests(unittest.TestCase):
    def test_horizontal_height_boundaries(self):
        for dx,dz,connected in [(0.10,0.025,True),(.100000001,.025,False),(.10,.025000001,False)]:
            with self.subTest(dx=dx,dz=dz):
                g=build_graph(network([[(-2,0,0),(0,0,0)],[(dx,0,dz),(2,0,dz)]]),metric='distance')
                self.assertEqual(np.isfinite(g.costs_from(node_at(g,(-2,0,0)))[node_at(g,(2,0,dz))]),connected)

    def test_chained_and_ambiguous_matches_stay_disconnected(self):
        g=build_graph(network([[(-2,0,0),(0,0,0)],[(.075,0,0),(.075,2,0)],
                               [(.15,0,0),(2,0,0)]]),metric='distance')
        self.assertTrue(any(r['kind']=='ambiguous_cluster' for r in g.physical.review))
        self.assertFalse(np.isfinite(g.costs_from(node_at(g,(-2,0,0)))[node_at(g,(2,0,0))]))
        self.assertLessEqual(g.nodes.max_horizontal_m.max(),.10)
        self.assertLessEqual(g.nodes.max_height_m.max(),.025)

    def test_interior_split_exact_tolerances_and_cost_conservation(self):
        for dy,dz,expected in [(.10,.025,3),(.100000001,.025,2),(.10,.025000001,2)]:
            with self.subTest(dy=dy,dz=dz):
                g=build_graph(network([([(0,0,0),(10,0,1)],{'gradient':.1}),
                                       [(5,dy,.5+dz),(5,3,.5+dz)]]))
                self.assertEqual(len(g.edges),expected)
                source=g.edges.loc[g.edges.source_id=='1']
                self.assertAlmostEqual(source.distance_m.sum(),10)
                self.assertAlmostEqual(source.time_forward_s.sum(),tobler_seconds(10,.1))

    def test_crossings_different_heights_and_same_building_floors(self):
        g=build_graph(network([[(-2,0,0),(2,0,0)],[(0,-2,0),(0,2,0)],
                               [(1,0,5),(1,2,5)]]),metric='distance')
        self.assertEqual(len(g.edges),3)
        self.assertTrue(any(r['kind']=='middle_crossing_not_auto_joined' for r in g.physical.review))
        for vertical,allowed in [(False,False),(True,True)]:
            g=build_graph(network([([(-2,0,0),(0,0,0)],{'building':1,'floor':1}),
                  ([(.05,0,0),(.05,2,1)],{'building':1,'floor':2,'kind':'Ramp' if vertical else 'Footway'})]),metric='distance')
            cost=g.costs_from(node_at(g,(-2,0,0)))[node_at(g,(.05,2,1))]
            self.assertEqual(np.isfinite(cost),allowed)

    def test_row_order_independence_parallel_closed_and_directions(self):
        n=network([([(0,0,0),(3,0,1)],{'id':10,'direction':1,'gradient':.1}),
                   ([(0,0,0),(1.5,.2,.5),(3,0,1)],{'id':20,'direction':1,'gradient':.2}),
                   ([(3,0,1),(5,0,2)],{'id':30,'direction':-1}),
                   ([(7,0,0),(8,0,0),(8,1,0),(7,0,0)],{'id':40})])
        a=build_graph(n,metric='distance'); b=build_graph(n.sample(frac=1,random_state=7),metric='distance')
        self.assertEqual(a.nodes.node_id.tolist(),b.nodes.node_id.tolist())
        self.assertEqual(a.edges.edge_id.tolist(),b.edges.edge_id.tolist())
        self.assertEqual(len(a.edges),4)
        start,end=node_at(a,(0,0,0)),node_at(a,(3,0,1))
        self.assertAlmostEqual(a.costs_from(start)[end],3)
        self.assertTrue(np.isinf(a.costs_from(end)[start]))
        self.assertAlmostEqual(a.costs_from(node_at(a,(5,0,2)))[end],2)
        closed=a.edges.loc[a.edges.source_id=='40'].iloc[0]
        self.assertEqual(closed.from_node,closed.to_node)

    def test_height_chain_and_ambiguous_self_crossing_projection(self):
        g=build_graph(network([[(-3,0,0),(0,0,0)],[(0,0,.02),(0,3,.02)],
                               [(0,0,.04),(3,0,.04)]]),metric='distance')
        self.assertFalse(np.isfinite(g.costs_from(node_at(g,(-3,0,0)))[node_at(g,(3,0,.04))]))
        self.assertTrue(any(r['kind']=='ambiguous_cluster' for r in g.physical.review))
        # An endpoint touching two separate visits of a self-crossing source
        # cannot select a receiving branch from geometry alone.
        g=build_graph(network([[(-2,-2,0),(2,2,0),(-2,2,0),(2,-2,0)],
                               [(0,0,0),(0,-3,0)]]),metric='distance')
        self.assertEqual(len(g.edges),2)
        self.assertTrue(any(r['kind']=='ambiguous_interior_projection' for r in g.physical.review))

    def test_exactly_outside_height_and_horizontal_limits(self):
        outside_h = float(np.nextafter(.10,np.inf))
        outside_z = float(np.nextafter(.025,np.inf))
        for dx,dz in [(outside_h,0),(0,outside_z)]:
            g=build_graph(network([[(-2,0,0),(0,0,0)],[(dx,0,dz),(2,0,dz)]]),metric='distance')
            self.assertFalse(np.isfinite(g.costs_from(node_at(g,(-2,0,0)))[node_at(g,(2,0,dz))]))

    def test_multiple_incident_paths_are_one_valid_junction(self):
        g=build_graph(network([[(-2,0,0),(0,0,0)],[(0,0,0),(2,0,0)],[(0,.05,.01),(0,2,.01)]]))
        self.assertEqual(g.nodes.member_count.max(),3)
        self.assertFalse(any(r['kind']=='ambiguous_cluster' for r in g.physical.review))


class RoutingTests(unittest.TestCase):
    def test_lift_split_once_and_three_consecutive_identities(self):
        n=network([([(0,0,0),(0,0,10)],{'id':100,'kind':'Lift'}),
                   [(-2,0,5),(0,0,5)],[(0,0,10),(2,0,10)]])
        g=build_graph(n)
        self.assertEqual(len(g.edges.loc[g.edges.source_id=='100']),2)
        self.assertAlmostEqual(g.costs_from(node_at(g,(0,0,0)))[node_at(g,(0,0,10))],30)
        distance=routing_graph(g.physical,metric='distance')
        self.assertEqual(distance.costs_from(node_at(g,(0,0,0)))[node_at(g,(0,0,10))],0)
        n=network([([(0,0,i*5),(0,0,(i+1)*5)],{'kind':'Lift'}) for i in range(3)])
        g=build_graph(n)
        self.assertAlmostEqual(g.costs_from(node_at(g,(0,0,0)))[node_at(g,(0,0,15))],90)

    def test_leaving_lift_resets_identity_and_reentry_costs_30(self):
        n=network([([(0,0,0),(0,0,10)],{'id':100,'kind':'Lift'}),
                   ([(0,0,5),(2,0,5),(0,0,5)],{'id':200})])
        g=build_graph(n)
        # Inspect actual transition chain: A(None)->B(100)->B(None)->A(100).
        a,b=node_at(g,(0,0,0)),node_at(g,(0,0,5))
        lookup={(r.node_index,None if pd.isna(r.lift_id) else str(r.lift_id)):r.state_index for r in g.states.itertuples()}
        chain=[lookup[(a,None)],lookup[(b,'100')],lookup[(b,None)],lookup[(a,'100')]]
        weights=[g.matrix[x,y] for x,y in zip(chain,chain[1:])]
        self.assertEqual(weights[0],30)
        self.assertEqual(weights[-1],30)
        self.assertAlmostEqual(sum(weights),60+tobler_seconds(4,0))

    def test_modes_disabled_unknown_codes_and_extreme_distance_preserved(self):
        n=network([([(0,0,0),(2,0,0)],{'kind':'Staircase'}),
                   ([(2,0,0),(4,0,0)],{'enabled':False}),
                   ([(4,0,0),(6,0,0)],{'barrier':True}),
                   ([(6,0,0),(8,0,0)],{'kind':'Stairlift'}),
                   ([(8,0,0),(10,0,0)],{'direction':9}),
                   ([(10,0,0),(12,0,1)],{'gradient':math.pi/2}),
                   ([(12,0,1),(14,0,2)],{'gradient':.1}),
                   ([(14,0,2),(14,0,4)],{})])
        physical=build_physical_graph(n)
        self.assertEqual(physical.sources.allow_general.tolist(),[True,False,True,False,False,True,True,True])
        self.assertEqual(physical.sources.allow_wheelchair.tolist(),[False,False,False,True,False,True,True,True])
        general=routing_graph(physical); wheelchair=routing_graph(physical,True)
        edge=physical.edges.loc[physical.edges.source_id=='7'].iloc[0]
        gt=general.transitions.loc[general.transitions.edge_index==edge.edge_index]
        wt=wheelchair.transitions.loc[wheelchair.transitions.edge_index==edge.edge_index]
        self.assertEqual(sorted(gt.cost),sorted(wt.cost))
        self.assertEqual(general.transitions.loc[general.transitions.source_id=='6'].shape[0],0)
        self.assertEqual(routing_graph(physical,metric='distance').transitions.loc[lambda x:x.source_id=='6'].shape[0],2)
        self.assertIn('unsupported_direction_code',physical.sources.general_exclusion.iloc[4])

    def test_minimum_parallel_matrix_and_explicit_zeros(self):
        matrix,mapping=minimum_matrix([(0,1,7.,0,1,'one'),(0,1,2.,1,1,'two'),(1,2,0.,2,1,'zero')],3)
        self.assertEqual(matrix.nnz,2)
        self.assertEqual(matrix[0,1],2)
        self.assertEqual(mapping.source_id.tolist(),['two','zero'])
        self.assertEqual(dijkstra(matrix,indices=0)[2],2)

    def test_saved_graph_roundtrip(self):
        p=build_physical_graph(network([([(0,0,0),(0,0,10)],{'kind':'Lift'}),
                                        [(0,0,5),(2,0,5)],[(2,0,5),(3,0,6)]]))
        with tempfile.TemporaryDirectory() as tmp:
            save_physical(tmp,p)
            for wheelchair in (False,True):
                for metric in ('distance','time'):
                    g=routing_graph(p,wheelchair,metric)
                    save_routing(tmp,g)
                    r=read_graph(tmp,wheelchair,metric)
                    for field in ('nodes','edges','sources'):
                        x=getattr(p,field); y=getattr(r.physical,field)
                        self.assertTrue(np.array_equal(shapely.to_wkb(x.geometry),shapely.to_wkb(y.geometry)))
                        assert_frame_equal(x.drop(columns='geometry'),y.drop(columns='geometry'),check_exact=True)
                    self.assertTrue(np.array_equal(g.matrix.data,r.matrix.data))
                    self.assertTrue(np.array_equal(g.costs_from(0),r.costs_from(0)))
                    self.assertEqual(r.nodes.attrs['vertical_crs'],'EPSG:5738')

    def test_failed_build_and_failed_publication_preserve_current(self):
        from estate_ranking.step_2 import publish_run, run
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=root/'runs/old'; old.mkdir(parents=True)
            (old/'SUCCESS.json').write_text('{"validation":"passed"}')
            current=root/'current'; current.symlink_to('runs/old')
            new=root/'runs/new'; new.mkdir()
            (new/'SUCCESS.json').write_text('{"validation":"passed"}')
            with patch('estate_ranking.step_2.os.replace',side_effect=OSError('publication failed')):
                with self.assertRaisesRegex(OSError,'publication failed'):
                    publish_run(new,current)
            self.assertEqual(current.resolve(),old.resolve())
            with patch('estate_ranking.step_2.freeze_input',side_effect=ValueError('invalid frozen input')):
                self.assertEqual(run(root/'missing',root),1)
            self.assertEqual(current.resolve(),old.resolve())
            self.assertEqual(list(root.glob('.current-*')),[])

    def test_unknown_required_codes_have_explicit_source_diagnostics(self):
        p=build_physical_graph(network([([(0,0,0),(2,0,0)],{'kind':'Unknown'}),
                                       ([(3,0,0),(5,0,0)],{'enabled':None}),
                                       ([(6,0,0),(8,0,0)],{'barrier':None})]))
        self.assertIn('unsupported_feature_type',p.sources.general_exclusion.iloc[0])
        self.assertIn('unsupported_enabled_code',p.sources.general_exclusion.iloc[1])
        self.assertIn('unsupported_wheelchair_barrier_code',p.sources.wheelchair_exclusion.iloc[2])
        self.assertEqual(set(p.edges.source_id),{'3'})

    def test_evidence_json_arrays_roundtrip_and_corruption_detected(self):
        from estate_ranking.step_2 import verify_evidence
        expected=[{'members':[('123',.5)],'height':2.0}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'review.jsonl'
            path.write_text(json.dumps(expected[0])+'\n')
            self.assertEqual(verify_evidence(tmp,'review',iter(expected)),1)
            path.write_text('{"members":[["wrong",0.5]],"height":2.0}\n')
            with self.assertRaisesRegex(AssertionError,'Evidence changed'):
                verify_evidence(tmp,'review',iter(expected))

    def test_second_sampling_round_can_find_nonflat_detail(self):
        p=build_profile('round-two',[(0,0,0),(10,0,0)],.1)
        first=[s['xyz'][0] for s in p.samples if s['round']==1]
        target=next(s['xyz'][0] for s in p.samples if s['round']==2)
        radius=min([abs(target-x) for x in first]+[target,10-target])*.1
        q=build_profile('round-two',[(0,0,0),(target-radius,0,0),
                        (target,0,1e-8),(target+radius,0,0),(10,0,0)],.1)
        self.assertEqual(q.rounds,2)
        self.assertEqual(q.classification,'sampled_nonflat')
        self.assertEqual(len(q.samples),8)
        self.assertTrue(any(a>0 for a in q.signed_angles))
        self.assertTrue(any(a<0 for a in q.signed_angles))

    def test_canonical_site_selection_preserves_versions(self):
        rows=[{'SiteID':1503020249,'LastAmendmentDate':'2022/06/06 00:00:00','record_id':'old'},
              {'SiteID':1503020249,'LastAmendmentDate':'2026/07/13 00:00:00','record_id':'new'}]
        raw=Table.from_rows('PedRouteRelSitePoly',rows)
        selected=canonical_sites([raw],load_policy(WORK/'config/routing_policy.json'),ValidationReport())
        self.assertEqual(selected.value('record_id',0),'new')
        self.assertEqual(len(raw),2)


if __name__=='__main__':
    unittest.main()
