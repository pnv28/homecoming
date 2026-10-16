"""Run all of Steps 2 and 3; select outputs only after both validate."""
from contextlib import ExitStack
import fcntl
from pathlib import Path
import json

from .graph import WORK
from . import step_2, step_3
from .run_registry import publish_pair


def run():
    with ExitStack() as stack:
        for name in ('rebuild','step_2','step_3'):
            p=WORK/'cache'/(name+'.lock');p.parent.mkdir(parents=True,exist_ok=True)
            handle=stack.enter_context(p.open('a'))
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        first=step_2.run(WORK/'precomputed/outputs/runs/20261014T090829Z-20d0139c',select=False)
        if not isinstance(first,Path):
            raise RuntimeError('Step 2 failed; selected pair is unchanged')
        second=step_3.run(input_directory=first,select=False)
        record=publish_pair(first,second)
        print('Selected verified Step 2/3 pair: '+json.dumps(record),flush=True)
        return record


if __name__=='__main__':run()
