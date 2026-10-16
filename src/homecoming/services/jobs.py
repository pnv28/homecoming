"""Bounded local work queue; job results and credentials stay in session memory."""
from concurrent.futures import ThreadPoolExecutor
import secrets
import threading
import time

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='homecoming')
LOCK = threading.RLock()
JOBS = {}
MAX_JOBS = 8


class BusyError(ValueError):
    pass


def submit(owner, operation, function):
    with LOCK:
        for key in list(JOBS):
            if time.monotonic()-JOBS[key]['created'] > 3600 and JOBS[key]['status'] != 'running':
                del JOBS[key]
        if sum(j['status'] in ('queued','running') for j in JOBS.values()) >= MAX_JOBS:
            raise BusyError('The local calculation queue is busy. Please try again shortly.')
        key = secrets.token_urlsafe(24)
        JOBS[key] = dict(id=key,owner=owner,operation=operation,status='queued',created=time.monotonic())
    def run():
        with LOCK:
            if key not in JOBS:
                return
            JOBS[key]['status'] = 'running'
        try:
            result = function()
            with LOCK:
                if key in JOBS:
                    JOBS[key].update(status='done',result=result)
        except Exception as exc:
            # Public messages are deliberately sanitised. Never return a raw HTTP
            # request/error representation: it could contain a key or PDF text.
            from homecoming.services.deepseek import ProviderError
            message = str(exc) if isinstance(exc,(ProviderError,ValueError)) else 'The operation could not be completed. Please retry or use manual input.'
            with LOCK:
                if key in JOBS:
                    JOBS[key].update(status='failed',error=message)
    POOL.submit(run)
    return key


def get(key,owner):
    with LOCK:
        row = JOBS.get(key)
        if row is None or row['owner'] != owner:
            raise KeyError('Unknown job.')
        return {k:v for k,v in row.items() if k not in ('owner','created')}


def clear(owner):
    with LOCK:
        for key in list(JOBS):
            if JOBS[key]['owner'] == owner:
                del JOBS[key]
