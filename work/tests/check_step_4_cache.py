"""Full-data public-reader acceptance; run after building the selected Step 4 cache.

PYTHONPATH=work/src .venv/bin/python work/tests/check_step_4_cache.py
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from estate_ranking.export import write_json
from estate_ranking.graph import WORK
from estate_ranking.graph_regressions import check_lift_connections
from estate_ranking.graph_cluster_audit import check_repaired_endpoint_cluster
from estate_ranking.ingest import read_json, sha256
from estate_ranking.routes import check_cost
from estate_ranking.step_4 import (_reader, read_subcosts, read_hospital_costs,
    read_transport_comparisons, read_route)


def main():
    start = time.perf_counter()
    cache = _reader()
    directory = cache.directory
    for name, expected in cache.manifest['implementation_sha256'].items():
        if sha256(WORK / 'src/estate_ranking' / name) != expected:
            raise AssertionError('Selected cache does not use the checked implementation: ' + name)
    groups = cache.data['groups']
    lookup = {(g['mode'],g['scenario'],g['estate_id'],g['group']):g for g in groups}
    routes = cache.data['routes']
    report = read_json(directory/'validation_report.json')
    assert report['connector_warnings'] == dict(Counter(
        w for r in routes for a in r['attachments'] for w in a['warnings']))
    selected = set()
    for key in {r['graph'] for r in routes}:
        rows = [r for r in routes if r['graph'] == key]
        selected.add(next(r['route_id'] for r in rows if r['status']=='ok'))
        selected.update(r['route_id'] for r in rows if r['uses_estimated_time'] or
                        r.get('origin_override') or
                        any('connector_above_threshold' in a['warnings'] for a in r['attachments']))
        unavailable = next((r for r in rows if r['status']!='ok'),None)
        if unavailable:
            selected.add(unavailable['route_id'])
    for g in cache.data['group_comparisons']:
        if g['selected_paths_changed']:
            for scenario, targets in [('primary',g['primary_target_ids']),('baseline',g['baseline_target_ids'])]:
                key=g['mode']+'_time'+('_baseline' if scenario=='baseline' else '')
                selected.update(key+':'+g['estate_id']+':'+t for t in targets)
    selected.update(r['baseline_route_id'] for r in cache.data['target_comparisons'] if r['path_changed'])
    # Patching local aliases and SciPy catches any accidental rerouting.
    with patch('estate_ranking.step_4.dijkstra',side_effect=AssertionError('reader ran Dijkstra')), \
         patch('estate_ranking.graph.dijkstra',side_effect=AssertionError('reader ran Dijkstra')), \
         patch('scipy.sparse.csgraph.dijkstra',side_effect=AssertionError('reader ran Dijkstra')):
        hospital = read_hospital_costs()
        assert isinstance(hospital,gpd.GeoDataFrame) and len(hospital)==10736
        assert hospital.attrs['hospital_cache']=='shared_general_distance'
        shared = None
        for wheelchair in (False,True):
            mode = 'wheelchair' if wheelchair else 'general'
            group_comparison,target_comparison=read_transport_comparisons(wheelchair)
            assert isinstance(group_comparison,gpd.GeoDataFrame) and len(group_comparison)==488
            assert len(target_comparison)==sum(len(g['target_ids']) for g in groups if g['mode']==mode and g['scenario']=='primary')
            for scenario in ('primary','baseline'):
                frame=read_subcosts(wheelchair,scenario=scenario)
                assert isinstance(frame,gpd.GeoDataFrame) and len(frame)==244
                current=frame[['id','hospital_distance_m','hospital_target_ids','hospital_status']]
                if shared is None:
                    shared=current
                else:
                    pd.testing.assert_frame_equal(shared,current,check_exact=True)
                for estate in frame.itertuples():
                    for label,kind in [('bus','bus_stop'),('mtr','mtr_access')]:
                        expected=lookup[mode,scenario,estate.id,kind]
                        actual=getattr(estate,label+'_time_s')
                        assert (pd.isna(actual) if expected['cost'] is None else actual==expected['cost'])
                        assert getattr(estate,label+'_target_ids')==expected['target_ids']
                        assert getattr(estate,label+'_status')==expected['status']
                chosen=hospital.target_id.iloc[0]
                selected_hospital=read_subcosts(wheelchair,hospital_id=chosen,scenario=scenario)
                expected=hospital.loc[hospital.target_id==chosen].set_index('estate_id').cost.reindex(selected_hospital.id)
                assert np.array_equal(selected_hospital.hospital_distance_m.to_numpy(dtype=float),expected.to_numpy(dtype=float),equal_nan=True)
        checked=[]
        previous_key=None
        for rid in sorted(selected):
            row=cache.routes[rid]
            key=row['graph']
            if key!=previous_key:
                cache._graphs.clear()
                previous_key=key
            frame=read_route(row['estate_id'],row['target_id'],key.startswith('wheelchair'),
                'baseline' if key.endswith('baseline') else 'primary')
            assert frame.attrs['status']==row['status']
            if row['status']=='ok':
                check_cost(frame.cost,row['cost'])
                network=frame.loc[frame.kind=='network']
                assert network.geometry.has_z.all()
                assert not frame.loc[frame.kind!='network'].geometry.dropna().has_z.any()
                assert bool(frame.uses_estimated_time.any())==row['uses_estimated_time']
                if key=='general_distance':
                    assert frame.time_s.isna().all()
                    assert frame.unit.eq('metres').all()
            else:
                assert frame.empty and frame.attrs['reason']
            checked.append(dict(route_id=rid,status=row['status'],sections=len(frame)))
    # Reopen every published spatial table and compare its authoritative costs/geometry.
    spatial={}
    for layer,key in [('hospital_costs',None),('transport_groups','groups'),
                      ('group_comparisons','group_comparisons'),('target_comparisons','target_comparisons')]:
        frame=gpd.read_file(directory/'results.gpkg',layer=layer,engine='pyogrio')
        records=[r for r in routes if r['graph']=='general_distance'] if key is None else cache.data[key]
        assert len(frame)==len(records)
        for column in ['cost'] if key in (None,'groups') else ['primary_cost','baseline_cost']:
            actual=frame[column].to_numpy(dtype=float)
            expected=np.array([np.nan if r[column] is None else r[column] for r in records],dtype=float)
            assert np.array_equal(actual,expected,equal_nan=True)
        expected_geometry=frame.estate_id.map(cache.estates.set_index('id').geometry)
        assert np.array_equal(shapely.to_wkb(frame.geometry),shapely.to_wkb(expected_geometry))
        spatial[layer]=len(frame)
    regressions={}
    for key in ('general_time','general_time_baseline','wheelchair_time','wheelchair_time_baseline','general_distance'):
        cache._graphs.clear()
        graph=cache.graph(key)
        regressions[key]={'endpoint_cluster':check_repaired_endpoint_cluster(graph)}
        if key!='general_distance':
            regressions[key]['lifts']=check_lift_connections(graph)
    report=dict(status='passed',run_id=directory.name,completed_utc=datetime.now(timezone.utc).isoformat(),
        dijkstra_disabled=True,subcost_mode_scenarios_checked=4,estates_per_view=244,
        hospital_pairs=len(hospital),group_statuses=dict(Counter(g['mode']+'/'+g['scenario']+'/'+g['status'] for g in groups)),
        shared_hospital_results_identical=True,selected_hospital_modes_identical=True,
        spatial_roundtrip_rows=spatial,route_reader_samples=checked,upstream_regressions=regressions,
        runtime_seconds=time.perf_counter()-start,stored_bytes=sum(p.stat().st_size for p in directory.iterdir()))
    write_json(WORK/'precomputed/docs/step_4_reader_acceptance.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('route_reader_samples','upstream_regressions')},indent=2))


if __name__=='__main__':main()
