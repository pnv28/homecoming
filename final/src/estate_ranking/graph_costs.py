"""Source-level cost profiles. Topology cuts only apportion existing intervals."""
from dataclasses import dataclass
import hashlib
import math

import numpy as np
from shapely.geometry import LineString


SEED = 20261013
MAX_LOG = math.log(np.finfo(float).max)


def interpolate_xyz(coords, position):
    i = min(int(position), len(coords) - 2)
    f = position - i
    return coords[i] + f * (coords[i + 1] - coords[i])


def total_or_none(values):
    if any(v is None for v in values):
        return None
    try:
        result = math.fsum(values)
        return result if math.isfinite(result) else None
    except OverflowError:
        return None


def tobler_seconds(length, angle):
    """Evaluate in log space; return unavailable rather than cap overflow."""
    if length == 0:
        return 0.0
    exponent = math.log(length) + math.log(0.6) + 3.5 * abs(math.tan(angle) + 0.05)
    if not math.isfinite(exponent) or exponent > MAX_LOG:
        return None
    return math.exp(exponent)


@dataclass
class PieceCost:
    distance_m: float
    forward_seconds: object
    reverse_seconds: object
    forward_status: str
    reverse_status: str


@dataclass
class CostProfile:
    source_id: str
    coords: np.ndarray
    gradient: float
    lift: bool
    positions: np.ndarray
    heights: np.ndarray
    lengths: np.ndarray
    signed_angles: np.ndarray
    forward: list
    reverse: list
    samples: list
    rounds: int
    classification: str
    forward_status: str
    reverse_status: str
    interval_reasons: list
    fallback: object = None

    def piece(self, start, end):
        cost = self.piece_costs(start, end)
        return cost.distance_m, cost.forward_seconds, cost.reverse_seconds

    def piece_costs(self, start, end, scenario='primary'):
        if scenario not in ('primary', 'baseline'):
            raise ValueError('scenario must be primary or baseline')
        # Vertex index + fraction also represents vertical source intervals.
        lower = np.maximum(self.positions[:-1], start)
        upper = np.minimum(self.positions[1:], end)
        fraction = np.maximum(upper - lower, 0) / np.diff(self.positions)
        distance = float(np.dot(fraction, self.lengths))
        overlaps = np.flatnonzero(fraction > 0)
        def part(values, direction):
            times = []
            estimated = False
            for i in overlaps:
                replacement = (self.fallback or {}).get(int(i)) if scenario == 'primary' else None
                if replacement and values[i] is None:
                    times.append(replacement[direction + '_seconds'] * float(fraction[i]))
                    estimated = True
                    continue
                reason = self.interval_reasons[i]
                if reason:
                    return None, reason
                # An invalid overlapping interval remains unavailable; only
                # intervals outside this piece are ignored. No costs are capped.
                value = values[i]
                if value is None:
                    return None, 'unrepresentable_tobler_time'
                value *= float(fraction[i])
                times.append(value)
            total = total_or_none(times)
            return total, (('estimated_distance_height' if estimated else 'available')
                           if total is not None else 'unrepresentable_tobler_time')
        forward, forward_status = part(self.forward, 'forward')
        reverse, reverse_status = part(self.reverse, 'reverse')
        return PieceCost(distance, forward, reverse, forward_status, reverse_status)

    def derived_evidence(self):
        return {'source_id': self.source_id, 'intervals': list((self.fallback or {}).values())}

    def geometry(self, start, end):
        indices = np.arange(len(self.coords))
        middle = self.coords[(indices > start) & (indices < end)]
        return LineString(np.vstack([interpolate_xyz(self.coords, start), middle,
                                    interpolate_xyz(self.coords, end)]))

    def evidence(self):
        return {'source_id': self.source_id, 'gradient_radians': self.gradient,
                'lift': self.lift, 'seed': SEED, 'sample_rounds': self.rounds,
                'samples': self.samples, 'classification': self.classification,
                'positions': self.positions.tolist(), 'heights_hkpd_m': self.heights.tolist(),
                'horizontal_lengths_m': self.lengths.tolist(),
                'signed_angles_radians': self.signed_angles.tolist(),
                'forward_seconds': self.forward, 'reverse_seconds': self.reverse,
                'interval_reasons': self.interval_reasons,
                'forward_interval_status': [r or ('available' if v is not None else 'unrepresentable_tobler_time')
                                            for r,v in zip(self.interval_reasons,self.forward)],
                'reverse_interval_status': [r or ('available' if v is not None else 'unrepresentable_tobler_time')
                                            for r,v in zip(self.interval_reasons,self.reverse)],
                'forward_status': self.forward_status, 'reverse_status': self.reverse_status}


