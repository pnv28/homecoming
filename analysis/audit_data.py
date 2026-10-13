"""Reproduce the local data audit; no routing or accessibility certification."""
import collections
import csv
import json
import math
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pyogrio
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis'


def csv_rows(name):
    with (ROOT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def load_json(name):
    with (ROOT / name).open(encoding='utf-8-sig') as f:
        return json.load(f)


def counts(values):
    return dict(collections.Counter(str(v) for v in values))


def haversine(lat, lon, xy):
    x, y = xy
    a = math.sin(math.radians(y-lat)/2)**2
    a += math.cos(math.radians(lat))*math.cos(math.radians(y))*math.sin(math.radians(x-lon)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(a)))


def main():
    estates = load_json('prh-estates (1).json')
    bus = load_json('JSON_BUS.json')['features']
    hospitals = load_json('facility-hosp.json')
    facilities = csv_rows('barrier_free_facilities.csv')
    categories = csv_rows('barrier_free_facility_category.csv')
    stations = csv_rows('mtr_lines_and_stations.csv')
    by_stop = collections.defaultdict(list)
    for f in bus:
        by_stop[str(f['properties']['stopId'])].append(f)
    facility_ids = {x['Station_No'] for x in facilities}
    station_ids = {x['Station ID'] for x in stations if x['Station ID'].strip()}
    report = {
        'estates': {'records': len(estates), 'unique_names': len({x['Estate Name']['en'] for x in estates}),
                    'with_bfa_link': sum('barrier-free' in x.get('Further Information', {}).get('en', '') for x in estates),
                    'missing_coordinates': sum(not x.get('Estate Map Latitude') or not x.get('Estate Map Longitude') for x in estates)},
        'bus': {'records': len(bus), 'unique_stop_ids': len(by_stop),
                'unique_coordinates': len({tuple(x['geometry']['coordinates']) for x in bus}),
                'stop_ids_with_multiple_coordinates': sum(len({tuple(x['geometry']['coordinates']) for x in fs}) > 1 for fs in by_stop.values()),
                'companies': counts(x['properties']['companyCode'] for x in bus),
                'date_min': min(x['properties']['lastUpdateDate'] for x in bus),
                'date_max': max(x['properties']['lastUpdateDate'] for x in bus),
                'boarding_codes': counts(x['properties']['stopPickDrop'] for x in bus)},
        'mtr': {'rows': len(stations), 'unique_ids': len(station_ids),
                'blank_line_rows': [x for x in stations if not x['Line Code']],
                'facilities_rows': len(facilities), 'facility_stations': len(facility_ids),
                'categories': len(categories), 'nonempty_exit_coordinates': sum(bool(x['Exit_Coordinate_X_Y'].strip()) for x in facilities),
                'facility_ids_without_station_id': sorted(facility_ids-station_ids),
                'station_ids_without_facility_id': sorted(station_ids-facility_ids),
                'duplicate_station_facility_keys': len(facilities)-len({(x['Station_No'], x['Key']) for x in facilities})},
        'hospitals': {'records': len(hospitals)},
    }
    examples = []
    unique_stops = [fs[0] for fs in by_stop.values()]
    for estate in estates[:5]:
        lat, lon = estate['Estate Map Latitude'], estate['Estate Map Longitude']
        nearest = min(unique_stops, key=lambda f: haversine(lat, lon, f['geometry']['coordinates']))
        examples.append({'estate': estate['Estate Name']['en'], 'stop_id': nearest['properties']['stopId'],
                         'stop_name': nearest['properties']['stopNameE'],
                         'straight_line_metres': round(haversine(lat, lon, nearest['geometry']['coordinates']), 1),
                         'interpretation': 'Geographic proximity only; route and boarding accessibility unverified.'})
    report['geographic_examples'] = examples
    with tempfile.TemporaryDirectory(prefix='homecoming_audit_') as td:
        with zipfile.ZipFile(ROOT / '3D_Pedestrian_Network_FGDB.zip') as z:
            z.extractall(td)
        gdb = next(Path(td).glob('*.gdb'))
        domains = {}
        for p in gdb.glob('*.gdbtable'):
            for xml in re.findall(rb'<GPCodedValueDomain2\b.*?</GPCodedValueDomain2>', p.read_bytes(), re.S):
                root = ET.fromstring(xml)
                domains[root.findtext('DomainName')] = {
                    'description': root.findtext('Description'),
                    'values': {v.findtext('Code'): v.findtext('Name') for v in root.findall('.//CodedValue')},
                }
        report['gdb_domains'] = domains
        layers = {}
        route = None
        for name, _ in pyogrio.list_layers(gdb):
            info = pyogrio.read_info(gdb, layer=name)
            layers[name] = {'count': info['features'], 'geometry_type': info['geometry_type'], 'fields': info['fields'].tolist()}
            meta, _, _, data = pyogrio.raw.read(gdb, layer=name, read_geometry=False)
            rows = dict(zip(meta['fields'], data))
            if name == 'PedestrianRoute':
                route = rows
                for k in ['Location', 'FeatureType', 'WheelchairBarrier', 'WheelchairAccess', 'WeatherProof', 'Direction', 'Enabled', 'ObstaclesType']:
                    layers[name][k] = counts(rows[k])
                a = rows['Gradient']
                layers[name]['gradient_quantiles_raw'] = np.nanquantile(a, [0, .5, .9, .99, 1]).tolist()
                for k in ['AccessTimeID', 'TerminalID', 'FloorID', 'SiteID']:
                    layers[name][k+'_nonnull'] = int(np.isfinite(rows[k]).sum())
            if name == 'PedRouteRelTerminalPoly':
                layers[name]['terminal_types'] = counts(rows['TerminalType'])
            if name == 'AccessTime':
                layers[name]['access_types'] = counts(rows['AccessTimeType'])
            if name == 'AccessTimeDetails':
                layers[name]['day_codes'] = counts(rows['DayCode'])
        report['network_layers'] = layers
        report['barrier_by_feature_type'] = {
            str(code): counts(route['WheelchairBarrier'][route['FeatureType'] == code])
            for code in np.unique(route['FeatureType'])
        }
    pdf = next(ROOT.glob('*.pdf'))
    OUT.mkdir(exist_ok=True)
    (OUT / 'metadata_extracted.txt').write_text('\n'.join(p.extract_text() for p in PdfReader(pdf).pages))
    (OUT / 'audit_summary.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k not in ['gdb_domains', 'network_layers', 'barrier_by_feature_type']}, indent=2))
    print('Wrote analysis/audit_summary.json and analysis/metadata_extracted.txt')


if __name__ == '__main__':
    main()
