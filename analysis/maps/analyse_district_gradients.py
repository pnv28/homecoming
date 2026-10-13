"""Summarise stored route gradients within North and Yuen Long districts."""
from pathlib import Path
import json
import csv
import numpy as np
import shapely
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
from pyogrio.raw import read

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
project = Transformer.from_crs(4326, 2326, always_xy=True)
source = '/vsizip/' + str(ROOT / 'data/organized/core/pedestrian/3D_Pedestrian_Network_FGDB.zip') + '/3DPN_P2.gdb'
meta, _, wkb, values = read(source, layer='PedestrianRoute', columns=[
    'PedestrianRouteID', 'FeatureType', 'Gradient', 'AliasNameEN', 'StreetNameEN', 'Enabled'])
a = dict(zip(meta['fields'], values))
geoms = shapely.from_wkb(wkb)
tree = shapely.STRtree(geoms)
report = {'method': 'Routes intersecting district boundary polygons; positive in-district XY length for walking statistics. Crossing routes can appear in both districts. Stored per-route Gradient used, not terrain-derived slope.',
          'angle_conversion': 'degrees = abs(Gradient) * 180/pi; grade_percent = 100*tan(abs(Gradient))',
          'walking_excluded_feature_codes': [8, 9, 10, 12, 13, 16, 17, 18, 20, 21], 'districts': {}}

def summarise(ids, lengths):
    radians = np.abs(a['Gradient'][ids])
    ok = np.isfinite(radians)
    radians, lengths = radians[ok], lengths[ok]
    degrees = np.rad2deg(radians)
    quantiles = np.quantile(degrees, [.5, .9, .95, .99])
    order = np.argsort(degrees)
    cum = np.cumsum(lengths[order])
    weighted = [float(degrees[order[min(np.searchsorted(cum, q * cum[-1]), len(order)-1)]]) for q in [.5,.9,.95,.99]] if cum[-1] else []
    bins = [0, 2, 5, 10, 15, 30, 90.001]
    hist = np.histogram(degrees, bins=bins)[0]
    return {'route_count': len(ids), 'finite_gradient_count': int(ok.sum()), 'length_km': float(lengths.sum()/1000),
            'quantiles_degrees_p50_p90_p95_p99': quantiles.tolist(),
            'length_weighted_quantiles_degrees_p50_p90_p95_p99': weighted,
            'max_degrees': float(degrees.max()),
            'at_least_5_degrees_percent_of_routes': float((degrees>=5).mean()*100),
            'at_least_10_degrees_percent_of_routes': float((degrees>=10).mean()*100),
            'at_least_5_degrees_percent_of_length': float(lengths[degrees>=5].sum()/lengths.sum()*100),
            'at_least_10_degrees_percent_of_length': float(lengths[degrees>=10].sum()/lengths.sum()*100),
            'bin_edges_degrees': bins, 'bin_route_counts': hist.tolist()}

for f in json.loads((OUT/'district_boundaries.json').read_text())['features']:
    name = f['properties']['District']
    if name not in ['Yuen Long District', 'North District']: continue
    polygon = shapely.make_valid(transform(project.transform, shape(f['geometry'])))
    ids = tree.query(polygon, predicate='intersects')
    lengths = shapely.length(shapely.intersection(geoms[ids], polygon))
    walking = ~np.isin(a['FeatureType'][ids], report['walking_excluded_feature_codes']) & (lengths>0)
    d = {'map_district_number': 18 if name.startswith('Yuen') else 7,
         'all_intersecting_routes': summarise(ids, lengths),
         'walking_including_ramps': summarise(ids[walking], lengths[walking])}
    wi = ids[walking]
    order = np.argsort(a['Gradient'][wi])[::-1][:20]
    d['steepest_walking_records'] = [{
        'route_id': int(a['PedestrianRouteID'][wi[j]]), 'feature_type': int(a['FeatureType'][wi[j]]),
        'degrees': float(np.rad2deg(a['Gradient'][wi[j]])), 'alias': str(a['AliasNameEN'][wi[j]]),
        'street': str(a['StreetNameEN'][wi[j]]), 'within_district_xy_length_metres': float(lengths[walking][j])}
        for j in order]
    report['districts'][name] = d
    print(name, json.dumps(d['walking_including_ramps'], indent=2), flush=True)
    with (OUT/('district_18_yuen_long_gradients.csv' if name.startswith('Yuen') else 'district_7_north_gradients.csv')).open('w') as out:
        writer = csv.writer(out)
        writer.writerow(['PedestrianRouteID','FeatureType','Gradient_radians','Slope_degrees','Grade_percent','Within_district_XY_length_m','Included_in_walking_summary','AliasNameEN','StreetNameEN'])
        for k, i in enumerate(ids):
            angle = abs(a['Gradient'][i])
            writer.writerow([int(a['PedestrianRouteID'][i]),int(a['FeatureType'][i]),angle,np.rad2deg(angle),100*np.tan(angle),lengths[k],bool(walking[k]),a['AliasNameEN'][i],a['StreetNameEN'][i]])
(OUT/'district_gradient_summary.json').write_text(json.dumps(report, indent=2)+'\n')
