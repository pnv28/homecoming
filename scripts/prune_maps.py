"""Remove superseded generated maps, retaining all current route identities.

Safe during a resumable build: pending route keys count as live, not just the
assets that have already finished. Original graph artifacts are never visited.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from homecoming.services.maps import VERSION
from homecoming.settings import MAP_ROOT,STEP_4


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Delete the listed obsolete generated files.')
    args=parser.parse_args()
    library=json.loads((MAP_ROOT/'index.json').read_text())
    if library.get('renderer')!=VERSION or library.get('snapshot')!=STEP_4.resolve().name:
        raise ValueError('Only the current renderer/snapshot index can be used for pruning.')
    live={row['asset'] for row in library['routes'].values() if row.get('asset')}
    if not live or any(not re.fullmatch('[0-9a-f]{28}',key) for key in live):
        raise ValueError('Invalid or empty route identities.')
    obsolete=[]
    for path in (MAP_ROOT/'assets').rglob('*'):
        match=re.fullmatch(r'([0-9a-f]{28})(?:@2x)?\.(?:svg|webp)(?:\.tmp)?',path.name)
        if match and match[1] not in live and path.is_file() and not path.is_symlink():
            obsolete.append(path)
    size=sum(path.stat().st_size for path in obsolete)
    for path in obsolete:
        if args.apply:path.unlink()
    print(json.dumps(dict(applied=args.apply,current_route_asset_sets=len(live),
        obsolete_files=len(obsolete),obsolete_bytes=size),indent=2))


if __name__=='__main__':main()
