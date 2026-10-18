"""Draw a geographic Northern Link overlay and a separately typeset detail map.

Route reference: LegCo brief 9 July 2025, Annex A (PDF page 12).
The MTR SVG supplies the network connections, names and line colours.
All railway artwork is drawn afresh; no schematic symbols are stretched.
"""
from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import ImageFont
from pyproj import Transformer
from shapely.geometry import Point, box, shape
from shapely.ops import transform

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
NS = 'http://www.w3.org/2000/svg'
XLINK = 'http://www.w3.org/1999/xlink'
S = '{' + NS + '}'
ET.register_namespace('', NS)
ET.register_namespace('xlink', XLINK)
PAPER, INK = '#f7f6f2', '#233845'
MAGENTA, BLUE, BROWN = '#a40084', '#379ec9', '#9e3824'
OFFICIAL_URL = 'https://www.legco.gov.hk/yr2025/english/brief/tlb102002001p002_20250709-e.pdf'
SOURCE_URL = 'https://mtrnorthernlink.hk/images/pages/about/map_en.svg'


def node(parent, tag, **attrs):
    return ET.SubElement(parent, S + tag, {
        k.replace('_', '-'): str(v) for k, v in attrs.items()
    })


def text(parent, x, y, label, size=18, **attrs):
    el = node(parent, 'text', x=x, y=y, font_size=size,
              font_family='Arial, sans-serif', fill=INK, **attrs)
    el.text = label
    return el


def use(parent, target, **attrs):
    el = node(parent, 'use', **attrs)
    el.set('{' + XLINK + '}href', '#' + target)
    return el


svg = ET.parse(OUT / 'hong_kong_estates_hospitals_numbered.svg').getroot()
width, old_height = map(float, svg.get('viewBox').split()[2:])
base = svg.find(S + 'g[@id="precise-base-map"]')
points = svg.find(S + 'g[@id="exact-location-points"]')
assert len(points) == 288
original_points = ET.tostring(points)
original_base = ET.tostring(base)
features = json.loads((ROOT / 'data/organized/core/mtr/official_igeocom/railway_stations.geojson').read_text())['features']
project = Transformer.from_crs('EPSG:4326', 'EPSG:2326', always_xy=True)
bounds = [transform(project.transform, shape(f['geometry'])).bounds
          for f in json.loads((OUT / 'district_boundaries.json').read_text())['features']]
x0, y0 = min(b[0] for b in bounds) - 1600, min(b[1] for b in bounds) - 1600
x1, y1 = max(b[2] for b in bounds) + 1600, max(b[3] for b in bounds) + 1600
map_w, map_h = 869.76 * 2.7, 600.167364 * 2.7


def page_xy(easting, northing):
    return np.array((55 + (easting - x0) / (x1 - x0) * map_w,
                     160 + (y1 - northing) / (y1 - y0) * map_h))


def existing(name):
    p = next(f['properties'] for f in features if
             f['properties']['ENGLISHNAME'] == f'Mass Transit Railway {name} Station')
    return np.array((p['EASTING'], p['NORTHING']))


# Reference coordinates on the 1440 x 1080 rendering of Annex A. This is a
# geographic plan, unlike the highly generalised artwork in the source SVG.
control = {
    'Lo Wu': (865, 76), 'Lok Ma Chau': (468, 207),
    'Sheung Shui': (1005, 342), 'Fanling': (1087, 414),
    'Long Ping': (139, 803), 'Yuen Long': (230, 813),
    'Kam Sheung Road': (472, 923), 'Tai Wo': (1262, 773),
    'Tai Po Market': (1337, 827),
}
source_controls = np.c_[list(control.values()), np.ones(len(control))]
grid_controls = np.array([existing(name) for name in control])
registration = np.linalg.lstsq(source_controls, grid_controls, rcond=None)[0]
residuals = np.linalg.norm(source_controls @ registration - grid_controls, axis=1)


def reference_xy(x, y):
    return page_xy(*(np.array((x, y, 1)) @ registration))


def geographic_xy(longitude, latitude):
    x, y = page_xy(*project.transform(longitude, latitude))
    return (float(x), float(y), 'page')


