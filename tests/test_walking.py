"""The sparse endpoint adapter must match the original complete compilation."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import geopandas as gpd
import numpy as np
from shapely.geometry import MultiLineString,Point
from estate_ranking.graph import build_physical_graph
from estate_ranking.attachments import attach_points,attached_routing_graph
from homecoming.services.coordinate import find_route as reference_route
from homecoming.services.fast_coordinate import find_route
from homecoming.services.profiles import verified_profiles,same_evidence
from estate_ranking.graph_costs import build_profile


def saved_graph(paths,wheelchair=False):
    rows=[]
    for i,item in enumerate(paths):
        options=item[1] if isinstance(item,tuple) else {}
        coords=item[0] if isinstance(item,tuple) else item
        rows.append(dict(PedestrianRouteID=options.get('id',i+1),
            FeatureType_label=options.get('kind','Footway'),Direction=options.get('direction',0),
            Enabled_bool=True,WheelchairBarrier_bool=False,Gradient=options.get('gradient',0.),
            FloorID=None,BuildingID_1=None,BuildingID_2=None,geometry=MultiLineString([coords])))
    physical=build_physical_graph(gpd.GeoDataFrame(rows,crs=2326),audit_crossings=False)
    estates=gpd.GeoDataFrame([dict(id='estate:test',geometry=Point(-1,-1))],crs=2326)
    destinations=gpd.GeoDataFrame([dict(id='mtr:test',general_mode_candidate=True,wheelchair_mode_candidate=True,geometry=Point(11,1))],crs=2326)
    attached=attach_points(physical,{'estate':estates,'mtr_access':destinations})
    return attached_routing_graph(attached,wheelchair,'time')


class FastWalkingTests(unittest.TestCase):
    def test_native_roundoff_restores_exact_frozen_costs(self):
        physical=saved_graph([[(0,0,0),(10,0,0)]]).physical
        frozen=physical.profiles[0].evidence()
        sid=frozen['source_id']
        def different_libm(*args,**kwargs):
            profile=build_profile(*args,**kwargs)
            profile.forward[0]=float(np.nextafter(profile.forward[0],np.inf))
            return profile
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profiles.jsonl'
            path.write_text(json.dumps(frozen)+'\n')
            with patch('homecoming.services.profiles.build_profile',side_effect=different_libm):
                profiles=verified_profiles(physical,{sid},directory)
            self.assertEqual(profiles[0].evidence(),frozen)
            changed={**frozen,'forward_seconds':[frozen['forward_seconds'][0]+.01]}
            path.write_text(json.dumps(changed)+'\n')
            with self.assertRaisesRegex(ValueError,'does not match'):
                verified_profiles(physical,{sid},directory)
        self.assertFalse(same_evidence({'cost':None},{'cost':0.}))
        self.assertFalse(same_evidence({'status':'unavailable'},{'status':'available'}))
        self.assertFalse(same_evidence({'seed':1},{'seed':2}))

    def compare(self,graph,start,end):
        original_edges=len(graph.edges)
        expected,_,_=reference_route(graph.physical,start,end,graph.wheelchair)
        # A runtime search must not recompile the whole pedestrian graph.
        with patch('estate_ranking.graph.routing_graph',side_effect=AssertionError('whole graph rebuild')):
            actual,route,_=find_route(graph,start,end,None)
        self.assertEqual(actual['status'],expected['status'])
        if actual['status']=='ok':
            self.assertAlmostEqual(actual['time_s'],expected['time_s'],places=9)
            self.assertAlmostEqual(actual['distance_m'],expected['distance_m'],places=9)
            self.assertAlmostEqual(route.time_s.sum(),actual['time_s'])
        self.assertEqual(len(graph.edges),original_edges)
        return actual,route

    def test_interior_positions_and_shared_attachment(self):
        graph=saved_graph([[(0,0,0),(10,0,0)]])
        self.compare(graph,Point(2,1),Point(8,2))
        self.compare(graph,Point(2,0),Point(2,1))

    def test_directed_forward_and_unreachable_reverse(self):
        graph=saved_graph([([(0,0,0),(10,0,0)],{'direction':1})])
        actual,_=self.compare(graph,Point(2,1),Point(8,1))
        self.assertEqual(actual['status'],'ok')
        actual,_=self.compare(graph,Point(8,1),Point(2,1))
        self.assertEqual(actual['status'],'unreachable')

    def test_lift_identity_continuation(self):
        graph=saved_graph([[(-1,0,0),(0,0,0)],
            ([(0,0,0),(0,0,5),(0,0,10)],{'kind':'Lift','id':20}),
            [(0,0,5),(.2,0,5)],[(0,0,10),(1,0,10)]])
        _,route=self.compare(graph,Point(-.8,0),Point(.8,0))
        self.assertEqual(route.loc[route.lift_id.notna(),'time_s'].tolist(),[30.,0.])

    def test_wheelchair_barrier_and_zero_length(self):
        paths=[[(0,0,0),(1,0,0)], ([(1,0,0),(2,0,1)],{'kind':'Staircase'}),[(2,0,1),(3,0,1)]]
        for wheelchair in (False,True):
            graph=saved_graph(paths,wheelchair)
            actual,_=self.compare(graph,Point(0,0),Point(3,0))
            self.assertEqual(actual['status'],'unreachable' if wheelchair else 'ok')
        actual,route,_=find_route(graph,Point(1,1),Point(1,1),None)
        self.assertEqual(actual['time_s'],0.)
        self.assertTrue(route.empty)

    def test_connector_limit(self):
        graph=saved_graph([[(0,0,0),(10,0,0)]])
        actual,_,_=find_route(graph,Point(2,0),Point(500,500),None)
        self.assertEqual(actual['status'],'unattached')


if __name__=='__main__':unittest.main()
