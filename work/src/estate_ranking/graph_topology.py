"""Conservative, deterministic XYZ endpoint junctions with complete-link clusters."""
from collections import defaultdict
import hashlib
import math

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely import STRtree
from shapely.geometry import Point, LineString

from .graph_costs import interpolate_xyz


HORIZONTAL = 0.10
HEIGHT = 0.025
VERTICAL_TYPES = {'Lift', 'M_Lift', 'Staircase', 'M_Staircase', 'Escalator',
                  'M_Escalator', 'Stairlift', 'M_Stairlift', 'Ramp', 'M_Ramp'}


def stable_id(prefix, members):
    value = '|'.join('{}@{}'.format(source, float(position).hex()) for source, position in sorted(members))
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:24]


def projections(coords, point):
    """All local XY projections, checking Z independently, including verticals."""
    a, delta = coords[:-1], np.diff(coords, axis=0)
    h2 = np.sum(delta[:, :2] ** 2, axis=1)
    f = np.zeros(len(a))
    horizontal = h2 > 0
    f[horizontal] = np.sum((point[:2] - a[horizontal, :2]) * delta[horizontal, :2], axis=1) / h2[horizontal]
    vertical = ~horizontal & (delta[:, 2] != 0)
    f[vertical] = (point[2] - a[vertical, 2]) / delta[vertical, 2]
    f = np.clip(f, 0, 1)
    xyz = a + delta * f[:, None]
    distance = np.linalg.norm(xyz[:, :2] - point[:2], axis=1)
    valid = (distance <= HORIZONTAL) & (xyz[:, 2] <= point[2] + HEIGHT) & (point[2] <= xyz[:, 2] + HEIGHT)
    return [(float(i + f[i]), xyz[i], float(distance[i])) for i in np.flatnonzero(valid)]