stations = {}
for name in [*control, 'Tin Shui Wai']:
    stations[name] = dict(xy=page_xy(*existing(name)), proposed=False,
                          color=BROWN if name in ['Tin Shui Wai', 'Long Ping', 'Yuen Long', 'Kam Sheung Road'] else BLUE)
for name, p in {
    'Au Tau': (374, 686), 'Ngau Tam Mei': (447, 557),
    'San Tin': (566, 423), 'Kwu Tung': (763, 262),
    'Chau Tau': (565, 308), 'The Loop': (588, 153),
    'Huanggang Port': (499, 125),
}.items():
    stations[name] = dict(xy=reference_xy(*p), proposed=True, color=MAGENTA)
stations['Ngau Tam Mei depot'] = dict(xy=reference_xy(446, 627), proposed=True,
                                     color=MAGENTA, facility=True)

# Cubic Beziers traced from the geographic plan. Existing station endpoints
# snap to the local official station data. The control handles remain smooth;
# no triangle clipping, nonuniform scaling, or deformed station symbols.
routes = [
    dict(name='East Rail Line', color=BLUE, planned=False, commands=[
        ('M', 'Lo Wu'), ('C', (862, 118), (888, 169), (892, 223)),
        ('C', (899, 267), (951, 295), 'Sheung Shui'),
        ('C', (1039, 371), (1060, 397), 'Fanling'),
        ('C', (1130, 440), (1181, 440), (1205, 475)),
        ('C', (1240, 525), (1206, 595), (1195, 640)),
        ('C', (1179, 707), (1207, 738), 'Tai Wo'),
        ('C', (1290, 790), (1305, 821), 'Tai Po Market'),
        ('C', geographic_xy(114.179, 22.441), geographic_xy(114.181, 22.435), geographic_xy(114.192, 22.428)),
        ('C', geographic_xy(114.201, 22.425), geographic_xy(114.203, 22.419),
         (*page_xy(*existing('University')), 'page')),
    ]),
    dict(name='Lok Ma Chau branch', color=BLUE, planned=False, commands=[
        ('M', 'Lok Ma Chau'), ('C', (515, 191), (546, 207), (558, 242)),
        ('C', (565, 286), (578, 312), (627, 300)),
        ('C', (673, 288), (719, 265), 'Kwu Tung'),
        ('C', (819, 261), (869, 281), (908, 268)),
        ('C', (940, 267), (971, 308), 'Sheung Shui'),
    ]),
    dict(name='Tuen Ma Line', color=BROWN, planned=False, commands=[
        ('M', (*page_xy(*existing('Siu Hong')), 'page')),
        ('C', geographic_xy(113.981, 22.428), geographic_xy(113.987, 22.445), 'Tin Shui Wai'),
        ('C', (20, 799), (95, 801), 'Long Ping'),
        ('C', (174, 803), (198, 811), 'Yuen Long'),
        ('C', (286, 815), (342, 793), (381, 823)),
        ('C', (422, 850), (448, 890), 'Kam Sheung Road'),
        ('C', (492, 955), (508, 980), (524, 1008)),
    ]),
    dict(name='Northern Link main line', color=MAGENTA, planned=True, commands=[
        ('M', 'Kam Sheung Road'), ('C', (439, 874), (391, 807), (371, 741)),
        ('C', (368, 725), (372, 706), 'Au Tau'),
        ('C', (387, 640), (416, 585), 'Ngau Tam Mei'),
        ('C', (482, 516), (535, 462), 'San Tin'),
        ('C', (606, 380), (652, 312), (681, 288)),
        ('C', (710, 267), (738, 265), 'Kwu Tung'),
    ]),
    dict(name='Northern Link spur', color=MAGENTA, planned=True, spur=True, commands=[
        ('M', 'San Tin'), ('C', (590, 389), (617, 355), (598, 336)),
        ('C', (586, 322), (573, 316), 'Chau Tau'),
        ('C', (539, 280), (532, 254), (552, 234)),
        ('C', (567, 219), (609, 209), (619, 187)),
        ('C', (628, 172), (606, 157), 'The Loop'),
        ('C', (570, 133), (562, 132), (552, 141)),
        ('C', (542, 153), (514, 137), 'Huanggang Port'),
    ]),
    dict(name='Depot connection', color=MAGENTA, planned=True, spur=True, depot=True, commands=[
        ('M', (392, 641)), ('L', (416, 655)), ('L', (431, 651)), ('L', (446, 627)),
    ]),
]

