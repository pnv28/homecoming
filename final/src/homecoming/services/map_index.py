import io
import json
import threading
from PIL import Image
from homecoming.settings import MAP_ROOT, STEP_4
from homecoming.services.maps import VERSION

LOCK=threading.Lock()
_signature=None
_index={}


def index():
    global _signature,_index
    path=MAP_ROOT/'index.json'
    if not path.exists():
        return dict(routes={},assets={},complete=False)
    signature=path.stat().st_mtime_ns
    with LOCK:
        if signature!=_signature:
            value=json.loads(path.read_text())
            if value.get('snapshot')!=STEP_4.resolve().name or value.get('renderer')!=VERSION:
                raise ValueError('The prepared map library belongs to a different data snapshot or renderer.')
            _index=value;_signature=signature
        return _index


def route_assets(route_id):
    library=index()
    route=library.get('routes',{}).get(route_id,{})
    value=library.get('assets',{}).get(route.get('asset'))
    if not value:
        return None
    return dict(**{k:v for k,v in value.items() if k!='files'},
                files={k:'/prepared-maps/'+v['path'] for k,v in value['files'].items()})


def png_bytes(path):
    with Image.open(path) as image:
        out=io.BytesIO();image.save(out,'PNG')
        return out.getvalue()
