"""District terrain map and separate feature overlays on the full precise network."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/hk-pedestrian-matplotlib')
from pathlib import Path
import json
import zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LightSource, Normalize
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch, Polygon
from pyproj import Transformer
from pyogrio.raw import read
import shapely
from shapely.geometry import shape
from shapely.ops import transform

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
SERIES = OUT / 'feature_series'
SERIES.mkdir(exist_ok=True)
plt.rcParams.update({'svg.fonttype': 'none', 'path.simplify': False, 'font.family': 'DejaVu Sans'})
project = Transformer.from_crs(4326, 2326, always_xy=True)
districts = sorted([(f['properties']['District'].replace(' District', ''),
                     shapely.make_valid(transform(project.transform, shape(f['geometry']))))
                    for f in json.loads((OUT / 'district_boundaries.json').read_text())['features']])
land = shapely.make_valid(shapely.union_all([
    transform(project.transform, shape(f['geometry']))
    for f in json.loads((OUT / 'hong_kong_land.geojson').read_text())['features']]))
bb = np.array([g.bounds for _, g in districts])
x0, y0 = bb[:, :2].min(axis=0) - 1600
x1, y1 = bb[:, 2:].max(axis=0) + 1600

def line_path(geoms):
    parts = shapely.get_parts(geoms)
    coords = shapely.get_coordinates(parts)
    codes = np.full(len(coords), MPath.LINETO, dtype=np.uint8)
    if len(coords):
        codes[np.r_[0, np.cumsum(shapely.get_num_coordinates(parts))[:-1]]] = MPath.MOVETO
    return MPath(coords, codes)

def land_path():
    vertices, codes = [], []
    for poly in shapely.get_parts(land):
        if poly.geom_type != 'Polygon':
            continue
        poly = shapely.geometry.polygon.orient(poly)
        for ring in [poly.exterior, *poly.interiors]:
            xy = np.asarray(ring.coords)
            code = np.full(len(xy), MPath.LINETO, dtype=np.uint8)
            code[0] = MPath.MOVETO; code[-1] = MPath.CLOSEPOLY
            vertices.append(xy); codes.append(code)
    return MPath(np.concatenate(vertices), np.concatenate(codes))

def canvas(title, subtitle, terrain=False):
    fig = plt.figure(figsize=(16, 12), facecolor='#f7f6f2')
    ax = fig.add_axes([.035, .15, .755, .73])
    ax.set_facecolor('#e6eff2')
    for i, (_, g) in enumerate(districts):
        for poly in shapely.get_parts(shapely.intersection(g, land)):
            if poly.geom_type != 'Polygon':
                continue
            ax.add_patch(Polygon(np.asarray(poly.exterior.coords), facecolor='#f0f1e7' if terrain else
                                 ['#faf8ec', '#f0f2e7', '#f7eee0'][i % 3], edgecolor='none', zorder=1))
            for hole in poly.interiors:
                ax.add_patch(Polygon(np.asarray(hole.coords), facecolor='#e6eff2', edgecolor='none', zorder=1))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    fig.text(.045, .945, title, fontsize=23, weight='bold', color='#233845')
    fig.text(.045, .912, subtitle, fontsize=12, color='#526875')
    fig.text(.815, .85, '18 DISTRICTS', fontsize=12, weight='bold', color='#233845')
    for i, (name, _) in enumerate(districts, 1):
        fig.text(.815, .815 - (i - 1) * .021, f'{i:02d}  {name}', fontsize=9, color='#233845')
    return fig, ax

def boundaries(ax):
    for poly in shapely.get_parts(land):
        if poly.geom_type == 'Polygon':
            xy = np.asarray(poly.exterior.coords)
            ax.plot(xy[:, 0], xy[:, 1], color='#809299', lw=.35, zorder=3)
    for i, (_, g) in enumerate(districts, 1):
        for poly in shapely.get_parts(g):
            if poly.geom_type != 'Polygon':
                continue
            for ring in [poly.exterior, *poly.interiors]:
                xy = np.asarray(ring.coords)
                ax.plot(xy[:, 0], xy[:, 1], color='#485a65', lw=.65, zorder=4)
        polys = [p for p in shapely.get_parts(shapely.intersection(g, land)) if p.geom_type == 'Polygon']
        anchor = max(polys, key=lambda p: p.area).representative_point()
        ax.text(anchor.x, anchor.y, str(i), ha='center', va='center', fontsize=9, color='#233845',
                weight='bold', zorder=6, bbox=dict(boxstyle='circle,pad=.25', fc='white', ec='#657680', lw=.6, alpha=.94))
    sx, sy = x0 + 2700, y0 + 2200
    ax.plot([sx, sx + 10000], [sy, sy], color='#233845', lw=2, zorder=6)
    for x in [sx, sx + 5000, sx + 10000]:
        ax.plot([x, x], [sy - 250, sy + 250], color='#233845', lw=1, zorder=6)
    ax.text(sx + 5000, sy + 650, '10 km', ha='center', fontsize=9)
    ax.annotate('N', xy=(x1 - 2400, y1 - 5500), xytext=(x1 - 2400, y1 - 8500),
                ha='center', fontsize=12, weight='bold', arrowprops=dict(arrowstyle='-|>', color='#233845'))

def footer(fig, source, note):
    fig.text(.045, .09, source, fontsize=9, color='#526875')
    fig.text(.045, .068, 'CRS  Hong Kong 1980 Grid (EPSG:2326) · vector district outlines projected from WGS84', fontsize=9, color='#526875')
    fig.text(.045, .046, note, fontsize=9, color='#526875')

def save(fig, stem):
    fig.savefig(str(stem) + '.svg', facecolor=fig.get_facecolor())
    fig.savefig(str(stem) + '_preview.png', dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

def terrain_map():
    print('Reading terrain ASCII and averaging 4 x 4 native cells for display', flush=True)
    with zipfile.ZipFile(ROOT / 'data/organized/supplementary/terrain/Whole_HK_DTM_5m.zip') as z:
        with z.open('Whole_HK_DTM_5m.asc') as f:
            header = {}
            for _ in range(6):
                key, value = f.readline().split(); header[key.decode().lower()] = float(value)
            cols, rows = int(header['ncols']), int(header['nrows'])
            factor = 4
            # Only outer edge cells are trimmed; 5 m south / 15 m east are outside HK land.
            out_rows, out_cols = rows // factor, cols // factor
            sums = np.zeros((out_rows, out_cols), dtype=np.float32)
            counts = np.zeros_like(sums, dtype=np.uint8)
            native_min, native_max, nodata_count = float('inf'), float('-inf'), 0
            for row in range(rows):
                values = np.fromstring(f.readline().decode('ascii'), sep=' ', dtype=np.float32)
                assert len(values) == cols, (row, len(values))
                valid = np.isfinite(values) & (values != header['nodata_value'])
                nodata_count += int((~valid).sum())
                if valid.any():
                    native_min = min(native_min, float(values[valid].min()))
                    native_max = max(native_max, float(values[valid].max()))
                if row >= out_rows * factor:
                    continue
                v = values[:out_cols * factor].reshape(out_cols, factor)
                ok = valid[:out_cols * factor].reshape(out_cols, factor)
                sums[row // factor] += np.where(ok, v, 0).sum(axis=1)
                counts[row // factor] += ok.sum(axis=1).astype(np.uint8)
    elevation = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    spacing = header['cellsize'] * factor
    north = header['yllcorner'] + rows * header['cellsize']
    extent = [header['xllcorner'], header['xllcorner'] + out_cols * spacing,
              north - out_rows * spacing, north]
    cmap = LinearSegmentedColormap.from_list('hk-elevation',
        ['#dcebd0', '#9cbf83', '#739960', '#b8ad7c', '#b28d61', '#8e6c54', '#ddd8cd'])
    norm = Normalize(vmin=0, vmax=1000)
    rgba = cmap(norm(elevation)).astype(np.float32)
    shade = LightSource(azdeg=315, altdeg=45).hillshade(elevation, vert_exag=1, dx=spacing, dy=spacing)
    rgba[:, :, :3] *= (.65 + .35 * shade[:, :, None])
    rgba[:, :, 3] = (counts > 0)
    fig, ax = canvas('HONG KONG / TERRAIN ELEVATION', '5 m source DTM · elevation colour + shaded relief · district outlines', terrain=True)
    img = ax.imshow(rgba, extent=extent, origin='upper', interpolation='nearest', zorder=2)
    img.set_gid('dtm-elevation-raster')
    img.set_clip_path(PathPatch(land_path(), transform=ax.transData))
    boundaries(ax)
    fig.text(.815, .415, 'ELEVATION', fontsize=12, weight='bold', color='#233845')
    cax = fig.add_axes([.823, .23, .02, .16])
    bar = fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
    bar.set_label('metres', fontsize=10); bar.set_ticks([0, 200, 400, 600, 800, 1000])
    fig.text(.815, .18, '20 m display cells\n(mean of 4 × 4 source cells)\nNW illumination · no exaggeration', fontsize=9, color='#526875', va='top')
    footer(fig, 'SOURCE  Whole_HK_DTM_5m.zip · HAD districts · © OpenStreetMap contributors (coastline)',
           'Elevation raster embedded in SVG; district outlines remain vector. NoData transparent; coastline masks sea cells.')
    save(fig, OUT / 'hong_kong_dtm_districts')
    stats = {'header': header, 'native_min': native_min, 'native_max': native_max,
             'native_nodata_cells': nodata_count, 'display_cell_metres': spacing,
             'display_shape': list(elevation.shape), 'display_extent': extent,
             'trimmed_south_metres': (rows % factor) * header['cellsize'],
             'trimmed_east_metres': (cols % factor) * header['cellsize']}
    (OUT / 'dtm_render_summary.json').write_text(json.dumps(stats, indent=2) + '\n')
    print('Terrain complete:', stats, flush=True)

def feature_series():
    source = '/vsizip/' + str(ROOT / 'data/organized/core/pedestrian/3D_Pedestrian_Network_FGDB.zip') + '/3DPN_P2.gdb'
    meta, _, wkb, values = read(source, layer='PedestrianRoute', columns=['FeatureType', 'Gradient'])
    attributes = dict(zip(meta['fields'], values))
    types, gradient = attributes['FeatureType'], attributes['Gradient']
    geoms = shapely.from_wkb(wkb)
    base_path = line_path(geoms)
    assert len(geoms) == 465892 and len(base_path.vertices) == 1963912
    special = np.isin(types, [8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 21])
    categories = [
        ('escalators', 'Escalators', np.isin(types, [8, 16]), '#ea7800'),
        ('elevators', 'Elevators / lifts', np.isin(types, [10, 18]), '#6d32b5'),
        ('ramps', 'Ramps', np.isin(types, [11, 19]), '#b88600'),
        ('travelators', 'Travelators', np.isin(types, [9, 17]), '#2674cc'),
        ('stairlifts', 'Stairlifts', np.isin(types, [13, 21]), '#cc3998'),
        ('slopes', 'Slopes (gradient >= 5°)', ~special & np.isfinite(gradient) & (np.abs(gradient) >= np.deg2rad(5)), '#008080'),
    ]
    stats = {}
    for key, label, mask, color in categories:
        print('Rendering individual layer:', key, int(mask.sum()), flush=True)
        fig, ax = canvas('HONG KONG / ' + label.upper(), 'Precise path network background · one highlighted feature category')
        # Identical full-network XY geometry to hong_kong_paths_precise.svg; subdued style.
        base = PathPatch(base_path, fill=False, edgecolor='#889497', linewidth=.105, alpha=.42, zorder=2)
        base.set_gid('pedestrian-path-overlay'); ax.add_patch(base)
        selected = geoms[mask]
        highlight = PathPatch(line_path(selected), fill=False, edgecolor=color,
                              linewidth=.9 if key != 'slopes' else .40, alpha=.95, zorder=3.2)
        highlight.set_gid('pedestrian-' + key); ax.add_patch(highlight)
        if key != 'slopes':
            # Short/vertical connectors need visible location symbols at city-wide scale.
            xy = shapely.get_coordinates(shapely.line_interpolate_point(shapely.get_parts(selected), .5, normalized=True))
            assert np.isfinite(xy).all() and len(xy) == int(mask.sum())
            marks = ax.scatter(xy[:, 0], xy[:, 1], s=8 if key not in ['travelators', 'stairlifts'] else 22,
                               marker='D' if key == 'stairlifts' else 'o', facecolor=color,
                               edgecolor='white', linewidth=.25, alpha=.85, zorder=5)
            marks.set_gid('pedestrian-' + key + '-location-markers')
        boundaries(ax)
        fig.text(.815, .415, 'HIGHLIGHTED', fontsize=12, weight='bold', color='#233845')
        fig.text(.815, .38, label, fontsize=11, color=color, weight='bold')
        fig.text(.815, .35, f'{int(mask.sum()):,} source route features', fontsize=10, color='#526875')
        fig.text(.815, .29, 'Grey: full precise path network\n465,892 routes · Z flattened\n\nColoured lines: original geometry\nDots: exact XY midpoints\nZoom SVG for path detail', fontsize=9, color='#526875', va='top', linespacing=1.6)
        if key == 'slopes':
            fig.text(.815, .14, '5° is a display cutoff.\nExplicit connector types excluded.\nSlopes use lines, without dots.', fontsize=9, color='#526875', va='top')
        footer(fig, 'SOURCE  Local pedestrian FGDB · HAD districts · © OpenStreetMap contributors (coastline)',
               'All original XY vertices retained. Background matches precise path geometry; selected feature highlighted on top.')
        save(fig, SERIES / f'hong_kong_paths_precise_{key}')
        stats[key] = {'highlighted_routes': int(mask.sum()), 'base_routes': len(geoms),
                      'base_vertices': len(base_path.vertices), 'selected_vertices': len(line_path(selected).vertices)}
    (SERIES / 'render_summary.json').write_text(json.dumps(stats, indent=2) + '\n')

if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1 or 'terrain' in sys.argv[1:]: terrain_map()
    if len(sys.argv) == 1 or 'series' in sys.argv[1:]: feature_series()
