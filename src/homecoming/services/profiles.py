"""Verify native calculations, then reuse the exact frozen source cost values.

libm can differ by a final floating-point bit between macOS ARM and Linux x86.
Discrete evidence remains exact; only floating values allow rounding tolerance.
The engine's strict fallback-review hashes and subdivision checks stay intact.
"""
import json
import math
from pathlib import Path

import numpy as np

from estate_ranking.graph_costs import build_profile
from estate_ranking.time_fallback import apply_review


def same_evidence(actual, frozen):
    if type(actual) is not type(frozen):
        return False
    if isinstance(actual, dict):
        return actual.keys() == frozen.keys() and all(same_evidence(actual[k], frozen[k]) for k in actual)
    if isinstance(actual, list):
        return len(actual) == len(frozen) and all(same_evidence(a, b) for a, b in zip(actual, frozen))
    if isinstance(actual, float):
        return math.isfinite(actual) and math.isfinite(frozen) and math.isclose(actual, frozen, rel_tol=2e-12, abs_tol=1e-12)
    return actual == frozen


def records(path, wanted):
    found = {}
    if not wanted:
        return found
    with Path(path).open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['source_id'] in wanted:
                found[row['source_id']] = row
                if found.keys() == wanted:
                    break
    if found.keys() != wanted:
        raise ValueError('Missing frozen source cost evidence.')
    return found


def verified_profiles(physical, source_ids, directory):
    frozen = records(Path(directory) / 'profiles.jsonl', source_ids)
    rows = physical.sources.set_index(physical.sources.PedestrianRouteID.astype(str))
    profiles = []
    for sid in sorted(source_ids):
        row = rows.loc[sid]
        geometry = row.geometry.geoms[0] if row.geometry.geom_type == 'MultiLineString' else row.geometry
        profile = build_profile(sid, np.asarray(geometry.coords), float(row.Gradient),
                                row.FeatureType_label in {'Lift', 'M_Lift'})
        evidence = frozen[sid]
        native = json.loads(json.dumps(profile.evidence(), allow_nan=False))
        if not same_evidence(native, evidence):
            raise ValueError('Saved walking cost evidence does not match source geometry: ' + sid)
        # Restore the saved values before applying the original review: its
        # evidence digest remains byte-for-byte strict on every platform.
        profile.gradient = evidence['gradient_radians']
        for attribute, field in (('positions', 'positions'), ('heights', 'heights_hkpd_m'),
                                 ('lengths', 'horizontal_lengths_m'), ('signed_angles', 'signed_angles_radians')):
            setattr(profile, attribute, np.asarray(evidence[field], dtype=float))
        profile.forward = evidence['forward_seconds']
        profile.reverse = evidence['reverse_seconds']
        profile.samples = evidence['samples']
        if profile.evidence() != evidence:
            raise ValueError('Could not restore exact frozen walking evidence: ' + sid)
        apply_review(profile, row, physical.policy)
        if (profile.classification != row.cost_classification or profile.rounds != row.sample_rounds
                or profile.forward_status != row.time_forward_status
                or profile.reverse_status != row.time_reverse_status):
            raise ValueError('Saved walking classification changed: ' + sid)
        profiles.append(profile)
    wanted = {p.source_id for p in profiles if p.fallback}
    derived = records(Path(directory) / 'derived_profiles.jsonl', wanted)
    for profile in profiles:
        if profile.source_id in derived:
            evidence = derived[profile.source_id]
            if not same_evidence(profile.derived_evidence(), evidence):
                raise ValueError('Saved reviewed walking evidence changed: ' + profile.source_id)
            profile.fallback = {item['interval_index']: item for item in evidence['intervals']}
    return profiles
