"""Make one row per Transport Department stop ID, with service flags."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'bus_stops.json'


def main():
    stops = {}
    for filename in ('data/organized/core/bus/route_stop_records.geojson', 'data/organized/core/bus/JSON_GMB.json'):
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
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for stop_id in sorted(stops):
        row = dict(stops[stop_id])
        operators = row['operators']
        for operator in ('GMB', 'KMB', 'CTB'):
            row[operator] = operator in operators
        row['operators'] = sorted(operators)
        rows.append(row)
    OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Verify output rows and aggregated flags against all source memberships.
    rows = json.loads(OUTPUT.read_text(encoding='utf-8'))
    assert len(rows) == len(stops) == len({r['stop_id'] for r in rows})
    for row in rows:
        for operator in ('GMB', 'KMB', 'CTB'):
            assert type(row[operator]) is bool
            assert row[operator] == (operator in stops[row['stop_id']]['operators'])
    print(f'Wrote and verified {len(rows)} stops: {OUTPUT}')
    print({op: sum(r[op] for r in rows) for op in ('GMB', 'KMB', 'CTB')})


if __name__ == '__main__':
    main()
