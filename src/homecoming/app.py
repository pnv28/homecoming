"""Local operator interface. Extraction never invokes ranking or an overview."""
from datetime import datetime, timezone
from functools import lru_cache
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import secrets
import threading
import time
from typing import Optional

import anyio
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from homecoming.schemas import Parameters, SearchRequest, WalkRequest
from homecoming.settings import ROOT, MAP_ROOT, RUNTIME, MAX_PDF_BYTES, MODEL, DEEPSEEK_API_KEY
from homecoming.services import data, deepseek, documents, jobs, map_index, routing

app=FastAPI(title='homecoming',docs_url=None,redoc_url=None)
HERE=Path(__file__).resolve().parent
templates=Jinja2Templates(directory=str(HERE/'templates'))
app.mount('/static',StaticFiles(directory=HERE/'static'),name='static')
app.mount('/prepared-maps',StaticFiles(directory=MAP_ROOT),name='prepared-maps')
app.mount('/runtime-maps',StaticFiles(directory=RUNTIME/'map_cache'),name='runtime-maps')
SESSIONS={}
SESSION_LOCK=threading.RLock()


@app.middleware('http')
async def session_middleware(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'This local app only accepts requests from its own page.'},status_code=403)
    token=request.cookies.get('homecoming_session')
    with SESSION_LOCK:
        for sid in list(SESSIONS):
            if time.monotonic()-SESSIONS[sid]['touched']>8*3600:
                del SESSIONS[sid]
        if token not in SESSIONS:
            token=secrets.token_urlsafe(32)
            SESSIONS[token]=dict(results={},touched=time.monotonic())
        SESSIONS[token]['touched']=time.monotonic()
        request.state.owner=token
        request.state.session=SESSIONS[token]
    response=await call_next(request)
    response.set_cookie('homecoming_session',token,httponly=True,samesite='strict',
                        secure=request.url.scheme=='https',max_age=8*3600)
    if not request.url.path.startswith(('/static/','/prepared-maps/','/runtime-maps/')):
        response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    return response


@app.exception_handler(ValueError)
async def value_error(request,exc):
    return JSONResponse({'detail':str(exc)},status_code=400)


@app.get('/',response_class=HTMLResponse)
def home(request:Request):
    # Change asset URLs with their contents so cached scripts cannot lag behind
    # freshly rendered HTML after an update.
    versions={name:hashlib.sha256((HERE/'static'/name).read_bytes()).hexdigest()[:16]
              for name in ('app.css','app.js')}
    return templates.TemplateResponse(request=request,name='index.html',context={'asset_versions':versions})


@app.get('/api/health')
def health():
    progress=MAP_ROOT/'progress.json'
    return dict(status='ok',maps=json.loads(progress.read_text()) if progress.exists() else {'complete':False})


@app.get('/api/map/context')
def path_context(left:float,bottom:float,right:float,top:float,cx:float,cy:float,scale:float):
    """Return original vector paths for the current close-zoom viewport."""
    values=(left,bottom,right,top,cx,cy,scale)
    if not all(math.isfinite(value) for value in values) or not 0 < scale <= 100:
        raise ValueError('Invalid map viewport.')
    if not (780000 <= left < right <= 890000 and 780000 <= bottom < top <= 880000):
        raise ValueError('Map viewport is outside Hong Kong.')
    # The shared offline background already contains all paths at every extent.
    # Only add individual vectors at close zoom to keep interaction responsive.
    content=''
    if max(right-left,top-bottom) <= 3000:
        from homecoming.services.basemap import vector_context
        content=vector_context([left,bottom,right,top],cx,cy,scale)
    return Response(content,media_type='image/svg+xml')


@app.get('/api/bootstrap')
def bootstrap(request:Request):
    catalog=data.catalog()
    data.cache()
    return dict(connected=bool(DEEPSEEK_API_KEY),model=MODEL,
        categories=['Urban','Extended Urban','New Territories','Islands'],
        hospitals=catalog['lists']['hospital'],estates=catalog['lists']['estate'],
        locations=catalog['lists']['hospital']+catalog['lists']['mtr'],
        snapshot=data.cache().directory.name,
        map_library_complete=map_index.index().get('complete',False))


@app.post('/api/reset')
def reset(request:Request):
    # Clearing one applicant never disconnects the shared server-side AI key.
    request.state.session.update(results={})
    with SESSION_LOCK:
        SESSIONS[request.state.owner]=dict(results={},touched=time.monotonic())
    jobs.clear(request.state.owner)
    return dict(ok=True)


