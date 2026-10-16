import hashlib
import json
import threading
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import Point

from estate_ranking.attachments import read_attached_graph
from homecoming.settings import STEP_3, ROOT, RUNTIME
from homecoming.services.fast_coordinate import find_route
from homecoming.services.loading import load_attached,full_sources
from homecoming.services.maps import VERSION, Context, atomic_bytes, make_scene, render_assets

LOCK = threading.RLock()
_attached = None
_graphs = {}
TO_GRID = Transformer.from_crs(4326,2326,always_xy=True)
TO_GPS = Transformer.from_crs(2326,4326,always_xy=True)


def walking(parameters):
    global _attached
    signature = dict(parameters=parameters.model_dump(),snapshot=STEP_3.resolve().name,policy='endpoints-200m-v2',renderer=VERSION)
    key = hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()[:28]
    saved = RUNTIME / 'route_cache' / (key+'.json')
    if saved.exists():
        return json.loads(saved.read_text())
    start = Point(TO_GRID.transform(parameters.start.longitude,parameters.start.latitude))
    end = Point(TO_GRID.transform(parameters.end.longitude,parameters.end.latitude))
    with LOCK:
        if _attached is None:
            _attached = load_attached()
        # Both endpoints must actually be near the supplied dataset. In particular,
        # don't let the expanded facility policy create a cross-district connector.
        for label,point in [('start',start),('destination',end)]:
            candidates = _attached.physical.edges.sindex.query(point,predicate='dwithin',distance=200.)
            if not len(candidates):
                return dict(status='unattached',message='No suitable mapped path within 200 m of the '+label+'.',
                            time_s=None,distance_m=None,attachments=[])
        upstream = ROOT / json.loads((STEP_3/'schema.json').read_text())['upstream_step_2']
        if parameters.wheelchair not in _graphs:
            _graphs[parameters.wheelchair]=read_attached_graph(STEP_3,parameters.wheelchair,'time',_attached)
            _graphs[parameters.wheelchair].source_loader=full_sources
        result,route,attachments = find_route(_graphs[parameters.wheelchair],start,end,upstream)
        result['attachments'] = []
        for row in attachments.itertuples():
            result['attachments'].append(dict(endpoint=row.entity_id,status=row.status,reason=row.reason,
                warnings=row.warnings.split(';') if row.warnings else [],
                connector_m=float(row.distance_m) if row.status=='attached' else None))
        if result['status']=='ok':
            sections=[]
            for row in route.itertuples():
                if row.geometry is None:
                    continue
                kind = 'connector' if row.kind!='network' else 'lift' if row.lift_id else 'estimate' if row.time_model=='distance_height_estimate' else 'network'
                sections.append(dict(coords=[list(c)[:2] for c in row.geometry.coords],kind=kind,
                                     distance_m=float(row.distance_m),cost=float(row.time_s),source=str(row.source_id)))
            scene=make_scene(sections,list(start.coords[0]),list(end.coords[0]),Context(_attached.physical.edges),parameters.wheelchair)
            title=(parameters.start.label or 'Start')+' → '+(parameters.end.label or 'Destination')
            subtitle='{:.0f} m · {:.1f} min · {}'.format(result['distance_m'],result['time_s']/60,
                'Wheelchair mode' if parameters.wheelchair else 'General walking')
            files=render_assets(key,scene,title,subtitle,root=RUNTIME/'map_cache')
            result['assets']={kind:'/runtime-maps/'+record['path'] for kind,record in files.items()}
            result['section_count']=len(sections)
        result.update(snapshot=STEP_3.resolve().name,parameters=parameters.model_dump())
        atomic_bytes(saved,json.dumps(result,allow_nan=False).encode())
        return result
