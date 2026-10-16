"""Source-ID/XYZ based checks for the two reported real lift connections."""
import math

import numpy as np
from scipy.sparse.csgraph import dijkstra

from .graph_costs import interpolate_xyz


REAL_LIFT_PAIRS = [('290063550','260001786',0.0222275),
                   ('290064373','280005280',0.0049668)]


def _coords(physical, source):
    rows = physical.sources.loc[physical.sources.PedestrianRouteID.astype(str)==source]
    if len(rows) != 1:
        raise AssertionError('Expected exactly one source record: '+source)
    geometry = rows.geometry.iloc[0]
    return np.asarray((geometry.geoms[0] if geometry.geom_type=='MultiLineString' else geometry).coords)


def _member_node(physical, source, position):
    rows = physical.memberships.loc[(physical.memberships.source_id.astype(str)==source) &
                                    (physical.memberships.position==position)]
    if len(rows) != 1:
        raise AssertionError('Missing/ambiguous source-position node: '+source)
    return int(rows.node_index.iloc[0])


def check_lift_connections(graph, pairs=REAL_LIFT_PAIRS, require_direct=True):
    """Locate original footway endpoints and far lift ends without saved indexes.

    Equal-height residuals independently reproduce the reported input evidence.
    Routing checks target the lift identity state, ensuring the path actually
    enters that lift instead of merely reaching the same physical node.
    """
    physical = graph.physical
    results = []
    for foot, lift, expected_residual in pairs:
        foot_coords, lift_coords = _coords(physical,foot), _coords(physical,lift)
        candidates = []
        for endpoint in (0,len(foot_coords)-1):
            point = foot_coords[endpoint]
            for i,(a,b) in enumerate(zip(lift_coords[:-1],lift_coords[1:])):
                if b[2] == a[2]:
                    continue
                fraction = (point[2]-a[2])/(b[2]-a[2])
                if 0 <= fraction <= 1:
                    xyz = interpolate_xyz(lift_coords,float(i+fraction))
                    separation = float(np.linalg.norm(xyz[:2]-point[:2]))
                    if separation <= .10:
                        candidates.append((separation,endpoint,float(i+fraction),xyz))
        if not candidates:
            raise AssertionError('Reported equal-height lift evidence is missing')
        separation,endpoint,parameter,xyz = min(candidates,key=lambda c:(c[0],c[1],c[2]))
        if abs(separation-expected_residual)>1e-6:
            raise AssertionError('Source-coordinate regression evidence changed')
        foot_node = _member_node(physical,foot,float(endpoint))
        far_end = max((0,len(lift_coords)-1),key=lambda i:abs(lift_coords[i,2]-foot_coords[endpoint,2]))
        lift_node = _member_node(physical,lift,float(far_end))
        def state(node, identity):
            mask = graph.states.node_index==node
            mask &= graph.states.lift_id.isna() if identity is None else graph.states.lift_id.astype(str)==identity
            indexes = graph.states.loc[mask,'state_index']
            return int(indexes.iloc[0]) if len(indexes)==1 else None
        forward_target,reverse_target = state(lift_node,lift),state(foot_node,lift)
        forward = (float(dijkstra(graph.matrix,indices=state(foot_node,None))[forward_target])
                   if forward_target is not None else math.inf)
        reverse = (float(dijkstra(graph.matrix,indices=state(lift_node,None))[reverse_target])
                   if reverse_target is not None else math.inf)
        direct_members = physical.memberships.loc[(physical.memberships.node_index==foot_node) &
                                                  (physical.memberships.source_id.astype(str)==lift)]
        if require_direct:
            if len(direct_members)!=1 or forward!=30. or reverse!=30.:
                raise AssertionError('Reported footway/lift connection is not a 30-second lift use: '+foot+' / '+lift)
            for position in direct_members.position:
                actual = interpolate_xyz(lift_coords,position)
                original = foot_coords[endpoint]
                if (np.linalg.norm(actual[:2]-original[:2])>.10 or
                    actual[2]>original[2]+.025 or original[2]>actual[2]+.025):
                    raise AssertionError('Regression junction exceeded tolerances')
        results.append({'footway_id':foot,'lift_id':lift,'footway_endpoint_position':int(endpoint),
            'footway_endpoint_xyz':foot_coords[endpoint].tolist(),
            'equal_height_lift_parameter':parameter,'equal_height_lift_xyz':xyz.tolist(),
            'equal_height_horizontal_separation_m':separation,
            'accepted_lift_parameters':direct_members.position.tolist(),
            'forward_lift_state_seconds':forward if math.isfinite(forward) else None,
            'reverse_lift_state_seconds':reverse if math.isfinite(reverse) else None,
            'direct_connection':bool(len(direct_members))})
    return results
