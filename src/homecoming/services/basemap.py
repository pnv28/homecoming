"""Complete original pedestrian geometry and local DTM, for display only.

Shared tiles avoid repeating hundreds of thousands of SVG paths in each long
hospital walk. No features are sampled or filtered by routing eligibility.
"""
from functools import lru_cache
import json
import math
import threading

import numpy as np
from PIL import Image, ImageDraw
import pyogrio
import shapely
from shapely.geometry import box

from homecoming.settings import ROOT

BASEMAP_VERSION = 'original-paths-dtm-1'
TILE_SIZE = 512
LEVELS = (.25, .5, 1., 2., 4., 8., 16., 32., 64., 128., 256.)
WATER = '#e6eff2'
PATH_COLOR = '#a95430'


class Basemap:
    def __init__(self):
        source = ROOT / 'precomputed/outputs/step_2/current/graph.gpkg'
        # This is the original PedestrianRoute layer used by analysis/maps,
        # preserved before graph splitting, pruning and eligibility decisions.
        self.paths = pyogrio.read_dataframe(source, layer='sources', columns=[])
        self.geometry = self.paths.geometry.to_numpy()
        self.index = self.paths.sindex
        self.lock = threading.RLock()
        directory = ROOT / 'assets/maps'
        self.metadata = json.loads((directory / 'terrain_relief.json').read_text())
        with Image.open(directory / 'terrain_relief.png') as image:
            self.terrain = image.convert('RGB')
        self.directory = ROOT / 'precomputed/maps/basemap' / BASEMAP_VERSION

    def lines(self, bounds):
        indices = self.index.query(box(*bounds))
        # Query all original features. Do not connect unrelated endpoints or
        # suppress stairs / non-wheelchair paths in the decorative background.
        return shapely.get_parts(self.geometry[indices])

    def relief(self, bounds, size):
        west, south, east, north = self.metadata['bounds']
        cell = self.metadata['resolution_m']
        left, bottom, right, top = bounds
        return self.terrain.transform(size, Image.Transform.AFFINE,
            ((right-left)/size[0]/cell, 0, (left-west)/cell,
             0, (top-bottom)/size[1]/cell, (north-top)/cell),
            resample=Image.Resampling.BILINEAR, fillcolor=WATER)

    @lru_cache(maxsize=512)
    def tile(self, level, column, row):
        path = self.directory / str(level) / '{}_{}.png'.format(column, row)
        # Completed tiles are immutable and atomically published. Independent
        # reads can decode concurrently; only first-time tile creation needs
        # the lock. Serialising PNG reads dominated the large hospital build.
        if path.exists():
            with Image.open(path) as image:
                return image.convert('RGB')
        with self.lock:
            if path.exists():
                with Image.open(path) as image:
                    return image.convert('RGB')
            span = TILE_SIZE * level
            left, bottom = column * span, row * span
            bounds = [left, bottom, left + span, bottom + span]
            image = self.relief(bounds, (TILE_SIZE, TILE_SIZE))
            draw = ImageDraw.Draw(image)
            # A muted but visible original network; the selected route gets a
            # white casing and a much heavier blue stroke above this layer.
            color = PATH_COLOR if level <= 4 else '#b38066'
            for geometry in self.lines(bounds):
                coords = shapely.get_coordinates(geometry)
                pixels = np.column_stack(((coords[:, 0]-left)/level,
                                          TILE_SIZE-(coords[:, 1]-bottom)/level))
                if len(pixels) > 1:
                    draw.line([tuple(p) for p in pixels], fill=color, width=1)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            image.save(temporary, format='PNG')
            temporary.replace(path)
            return image

    def image(self, bounds, size):
        left, bottom, right, top = bounds
        if max(right-left, top-bottom) <= 3000:
            # Draw close views directly at their output resolution. In particular,
            # a short walk's HD background must not magnify coarse tile pixels.
            image = self.relief(bounds, size)
            draw = ImageDraw.Draw(image)
            sx, sy = size[0]/(right-left), size[1]/(top-bottom)
            width = max(1, round(size[0]/1000))
            for geometry in self.lines(bounds):
                coords = shapely.get_coordinates(geometry)
                pixels = np.column_stack(((coords[:,0]-left)*sx, (top-coords[:,1])*sy))
                if len(pixels)>1:
                    draw.line([tuple(p) for p in pixels], fill=PATH_COLOR, width=width)
            return image
        desired = max((right-left)/size[0], (top-bottom)/size[1])
        # Finer or equal resolution, so HD receives real additional map detail.
        level = max((x for x in LEVELS if x <= desired), default=LEVELS[0])
        span = TILE_SIZE * level
        x0, x1 = math.floor(left/span), math.floor(right/span)
        y0, y1 = math.floor(bottom/span), math.floor(top/span)
        image = Image.new('RGB', ((x1-x0+1)*TILE_SIZE, (y1-y0+1)*TILE_SIZE), WATER)
        for row in range(y0, y1+1):
            for column in range(x0, x1+1):
                image.paste(self.tile(level, column, row),
                            ((column-x0)*TILE_SIZE, (y1-row)*TILE_SIZE))
        crop = ((left-x0*span)/level, ((y1+1)*span-top)/level,
                (right-x0*span)/level, ((y1+1)*span-bottom)/level)
        return image.resize(size, resample=Image.Resampling.LANCZOS, box=crop)


@lru_cache(maxsize=1)
def basemap():
    return Basemap()


def vector_context(bounds, cx, cy, scale):
    """Close-zoom vector detail; large extents keep the complete tiled layer."""
    geometries = basemap().lines(bounds)
    if len(geometries) > 16000:
        return ''
    out = []
    clip = box(*bounds)
    for geometry in geometries:
        # Clip before projection to keep long originals from escaping the view.
        clipped = geometry.intersection(clip)
        pieces = clipped.geoms if hasattr(clipped, 'geoms') else [clipped]
        for piece in pieces:
            coords = shapely.get_coordinates(piece)
            if len(coords) < 2:
                continue
            points = ' '.join('{:.2f},{:.2f}'.format(500+(x-cx)*scale, 365-(y-cy)*scale) for x,y in coords)
            out.append('<polyline vector-effect="non-scaling-stroke" points="' + points + '"/>')
    return ''.join(out)
