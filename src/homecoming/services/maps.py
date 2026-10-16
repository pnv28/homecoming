"""A shared vector scene rendered to SVG and compact WebP, without online tiles."""
from functools import lru_cache
import base64
import hashlib
from html import escape
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import shapely

from homecoming.settings import MAP_ROOT, ROOT, STEP_4

VERSION = 'scene-2-terrain'
WIDTH, HEIGHT = 1000, 700
BG = '#f6f8f4'
TEAL = '#0755c9'
COLORS = {'network': TEAL, 'connector': '#a64b00', 'estimate': '#783eb4', 'lift': '#00745b'}
CONTEXT_BOUNDS = [-500, -350, 2000, 1400]


def asset_key(row):
    # Graph labels are deliberately absent: identical baseline/primary displays
    # can share assets, while changed geometry, costs, labels or evidence cannot.
    fields = {k: row.get(k) for k in ('estate_id', 'target_id', 'path_identity',
              'attachment_identity', 'cost', 'unit', 'warnings', 'uses_estimated_time')}
    fields['hospital'] = row['graph'] == 'general_distance'
    fields['wheelchair'] = row['graph'].startswith('wheelchair')
    fields['snapshot'] = STEP_4.resolve().name
    fields['renderer'] = VERSION
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:28]


def paths_for(key, root=MAP_ROOT):
    directory = Path(root) / 'assets' / key[:2]
    return {kind: directory / (key + suffix) for kind, suffix in
            [('svg', '.svg'), ('standard', '.webp'), ('hd', '@2x.webp')]}


class FastRoutes:
    """Recover the exact cached predecessor chain using array lookups.

    Avoid rebuilding large DataFrame indexes for each of thousands of maps.
    The checked engine remains the source of transitions, geometry and costs.
    """
    def __init__(self, cache, key):
        self.cache, self.graph = cache, cache.graph(key)
        g = self.graph
        self.edge = g.transitions.edge_index.to_numpy(dtype=int)
        self.direction = g.transitions.direction.to_numpy(dtype=int)
        self.cost = g.transitions.cost.to_numpy(dtype=float)
        self.source = g.transitions.source_id.to_numpy()
        self.geometry = g.edges.geometry.to_numpy()
        self.distance = g.edges.distance_m.to_numpy(dtype=float)
        self.lift = g.edges.lift_id.fillna('').to_numpy()
        self.estimated_forward = g.edges.time_forward_status.eq('estimated_distance_height').to_numpy()
        self.estimated_reverse = g.edges.time_reverse_status.eq('estimated_distance_height').to_numpy()
        self.attachments = {r.attachment_id: r for r in g.attachments.itertuples()}
        self.points = {r.id: r.geometry for f in g.entities.values() for r in f.itertuples()}
        self.key = key
        self._predecessors = {}

    def indices(self, row):
        search = self.cache.searches[row['search_id']]
        block_id = search['block']
        if block_id not in self._predecessors:
            # Warm the engine's checked link archive, then index each immutable
            # predecessor block once instead of repeated strided-array searches.
            if self.key not in self.cache._links:
                self.cache.indices(row)
            block = self.cache._links[self.key]['s' + str(block_id)]
            self._predecessors[block_id] = {int(s):(int(p),int(t)) for s,p,t in block}
        links = self._predecessors[block_id]
        root,state = search['root_state'],row['endpoint_state']
        indices,seen = [],set()
        while state != root:
            if state in seen or state not in links:
                raise ValueError('Invalid cached map predecessor chain.')
            seen.add(state)
            state,transition = links[state]
            indices.append(transition)
        return indices if search['direction']=='reverse' else indices[::-1]

    def sections(self, row):
        result = []
        override = row.get('origin_override')
        if override:
            a = override['attachment']
            p = self.points[row['estate_id']]
            result.append(dict(coords=[list(p.coords[0])[:2], a['position'][:2]], kind='connector',
                               distance_m=a['distance_m'], cost=a['distance_m'], source=a['source_id']))
        for index in self.indices(row):
            edge = self.edge[index]
            direction = self.direction[index]
            if edge < 0:
                a = self.attachments[self.source[index]]
                p = self.points[a.entity_id]
                coords = [list(p.coords[0])[:2], list(a.geometry.coords[0])[:2]]
                if a.role != 'departure':
                    coords.reverse()
                kind, distance = 'connector', float(a.distance_m)
            else:
                coords = shapely.get_coordinates(self.geometry[edge]).tolist()
                if direction < 0:
                    coords.reverse()
                estimated = self.estimated_forward[edge] if direction > 0 else self.estimated_reverse[edge]
                kind = ('lift' if self.lift[edge] else 'estimate' if estimated and
                        self.key.endswith('time') else 'network')
                distance = float(self.distance[edge])
            result.append(dict(coords=coords, kind=kind, distance_m=distance,
                               cost=float(self.cost[index]), source=str(self.source[index])))
        total = math.fsum(s['cost'] for s in result)
        if not math.isclose(total, row['cost'], rel_tol=2e-12, abs_tol=1e-8):
            raise ValueError('Recovered map route does not conserve its cached cost.')
        return result