def build_topology(sources, profiles, review, progress=lambda message: None):
    """sources are in stable ID order and include enabled, supported union modes."""
    if not len(sources):
        return (gpd.GeoDataFrame({'node_id': [], 'node_index': [], 'member_count': [],
                                 'max_horizontal_m': [], 'max_height_m': []}, geometry=[], crs=2326),
                pd.DataFrame(columns=['node_index','source_index','position','alignment_xy_m','alignment_z_m']), {})
    ids = sources.PedestrianRouteID.astype(str).tolist()
    coords = [p.coords for p in profiles]
    floors = sources.FloorID.tolist()
    buildings = [set(v for v in row if pd.notna(v)) for row in sources[['BuildingID_1', 'BuildingID_2']].itertuples(index=False, name=None)]
    vertical = [kind in VERTICAL_TYPES and np.ptp(c[:, 2]) > 0
                for kind, c in zip(sources.FeatureType_label, coords)]
    def floor_ok(a, b):
        if pd.isna(floors[a]) or pd.isna(floors[b]) or floors[a] == floors[b]:
            return True
        return not (buildings[a] & buildings[b]) or vertical[a] or vertical[b]
    exact = defaultdict(list)
    for i, c in enumerate(coords):
        exact[tuple(c[0])].append((i, 0.))
        exact[tuple(c[-1])].append((i, float(len(c)-1)))
    site_xyz = [np.array(xyz) for xyz in sorted(exact)]
    members = [sorted(exact[tuple(xyz)]) for xyz in site_xyz]
    endpoint_count = len(members)
    # Near-endpoint candidates: a separate XYZ/floor check follows the 2D index.
    path_lines = np.array([LineString(c) for c in coords], dtype=object)
    tree = STRtree(path_lines)
    projection_sites = {}
    floor_rejections = set()
    for start in range(0, endpoint_count, 10000):
        points = shapely.points(np.asarray(site_xyz[start:min(start+10000, endpoint_count)]))
        pairs = tree.query(points, predicate='dwithin', distance=HORIZONTAL)
        for local, path in pairs.T:
            site = start + int(local)
            path = int(path)
            if any(i == path for i, _ in members[site]):
                continue
            if not all(floor_ok(i, path) for i, _ in members[site]):
                floor_rejections.add(('endpoint_to_interior', site, path))
                continue
            candidates = projections(coords[path], site_xyz[site])
            if not candidates:
                continue
            # Prefer a qualifying existing endpoint of this receiving path.
            if any(t == 0 or t == len(coords[path])-1 for t, _, _ in candidates):
                continue
            # Adjacent-segment projections at a bend describe one nearby place;
            # separate visits to the same position are ambiguous source evidence.
            positions = sorted({t for t, _, _ in candidates})
            if positions[-1] - positions[0] > 1:
                review.append({'kind': 'ambiguous_interior_projection', 'endpoint_members':
                    [(ids[i], t) for i,t in members[site]], 'receiving_source': ids[path],
                    'candidate_positions': positions})
                continue
            t, xyz, _ = min(candidates, key=lambda item: (item[2], item[0]))
            projection_sites[(path, t)] = xyz
        if start % 100000 == 0:
            progress('Endpoint/interior candidates: {}/{}'.format(min(start+10000, endpoint_count), endpoint_count))
    for key in sorted(projection_sites):
        site_xyz.append(projection_sites[key])
        members.append([key])
    xyz = np.asarray(site_xyz)
    points = shapely.points(xyz)
    tree = STRtree(points)
    adjacency_a, adjacency_b = [], []
    for start in range(0, len(points), 20000):
        pairs = tree.query(points[start:start+20000], predicate='dwithin', distance=HORIZONTAL)
        a, b = pairs[0] + start, pairs[1]
        keep = (a < b) & (xyz[a, 2] <= xyz[b, 2] + HEIGHT) & (xyz[b, 2] <= xyz[a, 2] + HEIGHT)
        for left, right in zip(a[keep].tolist(), b[keep].tolist()):
            if all(floor_ok(i,j) for i,_ in members[left] for j,_ in members[right]):
                adjacency_a.append(left)
                adjacency_b.append(right)
            else:
                floor_rejections.add(('candidate_sites', left, right))
    adjacency = coo_matrix((np.ones(len(adjacency_a), dtype=np.int8), (adjacency_a, adjacency_b)),
                           shape=(len(points),len(points))).tocsr()
    _, labels = connected_components(adjacency, directed=False)
    groups = defaultdict(list)
    for i, label in enumerate(labels):
        groups[int(label)].append(i)
    degree = np.bincount(np.asarray(adjacency_a + adjacency_b, dtype=int), minlength=len(points))
    clusters = []
    for group in groups.values():
        # Connected candidate components must be cliques. No greedy/chained
        # merge can choose an arbitrary side of an ambiguous neighbourhood.
        complete = all(degree[i] == len(group)-1 for i in group)
        # A cluster must not collapse separate interior visits of one path.
        visits = defaultdict(list)
        for i in group:
            for path,t in members[i]:
                visits[path].append(t)
        repeated_interior = any(max(v)-min(v)>1 and any(0<t<len(coords[p])-1 for t in v)
                                for p,v in visits.items())
        if complete and not repeated_interior:
            if any(i < endpoint_count for i in group):
                clusters.append(group)
        else:
            review.append({'kind': 'ambiguous_cluster', 'sites': [
                {'xyz': xyz[i].tolist(), 'members': [(ids[p],t) for p,t in members[i]]} for i in group],
                'reason': 'separate_interior_visits' if repeated_interior else 'not_pairwise_compatible'})
            clusters.extend([[i] for i in group if i < endpoint_count])
    nodes, memberships, cuts = [], [], defaultdict(dict)
    for group in clusters:
        all_members = sorted(set(m for i in group for m in members[i]))
        node_id = stable_id('N-', [(ids[p],t) for p,t in all_members])
        representative = min(tuple(xyz[i]) for i in group)
        values = xyz[group]
        max_h = max((float(np.linalg.norm(a[:2]-b[:2])) for a in values for b in values), default=0.)
        max_z = float(np.ptp(values[:,2]))
        if max_h > HORIZONTAL or any(a[2] > b[2]+HEIGHT or b[2] > a[2]+HEIGHT for a in values for b in values):
            raise AssertionError('Accepted cluster exceeds connection limits')
        nodes.append({'node_id': node_id, 'member_count': len(all_members),
                      'max_horizontal_m': max_h, 'max_height_m': max_z,
                      'geometry': Point(representative)})
        for path,t in all_members:
            original = interpolate_xyz(coords[path], t)
            memberships.append({'node_id':node_id, 'source_index':path, 'position':t,
                'alignment_xy_m':float(np.linalg.norm(original[:2]-np.array(representative[:2]))),
                'alignment_z_m':float(original[2]-representative[2])})
            cuts[path][t] = node_id
    frame = gpd.GeoDataFrame(nodes, crs=2326).sort_values('node_id').reset_index(drop=True)
    frame['node_index'] = np.arange(len(frame))
    lookup = dict(zip(frame.node_id, frame.node_index))
    membership = pd.DataFrame(memberships)
    membership['node_index'] = membership.node_id.map(lookup)
    membership['source_id'] = [ids[p] for p in membership.source_index]
    membership = membership.sort_values(['node_index','source_id','position']).reset_index(drop=True)
    for path in cuts:
        cuts[path] = {t:lookup[n] for t,n in cuts[path].items()}
    review.append({'kind':'topology_summary','exact_endpoint_sites':endpoint_count,
                   'interior_candidate_sites':len(projection_sites), 'floor_rejections':len(floor_rejections),
                   'accepted_nodes':len(frame)})
    def source_context(path):
        return {'source_id':ids[path], 'floor_id':None if pd.isna(floors[path]) else int(floors[path]),
                'building_ids':sorted(int(v) for v in buildings[path]),
                'explicit_vertical_transition':bool(vertical[path])}
    for stage,a,b in sorted(floor_rejections):
        left = [{'source':source_context(p),'position':t} for p,t in members[a]]
        right = ([{'source':source_context(b),'position':None}] if stage=='endpoint_to_interior'
                 else [{'source':source_context(p),'position':t} for p,t in members[b]])
        review.append({'kind':'floor_conflict_rejected','stage':stage,'xyz':xyz[a].tolist(),
                       'left_members':left,'right_members':right})
    return frame, membership, cuts


