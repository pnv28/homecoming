"""Mobility screening metrics, not a certification of accessible routes."""
from pathlib import Path
import csv
import json
import numpy as np
from pyogrio.raw import read

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
source = '/vsizip/' + str(ROOT / '3D_Pedestrian_Network_FGDB.zip') + '/3DPN_P2.gdb'
meta, _, _, values = read(source, layer='PedestrianRoute', read_geometry=False,
    columns=['PedestrianRouteID', 'FeatureType', 'WheelchairBarrier', 'WheelchairAccess',
             'ObstaclesType', 'Enabled', 'AccessTimeID', 'Gradient'])
a = dict(zip(meta['fields'], values))
lookup = {int(rid): i for i, rid in enumerate(a['PedestrianRouteID'])}
report = {'interpretation': 'Screening only. Gradient thresholds are display/analysis bands inspired by ramp design guidance, not a pass/fail test of outdoor route accessibility. WheelchairAccess indicates accessible entrance connections, not general route passability. WheelchairBarrier domain description is ambiguous; raw True/False counts are reported, with True associated predominantly with stairs/escalators in this file.',
    'thresholds_grade_percent': [5, 100/12], 'districts': {}}
for district, file in [('Yuen Long', 'district_18_yuen_long_gradients.csv'), ('North', 'district_7_north_gradients.csv')]:
    with (OUT/file).open() as f: rows = list(csv.DictReader(f))
    idx = np.array([lookup[int(r['PedestrianRouteID'])] for r in rows])
    lengths = np.array([float(r['Within_district_XY_length_m']) for r in rows])
    walking = np.array([r['Included_in_walking_summary']=='True' for r in rows])
    grade = 100*np.tan(np.abs(a['Gradient'][idx]))
    bins = [grade<=5, (grade>5)&(grade<=100/12), grade>100/12]
    result = {'all_intersecting_routes': len(rows), 'walking_routes': int(walking.sum()),
              'walking_xy_length_km': float(lengths[walking].sum()/1000),
              'walking_grade_bands': {}, 'feature_counts': {}}
    for label, mask in zip(['up_to_5_percent','over_5_up_to_8_33_percent','over_8_33_percent'], bins):
        selected = walking & mask
        result['walking_grade_bands'][label] = {'route_count': int(selected.sum()),
            'route_percent': float(selected.sum()/walking.sum()*100),
            'xy_length_percent': float(lengths[selected].sum()/lengths[walking].sum()*100)}
    for label, codes in [('stairs',[12,20]),('escalators',[8,16]),('lifts',[10,18]),
                         ('ramps',[11,19]),('travelators',[9,17]),('stairlifts',[13,21])]:
        mask = np.isin(a['FeatureType'][idx], codes)
        result['feature_counts'][label] = int(mask.sum())
        if label=='ramps':
            result['ramp_grade_bands_counts'] = {label:int((mask & b).sum())
                for label,b in zip(['up_to_5_percent','over_5_up_to_8_33_percent','over_8_33_percent'], bins)}
    result['wheelchair_barrier_raw_true_routes'] = int((a['WheelchairBarrier'][idx]==1).sum())
    result['wheelchair_barrier_raw_true_walking_routes'] = int(((a['WheelchairBarrier'][idx]==1)&walking).sum())
    result['accessible_entrance_connection_routes'] = int((a['WheelchairAccess'][idx]==1).sum())
    result['not_enabled_routes'] = int((a['Enabled'][idx]!=1).sum())
    # Do not assume that a named obstacle always prevents wheelchair passage.
    obstacles = a['ObstaclesType'][idx]
    result['routes_with_named_obstacle'] = int((np.isfinite(obstacles)&(obstacles!=1)).sum())
    report['districts'][district] = result
    print(district, json.dumps(result, indent=2), flush=True)
(OUT/'district_mobility_summary.json').write_text(json.dumps(report,indent=2)+'\n')
