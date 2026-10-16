"""Thin adapters over the unchanged estate-ranking engine."""
from functools import lru_cache
import json
import math
import threading

import pandas as pd
import pyogrio

from estate_ranking.step_4 import _reader
from estate_ranking.step_5 import rank_estates, scoring_policy
from homecoming.settings import STEP_3, STEP_4

ENGINE_LOCK = threading.RLock()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, 'item'):
        return clean(value.item())
    return value


@lru_cache(maxsize=1)
def cache():
    with ENGINE_LOCK:
        return _reader()


@lru_cache(maxsize=1)
def catalog():
    entities = {}
    lists = {}
    for kind, layer in [('estate', 'estates'), ('hospital', 'hospitals'),
                        ('mtr', 'mtr_exits'), ('bus', 'bus_stops')]:
        frame = pyogrio.read_dataframe(STEP_3 / 'attachments.gpkg', layer=layer)
        rows = []
        for r in frame.to_dict('records'):
            value = clean(dict(id=r['id'], name=r.get('name_en') or r['name'],
                              name_zh=r.get('name_zh_hant'), kind=kind,
                              latitude=r['latitude'], longitude=r['longitude'],
                              x=r['easting'], y=r['northing'],
                              housing_district=r.get('housing_district'),
                              address=r.get('address'), exit_code=r.get('exit_code')))
            entities[value['id']] = value
            rows.append(value)
        lists[kind] = sorted(rows, key=lambda r: r['name'].casefold())
    return dict(entities=entities, lists=lists)


def ranking(parameters):
    with ENGINE_LOCK:
        frame = rank_estates(parameters.housing_district or None, parameters.wheelchair,
                             parameters.hospital_id, parameters.scenario, parameters.weights)
    fields = ['id', 'name_en', 'name_zh_hant', 'housing_district', 'latitude', 'longitude',
              'rank', 'ranking_status', 'final_cost', 'missing_components',
              'available_required_component_count']
    fields += [k + suffix for k in ('bus', 'mtr', 'hospital') for suffix in
               ('_target_ids', '_status', '_warnings', '_reason', '_scaled_cost')]
    fields += ['bus_time_s', 'mtr_time_s', 'hospital_distance_m']
    records = clean(frame[fields].to_dict('records'))
    entities = catalog()['entities']
    for r in records:
        for kind in ('bus', 'mtr', 'hospital'):
            r[kind + '_targets'] = [entities[k] for k in r[kind + '_target_ids']]
    return dict(estates=records, policy=clean(frame.attrs['scoring_policy']),
                snapshot=clean(frame.attrs['step_4']),
                complete=sum(r['ranking_status'] == 'complete' for r in records),
                incomplete=sum(r['ranking_status'] != 'complete' for r in records))


def route_record(estate_id, target_id, wheelchair=False, scenario='primary'):
    c = cache()
    if estate_id not in set(c.estates.id):
        raise ValueError('Unknown estate.')
    hospital = target_id.startswith('hospital:')
    key = 'general_distance' if hospital else ('wheelchair' if wheelchair else 'general') + '_time' + ('_baseline' if scenario == 'baseline' else '')
    rid = key + ':' + estate_id + ':' + target_id
    if rid not in c.routes:
        raise ValueError('This journey is not a cached destination. Use Plan a walk for other endpoints.')
    return c.routes[rid]