locations = []
for group in points:
    circle = group.find(S + 'circle')
    label = group.find(S + 'text')
    locations.append(dict(xy=np.array([float(circle.get('cx')), float(circle.get('cy'))]),
                          number=label.text, color=circle.get('fill'), id=group.get('id')))


def resolve(p):
    if isinstance(p, str):
        return stations[p]['xy']
    if len(p) == 3:
        return np.array(p[:2])
    return reference_xy(*p)


def draw_routes(parent, mapping, detail=False):
    g = node(parent, 'g', id='rail-routes-detail' if detail else 'rail-routes-overview')
    for route in routes:
        commands = []
        for command in route['commands']:
            coordinates = [mapping(resolve(p)) for p in command[1:]]
            commands.append(command[0] + ' ' + ' '.join(f'{x:.3f},{y:.3f}' for x, y in coordinates))
        path = ' '.join(commands)
        w = (5.6 if route['planned'] else 3.8) if detail else (2.5 if route['planned'] else 1.8)
        if route.get('spur'):
            w *= .74
        attrs = dict(d=path, fill='none', stroke_linecap='round', stroke_linejoin='round')
        node(g, 'path', **attrs, stroke=PAPER, stroke_width=w + (3 if detail else 1.6))
        colored = node(g, 'path', **attrs, stroke=route['color'], stroke_width=w)
        if route['planned']:
            colored.set('stroke-dasharray', ('5 6' if route.get('spur') else '11 7') if detail else '3 2')
    return g


PREFERRED = {
    'Tin Shui Wai': (-135, 40), 'Long Ping': (-100, 47), 'Yuen Long': (30, 40),
    'Kam Sheung Road': (25, 40), 'Au Tau': (-100, -10),
    'Ngau Tam Mei': (-170, -10), 'San Tin': (35, 35),
    'Kwu Tung': (0, -38), 'Chau Tau': (-130, 5),
    'The Loop': (28, -20), 'Huanggang Port': (-155, -25),
    'Lok Ma Chau': (-165, -15), 'Lo Wu': (12, -24),
    'Sheung Shui': (45, -45), 'Fanling': (45, 15),
    'Tai Wo': (30, -25), 'Tai Po Market': (30, 30),
    'Ngau Tam Mei depot': (30, 10),
}


def draw_stations(parent, mapping, viewport, detail=False):
    g = node(parent, 'g', id='rail-stations-detail' if detail else 'rail-stations-overview')
    visible = {name: s for name, s in stations.items()
               if box(*viewport).buffer(-12).contains(Point(mapping(s['xy'])))}
    for name, station in visible.items():
        x, y = mapping(station['xy'])
        if station.get('facility'):
            node(g, 'rect', x=x-(9 if detail else 4), y=y-(6 if detail else 3),
                 width=18 if detail else 8, height=12 if detail else 6,
                 rx=2 if detail else 1, fill=PAPER, stroke=MAGENTA,
                 stroke_width=1.8 if detail else .9)
            continue
        r = (7.5 if detail else 3.7)
        node(g, 'circle', cx=x, cy=y, r=r + (2.4 if detail else 1.1), fill=PAPER)
        node(g, 'circle', cx=x, cy=y, r=r, fill=PAPER,
             stroke=BLUE if name == 'Kwu Tung' else station['color'], stroke_width=2.5 if detail else 1.4)
        if name in ['Kwu Tung', 'Kam Sheung Road']:
            node(g, 'circle', cx=x, cy=y, r=r * .4, fill=MAGENTA)
        node(g, 'title').text = name
    return visible


def draw_locations(parent, mapping, viewport):
    g = node(parent, 'g', id='numbered-locations-detail')
    for loc in locations:
        x, y = mapping(loc['xy'])
        if not (viewport[0]+12 < x < viewport[2]-12 and viewport[1]+12 < y < viewport[3]-12):
            continue
        el = node(g, 'g', id='detail-' + loc['id'])
        node(el, 'circle', cx=x, cy=y, r=10, fill=loc['color'], stroke=PAPER, stroke_width=1)
        text(el, x, y + .3, loc['number'], 10.5 if len(loc['number']) > 2 else 11.3,
             style='fill:white', text_anchor='middle', dominant_baseline='central', font_weight='bold')


