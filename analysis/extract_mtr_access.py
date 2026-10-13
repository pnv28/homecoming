"""Extract official iGeoCom access points from downloaded GeoJSON/CSV ZIPs.

Usage: python analysis/extract_mtr_access.py GEOJSON_ZIP CSV_ZIP
Preserves source attributes and adds no inferred accessibility labels.
"""
import collections
import csv
import datetime
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data' / 'official_igeocom'
BASE = 'https://open.hkmapservice.gov.hk/OpenData/directDownload'


def main():
    gj_path, csv_path = map(Path, sys.argv[1:3])
    with zipfile.ZipFile(gj_path) as z:
        obj = json.loads(z.read('iGeoCOM_POI.geojson'))
    with zipfile.ZipFile(csv_path) as z:
        rows = list(csv.DictReader(io.StringIO(z.read('iGeoCOM_POI.csv').decode('utf-8-sig'))))
    access = [f for f in obj['features'] if f['properties']['TYPE'] == 'MTA']
    stations = [f for f in obj['features'] if f['properties']['TYPE'] == 'RSN']
    DEST.mkdir(parents=True, exist_ok=True)
    for filename, features in [('mtr_access_points.geojson', access), ('railway_stations.geojson', stations)]:
        (DEST / filename).write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, indent=2))
    geo_by_id = {str(f['properties']['GEONAMEID']): f for f in access}
    access_rows = [r for r in rows if r['TYPE'] == 'MTA']
    assert set(geo_by_id) == {r['GEONAMEID'] for r in access_rows}, 'Source versions differ'
    assert len(geo_by_id) == len(access), 'Duplicate access IDs'
    for r in access_rows:
        f = geo_by_id[r['GEONAMEID']]
        assert f['geometry']['type'] == 'Point'
        lon, lat = f['geometry']['coordinates']
        assert 113 < lon < 115 and 22 < lat < 23
        r['LONGITUDE_WGS84'], r['LATITUDE_WGS84'] = lon, lat
    with (DEST / 'mtr_access_points.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(access_rows[0]))
        w.writeheader()
        w.writerows(access_rows)
    summary = {
        'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'dataset_page': 'https://data.gov.hk/en-data/dataset/hk-landsd-openmap-development-hkms-digital-geocom',
        'geojson_url': BASE + '?productFormat=GEOJSON&productName=iGeoCom&sheetName=iGeoCom',
        'csv_url': BASE + '?productFormat=CSV&productName=iGeoCom&sheetName=iGeoCom',
        'dictionary_url': 'https://open.hkmapservice.gov.hk/OpenData/opendata_static/resources/resources_iGeoCom_GeoJSON.zip',
        'geojson_archive_sha256': hashlib.sha256(gj_path.read_bytes()).hexdigest(),
        'csv_archive_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        'all_poi_count': len(obj['features']),
        'access_record_count': len(access),
        'nonblank_access_site_names': len({f['properties']['E_SITENAME'] for f in access if f['properties']['E_SITENAME']}),
        'access_records_without_site_name': sum(not f['properties']['E_SITENAME'] for f in access),
        'railway_station_record_count': len(stations),
        'access_subcategory_counts': dict(collections.Counter(f['properties']['SUBCAT'] or '' for f in access)),
        'coordinate_systems': {'geometry': 'WGS84 longitude, latitude', 'EASTING_NORTHING': 'Hong Kong 1980 Grid'},
        'limitations': 'Counts are records, not verified unique exits or physical station complexes. Blank SUBCAT means unspecified, not inaccessible. No live equipment status or guaranteed platform access.',
    }
    (DEST / 'source_manifest.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
