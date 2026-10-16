"""Check file fingerprints, selected dependencies, numeric coverage, and map coverage."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--maps',action='store_true',help='Require every pre-generated route asset and verify its checksum.')
    args=parser.parse_args();started=time.monotonic()
    bundle=json.loads((ROOT/'precomputed/bundle_manifest.json').read_text())
    for record in bundle['artifacts']:
        path=ROOT/record['path']
        assert path.resolve().is_relative_to(ROOT),path
        assert path.stat().st_size==record['bytes'],path
        assert digest(path)==record['sha256'],path
    for path in ROOT.rglob('*'):
        if path.is_symlink() and not path.is_relative_to(ROOT/'runtime'):
            assert path.resolve().is_relative_to(ROOT),path
    from homecoming.services.data import cache,catalog
    from estate_ranking.step_5 import rank_estates,read_rankings
    from pandas.testing import assert_frame_equal
    from unittest.mock import patch
    c=cache()
    hospital=[r for r in c.data['routes'] if r['graph']=='general_distance']
    assert len(hospital)==244*44
    assert set(Counter(r['estate_id'] for r in hospital).values())=={44}
    assert sum(r['status']=='ok' for r in hospital)==6323
    assert set(Counter((r['scenario'],r['mode'],r['group']) for r in c.data['groups']).values())=={244}
    views={}
    with patch('estate_ranking.step_4.dijkstra',side_effect=AssertionError('Unexpected search during ranking')):
        for wheelchair in (False,True):
            for scenario in ('primary','baseline'):
                saved=read_rankings(wheelchair,scenario)
                actual=rank_estates(wheelchair=wheelchair,scenario=scenario)
                assert_frame_equal(saved,actual,check_exact=True)
                views[scenario+('_wheelchair' if wheelchair else '_general')]=dict(saved.ranking_status.value_counts())
    report=dict(status='passed',snapshot=c.directory.name,bundle_files=len(bundle['artifacts']),
                hospital_pairs=len(hospital),reachable_hospital_pairs=6323,views=views,
                numeric_routing_searches=0,all_selectors_internal=True)
    if args.maps:
        from homecoming.services.maps import asset_key
        from PIL import Image
        import xml.etree.ElementTree as ET
        library=json.loads((ROOT/'precomputed/maps/index.json').read_text())
        assert library['complete'] is True
        assert library['snapshot']==c.directory.name
        expected={asset_key(row) for row in c.routes.values() if row['status']=='ok'}
        assert set(library['assets'])==expected
        for row in c.routes.values():
            item=library['routes'][row['route_id']]
            assert item['status']==row['status']
            assert item['asset']==(asset_key(row) if row['status']=='ok' else None)
        files=0
        for asset in library['assets'].values():
            assert set(asset['files'])=={'svg','standard','hd'}
            for kind,record in asset['files'].items():
                path=ROOT/'precomputed/maps'/record['path']
                assert path.resolve().is_relative_to(ROOT/'precomputed/maps')
                assert path.stat().st_size==record['bytes'],path
                assert digest(path)==record['sha256'],path
                if kind=='svg':
                    svg=ET.parse(path).getroot()
                    assert svg.tag=='{http://www.w3.org/2000/svg}svg',path
                    assert svg.attrib['viewBox']=='0 0 1000 700',path
                    assert not any(node.tag.endswith('script') for node in svg.iter()),path
                    images=[node for node in svg.iter() if node.tag.endswith('image')]
                    assert len(images)==2 and all(image.attrib['href'].startswith('data:image/webp;base64,') for image in images),path
                    assert svg.attrib['data-context-bounds']=='-500 -350 2000 1400',path
                else:
                    with Image.open(path) as image:
                        assert image.format=='WEBP',path
                        assert image.size==((1200,840) if kind=='standard' else (3000,2100)),path
                files+=1
        report.update(map_asset_sets=len(expected),map_files=files,all_cached_route_statuses=len(c.routes))
    report['elapsed_seconds']=round(time.monotonic()-started,2)
    output=ROOT/'runtime/qa';output.mkdir(parents=True,exist_ok=True)
    (output/'bundle_report.json').write_text(json.dumps(report,indent=2,default=int))
    print(json.dumps(report,indent=2,default=int))


if __name__=='__main__':main()