@app.get('/sample-form.pdf')
def sample():
    return FileResponse(ROOT/'assets/samples/application-form.pdf',media_type='application/pdf',filename='homecoming-application-form.pdf')


@app.get('/demo-form/{kind}.pdf')
def demo_form(kind:str):
    if kind not in ('typed','scanned'):
        raise HTTPException(404,'Unknown demonstration form.')
    return FileResponse(ROOT/'assets/samples'/('synthetic-'+kind+'.pdf'),media_type='application/pdf',filename='homecoming-demo-'+kind+'.pdf')


@app.post('/api/extract')
async def extract(request:Request,file:UploadFile=File(...)):
    key=DEEPSEEK_API_KEY
    if not key:
        raise HTTPException(409,'AI is temporarily unavailable. You can enter the parameters manually.')
    payload=await file.read(MAX_PDF_BYTES+1)
    await file.close()
    if len(payload)>MAX_PDF_BYTES or not payload.lstrip().startswith(b'%PDF-'):
        raise ValueError('Upload a PDF smaller than 15 MB.')
    # Explicitly no call to ranking(), overview(), or /api/search here.
    job=jobs.submit(request.state.owner,'extraction',lambda:documents.extract_pdf(payload,key))
    return dict(job_id=job)


@app.post('/api/search')
def search(request:Request,body:SearchRequest):
    parameters=body.parameters
    if parameters.hospital_id and parameters.hospital_id not in {r['id'] for r in data.catalog()['lists']['hospital']}:
        raise ValueError('Choose a hospital from the selector.')
    result=data.ranking(parameters)
    result['parameters']=parameters.model_dump()
    result['search_id']=secrets.token_urlsafe(20)
    result['confirmed_utc']=datetime.now(timezone.utc).isoformat()
    with SESSION_LOCK:
        saved=request.state.session['results']
        saved[result['search_id']]=result
        while len(saved)>4:
            del saved[next(iter(saved))]
    return result


@app.post('/api/overview/{search_id}')
def explain(request:Request,search_id:str):
    session=request.state.session
    if not DEEPSEEK_API_KEY:
        raise HTTPException(409,'AI is temporarily unavailable. The computed ranking is ready to use.')
    result=session['results'].get(search_id)
    if result is None:
        raise HTTPException(404,'This confirmed search has expired. Submit the reviewed form again.')
    key=DEEPSEEK_API_KEY
    parameters=Parameters.model_validate(result['parameters'])
    job=jobs.submit(request.state.owner,'overview',lambda:deepseek.overview(key,result,parameters))
    return dict(job_id=job)


@app.get('/api/jobs/{job_id}')
def job(request:Request,job_id:str):
    try:
        return jobs.get(job_id,request.state.owner)
    except KeyError:
        raise HTTPException(404,'This job is no longer available.')


@app.get('/api/route')
def route(estate_id:str,target_id:str,wheelchair:bool=False,scenario:str='primary'):
    if scenario not in ('primary','baseline'):
        raise ValueError('Choose primary or baseline.')
    row=data.route_record(estate_id,target_id,wheelchair,scenario)
    return dict(status=row['status'],reason=row.get('reason'),route_id=row['route_id'],
        cost=row['cost'],unit=row['unit'],warnings=row['warnings'],
        attachments=row.get('attachments',[]),uses_estimated_time=row.get('uses_estimated_time',False),
        estimated_seconds=row.get('estimated_seconds'),
        shared_general_hospital=row['graph']=='general_distance',
        origin=data.catalog()['entities'][estate_id],destination=data.catalog()['entities'][target_id],
        map=map_index.route_assets(row['route_id']) if row['status']=='ok' else None)


@app.get('/api/export/png')
def export_png(asset:str,hd:bool=False,runtime:bool=False):
    from homecoming.services.maps import paths_for
    if len(asset)!=28 or any(c not in '0123456789abcdef' for c in asset):
        raise HTTPException(404,'Unknown map.')
    path=paths_for(asset,RUNTIME/'map_cache' if runtime else MAP_ROOT)['hd' if hd else 'standard']
    if not path.exists():
        raise HTTPException(404,'This map has not been prepared.')
    return Response(map_index.png_bytes(path),media_type='image/png',
                    headers={'Content-Disposition':'attachment; filename="homecoming-route.png"'})


