"""Make one row per Transport Department stop ID, with service flags."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'bus_stops.csv'


def main():
    stops = {}
    for filename in ('JSON_BUS.json.1', 'JSON_GMB.json'):
        with (ROOT / filename).open(encoding='utf-8-sig') as f:
            features = json.load(f)['features']
        for feature in features:
            p = feature['properties']
            stop_id = p['stopId']
            lon, lat = feature['geometry']['coordinates']
            if stop_id not in stops:
                stops[stop_id] = {
                    'stop_id': stop_id, 'bus_stop': p['stopNameE'],
                    'bus_stop_zh': p['stopNameC'], 'latitude': lat,
                    'longitude': lon, 'operators': set(),
                }
            row = stops[stop_id]
            assert (row['longitude'], row['latitude']) == (lon, lat), 'Conflicting coordinates for stop ID'
            row['operators'].update(p['companyCode'].split('+'))
    fields = ['stop_id', 'bus_stop', 'bus_stop_zh', 'latitude', 'longitude', 'GMB', 'KMB', 'CTB', 'operators']
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for stop_id in sorted(stops):
            row = dict(stops[stop_id])
            operators = row['operators']
            for operator in ('GMB', 'KMB', 'CTB'):
                row[operator] = 'true' if operator in operators else 'false'
            row['operators'] = '+'.join(sorted(operators))
            writer.writerow(row)
    # Verify output rows and aggregated flags against all source memberships.
    with OUTPUT.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(stops) == len({r['stop_id'] for r in rows})
    for row in rows:
        for operator in ('GMB', 'KMB', 'CTB'):
            assert (row[operator] == 'true') == (operator in stops[int(row['stop_id'])]['operators'])
    print(f'Wrote and verified {len(rows)} stops: {OUTPUT}')
    print({op: sum(r[op] == 'true' for r in rows) for op in ('GMB', 'KMB', 'CTB')})


if __name__ == '__main__':
    main()