class Context:
    def __init__(self, edges=None):
        # The display context is independent of the route's filtered graph.
        # Keep the argument for callers recovering routes from existing graphs.
        from homecoming.services.basemap import basemap
        self.map = basemap()

    def image(self, bounds, size):
        return self.map.image(bounds, size)


def make_scene(sections, start, end, context=None, wheelchair=False):
    coords = [p[:2] for s in sections for p in s['coords']] + [start[:2], end[:2]]
    points = np.asarray(coords, dtype=float)
    lo, hi = points.min(axis=0), points.max(axis=0)
    span = max(float(max(hi - lo)), 130.)
    lo -= span * .12
    hi += span * .12
    # Fixed aspect and uniform scale preserve the route's shape.
    scale = min(900 / max(hi[0] - lo[0], 1), 530 / max(hi[1] - lo[1], 1))
    cx, cy = (lo + hi) / 2
    def project(line):
        return [(round(500 + (p[0] - cx) * scale, 3),
                 round(365 - (p[1] - cy) * scale, 3)) for p in line]
    extent = [cx - 500 / scale, cy - 335 / scale, cx + 500 / scale, cy + 365 / scale]
    return dict(context=context, center=[float(cx),float(cy)],
                sections=[dict(s, coords=project(s['coords'])) for s in sections],
                start=project([start])[0], end=project([end])[0],
                scale=scale, extent=extent,
                distance_m=math.fsum(s['distance_m'] for s in sections))


def background(scene, view, size):
    if not scene.get('context'):
        return Image.new('RGB', size, BG)
    x,y,width,height = view
    cx,cy = scene['center']; scale = scene['scale']
    bounds = [cx+(x-500)/scale, cy+(365-y-height)/scale,
              cx+(x+width-500)/scale, cy+(365-y)/scale]
    return scene['context'].image(bounds, size)


@lru_cache(maxsize=16)
def font(size):
    for path in (ROOT / 'assets/fonts/DejaVuSans.ttf',
                 Path('/System/Library/Fonts/Supplemental/Arial.ttf')):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def svg_scene(scene, title, subtitle, unit='seconds'):
    # No scripts, external references or untrusted markup enter generated SVG.
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" role="img" data-context-bounds="-500 -350 2000 1400" data-center="{} {}" data-grid-scale="{}" aria-label="{}">'.format(*scene['center'], scene['scale'], escape(title, quote=True))]
    image = background(scene, CONTEXT_BOUNDS, (2000,1400))
    stream = io.BytesIO(); image.save(stream, 'WEBP', quality=82, method=0); image.close()
    encoded = base64.b64encode(stream.getvalue()).decode('ascii')
    # Keep terrain separate so close-zoom original vectors can replace the
    # network raster without removing the relief underneath.
    cx,cy=scene['center']; scale=scene['scale']
    terrain_bounds=[cx-1000/scale,cy-685/scale,cx+1000/scale,cy+715/scale]
    if scene.get('context'):
        terrain=scene['context'].map.relief(terrain_bounds,(2000,1400))
    else:
        terrain=Image.new('RGB',(2000,1400),BG)
    relief_stream=io.BytesIO(); terrain.save(relief_stream,'WEBP',quality=82,method=0); terrain.close()
    out.append('<image id="terrain-relief" x="-500" y="-350" width="2000" height="1400" href="data:image/webp;base64,' + base64.b64encode(relief_stream.getvalue()).decode('ascii') + '"/>')
    out.append('<image id="pedestrian-background" x="-500" y="-350" width="2000" height="1400" href="data:image/webp;base64,' + encoded + '"/>')
    out.append('<g id="local-path-detail" fill="none" stroke="#a95430" stroke-width="1.1" stroke-linejoin="round"></g>')
    def line(points):
        return ' '.join('{},{}'.format(*p) for p in points)
    out.append('<g fill="none" stroke-linecap="round" stroke-linejoin="round" class="route-lines">')
    # White casing separates the selected route from the original orange paths.
    for s in scene['sections']:
        out.append('<polyline points="{}" stroke="white" stroke-width="10" vector-effect="non-scaling-stroke"/>'.format(line(s['coords'])))
    for s in scene['sections']:
        color = COLORS[s['kind']]
        label = '{} · {:.1f} m · {:.2f} {} · source {}'.format(s['kind'], s['distance_m'], s['cost'], unit, s['source'])
        dash = ' stroke-dasharray="7 5"' if s['kind'] == 'connector' else ''
        out.append('<polyline points="{}" stroke="{}" stroke-width="6" vector-effect="non-scaling-stroke"{}><title>{}</title></polyline>'.format(line(s['coords']), color, dash, escape(label)))
    out.append('</g>')
    for label, point, fill in [('S', scene['start'], TEAL), ('E', scene['end'], '#c38335')]:
        x, y = point
        out.append('<circle cx="{}" cy="{}" r="11" fill="{}" stroke="white" stroke-width="3"/><text x="{}" y="{}" text-anchor="middle" fill="white" font-family="sans-serif" font-size="11" font-weight="bold">{}</text>'.format(x, y, fill, x, y + 4, label))
    out += ['<rect x="0" y="0" width="1000" height="62" fill="' + BG + '"/>',
            '<text x="28" y="28" font-family="sans-serif" font-size="18" fill="#173c36">' + escape(title[:95]) + '</text>',
            '<text x="28" y="49" font-family="sans-serif" font-size="12" fill="#62756d">' + escape(subtitle) + '</text>',
            '<rect x="0" y="654" width="1000" height="46" fill="' + BG + '"/>',
            '<text x="28" y="676" font-family="sans-serif" font-size="12" fill="#40564e">Blue: route · Dashed: connection · Green: lift · Purple: estimated time</text>',
            '<text x="28" y="692" font-family="sans-serif" font-size="10" fill="#52675f">Original pedestrian paths · DTM shaded terrain (display only) · Lands Department / OpenStreetMap contributors</text>']
    metres = max(1, round(100 / scene['scale']))
    out.append('<path d="M840 666v8h100v-8" fill="none" stroke="#62756d"/><text x="890" y="691" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#62756d">{} m</text>'.format(metres))
    out.append('</svg>')
    return ''.join(out)