layout_report = {}


def draw_labels(parent, mapping, viewport, visible, detail=False):
    size = 22 if detail else 10.6
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', round(size))
    padding = 4 if detail else 2
    bounds = box(*viewport).buffer(-14)
    occupied = []
    marker_radius = 11.4 if detail else 7
    marker_obstacles = [Point(mapping(loc['xy'])).buffer(marker_radius) for loc in locations]
    station_obstacles = [Point(mapping(station['xy'])).buffer(12 if detail else 5) for station in visible.values()]
    g = node(parent, 'g', id='station-labels-detail' if detail else 'station-labels-overview')
    names = list(visible)
    if not detail:
        names = [name for name in names if visible[name]['proposed'] or name == 'Kam Sheung Road']
    # Resolve the crowded urban stations first, then rural labels.
    names.sort(key=lambda name: 0 if name in ['Long Ping', 'Yuen Long', 'Tin Shui Wai', 'Sheung Shui', 'Fanling'] else 1)
    report = []
    for name in names:
        x, y = mapping(visible[name]['xy'])
        tw = font.getlength(name)
        th = size * 1.1
        factor = 1 if detail else .49
        preferred = np.array(PREFERRED[name]) * factor
        candidates = [preferred]
        for distance in [22, 40, 65, 95, 130]:
            gap = distance * factor
            candidates.extend([(gap, -th/2), (-tw-gap, -th/2), (-tw/2, -gap-th),
                               (-tw/2, gap), (gap, -gap-th), (-tw-gap, -gap-th),
                               (gap, gap), (-tw-gap, gap)])
        best = None
        for i, (dx, dy) in enumerate(candidates):
            rect = box(x+dx-padding, y+dy-padding, x+dx+tw+padding, y+dy+th+padding)
            marker_hits = sum(rect.intersects(obstacle) for obstacle in marker_obstacles)
            station_hits = sum(rect.intersects(obstacle) for obstacle in station_obstacles)
            overlaps = sum(rect.intersection(other).area for other in occupied)
            score = (marker_hits * 1e6 + station_hits * 1e6 + overlaps * 1e5
                     + (0 if bounds.contains(rect) else 1e10)
                     + np.linalg.norm(np.array([dx, dy]) - preferred) * .7
                     + np.linalg.norm([dx+tw/2, dy+th/2]) * .2 + i*.01)
            if best is None or score < best[0]:
                best = (score, dx, dy, rect, marker_hits, station_hits, overlaps)
        _, dx, dy, rect, mh, sh, overlap = best
        occupied.append(rect)
        # Quiet leader lines connect labels that must sit away from busy points.
        lx = min(max(x, x+dx), x+dx+tw)
        ly = min(max(y, y+dy), y+dy+th)
        distance = np.hypot(lx-x, ly-y)
        if distance > (24 if detail else 10):
            direction = np.array([lx-x, ly-y]) / distance
            start = np.array([x, y]) + direction * (11 if detail else 5)
            node(g, 'path', d=f'M {start[0]:.3f},{start[1]:.3f} L {lx:.3f},{ly:.3f}',
                 fill='none', stroke='#627883', stroke_width=.9 if detail else .5)
        text(g, x+dx, y+dy+size*.87, name, size, font_weight='bold',
             stroke=PAPER, stroke_width=5 if detail else 2.6,
             stroke_linejoin='round', paint_order='stroke fill')
        report.append(dict(name=name, marker_overlaps=mh, station_overlaps=sh,
                           label_overlap_area=overlap, within_map=bounds.contains(rect)))
    layout_report['detail' if detail else 'overview'] = report


def legend(parent, x, y):
    for dx, color, label, dashed in [(0, MAGENTA, 'Northern Link: proposed main line', True),
                                     (690, BLUE, 'East Rail Line', False),
                                     (1110, BROWN, 'Tuen Ma Line', False)]:
        p = node(parent, 'path', d=f'M {x+dx},{y-6} h 62', stroke=color,
                 stroke_width=5, fill='none', stroke_linecap='round')
        if dashed:
            p.set('stroke-dasharray', '10 7')
        text(parent, x+dx+77, y, label, 21)
    for dx, color, label in [(1535, '#16834b', 'Estates'), (1710, '#d7353f', 'Hospitals')]:
        node(parent, 'circle', cx=x+dx, cy=y-7, r=6, fill=color)
        text(parent, x+dx+17, y, label, 21)


