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


def height_ok(z, target):
    # Inclusive upper bounds avoid cancellation in a subtracted difference.
    return z <= target + HEIGHT and target <= z + HEIGHT


def within_junction(xyz, point):
    return math.hypot(*(xyz[:2] - point[:2])) <= HORIZONTAL and height_ok(xyz[2], point[2])


def projections(coords, point):
    """Closest XY point on each segment subject to the inclusive height band.

    The height constraint gives a parameter interval. XY distance is convex
    on a segment, so clamping its unconstrained minimum to that interval gives
    the joint constrained minimum. A vertical segment has constant XY distance;
    break that tie by choosing the closest height, without a near-vertical cutoff.
    """
    coords, point = np.asarray(coords, dtype=float), np.asarray(point, dtype=float)
    result = []
    for i, (a, b) in enumerate(zip(coords[:-1], coords[1:])):
        delta = b - a
        dz = float(delta[2])
        if dz == 0:
            if not height_ok(a[2], point[2]):
                continue
            lower, upper, center = 0., 1., 0.
        else:
            offset = float(point[2] - a[2])
            roots = ((offset - HEIGHT) / dz, (offset + HEIGHT) / dz)
            lower, upper = min(roots), max(roots)
            start_ok, end_ok = height_ok(a[2], point[2]), height_ok(b[2], point[2])
            if (lower > 1 or upper < 0) and not (start_ok or end_ok):
                continue
            lower, upper = max(0., min(lower, 1.)), min(1., max(upper, 0.))
            # Keep qualifying source endpoints despite division roundoff.
            if start_ok:
                lower = 0.
            if end_ok:
                upper = 1.
            center = max(lower, min(offset / dz, upper))
        horizontal = math.hypot(float(delta[0]), float(delta[1]))
        if horizontal == 0:
            fraction = center
        else:
            unit = delta[:2] / horizontal
            fraction = float(np.dot(point[:2] - a[:2], unit)) / horizontal
            fraction = max(lower, min(fraction, upper))
        position = float(i + fraction)
        xyz = interpolate_xyz(coords, position)
        if not height_ok(xyz[2], point[2]):
            # Quantisation of the parameter/XYZ can round a boundary just out
            # of the band. Search toward a qualifying height, never enlarge it.
            inside = float(i + center)
            inside_xyz = interpolate_xyz(coords, inside)
            if not height_ok(inside_xyz[2], point[2]):
                continue
            outside = position
            for _ in range(64):
                midpoint = (inside + outside) / 2
                if midpoint == inside or midpoint == outside:
                    break
                if height_ok(interpolate_xyz(coords, midpoint)[2], point[2]):
                    inside = midpoint
                else:
                    outside = midpoint
            position = inside
            xyz = interpolate_xyz(coords, position)
        distance = math.hypot(*(xyz[:2] - point[:2]))
        if distance <= HORIZONTAL and height_ok(xyz[2], point[2]):
            result.append((position, xyz, float(distance)))
    return result


def _span_within(coords, point, start, end):
    """A straight segment is convex; checking intervening vertices suffices."""
    vertices = coords[int(math.floor(start))+1:int(math.ceil(end))]
    return all(within_junction(xyz, point) for xyz in vertices)


def projection_visits(coords, point, candidates):
    """Connected visits through the permitted XYZ neighbourhood in path order.

    Numeric vertex-index gaps carry no distance meaning. Two candidates belong
    to one visit only when the traversed path between them stays in the same
    endpoint neighbourhood. This joins ordinary bends/shared vertices while
    separating a retraced branch whose turnaround leaves the neighbourhood.
    """
    ordered = sorted({c[0]: c for c in candidates}.values(), key=lambda c: c[0])
    groups = []
    for candidate in ordered:
        if groups and _span_within(coords, point, groups[-1][-1][0], candidate[0]):
            groups[-1].append(candidate)
        else:
            groups.append([candidate])
    # A closed source's drawing seam is one ordinary shared junction, not a
    # second visit. Join only the two groups connected through that seam.
    if (len(groups) > 1 and np.array_equal(coords[0], coords[-1]) and
        within_junction(coords[0], point) and
        _span_within(coords, point, 0., groups[0][0][0]) and
        _span_within(coords, point, groups[-1][-1][0], len(coords)-1)):
        groups[0] = groups[-1] + groups[0]
        groups.pop()
    return groups


