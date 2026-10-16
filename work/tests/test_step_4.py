"""Step 4 ties, scenarios, cached reconstruction, and publication boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from estate_ranking.attachments import attach_points, attached_routing_graph, save_attached, save_attached_routing
from estate_ranking.export import write_json
from estate_ranking.graph import save_physical
from estate_ranking.ingest import sha256
from estate_ranking.routes import predecessor_states, ordered_sections, path_transitions
from estate_ranking.step_4 import (SearchCache, JourneyCache, calculate, comparisons, winners,
    validate_saved, read_route, read_subcosts, read_hospital_costs, read_transport_comparisons, run, _opened)
from estate_ranking.time_fallback import routing_prefix
from test_time_fallback import reviewed
from test_step_3 import points


def fixture(paths=None, coords=None):
    paths = paths or [[(0,0,0),(10,0,0)]]
    graph, _ = reviewed(paths)
    coords = coords or {'estate': [(0,0)], 'hospital': [(10,0)],
                       'bus_stop': [(10,0),(10,0)], 'mtr_access': [(10,0),(10,0)]}
    attached = attach_points(graph, {k: points(k, v) for k, v in coords.items()})
    graphs = {routing_prefix(w, metric, s): attached_routing_graph(attached, w, metric, s)
        for w in (False, True) for metric, s in [('time','primary'), ('time','baseline'), ('distance','primary')]}
    return graph, attached, graphs


def compute(attached, graphs, directory):
    return calculate(attached, lambda w,m,s: graphs[routing_prefix(w,m,s)], directory, progress=lambda *a, **kw: None)


def saved(root, physical, attached, graphs, data):
    upstream2, upstream3 = root/'upstream2', root/'upstream3'
    save_physical(upstream2, physical)
    save_attached(upstream3, attached, upstream2)
    for graph in graphs.values():
        save_attached_routing(upstream3, graph)
    pair = {'status':'passed', 'pair_id':'fixture'}
    for key, directory in [('step_2',upstream2),('step_3',upstream3)]:
        write_json(directory/'manifest.json', {'artifacts':{}})
        pair[key] = dict(directory=str(directory), run_id=directory.name, manifest_sha256=sha256(directory/'manifest.json'))
    directory = root/'run'
    write_json(directory/'results.json', data)
    attached.entities['estate'].to_file(directory/'results.gpkg', layer='estates', engine='pyogrio')
    write_json(directory/'SUCCESS.json', dict(run_id='run', validation='passed'))
    write_json(directory/'manifest.json', dict(run_id='run', frozen_pair=pair,
        artifacts={p.name: {'sha256':sha256(p)} for p in directory.iterdir()}))
    return directory, pair


class Step4Tests(unittest.TestCase):
    def test_exact_ties_zero_cost_and_ineligible_targets(self):
        _, attached, graphs = fixture(coords={'estate':[(5,0)], 'hospital':[(5,0)],
            'bus_stop':[(5,0),(5,0),(6,0)], 'mtr_access':[(5,0),(5,0)]})
        with tempfile.TemporaryDirectory() as tmp:
            data = compute(attached, graphs, tmp)
            for row in data['groups']:
                self.assertEqual(row['cost'], 0.)
                self.assertEqual(len(row['target_ids']), 2)
            self.assertFalse(any(r['cost_changed'] or r['selected_paths_changed'] or r['attachment_changed'] for r in data['group_comparisons']))
            # Equality must use no epsilon or rounding.
            terminal = graphs['general_time'].terminals
            costs = np.full(len(graphs['general_time'].states), np.inf)
            states = terminal.loc[terminal.entity_type=='bus_stop','state_index'].to_numpy()
            costs[states] = [1., np.nextafter(1.,2.), 2.]
            value, ids = winners(costs, terminal, 'bus_stop')
            self.assertEqual(ids, ['bus_stop:0'])
            self.assertEqual(value,1.)

    def test_winner_change_and_unavailable_same_target_are_retained(self):
        # Primary reaches the short upper branch through an estimated vertical;
        # baseline chooses the reachable lower branch instead.
        paths = [[(-10,0,0),(0,0,0)], [(0,0,0),(0,0,2)],
                 [(0,0,2),(10,0,2)], [(0,0,0),(0,-50,0),(10,-50,0)]]
        _, attached, graphs = fixture(paths, {'estate':[(-10,0)], 'hospital':[(10,0)],
             'bus_stop':[(10,0),(10,-50)], 'mtr_access':[(10,0),(10,-50)]})
        with tempfile.TemporaryDirectory() as tmp:
            data=compute(attached,graphs,tmp)
            self.assertTrue(all(r['winners_changed'] for r in data['group_comparisons']))
            self.assertTrue(all(r['baseline_status']=='unreachable' for r in data['target_comparisons']))
            primary=[r for r in data['routes'] if r['graph']=='general_time'][0]
            self.assertTrue(primary['uses_estimated_time'])
            self.assertEqual(primary['estimated_seconds'],12.)
            self.assertTrue(primary['fallback_review_ids'])
            self.assertIn('non_lift_vertical_without_horizontal_run',primary['original_failure_reasons'])
            report=validate_saved(tmp,data,graphs.__getitem__)
            self.assertEqual(report['missing_links'],0)
            # Winner and comparison purposes share one record when destinations coincide.
            for r in data['routes']:
                if r['graph']=='general_time_baseline' and r['target_id'].endswith(':1'):
                    self.assertEqual(r['purposes'],['winner'])

    def test_scenario_specific_positions_long_connectors_and_hospital_direction(self):
        paths=[([(0,0,0),(.008,0,2)],{'gradient':np.pi/2}), [(0,10,0),(10,10,0)],
               ([(.008,0,2),(0,10,0)],{'kind':'Lift','id':20})]
        _, attached, graphs=fixture(paths, {'estate':[(.004,0)], 'hospital':[(9,10)],
            'bus_stop':[(9,500)], 'mtr_access':[(9,10)]})
        with tempfile.TemporaryDirectory() as tmp:
            data=compute(attached,graphs,tmp)
            self.assertTrue(any(r['attachment_changed'] for r in data['target_comparisons']))
            self.assertTrue(any('connector_above_threshold' in r['warnings'] for r in data['routes']))
            for r in data['routes']:
                if r['graph'].endswith('baseline'):
                    self.assertFalse(r['uses_estimated_time'])
            report=validate_saved(tmp,data,graphs.__getitem__)
            self.assertEqual(report['hospital_forward_pairs_checked'],1)

    def test_reopen_all_public_readers_with_dijkstra_disabled(self):
        physical, attached, graphs=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'run').mkdir()
            data=compute(attached,graphs,root/'run')
            directory,pair=saved(root,physical,attached,graphs,data)
            with patch('estate_ranking.step_4.dijkstra', side_effect=AssertionError('rerouting')):
                for wheelchair in (False,True):
                    for scenario in ('primary','baseline'):
                        result=read_subcosts(wheelchair,scenario=scenario,directory=directory)
                        self.assertIsInstance(result,gpd.GeoDataFrame)
                        self.assertEqual(len(result),1)
                        route=read_route('estate:0','bus_stop:0',wheelchair,scenario,directory)
                        self.assertAlmostEqual(route.cost.sum(), result.bus_time_s.iloc[0])
                        self.assertTrue(route.loc[route.kind=='network'].geometry.has_z.all())
                        h=read_route('estate:0','hospital:0',wheelchair,scenario,directory)
                        self.assertEqual(h.attrs['graph'],'general_distance')
                        self.assertEqual(h.cost.sum(),10.)
                        self.assertTrue(h.time_s.isna().all())
                    group,target=read_transport_comparisons(wheelchair,directory)
                    self.assertEqual(len(group),2)
                    self.assertEqual(len(target),4)
                self.assertEqual(len(read_hospital_costs(directory)),1)
                with self.assertRaises(KeyError):read_subcosts(hospital_id='unknown',directory=directory)
                with self.assertRaises(KeyError):read_route('unknown','bus_stop:0',directory=directory)
                with self.assertRaises(KeyError):read_route('estate:0','unknown',directory=directory)
                with self.assertRaises(ValueError):read_subcosts(scenario='other',directory=directory)
                # Reopen defaults must detect a changed registry despite the cached object.
                fake=root/'work';registry=fake/'precomputed/outputs/rebuild';registry.mkdir(parents=True)
                current=fake/'precomputed/outputs/step_4/current';current.parent.mkdir(parents=True);current.symlink_to(directory)
                write_json(registry/'current.json',pair)
                with patch('estate_ranking.step_4.WORK',fake):
                    self.assertEqual(len(read_subcosts()),1)
                    write_json(registry/'current.json',{**pair,'pair_id':'changed'})
                    with self.assertRaises(ValueError):read_subcosts()
                    self.assertEqual(len(read_subcosts(directory=directory)),1)
            _opened.cache_clear()

    def test_uncached_target_errors_and_unavailable_route_has_status(self):
        physical,attached,graphs=fixture([[(-10,0,0),(0,0,0)],[(0,0,0),(0,0,2)],[(0,0,2),(10,0,2)]],
            {'estate':[(-10,0)],'hospital':[(10,0)],'bus_stop':[(10,0),(9,0)],'mtr_access':[(10,0)]})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'run').mkdir()
            data=compute(attached,graphs,root/'run')
            directory,_=saved(root,physical,attached,graphs,data)
            primary=next(g for g in data['groups'] if g['mode']=='general' and g['scenario']=='primary' and g['group']=='bus_stop')
            target=primary['target_ids'][0]
            route=read_route('estate:0',target,scenario='baseline',directory=directory)
            self.assertTrue(route.empty)
            self.assertEqual(route.attrs['status'],'unreachable')
            other=({'bus_stop:0','bus_stop:1'}-set(primary['target_ids'])).pop()
            with self.assertRaisesRegex(KeyError,'not cached'):
                read_route('estate:0',other,directory=directory)
            _opened.cache_clear()

    def test_corrupt_links_cycles_and_missing_comparison_branch(self):
        _,attached,graphs=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            data=compute(attached,graphs,tmp)
            cache=JourneyCache.__new__(JourneyCache)
            cache.directory=Path(tmp);cache._links={}
            cache.searches={s['search_id']:s for s in data['searches']}
            row=next(r for r in data['routes'] if r['graph']=='general_time_baseline')
            cache.indices(row)
            key=row['graph'];block=cache._links[key]['s0']
            endpoint=int(np.searchsorted(block[:,0],row['endpoint_state']))
            original=block[endpoint].copy()
            block[endpoint,1]=row['endpoint_state']
            with self.assertRaisesRegex(ValueError,'Cyclic'):cache.indices(row)
            block[endpoint]=original
            cache._links[key]['s0']=np.delete(block,endpoint,axis=0)
            with self.assertRaisesRegex(ValueError,'Missing'):cache.indices(row)
            with self.assertRaises(ValueError):predecessor_states(np.array([1,0]),2,0)

    def test_lift_charges_and_general_distance(self):
        paths=[[(-1,0,0),(0,0,0)], ([(0,0,0),(0,0,5),(0,0,10)],{'kind':'Lift','id':20}),
               [(0,0,5),(.2,0,5)],[(0,0,10),(1,0,10)]]
        _,attached,graphs=fixture(paths,{'estate':[(-1,0)],'hospital':[(1,0)],'bus_stop':[(1,0)],'mtr_access':[(1,0)]})
        with tempfile.TemporaryDirectory() as tmp:
            data=compute(attached,graphs,tmp)
            cache=JourneyCache.__new__(JourneyCache);cache.directory=Path(tmp);cache._links={}
            cache.searches={s['search_id']:s for s in data['searches']}
            r=next(r for r in data['routes'] if r['graph']=='general_time')
            route=ordered_sections(graphs['general_time'],cache.indices(r))
            self.assertEqual(route.loc[route.lift_id.notna(),'time_s'].tolist(),[30.,0.])
            h=next(r for r in data['routes'] if r['graph']=='general_distance')
            self.assertEqual(h['cost'],2.)
            report=validate_saved(tmp,data,graphs.__getitem__)
            self.assertGreater(report['all_reachable_paths_checked'],0)

    def test_reachable_baseline_comparison_branch_survives_pruning(self):
        paths=[[(-10,0,0),(0,0,0)],[(0,0,0),(0,0,2)],[(0,0,2),(10,0,2)],
               [(0,0,0),(0,-40,0),(10,-40,0)],
               ([(0,0,0),(0,100,1),(0,0,2)],{'gradient':.025})]
        _,attached,graphs=fixture(paths,{'estate':[(-10,0)],'hospital':[(10,0)],
            'bus_stop':[(10,0),(10,-40)],'mtr_access':[(10,0),(10,-40)]})
        with tempfile.TemporaryDirectory() as tmp:
            data=compute(attached,graphs,tmp)
            self.assertTrue(all(r['winners_changed'] for r in data['group_comparisons']))
            self.assertTrue(all(r['baseline_status']=='ok' and r['path_changed'] for r in data['target_comparisons']))
            comparison=next(r for r in data['routes'] if r['graph']=='general_time_baseline' and r['target_id']=='bus_stop:0')
            self.assertEqual(comparison['purposes'],['primary_winner_comparison'])
            self.assertGreater(comparison['cost'],next(r['cost'] for r in data['groups'] if r['mode']=='general' and r['scenario']=='baseline' and r['group']=='bus_stop'))
            validate_saved(tmp,data,graphs.__getitem__)
            cache=JourneyCache.__new__(JourneyCache);cache.directory=Path(tmp);cache._links={}
            cache.searches={r['search_id']:r for r in data['searches']}
            with patch('estate_ranking.step_4.dijkstra',side_effect=AssertionError('rerouting')):
                route=ordered_sections(graphs[comparison['graph']],cache.indices(comparison))
                self.assertAlmostEqual(route.cost.sum(),comparison['cost'])
                self.assertFalse(route.uses_estimated_time.any())

    def test_directed_hospital_and_mode_restrictions(self):
        paths=[[(-1,0,0),(0,0,0)], ([(0,0,0),(10,0,2)],{'kind':'Staircase','direction':1}),
               [(10,0,2),(11,0,2)]]
        _,attached,graphs=fixture(paths,{'estate':[(-1,0),(11,0)],'hospital':[(11,0),(-1,0)],
            'bus_stop':[(11,0)],'mtr_access':[(11,0)]})
        with tempfile.TemporaryDirectory() as tmp:
            data=compute(attached,graphs,tmp)
            hospitals={(r['estate_id'],r['target_id']):r for r in data['routes'] if r['graph']=='general_distance'}
            self.assertEqual(hospitals['estate:0','hospital:0']['cost'],12.)
            self.assertIsNone(hospitals['estate:1','hospital:1']['cost'])
            groups={(g['mode'],g['scenario'],g['estate_id'],g['group']):g for g in data['groups']}
            self.assertEqual(groups['general','primary','estate:0','bus_stop']['status'],'ok')
            self.assertEqual(groups['wheelchair','primary','estate:0','bus_stop']['status'],'unreachable')
            validate_saved(tmp,data,graphs.__getitem__)

    def test_excluded_targets_and_shared_hospital_ties(self):
        physical,attached,graphs=fixture(coords={'estate':[(0,0)],'hospital':[(10,0),(10,0)],
            'bus_stop':[(1,0),(10,0)],'mtr_access':[(10,0)]})
        # Rebuild selections with the nearer bus explicitly ineligible in both modes.
        entities=attached.entities.copy()
        entities['bus_stop']=points('bus_stop',[(1,0),(10,0)],[(False,False),(True,True)])
        attached=attach_points(physical,entities)
        graphs={routing_prefix(w,m,s):attached_routing_graph(attached,w,m,s) for w in (False,True)
                for m,s in [('time','primary'),('time','baseline'),('distance','primary')]}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'run').mkdir()
            data=compute(attached,graphs,root/'run')
            for g in data['groups']:
                if g['group']=='bus_stop':self.assertEqual(g['target_ids'],['bus_stop:1'])
            directory,_=saved(root,physical,attached,graphs,data)
            general=read_subcosts(directory=directory)
            wheelchair=read_subcosts(True,scenario='baseline',directory=directory)
            self.assertEqual(general.hospital_target_ids.iloc[0],['hospital:0','hospital:1'])
            self.assertEqual(general.hospital_distance_m.tolist(),wheelchair.hospital_distance_m.tolist())
            self.assertEqual(read_subcosts(hospital_id='hospital:1',directory=directory).hospital_target_ids.iloc[0],['hospital:1'])
            _opened.cache_clear()

    def test_estimated_label_uses_actual_directional_cost_status(self):
        _,attached,graphs=fixture()
        graph=graphs['general_time']
        # Physical review evidence may exist while this selected direction is healthy.
        graph.edges['uses_estimated_time']=True
        graph.edges['fallback_review_ids']='preserved-review-evidence'
        graph.edges['time_model_warning']='original_geometry_uncertain'
        cache=SearchCache(graph,'general_time')
        with tempfile.TemporaryDirectory() as tmp:
            _,rows=cache.retain_search('estate:0',lambda costs:[('estate:0','bus_stop:0',['winner'])])
            record=rows['estate:0','bus_stop:0']
            self.assertFalse(record['uses_estimated_time'])
            self.assertEqual(record['estimated_seconds'],0.)
            cache.save(tmp)
            reader=JourneyCache.__new__(JourneyCache);reader.directory=Path(tmp);reader._links={}
            reader.searches={s['search_id']:s for s in cache.searches}
            route=ordered_sections(graph,reader.indices(record))
            self.assertFalse(route.uses_estimated_time.any())
            self.assertTrue(route.loc[route.kind=='network','time_model'].eq('tobler').all())
            self.assertTrue(route.loc[route.kind=='network','fallback_review_ids'].eq('preserved-review-evidence').all())

    def test_changed_cache_artifact_and_frozen_reference_are_rejected(self):
        physical,attached,graphs=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'run').mkdir()
            data=compute(attached,graphs,root/'run')
            directory,pair=saved(root,physical,attached,graphs,data)
            JourneyCache(directory)
            original=(directory/'results.json').read_bytes()
            (directory/'results.json').write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):JourneyCache(directory)
            (directory/'results.json').write_bytes(original)
            upstream=Path(pair['step_3']['directory'])/'manifest.json'
            upstream.write_text(upstream.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'upstream manifest'):JourneyCache(directory)

    def test_failure_preserves_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);previous=root/'prior';previous.mkdir();output=root/'outputs';output.mkdir()
            (output/'current').symlink_to(previous)
            with patch('estate_ranking.step_4.WORK',root),patch('estate_ranking.step_4.freeze_pair',side_effect=ValueError('bad pair')):
                with self.assertRaises(ValueError):run(output)
            self.assertEqual((output/'current').resolve(),previous.resolve())
            self.assertEqual(len(list((root/'cache/step_4_staging').glob('*/FAILURE.json'))),1)


if __name__=='__main__':unittest.main()