# Overview: keep every original marker and the complete base unchanged.
defs = node(svg, 'defs', id='northern-link-definitions')
clip = node(defs, 'clipPath', id='rail-overview-clip')
node(clip, 'rect', x=55, y=160, width=map_w, height=map_h)
overview = ET.Element(S+'g', id='northern-link-geographic-overlay',
                      attrib={'clip-path': 'url(#rail-overview-clip)'})
identity = lambda p: p
overview_view = (55, 160, 55+map_w, 160+map_h)
draw_routes(overview, identity)
draw_stations(overview, identity, overview_view)
svg.insert(list(svg).index(points), overview)
overview_labels = node(svg, 'g', id='overview-railway-labels')
visible = {name: station for name, station in stations.items()}
draw_labels(overview_labels, identity, overview_view, visible)

# The detail has its own paper-sized line weights, rings and label layout.
added_height = 1480
new_height = old_height + added_height
svg.set('height', str(round(new_height)))
svg.set('viewBox', f'0 0 {width:g} {new_height:.2f}')
svg.find(S+'rect').set('height', str(new_height))
for el in svg.findall(S+'text'):
    if el.text == 'HONG KONG / ESTATES & HOSPITALS':
        el.text = 'HONG KONG / ESTATES, HOSPITALS & NORTHERN LINK'
        el.set('font-size', '35')
    elif el.text and el.text.startswith('Green: estates'):
        el.text = '244 estates · 44 hospitals · Northern Link main line and spur · Northern New Territories detail below'
    if float(el.get('y', '0')) > old_height-100:
        el.set('y', str(float(el.get('y'))+added_height))
svg.find(S+'g[@id="location-name-legend"]').set('transform', f'translate(0 {added_height})')

panel_top = 1885
text(svg, 55, panel_top+10, 'NORTHERN NEW TERRITORIES', 31, font_weight='bold')
text(svg, 55, panel_top+43, 'Northern Link main line and spur in their geographic setting', 21)
legend(svg, 55, panel_top+85)
panel_x, panel_y, panel_w, panel_h = 55, panel_top+112, map_w, 1170
viewport = (panel_x, panel_y, panel_x+panel_w, panel_y+panel_h)
extent_names = ['Tin Shui Wai', 'Kam Sheung Road', 'Huanggang Port', 'Lo Wu', 'Tai Po Market']
extent = np.array([stations[name]['xy'] for name in extent_names])
minimum, maximum = extent.min(axis=0), extent.max(axis=0)
zoom = min(panel_w/(maximum[0]-minimum[0]+125), panel_h/(maximum[1]-minimum[1]+85))
center = (minimum+maximum)/2
translation = np.array((panel_x+panel_w/2, panel_y+panel_h/2)) - center*zoom
mapping = lambda p: np.array(p)*zoom+translation
panel_clip = node(defs, 'clipPath', id='northern-detail-clip')
node(panel_clip, 'rect', x=panel_x, y=panel_y, width=panel_w, height=panel_h)
panel = node(svg, 'g', id='northern-detail', clip_path='url(#northern-detail-clip)')
node(panel, 'rect', x=panel_x, y=panel_y, width=panel_w, height=panel_h, fill=PAPER)
use(panel, 'precise-base-map', transform=f'translate({translation[0]} {translation[1]}) scale({zoom})', opacity='.65')
draw_routes(panel, mapping, detail=True)
detail_stations = draw_stations(panel, mapping, viewport, detail=True)
draw_locations(panel, mapping, viewport)
draw_labels(panel, mapping, viewport, detail_stations, detail=True)
decorations = node(panel, 'g', id='detail-scale-and-north')
bar_x, bar_y = panel_x+38, panel_y+65
bar_length = 3000 * map_w/(x1-x0)*zoom
node(decorations, 'path', d=f'M {bar_x},{bar_y-5} v 10 M {bar_x},{bar_y} h {bar_length} M {bar_x+bar_length},{bar_y-5} v 10',
     stroke=INK, stroke_width=1.8, fill='none')
text(decorations, bar_x+bar_length/2, bar_y-12, '3 km', 17,
     text_anchor='middle', stroke=PAPER, stroke_width=3, paint_order='stroke fill')
