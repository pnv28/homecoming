"""Prepare display-only terrain from the original Hong Kong 5 m DTM.

The routing model and its elevation measurements are deliberately untouched.
Run once before regenerating route maps. Runtime uses only the app's bundled files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'runtime/matplotlib'))
from matplotlib.colors import LightSource, LinearSegmentedColormap, Normalize


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtm-archive',type=Path,required=True,
        help='Path to Whole_HK_DTM_5m.zip in the development checkout.')
    archive=parser.parse_args().dtm_archive.expanduser().resolve()
    destination = ROOT / 'assets/maps'
    with zipfile.ZipFile(archive) as zipped:
        member = next(n for n in zipped.namelist() if n.endswith('.asc'))
        digest = hashlib.sha256()
        with zipped.open(member) as stream:
            header = {}
            for _ in range(6):
                line = stream.readline(); digest.update(line)
                key, value = line.decode().split()
                header[key.lower()] = float(value)
            rows, cols = int(header['nrows']), int(header['ncols'])
            # A 20 m display layer matches the terrain map in analysis/maps.
            # Average complete 4 x 4 cells, retaining the north-west alignment.
            terrain = np.empty((rows // 4, cols // 4), dtype=np.float32)
            block = []
            for row, line in enumerate(stream):
                digest.update(line)
                values = np.fromstring(line, dtype=np.float32, sep=' ')
                if len(values) != cols:
                    raise ValueError('Unexpected DTM row length.')
                block.append(values[:cols // 4 * 4].reshape(-1, 4).mean(axis=1))
                if len(block) == 4:
                    terrain[row // 4] = np.mean(block, axis=0)
                    block = []
                if row % 1600 == 0:
                    print('DTM row {}/{}'.format(row, rows), flush=True)
    west = header['xllcorner']; north = header['yllcorner'] + rows * header['cellsize']
    resolution = header['cellsize'] * 4
    height, width = terrain.shape
    # Quiet, warm land colours keep the paths and route dominant.
    cmap = LinearSegmentedColormap.from_list('terrain', ['#f2f1e5', '#e7ead7', '#d9dfc3', '#d4d1b9', '#e1ddcf'])
    relief = LightSource(azdeg=315, altdeg=45).shade(
        terrain, cmap=cmap, norm=Normalize(-30, 960), vert_exag=1,
        dx=resolution, dy=resolution, blend_mode='soft')
    image = Image.fromarray(np.uint8(np.clip(relief[:, :, :3], 0, 1) * 255))
    # Modern land boundaries provide the same coastline used by the existing maps.
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    project = Transformer.from_crs(4326, 2326, always_xy=True).transform
    coastline = json.loads((destination / 'hong_kong_land.geojson').read_text())
    def pixels(ring):
        return [((x-west)/resolution, (north-y)/resolution) for x, y, *_ in ring.coords]
    for feature in coastline['features']:
        land = transform(project, shape(feature['geometry']))
        for polygon in (land.geoms if land.geom_type == 'MultiPolygon' else [land]):
            draw.polygon(pixels(polygon.exterior), fill=255)
            for hole in polygon.interiors:
                draw.polygon(pixels(hole), fill=0)
    water = Image.new('RGB', image.size, '#e6eff2')
    water.paste(image, mask=mask)
    path = destination / 'terrain_relief.png'
    water.save(path, optimize=True)
    metadata = dict(schema_version=1, crs='EPSG:2326', resolution_m=resolution,
        bounds=[west, north-height*resolution, west+width*resolution, north],
        size=[width, height], source=archive.name, source_member=member,
        source_ascii_sha256=digest.hexdigest(), source_header=header,
        aggregation='Mean of complete 4 x 4 cells; north-west alignment',
        illumination=dict(azimuth_degrees=315, altitude_degrees=45, vertical_exaggeration=1),
        image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        use='Display only; no effect on route geometry, distance, time or ranking.')
    (destination / 'terrain_relief.json').write_text(json.dumps(metadata, indent=2))
    print('Prepared {} x {} terrain image.'.format(width, height), flush=True)


if __name__ == '__main__':
    main()
