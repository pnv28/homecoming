"""Read only runtime graph fields; keep full original source evidence on disk.

The public engine readers are unchanged. Route geometry/state tables remain the
exact saved tables; large raw source attributes are fetched for the few source
paths being subdivided, rather than copied into memory for every source path.
"""
import json
import pandas as pd
import geopandas as gpd
import pyogrio

from estate_ranking.attachments import AttachedPoints,LAYERS
from estate_ranking.graph import PhysicalGraph
from homecoming.settings import ROOT,STEP_3


def restored(path,layer,dtypes,columns=None,where=None,geometry=True):
    frame=pyogrio.read_dataframe(path,layer=layer,columns=columns,where=where,
                                read_geometry=geometry,datetime_as_string=True)
    for name,dtype in dtypes.items():
        if name not in frame:continue
        if name in ('fallback_review_ids','time_model_warning','reason','warnings') or (dtype=='object' and name.endswith('_exclusion')):
            frame[name]=frame[name].fillna('')
        frame[name]=frame[name].astype(dtype)
    return frame


def load_attached():
    schema=json.loads((STEP_3/'schema.json').read_text())
    upstream=ROOT/schema['upstream_step_2']
    source_schema=json.loads((upstream/'schema.json').read_text())
    frames={}
    for layer in ('nodes','edges','attachments','connectors',*LAYERS.values()):
        frames[layer]=restored(STEP_3/'attachments.gpkg',layer,schema['spatial_dtypes'][layer])
        frames[layer].attrs['vertical_crs']='EPSG:5738' if layer in ('nodes','edges','attachments') else None
    context=['PedestrianRouteID','FeatureType_label','Location_label','FloorID','BuildingID_1','BuildingID_2']
    sources=restored(upstream/'graph.gpkg','sources',source_schema['spatial_dtypes']['sources'],columns=context,geometry=False)
    members=pd.read_csv(STEP_3/'memberships.csv',dtype={'source_id':str,'node_id':str},float_precision='round_trip')
    physical=PhysicalGraph(frames['nodes'],frames['edges'],sources,members,[],[],
                            json.loads((upstream/'model_policy.json').read_text()))
    attached=AttachedPoints(physical,{k:frames[v] for k,v in LAYERS.items()},frames['attachments'],frames['connectors'],pd.DataFrame(),{})
    return attached


def full_sources(source_ids):
    schema=json.loads((STEP_3/'schema.json').read_text())
    upstream=ROOT/schema['upstream_step_2']
    source_schema=json.loads((upstream/'schema.json').read_text())
    # IDs originate from the frozen graph, not from user-provided SQL text.
    ids=sorted(set(map(str,source_ids)))
    if not ids or any(not sid.isdecimal() for sid in ids):
        raise ValueError('Unexpected source identity in the saved pedestrian graph.')
    where='PedestrianRouteID IN ('+','.join(ids)+')'
    frame=restored(upstream/'graph.gpkg','sources',source_schema['spatial_dtypes']['sources'],where=where)
    if set(frame.PedestrianRouteID.astype(str))!=set(ids):
        raise ValueError('Missing original source evidence for endpoint subdivision.')
    frame.attrs['vertical_crs']='EPSG:5738'
    return frame