def raster_scene(scene, title, subtitle, size=1200):
    factor = size / WIDTH
    img = background(scene, [0,0,1000,700], (size, round(HEIGHT * factor)))
    draw = ImageDraw.Draw(img)
    def points(coords):
        return [(round(x * factor), round(y * factor)) for x, y in coords]
    for s in scene['sections']:
        if len(s['coords']) > 1:
            draw.line(points(s['coords']), fill='white', width=max(3,round(10*factor)), joint='curve')
    for s in scene['sections']:
        line = points(s['coords'])
        if len(line) < 2:
            continue
        if s['kind'] == 'connector':
            for a, b in zip(line[:-1], line[1:]):
                length = math.dist(a, b)
                for offset in np.arange(0, length, 12 * factor):
                    u, v = offset / max(length, 1), min(1, (offset + 7 * factor) / max(length, 1))
                    draw.line([(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u),
                               (a[0]+(b[0]-a[0])*v,a[1]+(b[1]-a[1])*v)], fill=COLORS['connector'], width=max(3, round(6*factor)))
        else:
            draw.line(line, fill=COLORS[s['kind']], width=max(3, round(6*factor)), joint='curve')
    for label, point, fill in [('S', scene['start'], TEAL), ('E', scene['end'], '#c38335')]:
        x, y = points([point])[0]; r = 11 * factor
        draw.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline='white',width=max(2,round(3*factor)))
        draw.text((x,y),label,fill='white',font=font(round(11*factor)),anchor='mm')
    draw.rectangle((0,0,size,62*factor),fill=BG)
    draw.text((28*factor,12*factor),title[:90],font=font(round(18*factor)),fill='#173c36')
    draw.text((28*factor,37*factor),subtitle,font=font(round(12*factor)),fill='#62756d')
    draw.rectangle((0,654*factor,size,700*factor),fill=BG)
    draw.text((28*factor,664*factor),'Blue: route   Dashed: connection   Green: lift   Purple: estimated time',font=font(round(12*factor)),fill='#40564e')
    draw.text((28*factor,684*factor),'Original pedestrian paths · DTM shaded terrain (display only) · Lands Department / OpenStreetMap contributors',font=font(round(10*factor)),fill='#52675f')
    return img


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def render_svg_asset(key, scene, title, subtitle, unit='seconds', root=MAP_ROOT):
    path=paths_for(key,root)['svg']
    atomic_bytes(path,svg_scene(scene,title,subtitle,unit).encode())
    return {'svg':dict(path=str(path.relative_to(root)),bytes=path.stat().st_size,
                       sha256=hashlib.sha256(path.read_bytes()).hexdigest())}


def render_assets(key, scene, title, subtitle, unit='seconds', root=MAP_ROOT):
    paths = paths_for(key, root)
    atomic_bytes(paths['svg'], svg_scene(scene, title, subtitle, unit).encode())
    hd = raster_scene(scene, title, subtitle, 3000)
    for name in ('standard', 'hd'):
        image = hd.resize((1200,840), Image.Resampling.LANCZOS) if name=='standard' else hd
        stream = io.BytesIO()
        image.save(stream, 'WEBP', quality=78, method=0)
        atomic_bytes(paths[name], stream.getvalue())
        image.close()
    return {name: dict(path=str(p.relative_to(root)), bytes=p.stat().st_size,
                       sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in paths.items()}
