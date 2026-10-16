"""Copy the selected pipeline snapshots into a portable, independently verified bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

FINAL = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def package(development_root):
    development_root=Path(development_root).expanduser().resolve()
    SOURCE=development_root/'work'
    if not (SOURCE/'src/estate_ranking').is_dir():
        raise ValueError('The development root must contain the original work/src/estate_ranking tree.')
    target = FINAL / 'src/estate_ranking'
    target.mkdir(parents=True, exist_ok=True)
    for path in (SOURCE / 'src/estate_ranking').glob('*.py'):
        shutil.copy2(path, target / path.name)
    shutil.copytree(SOURCE / 'config', FINAL / 'config', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('entity_ids.json'))
    queue = [(SOURCE / 'precomputed/outputs' / name).resolve() for name in
             ('current', 'step_2/current', 'step_3/current', 'step_4/current', 'step_5/current')]
    copied = set()
    while queue:
        directory = queue.pop(0)
        if directory in copied:
            continue
        relative = directory.relative_to(SOURCE)
        print('Packaging ' + str(relative), flush=True)
        shutil.copytree(directory, FINAL / relative, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.DS_Store', '__pycache__'))
        copied.add(directory)
        parent = directory / 'amendment_parent.json'
        if parent.exists():
            queue.append(SOURCE / json.loads(parent.read_text())['directory'])
    for name in ('current', 'step_2/current', 'step_3/current', 'step_4/current', 'step_5/current'):
        origin = SOURCE / 'precomputed/outputs' / name
        link = FINAL / 'precomputed/outputs' / name
        if not link.is_symlink():
            link.symlink_to(origin.readlink())
    shutil.copytree(SOURCE / 'precomputed/outputs/rebuild', FINAL / 'precomputed/outputs/rebuild', dirs_exist_ok=True)
    link = FINAL / 'config/entity_ids.json'
    if not link.is_symlink():
        link.symlink_to('../precomputed/outputs/current/entity_ids.json')
    for name in ('hong_kong_land.geojson', 'district_boundaries.json'):
        shutil.copy2(development_root / 'analysis/maps' / name, FINAL / 'assets/maps' / name)
    shutil.copy2(development_root / 'THIS FORM.pdf', FINAL / 'assets/samples/application-form.pdf')
    docs = FINAL / 'docs/engine'
    docs.mkdir(parents=True, exist_ok=True)
    for stage in range(1, 6):
        for path in (SOURCE / 'instructions' / ('step_' + str(stage))).glob('*implementation*.md'):
            shutil.copy2(path, docs / path.name)
    records = []
    for directory in sorted(copied):
        manifest = json.loads((directory / 'manifest.json').read_text()) if (directory / 'manifest.json').exists() else None
        for path in sorted((FINAL / directory.relative_to(SOURCE)).rglob('*')):
            if not path.is_file():
                continue
            signature = digest(path)
            if manifest and path.parent == FINAL / directory.relative_to(SOURCE) and path.name in manifest.get('artifacts', {}):
                expected = manifest['artifacts'][path.name]
                assert signature == (expected['sha256'] if isinstance(expected, dict) else expected), path
            assert signature == digest(directory / path.relative_to(FINAL / directory.relative_to(SOURCE))), path
            records.append(dict(path=str(path.relative_to(FINAL)), bytes=path.stat().st_size, sha256=signature))
    result = dict(schema_version=1, selected_runs=[str(p.relative_to(SOURCE)) for p in sorted(copied)],
                  artifacts=records, total_bytes=sum(r['bytes'] for r in records))
    (FINAL / 'precomputed/bundle_manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Verified {} files, {:.2f} GiB'.format(len(records), result['total_bytes'] / 1024**3), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development-root',type=Path,required=True,
        help='Checkout of the development branch containing work/, data/, and analysis/.')
    package(parser.parse_args().development_root)
