"""Render both maps from the original FGDB and official HAD district polygons."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/hk-pedestrian-matplotlib')
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch, Polygon
from pyproj import Transformer
import shapely
from shapely.geometry import shape
from shapely.ops import transform
from pyogrio.raw import read

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
plt.rcParams.update({'svg.fonttype': 'none', 'path.simplify': False, 'font.family': 'DejaVu Sans'})
project = Transformer.from_crs('EPSG:4326', 'EPSG:2326', always_xy=True)
districts = []
for f in json.loads((OUT / 'district_boundaries.json').read_text())['features']:
    districts.append((f['properties']['District'].replace(' District', ''),
                      transform(project.transform, shape(f['geometry']))))
districts.sort(key=lambda d: d[0])
land = shapely.union_all([
    transform(project.transform, shape(f['geometry']))
    for f in json.loads((OUT / 'hong_kong_land.geojson').read_text())['features']
])
land = shapely.make_valid(land)
source = '/vsizip/' + str(ROOT / 'data/organized/core/pedestrian/3D_Pedestrian_Network_FGDB.zip') + '/3DPN_P2.gdb'
_, _, wkb, _ = read(source, layer='PedestrianRoute', columns=[])
geometries = shapely.from_wkb(wkb)
assert len(geometries) == 465892

def route_path(geoms):
    parts = shapely.get_parts(geoms)
    coords = shapely.get_coordinates(parts)
    counts = shapely.get_num_coordinates(parts)
    codes = np.full(len(coords), MPath.LINETO, dtype=np.uint8)
    codes[np.r_[0, np.cumsum(counts)[:-1]]] = MPath.MOVETO
    return MPath(coords, codes), len(coords)

bounds = np.array([g.bounds for _, g in districts])
x0, y0 = bounds[:, :2].min(axis=0) - 1600
x1, y1 = bounds[:, 2:].max(axis=0) + 1600
stats = {}
for mode in ['overview', 'precise']:
    print('Rendering', mode, flush=True)
    tolerance = 35 if mode == 'overview' else 0
    geoms = shapely.simplify(geometries, tolerance, preserve_topology=True) if tolerance else geometries
    path, nvertices = route_path(geoms)
    fig = plt.figure(figsize=(16, 12), facecolor='#f7f6f2')
    ax = fig.add_axes([.035, .15, .755, .73])
    ax.set_facecolor('#e6eff2')
    for i, (_, g) in enumerate(districts):
        clipped = shapely.intersection(shapely.make_valid(g), land)
        polygons = [p for p in shapely.get_parts(clipped) if p.geom_type == 'Polygon']
        for poly in polygons:
            ax.add_patch(Polygon(np.asarray(poly.exterior.coords), closed=True,
                                 facecolor=['#faf8ec', '#f0f2e7', '#f7eee0'][i % 3],
                                 edgecolor='none', zorder=1))
            for hole in poly.interiors:
                ax.add_patch(Polygon(np.asarray(hole.coords), facecolor='#e6eff2', edgecolor='none', zorder=1))
    network = PathPatch(path, fill=False, edgecolor='#c45428' if mode == 'overview' else '#c04b23',
                        linewidth=.34 if mode == 'overview' else .105,
                        alpha=.58 if mode == 'overview' else .80, zorder=2)
    network.set_gid('pedestrian-path-overlay')
    ax.add_patch(network)
    for poly in shapely.get_parts(land):
        if poly.geom_type == 'Polygon':
            xy = np.asarray(poly.exterior.coords)
            ax.plot(xy[:, 0], xy[:, 1], color='#809299', lw=.35, zorder=2.5)
    for i, (name, g) in enumerate(districts, 1):
        polygons = list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]
        for poly in polygons:
            for ring in [poly.exterior, *poly.interiors]:
                xy = np.asarray(ring.coords)
                ax.plot(xy[:, 0], xy[:, 1], color='#485a65', lw=.65, zorder=3)
        on_land = [p for p in shapely.get_parts(shapely.intersection(shapely.make_valid(g), land)) if p.geom_type == 'Polygon']
        anchor = max(on_land or polygons, key=lambda p: p.area).representative_point()
        ax.text(anchor.x, anchor.y, str(i), ha='center', va='center', fontsize=9,
                color='#233845', fontweight='bold', zorder=4,
                bbox=dict(boxstyle='circle,pad=.25', fc='white', ec='#657680', lw=.6, alpha=.94))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    # Scale and north arrow use the same projected metre coordinates as the paths.
    sx, sy = x0 + 2700, y0 + 2200
    ax.plot([sx, sx + 10000], [sy, sy], color='#233845', lw=2, zorder=5)
    for x in [sx, sx + 5000, sx + 10000]:
        ax.plot([x, x], [sy - 250, sy + 250], color='#233845', lw=1, zorder=5)
    ax.text(sx + 5000, sy + 650, '10 km', ha='center', fontsize=9)
    ax.annotate('N', xy=(x1 - 2400, y1 - 5500), xytext=(x1 - 2400, y1 - 8500),
                ha='center', fontsize=12, fontweight='bold', arrowprops=dict(arrowstyle='-|>', color='#233845'))
    fig.text(.045, .945, 'HONG KONG / PEDESTRIAN NETWORK', fontsize=23, weight='bold', color='#233845')
    subtitle = 'Overview · simplified route bends, broader strokes' if mode == 'overview' else 'Precise · every original route vertex, aligned in HK1980 coordinates'
    fig.text(.045, .912, subtitle, fontsize=12, color='#526875')
    fig.text(.815, .85, '18 DISTRICTS', fontsize=12, weight='bold', color='#233845')
    for i, (name, _) in enumerate(districts, 1):
        fig.text(.815, .815 - (i - 1) * .028, f'{i:02d}  {name}', fontsize=9, color='#233845')
    fig.text(.815, .29, 'Orange  Pedestrian routes\nSlate     District outlines\n\n465,892 route features\nTop-down view; Z flattened', fontsize=10, color='#526875', linespacing=1.65, va='top')
    fig.text(.045, .09, 'SOURCE  Local pedestrian FGDB · Home Affairs Department districts · OpenStreetMap land via bmkor/hk_osm_map', fontsize=9, color='#526875')
    fig.text(.045, .068, 'CRS  Hong Kong 1980 Grid (EPSG:2326) · official district polygons transformed from WGS84', fontsize=9, color='#526875')
    note = 'Routes simplified with 35 m tolerance; all route features retained. Intended for a general view.' if tolerance else 'Original XY vertices retained without simplification. Finite image resolution and stroke width limit visible detail.'
    fig.text(.045, .046, note, fontsize=9, color='#526875')
    stem = OUT / f'hong_kong_paths_{mode}'
    fig.savefig(str(stem) + '.png', dpi=220 if tolerance else 400, facecolor=fig.get_facecolor())
    fig.savefig(str(stem) + '.svg', facecolor=fig.get_facecolor())
    plt.close(fig)
    stats[mode] = {'routes': len(geoms), 'rendered_vertices': nvertices, 'simplification_metres': tolerance,
                   'png_pixels': [3520, 2640] if tolerance else [6400, 4800]}
    print(stats[mode], flush=True)
(OUT / 'render_summary.json').write_text(json.dumps(stats, indent=2) + '\n')
(OUT / 'README.md').write_text('''# Hong Kong pedestrian network maps

Four deliverables: `hong_kong_paths_overview.{svg,png}` and `hong_kong_paths_precise.{svg,png}`.
Each includes the district map and path overlay. SVG groups marked `pedestrian-path-overlay`
contain the network as vector geometry; SVG text remains text.

All 465,892 source routes are included in both versions. Overview simplifies route bends
with 35 m Douglas–Peucker tolerance and uses thicker lines. Precise retains every original
XY vertex. Elevation is flattened; overlapping paths at different heights appear together.
Districts are projected from WGS84 into the routes' native EPSG:2326 grid. No path snapping,
warping, or clipping to district boundaries is performed. Alignment is limited by the input
datasets' accuracy and vintage; this is not a surveyed accuracy guarantee. District outlines
are administrative polygons and include marine areas. Land fills use a separate historical
OpenStreetMap-derived coastline; reclamation may differ from the newer path data. Coastline
geometry affects only the background, never path coordinates.

Boundary source: https://www.had.gov.hk/psi/hong-kong-administrative-boundaries/hksar_18_district_boundary.json
Catalogue: https://data.gov.hk/en-data/dataset/hk-had-json1-hong-kong-administrative-boundaries
Downloaded 2026-10-12. The downloaded JSON is preserved alongside the outputs.
Land source: https://github.com/bmkor/hk_osm_map/blob/master/Hong_Kong.geojson
Land attribution: OpenStreetMap contributors (https://www.openstreetmap.org/copyright).

Reproduce from repository root: `.venv/bin/python analysis/maps/render_maps.py`
Packages: numpy, pyogrio, shapely, pyproj, matplotlib, pillow.
''')
