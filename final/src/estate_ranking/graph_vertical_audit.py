"""Read-only evidence for unsupported vertical intervals and source provenance.

Auditing never substitutes heights, gradients, equipment types or geometry.
"""
from collections import Counter
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio

from .graph_costs import build_profile


VERTICAL_STATUS = 'non_lift_vertical_without_horizontal_run'


def _coords(geometry):
    if geometry.geom_type == 'MultiLineString':
        if len(geometry.geoms) != 1:
            raise ValueError('Audit requires the supported single-part source geometry')
        geometry = geometry.geoms[0]
    return np.asarray(geometry.coords, dtype=float)


def _json_value(value):
    if pd.isna(value):
        return None
    return value.item() if isinstance(value, np.generic) else value


def _same_value(left, right, date=False):
    if pd.isna(left) or pd.isna(right):
        return bool(pd.isna(left) and pd.isna(right))
    if date:
        # Step 1 deliberately serialises source dates as text. Check instants,
        # rather than pretending a slash-separated string is a new source date.
        return bool(pd.Timestamp(left) == pd.Timestamp(right))
    return bool(left == right)


def audit_source_provenance(physical, source_ids, frozen_input_directory, raw_gdb):
    """Verify selected records against both frozen Step 1 and original FGDB.

    All original attributes are compared, including nulls. Date formatting is
    normalised to instants; XYZ WKB and numeric attributes must match exactly.
    A mismatch fails the audit rather than silently becoming a correction.
    """
    ids = sorted(set(str(int(value)) for value in source_ids), key=int)
    if not ids:
        return {'sources_checked': 0, 'all_match': True, 'records': []}
    clause = 'PedestrianRouteID IN (' + ','.join(ids) + ')'
    raw = pyogrio.read_dataframe(raw_gdb, layer='PedestrianRoute', where=clause)
    frozen = pyogrio.read_dataframe(Path(frozen_input_directory) / 'harmonised.gpkg',
                                   layer='network', where=clause)
    selected = physical.sources.loc[physical.sources.PedestrianRouteID.astype(str).isin(ids)]
    frames = [frame.set_index(frame.PedestrianRouteID.astype(str))
              for frame in (raw, frozen, selected)]
    for frame in frames:
        if set(frame.index) != set(ids) or frame.index.duplicated().any():
            raise AssertionError('Missing or duplicate provenance source IDs')
    columns = [name for name in raw.columns if name != 'geometry']
    records = []
    for source_id in ids:
        original, step_1, graph = [frame.loc[source_id] for frame in frames]
        geometry_matches = (original.geometry.wkb == step_1.geometry.wkb == graph.geometry.wkb)
        mismatches = [name for name in columns
                      if not (_same_value(original[name], step_1[name], name.endswith('Date'))
                              and _same_value(original[name], graph[name], name.endswith('Date')))]
        if not geometry_matches or mismatches:
            raise AssertionError('Source provenance mismatch {}: geometry={}, fields={}'
                                 .format(source_id, geometry_matches, mismatches))
        records.append({'source_id': source_id, 'original_xyz_wkb_exact': True,
                        'xyz_wkb_sha256': hashlib.sha256(original.geometry.wkb).hexdigest(),
                        'all_original_attributes_match': True,
                        'original_attributes_checked': columns,
                        'date_comparison': 'same_instant_after_storage_format_normalisation'})
    return {'sources_checked': len(ids), 'all_match': True,
            'raw_layer': 'PedestrianRoute', 'frozen_layer': 'network', 'records': records}


def audit_vertical_sources(physical):
    """Explain original zero-XY/nonzero-Z intervals and affected derived pieces."""
    selected = physical.sources.loc[
        (physical.sources.time_forward_status == VERTICAL_STATUS) |
        (physical.sources.time_reverse_status == VERTICAL_STATUS)]
    profiles = {str(p.source_id): p for p in physical.profiles}
    records = []
    for row in selected.itertuples():
        source_id = str(row.PedestrianRouteID)
        coords = _coords(row.geometry)
        profile = profiles.get(source_id)
        if profile is None:
            profile = build_profile(source_id, coords, float(row.Gradient),
                                    row.FeatureType_label in {'Lift', 'M_Lift'})
        if (not np.array_equal(profile.coords, coords) or profile.gradient != float(row.Gradient)
                or profile.forward_status != row.time_forward_status
                or profile.reverse_status != row.time_reverse_status):
            raise AssertionError('Profile/source evidence mismatch: ' + source_id)
        diff = np.diff(coords, axis=0)
        indices = np.flatnonzero(np.all(diff[:, :2] == 0, axis=1) & (diff[:, 2] != 0))
        if not len(indices):
            raise AssertionError('Vertical diagnostic without original vertical geometry: ' + source_id)
        intervals = [{'original_segment_index': int(i), 'start_xyz': coords[i].tolist(),
                      'end_xyz': coords[i + 1].tolist(), 'horizontal_metres': 0.,
                      'height_change_metres': float(diff[i, 2]),
                      'location': 'start' if i == 0 else 'end' if i == len(diff) - 1 else 'interior'}
                     for i in indices]
        pieces = []
        for edge in physical.edges.loc[physical.edges.source_id.astype(str) == source_id].itertuples():
            pieces.append({'edge_id': str(edge.edge_id), 'start_position': float(edge.start_position),
                           'end_position': float(edge.end_position),
                           'distance_metres': float(edge.distance_m),
                           'forward_seconds': _json_value(edge.time_forward_s),
                           'reverse_seconds': _json_value(edge.time_reverse_s),
                           'forward_status': edge.time_forward_status,
                           'reverse_status': edge.time_reverse_status})
        usable = [i for i, reason in enumerate(profile.interval_reasons)
                  if reason is None and profile.forward[i] is not None and profile.reverse[i] is not None]
        records.append({'source_id': source_id, 'feature_type': row.FeatureType_label,
                        'gradient_radians': float(row.Gradient), 'direction': int(row.Direction),
                        'allow_general': bool(row.allow_general),
                        'allow_wheelchair': bool(row.allow_wheelchair),
                        'source_forward_status': profile.forward_status,
                        'source_reverse_status': profile.reverse_status,
                        'profile_reproduces_source_diagnostics': True,
                        'classification': 'original_zero_horizontal_nonzero_height_interval',
                        'automatic_source_correction_supported': False,
                        'retained_limitation': 'No evidence identifies replacement geometry or equipment type',
                        'original_xyz': coords.tolist(), 'vertical_intervals': intervals,
                        'zero_height_vertices': int(np.count_nonzero(coords[:, 2] == 0)),
                        'healthy_profile_interval_count': len(usable),
                        'healthy_profile_horizontal_metres': float(sum(profile.lengths[i] for i in usable)),
                        'pieces': pieces})
    summary = {'source_count': len(records),
               'original_vertical_interval_count': sum(len(r['vertical_intervals']) for r in records),
               'feature_types': dict(Counter(r['feature_type'] for r in records)),
               'sources_with_zero_height_vertices': sum(r['zero_height_vertices'] > 0 for r in records),
               'supported_source_geometry_corrections': 0,
               'sources': records}
    return summary