nx, ny = panel_x+panel_w-48, panel_y+45
node(decorations, 'path', d=f'M {nx},{ny+34} V {ny} l -5,13 l 5,-3 l 5,3 Z', fill=INK, stroke=INK, stroke_width=1.5)
text(decorations, nx, ny+57, 'N', 19, text_anchor='middle', font_weight='bold')
node(svg, 'rect', x=panel_x, y=panel_y, width=panel_w, height=panel_h,
     fill='none', stroke='#b0bec4', stroke_width=1)
text(svg, 55, panel_y+panel_h+33,
     'Dashed magenta: proposed railway · Fine dashed branch: spur line / depot access · Small rings: station locations', 18)
text(svg, 55, panel_y+panel_h+63,
     'Route reference: official Northern Link alignment plan, Annex A, July 2025. Proposed alignment and station positions are indicative.', 17)

# Standalone detail sheet is easy to inspect without opening the long index page.
detail = ET.Element(S+'svg', width='2460', height='1460', viewBox='0 0 2460 1460', version='1.1')
node(detail, 'rect', width=2460, height=1460, fill=PAPER)
detail_defs = node(detail, 'defs')
for original_defs in svg.findall(S+'defs'):
    detail_defs.append(deepcopy(original_defs))
detail_defs.append(deepcopy(base))
container = node(detail, 'g', transform=f'translate(0 {-panel_top+35})')
for el in list(svg):
    if el is panel or (el.tag == S+'text' and panel_top <= float(el.get('y', '0')) <= panel_y+panel_h+64):
        container.append(deepcopy(el))
    elif el.tag == S+'path' and panel_top <= float(el.get('y', '-1')):
        container.append(deepcopy(el))
# Legend paths have no y attribute and are copied explicitly.
for el in svg.findall(S+'path'):
    if el.get('d', '').startswith('M ') and str(panel_top+85-6) in el.get('d', ''):
        container.append(deepcopy(el))
for el in svg.findall(S+'circle'):
    if float(el.get('cy', '-1')) == panel_top+85-7:
        container.append(deepcopy(el))

metadata = dict(version=2, schematic_reference=SOURCE_URL, geographic_reference=OFFICIAL_URL,
                reference_page=12, method='Redrawn SVG centerlines from geographic plan; uniform circular symbols; separate label layout per view',
                grid_crs='EPSG:2326', geographic_plan_fit_rms_m=float(np.sqrt(np.mean(residuals**2))),
                proposed_positions='Indicative positions digitised from official plan; not surveyed',
                existing_station_positions='Local official railway station dataset; exact original coordinates',
                anchors=[dict(name=name, reference_xy=xy, fit_residual_m=float(error)) for (name, xy), error in zip(control.items(), residuals)],
                label_layout=layout_report)
node(svg, 'metadata', id='northern-link-registration').text = json.dumps(metadata)
node(detail, 'metadata').text = json.dumps(metadata)
assert ET.tostring(points) == original_points
assert ET.tostring(base) == original_base
assert all(not e.tag == S+'image' for e in svg.iter())
for document in [svg, detail]:
    ids = [e.get('id') for e in document.iter() if e.get('id')]
    assert len(ids) == len(set(ids)), 'Duplicate identifiers'
    for el in document.iter():
        for k, v in el.attrib.items():
            if k.endswith('href') and v.startswith('#'):
                assert v[1:] in ids, v
ET.ElementTree(svg).write(OUT/'hong_kong_estates_hospitals_northern_link_overlay.svg', encoding='utf-8', xml_declaration=True)
ET.ElementTree(detail).write(OUT/'hong_kong_northern_link_detail.svg', encoding='utf-8', xml_declaration=True)
(OUT/'northern_link_overlay_registration.json').write_text(json.dumps(metadata, indent=2)+'\n')
for view, report in layout_report.items():
    print(view, 'labels', len(report), 'marker overlaps', sum(r['marker_overlaps'] for r in report),
          'label overlap area', sum(r['label_overlap_area'] for r in report),
          'outside view', sum(not r['within_map'] for r in report))
print('Geographic plan fit RMS:', round(metadata['geographic_plan_fit_rms_m']), 'm; existing stations use exact official coordinates')
print('Full map viewBox:', svg.get('viewBox'))