def separate_interior_visits(coords, positions):
    positions = sorted(set(positions))
    if len(positions) < 2:
        return False
    point = interpolate_xyz(coords, positions[0])
    candidates = [(t, interpolate_xyz(coords, t), 0.) for t in positions]
    return len(projection_visits(coords, point, candidates)) > 1


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
    projection_supports = defaultdict(set)
    ambiguous_attachments = set()
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
            # The constrained XY minimum can lie just inside a segment even
            # when its existing endpoint also satisfies both limits. Include
            # that endpoint as evidence before identifying visits. Otherwise
            # an unnecessary interior cut can create a non-clique with its own
            # endpoint and reject a supported junction. Separate traversal
            # visits must still be ruled out before preferring any endpoint.
            for t in (0., float(len(coords[path]) - 1)):
                endpoint = interpolate_xyz(coords[path], t)
                if within_junction(endpoint, site_xyz[site]):
                    candidates.append((t, endpoint,
                                       float(np.linalg.norm(endpoint[:2] - site_xyz[site][:2]))))
            if not candidates:
                continue
            visits = projection_visits(coords[path], site_xyz[site], candidates)
            if len(visits) > 1:
                ambiguous_attachments.add((site, path))
                review.append({'kind': 'ambiguous_interior_projection', 'endpoint_members':
                    [(ids[i], t) for i,t in members[site]], 'receiving_source': ids[path],
                    'endpoint_xyz': site_xyz[site].tolist(),
                    'candidate_positions': sorted({t for t,_,_ in candidates}),
                    'visits': [[{'position': t, 'xyz': xyz.tolist(), 'horizontal_m': distance}
                                for t,xyz,distance in visit] for visit in visits],
                    'reason': 'separate_traversal_visits'})
                continue
            # Prefer an existing receiving endpoint only after ruling out
            # another visit; drawing seams of closed paths remain valid.
            if any(t == 0 or t == len(coords[path])-1 for t, _, _ in candidates):
                continue
            t, xyz, _ = min(candidates, key=lambda item: (item[2], item[0]))
            projection_sites[(path, t)] = xyz
            projection_supports[(path, t)].add(site)
        if start % 100000 == 0:
            progress('Endpoint/interior candidates: {}/{}'.format(min(start+10000, endpoint_count), endpoint_count))
    supported_pairs = []
    for key in sorted(projection_sites):
        supported_pairs.extend((site, len(members)) for site in sorted(projection_supports[key]))
        site_xyz.append(projection_sites[key])
        members.append([key])
    xyz = np.asarray(site_xyz)
    points = shapely.points(xyz)
    def attachment_ok(left, right):
        return not (any((left, p) in ambiguous_attachments for p,_ in members[right]) or
                    any((right, p) in ambiguous_attachments for p,_ in members[left]))
    # Derived cuts are not new independent endpoints. Only original endpoint
    # pairs and explicitly supported endpoint projections seed connections.
    # Otherwise a lift cut near its own end creates a spurious chained merge.
    tree = STRtree(points[:endpoint_count])
    adjacency_a, adjacency_b = [], []
    for start in range(0, endpoint_count, 20000):
        pairs = tree.query(points[start:min(start+20000, endpoint_count)], predicate='dwithin', distance=HORIZONTAL)
        a, b = pairs[0] + start, pairs[1]
        keep = (a < b) & (xyz[a, 2] <= xyz[b, 2] + HEIGHT) & (xyz[b, 2] <= xyz[a, 2] + HEIGHT)
        for left, right in zip(a[keep].tolist(), b[keep].tolist()):
            if not attachment_ok(left, right):
                continue
            if all(floor_ok(i,j) for i,_ in members[left] for j,_ in members[right]):
                adjacency_a.append(left)
                adjacency_b.append(right)
            else:
                floor_rejections.add(('candidate_sites', left, right))
    for left, right in supported_pairs:
        if within_junction(xyz[left], xyz[right]):
            adjacency_a.append(left)
            adjacency_b.append(right)
    adjacency = coo_matrix((np.ones(len(adjacency_a), dtype=np.int8), (adjacency_a, adjacency_b)),
                           shape=(len(points),len(points))).tocsr()
    _, labels = connected_components(adjacency, directed=False)
    groups = defaultdict(list)
    for i, label in enumerate(labels):
        groups[int(label)].append(i)
    clusters = []
    for group in groups.values():
        # Connected candidate components must be cliques. No greedy/chained
        # merge can choose an arbitrary side of an ambiguous neighbourhood.
        complete = all(within_junction(xyz[a], xyz[b]) and attachment_ok(a,b) and
                       all(floor_ok(i,j) for i,_ in members[a] for j,_ in members[b])
                       for offset,a in enumerate(group) for b in group[offset+1:])
        # A cluster must not collapse separate interior visits of one path.
        visits = defaultdict(list)
        for i in group:
            for path,t in members[i]:
                visits[path].append(t)
        repeated_interior = any(separate_interior_visits(coords[p], v)
                                for p,v in visits.items() if any(0<t<len(coords[p])-1 for t in v))
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
    # Cost boundaries are subdivisions of one original traversal, not junction
    # candidates. Add them after all inferred connections have been decided so
    # an invalid interval cannot hide its healthy neighbours, or seed a new
    # cross-path proximity join. Existing supported cuts are reused.
    cost_boundary_nodes = 0
    for path, profile in enumerate(profiles):
        statuses = [(reason or ('available' if f is not None else 'unrepresentable_tobler_time'),
                     reason or ('available' if r is not None else 'unrepresentable_tobler_time'))
                    for reason, f, r in zip(profile.interval_reasons, profile.forward, profile.reverse)]
        for index in range(1, len(statuses)):
            if statuses[index - 1] == statuses[index]:
                continue
            t = float(profile.positions[index])
            if t in cuts[path]:
                continue
            original = interpolate_xyz(coords[path], t)
            node_id = stable_id('N-', [(ids[path], t)])
            nodes.append({'node_id':node_id, 'member_count':1,
                          'max_horizontal_m':0., 'max_height_m':0.,
                          'geometry':Point(original)})
            memberships.append({'node_id':node_id, 'source_index':path, 'position':t,
                                'alignment_xy_m':0., 'alignment_z_m':0.})
            cuts[path][t] = node_id
            cost_boundary_nodes += 1
            review.append({'kind':'cost_boundary_split', 'source_id':ids[path],
                           'position':t, 'xyz':original.tolist(),
                           'before_status':list(statuses[index - 1]),
                           'after_status':list(statuses[index]),
                           'connection_rule':'single_source_subdivision_no_new_junction'})
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
                   'accepted_nodes':len(frame),
                   'cost_boundary_nodes':cost_boundary_nodes,
                   'candidate_evidence':'original_endpoint_pairs_and_supported_projections'})
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