def build_profile(source_id, coords, gradient, lift=False):
    coords = np.asarray(coords, dtype=float)
    positions = np.arange(len(coords), dtype=float)
    samples, rounds, classification = [], 0, 'vertex_signed'
    if lift:
        classification = 'lift_entry_charge_in_routing_states'
    elif coords[0, 2] == coords[-1, 2] and gradient != 0:
        # Uniform in XYZ arclength; stable source-derived seed, never Python hash.
        digest = hashlib.sha256((str(SEED) + ':' + str(source_id)).encode()).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:16], 'big'))
        arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(coords, axis=0), axis=1))]
        seen = set()
        for round_number in (1, 2):
            rounds = round_number
            batch = []
            while len(batch) < 4:
                draw = float(rng.uniform(np.nextafter(0., 1.), 1.))
                if draw in seen:
                    continue
                seen.add(draw)
                if arc[-1] > 0:
                    d = draw * arc[-1]
                    j = min(np.searchsorted(arc, d, side='right') - 1, len(coords) - 2)
                    t = float(j + (d - arc[j]) / (arc[j + 1] - arc[j]))
                else:
                    t = draw * (len(coords) - 1)
                xyz = interpolate_xyz(coords, t)
                batch.append({'position': t, 'xyz': xyz.tolist(), 'round': round_number})
            samples.extend(batch)
            if any(s['xyz'][2] != coords[0, 2] for s in samples):
                classification = 'sampled_nonflat'
                break
            classification = 'relatively_flat'
        positions = np.unique(np.r_[positions, [s['position'] for s in samples]])
    xyz = np.array([interpolate_xyz(coords, p) for p in positions])
    segment_lengths = np.linalg.norm(np.diff(coords[:, :2], axis=0), axis=1)
    segment_indices = np.floor((positions[:-1]+positions[1:])/2).astype(int)
    lengths = segment_lengths[segment_indices] * np.diff(positions)
    dz = np.diff(xyz[:, 2])
    valid_gradient = math.isfinite(gradient) and 0 <= gradient <= math.pi / 2
    angles = np.sign(dz) * gradient
    if classification == 'relatively_flat':
        angles[:] = 0
    forward, reverse, reasons = [], [], []
    for h, z, angle in zip(lengths, dz, angles):
        reason = ('invalid_gradient' if not valid_gradient else
                  'non_lift_vertical_without_horizontal_run' if h == 0 and z != 0 else None)
        if lift:
            f, r, reason = 0., 0., None
        elif reason:
            f, r = None, None
        else:
            f, r = tobler_seconds(float(h), float(angle)), tobler_seconds(float(h), float(-angle))
        forward.append(f)
        reverse.append(r)
        reasons.append(reason)
    def status(values):
        reason = next((v for v in reasons if v), None)
        return reason or ('available' if total_or_none(values) is not None else 'unrepresentable_tobler_time')
    return CostProfile(str(source_id), coords, float(gradient), bool(lift), positions, xyz[:, 2],
                       lengths, angles, forward, reverse, samples, rounds, classification,
                       status(forward), status(reverse), reasons)