@app.post('/api/walk')
def walk(request:Request,body:WalkRequest):
    job=jobs.submit(request.state.owner,'walk',lambda:routing.walking(body))
    return dict(job_id=job)


@app.get('/api/coordinates')
def coordinates(x:float,y:float):
    import math
    if not math.isfinite(x) or not math.isfinite(y) or not (780000<x<880000 and 790000<y<860000):
        raise ValueError('Select a point within the Hong Kong map.')
    longitude,latitude=routing.TO_GPS.transform(x,y)
    return dict(latitude=latitude,longitude=longitude)


@app.get('/api/grid')
def grid(latitude:float,longitude:float):
    from homecoming.schemas import Endpoint
    try:
        point=Endpoint(latitude=latitude,longitude=longitude)
    except ValidationError:
        raise ValueError('Use valid latitude and longitude coordinates.')
    x,y=routing.TO_GRID.transform(point.longitude,point.latitude)
    return dict(x=x,y=y)


@lru_cache(maxsize=1)
def overview_frame():
    import shapely
    from shapely.geometry import shape
    from shapely.ops import transform
    features=json.loads((ROOT/'assets/maps/hong_kong_land.geojson').read_text())['features']
    land=shapely.union_all([transform(routing.TO_GRID.transform,shape(f['geometry'])) for f in features])
    x0,y0,x1,y1=land.bounds
    scale=min(940/(x1-x0),590/(y1-y0))
    cx,cy=(x0+x1)/2,(y0+y1)/2
    xmin,ymax=cx-500/scale,cy+325/scale
    return land,xmin,ymax,scale


@lru_cache(maxsize=1)
def overview_svg():
    import shapely
    land,xmin,ymax,scale=overview_frame()
    def project(coords):
        return ' '.join('{:.2f},{:.2f}'.format((x-xmin)*scale,(ymax-y)*scale) for x,y in coords)
    encoded=base64.b64encode((ROOT/'assets/maps/selection-background.webp').read_bytes()).decode('ascii')
    out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 650" data-context-bounds="0 0 1000 650" data-center="{} {}" data-grid-scale="{}" data-dynamic-background="true" data-min-width="4" data-xmin="{}" data-ymax="{}" data-scale="{}" aria-label="Hong Kong terrain and pedestrian paths: choose start and destination">'.format(xmin+500/scale,ymax-365/scale,scale,xmin,ymax,scale),
         '<rect width="1000" height="650" fill="#e9f0ed"/>']
    out.append('<image id="pedestrian-background" width="1000" height="650" href="data:image/webp;base64,'+encoded+'"/>')
    out.append('<image id="viewport-background" visibility="hidden"/>')
    for polygon in shapely.get_parts(land.simplify(25)):
        if polygon.geom_type=='Polygon':
            out.append('<polygon points="'+project(polygon.exterior.coords)+'" fill="none" stroke="#91aaa0" stroke-width=".5" vector-effect="non-scaling-stroke"/>')
    out.append('<g id="local-path-detail" fill="none" stroke="#a95430" stroke-width="1.2"/>')
    for estate in data.catalog()['lists']['estate']:
        x=(estate['x']-xmin)*scale;y=(ymax-estate['y'])*scale
        out.append('<circle class="estate-location" cx="{}" cy="{}" r="2.6" fill="#628e78" opacity=".65"/>'.format(x,y))
    out.append('</svg>')
    return ''.join(out)


@app.get('/api/map/background')
def map_background(left:float,bottom:float,right:float,top:float):
    if (not all(math.isfinite(v) for v in (left,bottom,right,top)) or
            not (780000 <= left < right <= 890000 and 780000 <= bottom < top <= 880000)):
        raise ValueError('Map viewport is outside Hong Kong.')
    if not .4 <= (right-left)/(top-bottom) <= 3:
        raise ValueError('Invalid map viewport proportions.')
    from homecoming.services.basemap import basemap
    size=(1400,round(1400*(top-bottom)/(right-left)))
    image=basemap().image([left,bottom,right,top],size)
    stream=io.BytesIO()
    image.save(stream,'WEBP',quality=85,method=0)
    image.close()
    return Response(stream.getvalue(),media_type='image/webp')


@app.get('/api/map/overview',response_class=Response)
def map_overview():
    return Response(overview_svg(),media_type='image/svg+xml')
