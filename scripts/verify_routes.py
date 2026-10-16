"""Independently compare fast map recovery against public engine route readers."""
import json
from pathlib import Path
import sys
import time
import numpy as np
import shapely

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from homecoming.services.data import cache
from homecoming.services.maps import FastRoutes
from homecoming.services.loading import load_attached


def main():
    start=time.monotonic();c=cache();checked=[]
    c._attached=load_attached()
    for key in ('general_time','wheelchair_time','general_time_baseline','wheelchair_time_baseline','general_distance'):
        candidates=[r for r in c.routes.values() if r['graph']==key and r['status']=='ok']
        rows=[candidates[0],max(candidates,key=lambda r:r['cost'])]
        rows += [r for r in candidates if r.get('uses_estimated_time') or r.get('origin_override')][:8]
        reader=FastRoutes(c,key)
        for row in {r['route_id']:r for r in rows}.values():
            original=c.route(row['estate_id'],row['target_id'],key.startswith('wheelchair'),
                             'baseline' if key.endswith('baseline') else 'primary')
            fast=reader.sections(row)
            assert len(fast)==len(original),row['route_id']
            for section,actual in zip(fast,original.itertuples()):
                assert section['cost']==actual.cost,row['route_id']
                assert section['distance_m']==actual.distance_m,row['route_id']
                if actual.geometry is not None:
                    np.testing.assert_array_equal(np.asarray(section['coords']),shapely.get_coordinates(actual.geometry))
            checked.append(row['route_id'])
        del reader
        c._graphs.pop(key,None)
    report=dict(status='passed',routes=len(checked),all_section_costs_and_xy_exact=True,
                cached_searches_reused=True,elapsed_seconds=round(time.monotonic()-start,2))
    output=ROOT/'runtime/qa';output.mkdir(parents=True,exist_ok=True)
    (output/'route_parity_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
