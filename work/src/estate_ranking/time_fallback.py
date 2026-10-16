"""Reviewed, traceable time estimates; original Tobler evidence stays immutable."""
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np


WORK = Path(__file__).resolve().parents[2]


def profile_digest(evidence):
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def derived_policy(source_policy, selected):
    """Allow the documented cost-policy extension, never untracked source edits."""
    old, new = copy.deepcopy(source_policy), copy.deepcopy(selected)
    for value in (old, new):
        value.pop('policy_version', None)
        value['transport_time'].pop('fallback', None)
        value['transport_time'].pop('nonfinite_time', None)
    if old != new:
        raise ValueError('Derived policy changed unrelated frozen preparation rules')
    result = copy.deepcopy(selected)
    fallback = result['transport_time'].get('fallback')
    if fallback and fallback.get('enabled'):
        if fallback.get('model') != 'horizontal_flat_time_plus_ascent_descent':
            raise ValueError('Unsupported fallback model')
        for name in ('uphill_seconds_per_metre', 'downhill_seconds_per_metre'):
            v = fallback.get(name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise ValueError('Fallback coefficients must be explicit finite positive values: ' + name)
        if fallback.get('wheelchair') != 'same_coefficients_explicit_approximation':
            raise ValueError('Unsupported wheelchair fallback policy')
        if 'review' not in fallback:
            path = WORK / fallback['review_file']
            fallback['review'] = json.loads(path.read_text())
            fallback['review_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def apply_review(profile, row, policy):
    fallback = policy['transport_time'].get('fallback', {})
    if not fallback.get('enabled') or profile.lift:
        return
    review = fallback.get('review', {}).get('sources', {}).get(profile.source_id)
    if not review:
        return  # New/unreviewed model failures stay explicit and unavailable.
    if profile_digest(profile.evidence()) != review['original_profile_sha256']:
        raise ValueError('Fallback review no longer matches original profile: ' + profile.source_id)
    checks = {'feature_type': row.FeatureType_label, 'direction': int(row.Direction),
              'enabled': bool(row.Enabled_bool), 'wheelchair_barrier': bool(row.WheelchairBarrier_bool),
              'allow_general': bool(row.allow_general), 'allow_wheelchair': bool(row.allow_wheelchair)}
    if any(review[k] != v for k, v in checks.items()):
        raise ValueError('Fallback review eligibility changed: ' + profile.source_id)
    accepted = {}
    for item in review['intervals']:
        i = item['interval_index']
        if item['decision'] != 'allow_estimated_time':
            continue
        if (profile.interval_reasons[i] not in (None, 'non_lift_vertical_without_horizontal_run')
                or (profile.forward[i] is not None and profile.reverse[i] is not None)):
            raise ValueError('Fallback cannot override a healthy or unsupported interval')
        h = float(profile.lengths[i])
        dz = float(profile.heights[i+1] - profile.heights[i])
        if (float(profile.positions[i]) != item['start_position'] or
                float(profile.positions[i+1]) != item['end_position'] or
                h != item['horizontal_m'] or dz != item['height_change_m']):
            raise ValueError('Fallback interval geometry changed')
        up, down = fallback['uphill_seconds_per_metre'], fallback['downhill_seconds_per_metre']
        flat = h * .6 * math.exp(.175)
        f = flat + up * max(dz, 0.) + down * max(-dz, 0.)
        r = flat + up * max(-dz, 0.) + down * max(dz, 0.)
        if not np.isfinite([f, r]).all() or min(f, r) <= 0:
            raise ValueError('Nonzero estimated traversal needs positive finite time')
        accepted[i] = {**item, 'forward_seconds': f, 'reverse_seconds': r,
                       'uphill_seconds_per_metre': up, 'downhill_seconds_per_metre': down}
    profile.fallback = accepted


def edge_cost_fields(profile, start, end, selected=None):
    original = profile.piece_costs(start, end, 'baseline')
    selected = selected or profile.piece_costs(start, end)
    ids = [r['review_id'] for i, r in (profile.fallback or {}).items()
           if profile.positions[i] < end and profile.positions[i+1] > start]
    warnings = sorted({w for i, r in (profile.fallback or {}).items()
                       if r['review_id'] in ids for w in r.get('warning', 'original_geometry_uncertain').split(';')})
    return {'time_forward_s': selected.forward_seconds, 'time_reverse_s': selected.reverse_seconds,
            'time_forward_status': selected.forward_status, 'time_reverse_status': selected.reverse_status,
            'original_time_forward_s': original.forward_seconds,
            'original_time_reverse_s': original.reverse_seconds,
            'original_time_forward_status': original.forward_status,
            'original_time_reverse_status': original.reverse_status,
            'fallback_review_ids': ';'.join(ids), 'uses_estimated_time': bool(ids),
            'time_model_warning': ';'.join(warnings)}


def routing_prefix(wheelchair, metric, scenario='primary'):
    if metric not in ('time', 'distance') or scenario not in ('primary', 'baseline'):
        raise ValueError('Invalid routing metric/scenario')
    if scenario == 'baseline' and metric != 'time':
        raise ValueError('Baseline scenario is only defined for time')
    return ('wheelchair' if wheelchair else 'general') + '_' + metric + (
        '_baseline' if scenario == 'baseline' else '')
