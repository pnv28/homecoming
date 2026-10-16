"""Scoring semantics, spatial roundtrips and frozen-cache publication boundaries."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from shapely.geometry import Point

from estate_ranking.export import write_json
from estate_ranking.step_4 import _opened
from estate_ranking.step_5 import (scoring_policy, _score, _options, _write_views, _read_view,
                                  rank_estates, read_rankings, run)
from test_step_4 import fixture, compute, saved


def costs(rows, names=None, categories=None):
    records = []
    for i, values in enumerate(rows):
        row = dict(id='estate:' + str(i), name='Estate ' + str(i),
            name_en=(names or ['Estate ' + str(j) for j in range(len(rows))])[i],
            housing_district=(categories or ['Urban'] * len(rows))[i],
            requested_hospital_id=None, geometry=Point(i, 0))
        for name, column, unit, value in zip(('bus','mtr','hospital'),
                ('bus_time_s','mtr_time_s','hospital_distance_m'), ('seconds','seconds','metres'), values):
            row.update({column:value, name+'_status':'ok' if value is not None else 'unreachable',
                name+'_unit':unit, name+'_reason':'' if value is not None else 'no_directed_path',
                name+'_target_ids':[name+':a',name+':b'] if value is not None else [],
                name+'_warnings':['level_uncertain']})
        records.append(row)
    frame=gpd.GeoDataFrame(records,crs=2326)
    frame.attrs.update(mode='general',scenario='primary',hospital_cache='shared_general_distance')
    return frame


def source_cache(root):
    physical, attached, graphs = fixture(paths=[[(0,0,0),(10,0,0)],[(0,100,0),(10,100,0)]],
        coords={'estate':[(0,0),(5,0)], 'hospital':[(10,0),(10,100)],
                'bus_stop':[(10,0)], 'mtr_access':[(10,0)]})
    attached.entities['estate']['housing_district']=['Urban','Islands']
    attached.entities['estate']['name_en']=['Estate A','Estate B']
    (root/'run').mkdir(parents=True)
    data=compute(attached,graphs,root/'run')
    return saved(root,physical,attached,graphs,data)


class ScoringTests(unittest.TestCase):
    def test_midpoints_monotonicity_zero_and_extreme_finite_costs(self):
        x=costs([(0,0,0),(300,450,2500),(600,900,5000),(1200,1800,10000),
                 (np.finfo(float).max,)*3])
        scored=_score(x,scoring_policy()).set_index('id')
        for name in ('bus','mtr','hospital'):
            values=scored.loc[x.id,name+'_scaled_cost'].to_numpy(dtype=float)
            np.testing.assert_allclose(values[:4],[0,100/3,50,200/3])
            self.assertTrue(np.all(np.diff(values)>=0))
            self.assertTrue(np.all((values>=0)&(values<=100)))
        self.assertEqual(scored.loc['estate:4','bus_time_s'],np.finfo(float).max)

    def test_weights_normalisation_rejections_and_zero_weight_missing_component(self):
        p=scoring_policy(dict(bus=2,mtr=1,hospital=1))
        self.assertEqual(p['normalised_weights'],dict(bus=.5,mtr=.25,hospital=.25))
        self.assertEqual(scoring_policy(dict(bus=1e308,mtr=1e308,hospital=1e308))['normalised_weights'],
                         scoring_policy()['normalised_weights'])
        source=costs([(600,900,None)])
        scored=_score(source,scoring_policy(dict(bus=1,mtr=1,hospital=0)))
        self.assertEqual(scored.final_cost.iloc[0],50.)
        self.assertEqual(scored.required_component_count.iloc[0],2)
        self.assertEqual(scored.missing_components.iloc[0],[])
        self.assertTrue(pd.isna(scored.hospital_scaled_cost.iloc[0]))
        bad=[{},dict(bus=0,mtr=0,hospital=0),dict(bus=True,mtr=1,hospital=1),
             dict(bus=-1,mtr=1,hospital=1),dict(bus=np.inf,mtr=1,hospital=1),
             dict(bus=np.nan,mtr=1,hospital=1),dict(bus='1',mtr=1,hospital=1),
             dict(bus=1,mtr=1,hospital=1,other=1)]
        for weights in bad:
            with self.subTest(weights=weights), self.assertRaises(ValueError):scoring_policy(weights)

    def test_complete_first_incomplete_available_counts_name_and_id(self):
        source=costs([(1e20,1e20,1e20),(None,0,0),(0,None,None),
                      (None,None,None),(0,None,0),(None,0,0)],
                     names=['Last cost','zebra','Single','None','Alpha','Alpha'])
        scored=_score(source,scoring_policy())
        self.assertEqual(scored.id.tolist(),['estate:0','estate:4','estate:5','estate:1','estate:2','estate:3'])
        self.assertEqual(scored.available_required_component_count.tolist(),[3,2,2,2,1,0])
        self.assertTrue(scored.final_cost.iloc[1:].isna().all())
        self.assertTrue(scored['rank'].iloc[1:].isna().all())
        self.assertEqual(scored.missing_components.iloc[1],['mtr'])

    def test_competition_ties_full_precision_and_stable_names(self):
        p=scoring_policy(dict(bus=1,mtr=0,hospital=0))
        source=costs([(0,0,0),(600,0,0),(600,0,0),(1800,0,0)],names=['zero','Zebra','alpha','last'])
        scored=_score(source,p)
        self.assertEqual(scored.id.tolist(),['estate:0','estate:2','estate:1','estate:3'])
        self.assertEqual(scored['rank'].tolist(),[1,2,2,4])
        near=_score(costs([(600+1e-7,0,0),(600,0,0)]),p)
        self.assertEqual(near.id.tolist(),['estate:1','estate:0'])
        self.assertEqual(near['rank'].tolist(),[1,2])
        self.assertEqual(round(near.final_cost.iloc[0],2),round(near.final_cost.iloc[1],2))

    def test_category_filter_reranks_without_changing_costs_and_empty_schema(self):
        source=costs([(100,100,100),(200,200,200),(300,300,300)],
                     categories=['Urban','Islands','Islands'])
        policy=scoring_policy();all_rows=_score(source,policy)
        selected=_score(source,policy,'Islands')
        self.assertEqual(selected['rank'].tolist(),[1,2])
        for estate in selected.itertuples():
            self.assertEqual(estate.final_cost,all_rows.set_index('id').loc[estate.id,'final_cost'])
        empty=_score(source,policy,'New Territories')
        self.assertIsInstance(empty,gpd.GeoDataFrame);self.assertTrue(empty.empty)
        self.assertEqual(empty.dtypes.to_dict(),selected.dtypes.to_dict())

    def test_source_cost_errors_are_not_disguised_as_missing_routes(self):
        source=costs([(600,900,5000)])
        variants=[('bus_time_s',-1),('bus_time_s',np.inf),('bus_time_s',None),
                  ('bus_status','unreachable'),('bus_status','unknown'),('bus_unit','minutes'),
                  ('housing_district','invalid')]
        for column,value in variants:
            changed=source.copy();changed[column]=value
            with self.subTest(column=column,value=value),self.assertRaises(ValueError):
                _score(changed,scoring_policy())
        for kwargs in (dict(wheelchair='false'),dict(scenario='other'),dict(housing_district='bad'),dict(hospital_id=3)):
            with self.assertRaises(ValueError):_options(**kwargs)

    def test_preserves_source_nested_data_metadata_and_dtypes_in_geopackage(self):
        source=costs([(0,0,0),(None,900,5000),(600,900,5000)],names=['中文',None,'Last'])
        source['evidence']=[{'source':'中文'},None,{'source':'example'}]
        source['nullable_flag']=pd.array([True,None,False],dtype='boolean')
        source['nullable_int']=pd.array([1,None,3],dtype='Int64')
        expected=_score(source,scoring_policy())
        original=copy.deepcopy(source)
        with tempfile.TemporaryDirectory() as tmp:
            _write_views(Path(tmp),{'primary_general':expected})
            actual=_read_view(Path(tmp),'primary_general')
            assert_frame_equal(actual,expected,check_exact=True)
            self.assertEqual(actual.attrs,expected.attrs)
        assert_frame_equal(source,original,check_exact=True)
        self.assertEqual(actual.bus_target_ids.iloc[0],['bus:a','bus:b'])

    def test_returned_destination_and_warning_lists_cannot_mutate_source(self):
        source=costs([(600,900,5000)])
        result=_score(source,scoring_policy())
        result.bus_target_ids.iloc[0].append('caller-only')
        result.hospital_warnings.iloc[0].clear()
        self.assertEqual(source.bus_target_ids.iloc[0],['bus:a','bus:b'])
        self.assertEqual(source.hospital_warnings.iloc[0],['level_uncertain'])


class CacheTests(unittest.TestCase):
    def tearDown(self):
        _opened.cache_clear()

    def test_frozen_source_readers_hospital_selection_modes_and_no_dijkstra(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory,_=source_cache(root/'source')
            with patch('estate_ranking.step_4.dijkstra',side_effect=AssertionError('rerouting')), \
                 patch('scipy.sparse.csgraph.dijkstra',side_effect=AssertionError('rerouting')):
                shared=None
                for w in (False,True):
                    for scenario in ('primary','baseline'):
                        frame=rank_estates(wheelchair=w,scenario=scenario,step_4_directory=directory)
                        self.assertEqual(frame.attrs['mode'],'wheelchair' if w else 'general')
                        self.assertEqual(frame.attrs['scenario'],scenario)
                        current=frame.set_index('id').hospital_distance_m.sort_index()
                        if shared is not None:pd.testing.assert_series_equal(current,shared)
                        shared=current
                missing=rank_estates(hospital_id='hospital:1',step_4_directory=directory)
                self.assertTrue(missing.final_cost.isna().all())
                self.assertTrue(missing.hospital_target_ids.map(lambda x:x==[]).all())
                self.assertTrue(missing.requested_hospital_id.eq('hospital:1').all())
                self.assertEqual(missing.attrs['requested_hospital_id'],'hospital:1')
                filtered=rank_estates('Islands',step_4_directory=directory)
                self.assertEqual(filtered.id.tolist(),['estate:1']);self.assertEqual(filtered['rank'].iloc[0],1)
                with self.assertRaises(KeyError):rank_estates(hospital_id='unknown',step_4_directory=directory)

    def test_four_view_publication_readers_staleness_history_and_corrupt_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,pair=source_cache(root/'source');work=root/'work'
            selected=work/'precomputed/outputs/step_4/current';selected.parent.mkdir(parents=True)
            selected.symlink_to(source)
            registry=work/'precomputed/outputs/rebuild/current.json';registry.parent.mkdir(parents=True)
            write_json(registry,pair)
            with patch('estate_ranking.step_5.WORK',work),patch('estate_ranking.step_4.WORK',work), \
                 patch('estate_ranking.step_4.dijkstra',side_effect=AssertionError('rerouting')):
                target=run()
                self.assertEqual((work/'precomputed/outputs/step_5/current').resolve(),target.resolve())
                for w in (False,True):
                    for scenario in ('primary','baseline'):
                        actual=read_rankings(w,scenario)
                        expected=rank_estates(wheelchair=w,scenario=scenario)
                        assert_frame_equal(actual,expected,check_exact=True)
                        self.assertEqual(actual.attrs['step_4']['run_id'],source.name)
                archive=read_rankings(directory=target)
                duplicate=root/'different/run';duplicate.parent.mkdir();shutil.copytree(source,duplicate)
                selected.unlink();selected.symlink_to(duplicate)
                with self.assertRaisesRegex(ValueError,'incompatible'):read_rankings()
                assert_frame_equal(archive,read_rankings(directory=target),check_exact=True)
                gpkg=target/'rankings.gpkg';original=gpkg.read_bytes();gpkg.write_bytes(original+b' ')
                with self.assertRaisesRegex(ValueError,'hash mismatch'):read_rankings(directory=target)
                gpkg.write_bytes(original)
                manifest=source/'manifest.json';manifest.write_text(manifest.read_text()+' ')
                with self.assertRaisesRegex(ValueError,'Pinned Step 4'):read_rankings(directory=target)

    def test_failed_build_preserves_previous_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prior=root/'prior';prior.mkdir();output=root/'outputs';output.mkdir()
            (output/'current').symlink_to(prior)
            with patch('estate_ranking.step_5.WORK',root), \
                 patch('estate_ranking.step_5._freeze_source',side_effect=ValueError('bad source')):
                with self.assertRaisesRegex(ValueError,'bad source'):run(output)
            self.assertEqual((output/'current').resolve(),prior.resolve())
            self.assertEqual(len(list((root/'cache/step_5_staging').glob('*/FAILURE.json'))),1)


if __name__=='__main__':
    unittest.main()
