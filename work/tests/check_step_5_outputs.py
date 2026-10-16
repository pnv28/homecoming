"""Independent full-data acceptance for the selected Step 5 spatial rankings.

PYTHONPATH=work/src .venv/bin/python work/tests/check_step_5_outputs.py
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import time
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from estate_ranking.export import write_json
from estate_ranking.graph import WORK
from estate_ranking.ingest import read_json, sha256
from estate_ranking.step_3 import verify_hashes
from estate_ranking.step_4 import _reader, read_subcosts, read_hospital_costs
from estate_ranking.step_5 import rank_estates, read_rankings, CATEGORIES


def verify(frame, source, weights):
    assert isinstance(frame,gpd.GeoDataFrame) and frame.crs.to_epsg()==2326
    assert_frame_equal(frame.set_index('id')[source.columns.drop('id')].sort_index(),
                       source.set_index('id').sort_index(),check_exact=True)
    ordered=frame.set_index('id')
    refs={'bus':600.,'mtr':900.,'hospital':5000.}
    active=[k for k,v in weights.items() if v>0]
    for r in frame.itertuples():
        missing=[];values=[]
        for name in ('bus','mtr','hospital'):
            x=getattr(r,{'bus':'bus_time_s','mtr':'mtr_time_s','hospital':'hospital_distance_m'}[name])
            scaled=getattr(r,name+'_scaled_cost')
            if getattr(r,name+'_status')=='ok':
                assert scaled==100*(x/(x+refs[name]))
                if name in active:values.append(scaled*weights[name])
            else:
                assert pd.isna(scaled)
                if name in active:missing.append(name)
        assert r.missing_components==missing
        assert r.available_required_component_count==len(active)-len(missing)
        if missing:
            assert r.ranking_status=='incomplete' and pd.isna(r.final_cost) and pd.isna(r.rank)
        else:
            assert r.ranking_status=='complete'
            assert math.isclose(r.final_cost,math.fsum(values)/sum(weights.values()),abs_tol=3e-14)
    complete=frame.loc[frame.ranking_status=='complete']
    assert complete.final_cost.is_monotonic_increasing
    assert frame.ranking_status.tolist()==['complete']*len(complete)+['incomplete']*(len(frame)-len(complete))
    incomplete=frame.iloc[len(complete):]
    assert incomplete.available_required_component_count.is_monotonic_decreasing
    costs=sorted(complete.final_cost.tolist())
    for row in complete.itertuples():assert row.rank==costs.index(row.final_cost)+1
    return dict(rows=len(frame),complete=len(complete),incomplete=len(incomplete))


def main():
    start=time.perf_counter();cache=_reader();directory=(WORK/'precomputed/outputs/step_5/current').resolve()
    manifest=read_json(directory/'manifest.json');upstream_signature=sha256(cache.directory/'manifest.json')
    for name,expected in manifest['implementation_sha256'].items():
        assert sha256(WORK/'src/estate_ranking'/name)==expected
    views={};categories={}
    with patch('estate_ranking.step_4.dijkstra',side_effect=AssertionError('routing during scoring')), \
         patch('estate_ranking.graph.dijkstra',side_effect=AssertionError('routing during scoring')), \
         patch('scipy.sparse.csgraph.dijkstra',side_effect=AssertionError('routing during scoring')):
        shared=None
        for scenario in ('primary','baseline'):
            for wheelchair in (False,True):
                key=scenario+('_wheelchair' if wheelchair else '_general')
                frame=read_rankings(wheelchair,scenario)
                source=read_subcosts(wheelchair,scenario=scenario,directory=cache.directory)
                assert len(frame)==244
                views[key]=verify(frame,source,dict(bus=1,mtr=1,hospital=1))
                calculated=rank_estates(wheelchair=wheelchair,scenario=scenario)
                assert_frame_equal(frame,calculated,check_exact=True)
                hospital=frame.set_index('id')[['hospital_distance_m','hospital_scaled_cost']].sort_index()
                if shared is not None:assert_frame_equal(hospital,shared,check_exact=True)
                shared=hospital
                kam=frame.loc[frame.id=='estate:cc88f4db68af5ef0b835baab84f1ffa8'].iloc[0]
                assert kam.hospital_status=='unreachable' and kam.ranking_status=='incomplete'
                for estate,distance in [('estate:c0a7aefd158a53aeacd784838953ae98',1842.0140739372866),
                                        ('estate:c894f8d28dea57d3aabcc17426d25ad0',2457.1474756251673)]:
                    assert frame.set_index('id').loc[estate,'hospital_distance_m']==distance
                categories[key]={}
                for category in CATEGORIES:
                    selected=rank_estates(category,wheelchair=wheelchair,scenario=scenario)
                    selected_source=source.loc[source.housing_district==category]
                    verify(selected,selected_source,dict(bus=1,mtr=1,hospital=1))
                    assert selected.set_index('id').final_cost.equals(
                        frame.set_index('id').final_cost.reindex(selected.id))
                    categories[key][category]=len(selected)
        pairs=read_hospital_costs(cache.directory)
        hospital_ids=sorted(pairs.target_id.unique())
        assert len(hospital_ids)==44
        for hospital_id in hospital_ids:
            chosen=rank_estates(hospital_id=hospital_id)
            source=read_subcosts(hospital_id=hospital_id,directory=cache.directory)
            verify(chosen,source,dict(bus=1,mtr=1,hospital=1))
            assert chosen.requested_hospital_id.eq(hospital_id).all()
        profiles=[dict(bus=2,mtr=1,hospital=1),dict(bus=1,mtr=1,hospital=0),
                  dict(bus=0,mtr=0,hospital=1),dict(bus=1e308,mtr=1e308,hospital=1e308)]
        source=read_subcosts(directory=cache.directory)
        for weights in profiles:
            frame=rank_estates(weights=weights)
            # Rescale for independent math.fsum without overflowing large weights.
            scaled={k:v/max(weights.values()) for k,v in weights.items()}
            verify(frame,source,scaled)
    assert sha256(cache.directory/'manifest.json')==upstream_signature
    verify_hashes(cache.directory,cache.manifest['artifacts'])
    for item in cache.frozen.values():
        if isinstance(item,dict) and 'manifest_sha256' in item:
            upstream=WORK/item['directory'];assert sha256(upstream/'manifest.json')==item['manifest_sha256']
            verify_hashes(upstream,read_json(upstream/'manifest.json')['artifacts'])
    with sqlite3.connect('file:'+str(directory/'rankings.gpkg')+'?mode=ro',uri=True) as connection:
        assert connection.execute('pragma integrity_check').fetchone()==('ok',)
    report=dict(status='passed',run_id=directory.name,completed_utc=datetime.now(timezone.utc).isoformat(),
        dijkstra_disabled=True,views=views,category_counts=categories,selected_hospitals_checked=len(hospital_ids),
        additional_weight_profiles=len(profiles),raw_subcosts_and_geometry_exact=True,
        step_4_and_graph_artifacts_unchanged=True,kam_peng_incomplete=True,
        amended_hospital_distances_preserved=True,gpkg_integrity='ok',runtime_seconds=time.perf_counter()-start)
    write_json(WORK/'precomputed/docs/step_5_reader_acceptance.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
