"""Resumable generation of all cached estate/facility WebP and SVG maps.

Run from final/: PYTHONPATH=src python scripts/precompute_maps.py
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from homecoming.services.data import cache, catalog
from homecoming.services.loading import load_attached
from homecoming.services.maps import (VERSION, Context, FastRoutes, asset_key,
    atomic_bytes, make_scene, paths_for, render_assets)
from homecoming.settings import MAP_ROOT, STEP_4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=0, help='Render at most this many new unique assets; 0 means all.')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    args.workers=max(1,min(args.workers,4))
    stopping=False
    def request_stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGINT,request_stop)
    signal.signal(signal.SIGTERM,request_stop)
    started = time.monotonic()
    print('Verifying and loading cached journeys...', flush=True)
    c, entities = cache(), catalog()['entities']
    c._attached=load_attached()
    index_path = MAP_ROOT / 'index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    if index.get('snapshot') != STEP_4.resolve().name or index.get('renderer') != VERSION:
        index = dict(schema_version=1, snapshot=STEP_4.resolve().name, renderer=VERSION,
                     complete=False, routes={}, assets={})
    for rid, row in c.routes.items():
        index['routes'][rid] = dict(status=row['status'], reason=row.get('reason'),
                                    asset=asset_key(row) if row['status'] == 'ok' else None)
    total = len({r['asset'] for r in index['routes'].values() if r['asset']})
    for key in list(index['assets']):
        if not all(p.exists() for p in paths_for(key).values()):
            del index['assets'][key]
    pending = []
    queued = set(index['assets'])
    rendered = 0
    def checkpoint():
        index['complete'] = len(index['assets']) == total
        index['updated_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_bytes(index_path, json.dumps(index, separators=(',', ':')).encode())
        status = dict(complete=index['complete'], assets=len(index['assets']), total=total,
                      workers=args.workers, process_id=os.getpid(), renderer=VERSION,
                      routes=len(index['routes']), rendered_this_run=rendered,
                      elapsed_seconds=round(time.monotonic()-started, 1),
                      bytes=sum(a['files'][k]['bytes'] for a in index['assets'].values() for k in a['files']))
        atomic_bytes(MAP_ROOT / 'progress.json', json.dumps(status, indent=2).encode())
        print('{}/{} asset sets; {} new; {:.1f} s'.format(len(index['assets']), total, rendered, time.monotonic()-started), flush=True)
    def collect(wait=False):
        nonlocal rendered
        while pending and (wait or pending[0][2].done()):
            key, metadata, future = pending.pop(0)
            metadata['files'] = future.result()
            index['assets'][key] = metadata
            rendered += 1
            if rendered % 25 == 0:
                checkpoint()
            if not wait:
                break
    checkpoint()
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,4))) as pool:
        keys = ['general_time', 'wheelchair_time', 'general_time_baseline',
                'wheelchair_time_baseline', 'general_distance']
        stop = False
        for graph_key in keys:
            rows = [r for r in c.routes.values() if r['graph'] == graph_key and r['status'] == 'ok'
                    and asset_key(r) not in queued]
            if not rows:
                continue
            print('Loading ' + graph_key + ': ' + str(len(rows)) + ' journeys', flush=True)
            reader = FastRoutes(c, graph_key)
            context = Context(reader.graph.edges)
            for row in rows:
                key = asset_key(row)
                if key in queued:
                    continue
                if stopping or (args.limit and rendered + len(pending) >= args.limit):
                    stop = True
                    break
                sections = reader.sections(row)
                origin, destination = entities[row['estate_id']], entities[row['target_id']]
                scene = make_scene(sections, [origin['x'],origin['y']], [destination['x'],destination['y']],
                                   context, graph_key.startswith('wheelchair'))
                title = origin['name'] + ' → ' + destination['name']
                if row['unit'] == 'metres':
                    subtitle = '{:.0f} m · Hospital walking distance · General network'.format(row['cost'])
                else:
                    subtitle = '{:.0f} m · {:.1f} min · {}'.format(scene['distance_m'],row['cost']/60,
                        'Wheelchair mode' if graph_key.startswith('wheelchair') else 'General walking')
                metadata = dict(distance_m=scene['distance_m'], section_count=len(sections),
                                lift_sections=sum(s['kind']=='lift' for s in sections),
                                estimated_sections=sum(s['kind']=='estimate' for s in sections),
                                title=title, subtitle=subtitle)
                pending.append((key,metadata,pool.submit(render_assets,key,scene,title,subtitle,row['unit'])))
                queued.add(key)
                if len(pending) >= max(2,args.workers*2):
                    key_done, metadata_done, future = pending.pop(0)
                    metadata_done['files'] = future.result()
                    index['assets'][key_done] = metadata_done
                    rendered += 1
                    if rendered % 25 == 0:
                        checkpoint()
                collect()
            collect(wait=True)
            # Keep the shared physical data but release scenario transition arrays.
            del reader, context
            c._graphs.pop(graph_key, None)
            checkpoint()
            if stop:
                break
    checkpoint()


if __name__ == '__main__':
    main()