def report_crossings(sources, profiles, review, progress=lambda message: None):
    """Report XY middle intersections/overlaps; these never add graph links."""
    lines = np.array([LineString(p.coords) for p in profiles], dtype=object)
    tree = STRtree(lines)
    ids = sources.PedestrianRouteID.astype(str).tolist()
    for start in range(0,len(lines),10000):
        pairs = tree.query(lines[start:start+10000], predicate='intersects')
        a,b = pairs[0]+start,pairs[1]
        keep = a < b
        a,b = a[keep],b[keep]
        intersections = shapely.intersection(lines[a],lines[b])
        for left,right,geom in zip(a,b,intersections):
            parts = list(shapely.get_parts(geom))
            for part in parts:
                if part.is_empty:
                    continue
                if part.geom_type == 'Point':
                    # Exact XY endpoint intersections are already audited above.
                    xy = np.array(part.coords[0])[:2]
                    if any(np.array_equal(xy,c[:2]) for c in
                           [profiles[left].coords[0], profiles[left].coords[-1],
                            profiles[right].coords[0], profiles[right].coords[-1]]):
                        continue
                    review.append({'kind':'middle_crossing_not_auto_joined', 'source_a':ids[left],
                                   'source_b':ids[right], 'xy':xy.tolist(),
                                   'height_a_hkpd_m':float(interpolate_xyz(profiles[left].coords,
                                      _nearest_position(profiles[left].coords, xy))[2]),
                                   'height_b_hkpd_m':float(interpolate_xyz(profiles[right].coords,
                                      _nearest_position(profiles[right].coords, xy))[2])})
                elif part.geom_type in {'LineString','MultiLineString'}:
                    review.append({'kind':'overlapping_xy_paths_preserved', 'source_a':ids[left],
                                   'source_b':ids[right], 'overlap_horizontal_m':part.length})
        if start % 100000 == 0:
            progress('Crossing audit: {}/{}'.format(min(start+10000,len(lines)),len(lines)))


def _nearest_position(coords, xy):
    a,delta = coords[:-1,:2],np.diff(coords[:,:2],axis=0)
    length2 = np.sum(delta**2,axis=1)
    f = np.divide(np.sum((xy-a)*delta,axis=1),length2,out=np.zeros(len(a)),where=length2>0)
    f = np.clip(f,0,1)
    distance = np.linalg.norm(a+delta*f[:,None]-xy,axis=1)
    i = int(np.argmin(distance))
    return i+f[i]
