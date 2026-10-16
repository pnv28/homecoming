"""Select a verified Step 2/3 pair through one atomic completion record."""
import hashlib
import json
import os
from pathlib import Path
import uuid

WORK = Path(__file__).resolve().parents[2]


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected_run(stage, work=None):
    work = Path(work or WORK).resolve()
    registry = work/'precomputed/outputs/rebuild/current.json'
    if not registry.exists():
        return (work/'precomputed/outputs'/stage/'current').resolve()
    record = json.loads(registry.read_text())
    item = record[stage]
    directory = (work/item['directory']).resolve(strict=True)
    if (_digest(directory/'manifest.json') != item['manifest_sha256'] or
        json.loads((directory/'SUCCESS.json').read_text())['run_id'] != item['run_id']):
        raise ValueError('Selected build-pair reference is invalid: '+stage)
    return directory


def publish_pair(step_2, step_3, work=None):
    from .step_2 import publish_run
    work = Path(work or WORK).resolve()
    candidates = {'step_2':Path(step_2).resolve(), 'step_3':Path(step_3).resolve()}
    frozen = json.loads((candidates['step_3']/'frozen_inputs.json').read_text())
    if (frozen['step_2']['run_id'] != candidates['step_2'].name or
        (work/frozen['step_2']['directory']).resolve() != candidates['step_2']):
        raise ValueError('Step 3 is not pinned to the candidate Step 2')
    record = {'status':'passed','pair_id':candidates['step_3'].name}
    for stage, directory in candidates.items():
        success=json.loads((directory/'SUCCESS.json').read_text())
        if success['validation']!='passed' or success['run_id']!=directory.name:
            raise ValueError('Unsuccessful candidate: '+stage)
        record[stage]={'directory':str(directory.relative_to(work)), 'run_id':directory.name,
                       'manifest_sha256':_digest(directory/'manifest.json')}
    root=work/'precomputed/outputs/rebuild'
    (root/'runs').mkdir(parents=True,exist_ok=True)
    history=root/'runs'/(record['pair_id']+'.json')
    history.write_text(json.dumps(record,indent=2)+'\n')
    temporary=root/('.current-'+uuid.uuid4().hex+'.json')
    temporary.write_text(json.dumps(record,indent=2)+'\n')
    previous={}
    try:
        for stage, candidate in candidates.items():
            current=work/'precomputed/outputs'/stage/'current'
            previous[stage]=current.resolve() if current.exists() else None
            publish_run(candidate,current)
        os.replace(temporary,root/'current.json')
    except BaseException:
        for stage, directory in previous.items():
            current=work/'precomputed/outputs'/stage/'current'
            if directory is not None:
                publish_run(directory,current)
            elif current.is_symlink():
                current.unlink()
        raise
    finally:
        if temporary.exists():temporary.unlink()
    return record
