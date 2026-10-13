"""Derive HD300 housing groups from HAD districts and selected EAC polygons.

The EAC selections are geographic proxies for the two named town areas, not
Housing Authority-issued allocation boundaries. See HOUSING_DISTRICTS_README.md.
"""
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import shapely
from shapely.geometry import Point, shape, mapping
from shapely.ops import transform
from pyproj import Transformer

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
NS = 'http://www.w3.org/2000/svg'
PROJECT = Transformer.from_crs(4326, 2326, always_xy=True)
UNPROJECT = Transformer.from_crs(2326, 4326, always_xy=True)
COLORS = {'Urban': '#f0c7a7', 'Extended Urban': '#b8d9e9',
          'New Territories': '#c9dfb3', 'Islands': '#d8c6e7'}
URBAN = {'Central and Western', 'Eastern', 'Southern', 'Wan Chai',
         'Kowloon City', 'Kwun Tong', 'Sham Shui Po', 'Wong Tai Sin', 'Yau Tsim Mong'}
NEW_TERRITORIES = {'Tuen Mun', 'Yuen Long', 'North', 'Tai Po'}
EXTENDED = {'Sha Tin', 'Tsuen Wan', 'Kwai Tsing'}


def polygons(geometry):
    return [p for p in shapely.get_parts(geometry) if p.geom_type == 'Polygon']


def load_regions():
    districts = {f['properties']['District'].removesuffix(' District'):
                 shapely.make_valid(transform(PROJECT.transform, shape(f['geometry'])))
                 for f in json.loads((OUT / 'district_boundaries.json').read_text())['features']}
    raw = json.loads((ROOT / 'data/organized/supplementary/map_context/housing_subdistricts_eac_2019.json').read_text())
    small = {r['CACODE']: shapely.make_valid(shape(r['json_geometry'])) for r in raw['records']}
    tung_chung = shapely.union_all([small[f'T{i:02}'] for i in range(2, 7)]).intersection(districts['Islands'])
    tko = shapely.union_all([small[f'Q{i:02}'] for i in range(6, 30)]).intersection(districts['Sai Kung'])
    regions = {
        'Urban': shapely.union_all([districts[n] for n in sorted(URBAN)]),
        'Extended Urban': shapely.union_all([districts[n] for n in sorted(EXTENDED)] + [tung_chung, tko]),
        'New Territories': shapely.union_all([districts[n] for n in sorted(NEW_TERRITORIES)]),
        'Islands': districts['Islands'].difference(tung_chung),
    }
    # The form does not name rural Sai Kung; leave it unclassified rather than
    # silently equating the whole administrative district with Tseung Kwan O.
    outside = districts['Sai Kung'].difference(tko)
    land = shapely.make_valid(shapely.union_all([
        transform(PROJECT.transform, shape(f['geometry']))
        for f in json.loads((OUT / 'hong_kong_land.geojson').read_text())['features']]))
    return districts, regions, outside, land


def save_crosswalk(regions):
    estates = json.loads((ROOT / 'data/organized/core/estates/prh-estates.json').read_text())
    previous = {r['estate_name']: r['housing_district'] for r in csv.DictReader(
        (OUT / 'estate_housing_district_crosswalk.csv').open())}
    rows = []
    for estate in sorted(estates, key=lambda e: e['Estate Name']['en'].casefold()):
        name = estate['Estate Name']['en']
        lon, lat = estate['Estate Map Longitude'], estate['Estate Map Latitude']
        point = Point(*PROJECT.transform(lon, lat))
        hits = [n for n, g in regions.items() if g.covers(point)]
        assert len(hits) == 1, (name, hits)
        assert previous[name] == hits[0], (name, previous[name], hits)
        rows.append(dict(estate_name=name, source_administrative_district=estate['District Name']['en'],
                         housing_district=hits[0], latitude=lat, longitude=lon))
    assert len(rows) == 244
    with (OUT / 'estate_housing_district_crosswalk.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    features = [dict(type='Feature', properties={'housing_district': n, 'color': COLORS[n],
                'boundary_status': 'Derived from HAD districts and EAC 2019 town-area proxies'},
                geometry=mapping(transform(UNPROJECT.transform, g))) for n, g in regions.items()]
    (OUT / 'housing_district_boundaries.geojson').write_text(json.dumps(
        dict(type='FeatureCollection', features=features), ensure_ascii=False) + '\n')
    return rows


def install_overlay(axes, clip_id, rect, extent, regions, outside, land):
    """Replace district fills/outlines in the original Matplotlib SVG axes."""
    mx, my, mw, mh = rect
    x0, y0, x1, y1 = extent
    def xy(x, y):
        return mx + (x-x0)/(x1-x0)*mw, my + (y1-y)/(y1-y0)*mh
    def path_data(geometry):
        chunks = []
        for poly in polygons(geometry):
            for ring in [poly.exterior, *poly.interiors]:
                coords = [xy(x, y) for x, y in ring.coords]
                chunks.append('M ' + ' L '.join(f'{x:.7f} {y:.7f}' for x, y in coords) + ' Z')
        return ' '.join(chunks)

    for el in list(axes):
        styles = ' '.join(p.get('style', '') for p in el.iter(f'{{{NS}}}path'))
        # Remove both the administrative outlines and their numbered badges.
        if ('stroke: #485a65' in styles or 'stroke: #657680' in styles
                or styles in {'fill: #faf8ec', 'fill: #f0f2e7', 'fill: #f7eee0', 'fill: #e6eff2'}
                or el.get('id', '') in {f'text_{i}' for i in range(3, 21)}):
            axes.remove(el)
    group = ET.Element(f'{{{NS}}}g', {'id': 'housing-district-fills', 'clip-path': f'url(#{clip_id})'})
    # Neutral background makes rural Sai Kung visibly unclassified.
    ET.SubElement(group, f'{{{NS}}}path', {'d': path_data(land), 'fill': '#e8e6df', 'fill-rule': 'evenodd'})
    for name, geometry in regions.items():
        el = ET.SubElement(group, f'{{{NS}}}path', {'d': path_data(geometry.intersection(land)),
            'fill': COLORS[name], 'fill-rule': 'evenodd', 'data-housing-district': name})
        ET.SubElement(el, f'{{{NS}}}title').text = name
    axes.insert(0, group)
    outlines = ET.SubElement(axes, f'{{{NS}}}g', {'id': 'housing-district-overlay',
                          'clip-path': f'url(#{clip_id})'})
    for name, geometry in regions.items():
        ET.SubElement(outlines, f'{{{NS}}}path', {'d': path_data(geometry), 'fill': 'none',
            'stroke': '#354c5c', 'stroke-width': '0.85', 'data-housing-district': name})
    return outlines
