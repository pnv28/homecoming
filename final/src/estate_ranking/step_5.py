"""Bounded estate costs and reproducible GeoDataFrame rankings; no routing.

Run: PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_5
"""
import argparse
import copy
from datetime import datetime, timezone
import fcntl
import json
from numbers import Real
from pathlib import Path
import time
import traceback
import uuid

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from .export import write_json
from .graph import WORK
from .ingest import read_json, sha256
from .step_2 import publish_run
from .step_3 import verify_hashes
from .step_4 import _reader as _journey_reader, read_subcosts


COMPONENTS = ('bus', 'mtr', 'hospital')
REFERENCES = dict(bus=600., mtr=900., hospital=5000.)
COST_COLUMNS = dict(bus='bus_time_s', mtr='mtr_time_s', hospital='hospital_distance_m')
CATEGORIES = ('Urban', 'Extended Urban', 'New Territories', 'Islands')
SCENARIOS = ('primary', 'baseline')


def scoring_policy(weights=None):
    supplied = dict.fromkeys(COMPONENTS, 1.) if weights is None else weights
    if not isinstance(supplied, dict) or set(supplied) != set(COMPONENTS):
        raise ValueError('weights must contain exactly bus, mtr and hospital')
    raw = {}
    for name in COMPONENTS:
        value = supplied[name]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError('Weights must be finite nonnegative numbers')
        try:
            value = float(value)
        except (ValueError, OverflowError) as exc:
            raise ValueError('Weights must be finite nonnegative numbers') from exc
        if not np.isfinite(value) or value < 0:
            raise ValueError('Weights must be finite nonnegative numbers')
        raw[name] = value
    maximum = max(raw.values())
    if maximum == 0:
        raise ValueError('At least one weight must be positive')
    relative = np.array([raw[k] / maximum for k in COMPONENTS])
    normalised = relative / relative.sum()
    return dict(schema_version=1, formula='100 * (x / (x + k))', lower_is_better=True,
        references=REFERENCES.copy(), units=dict(bus='seconds', mtr='seconds', hospital='metres'),
        supplied_weights=raw, normalised_weights=dict(zip(COMPONENTS, map(float, normalised))),
        active_components=[k for k in COMPONENTS if raw[k] > 0],
        ties='exact_unrounded_competition',
        incomplete_order='available_required_count_desc_then_name_casefold_then_id',
        missing_total_and_rank=True)


def _options(wheelchair=False, scenario='primary', housing_district=None, hospital_id=None):
    if not isinstance(wheelchair, (bool, np.bool_)):
        raise ValueError('wheelchair must be a boolean')
    if scenario not in SCENARIOS:
        raise ValueError('scenario must be primary or baseline')
    if housing_district is not None and housing_district not in CATEGORIES:
        raise ValueError('Unknown housing allocation category: ' + str(housing_district))
    if hospital_id is not None and not isinstance(hospital_id, str):
        raise ValueError('hospital_id must be a hospital ID string or None')


def _reference(directory):
    directory = Path(directory).resolve(strict=True)
    try:
        name = str(directory.relative_to(WORK))
    except ValueError:
        name = str(directory)
    return dict(run_id=directory.name, directory=name,
                manifest_sha256=sha256(directory / 'manifest.json'))


def _freeze_source(directory=None):
    # The default Step 4 reader also checks its selected rebuild pair. Resolve once.
    cache = _journey_reader(directory)
    reference = _reference(cache.directory)
    verify_hashes(cache.directory, cache.manifest['artifacts'])
    return cache, reference


def _verify_source(reference, require_selected=False):
    directory = (WORK / reference['directory']).resolve(strict=True)
    if _reference(directory) != reference:
        raise ValueError('Pinned Step 4 manifest or run identity changed')
    cache = _journey_reader(directory)
    if cache.manifest['run_id'] != reference['run_id']:
        raise ValueError('Pinned Step 4 run identity differs')
    verify_hashes(directory, cache.manifest['artifacts'])
    for item in cache.frozen.values():
        if isinstance(item, dict) and 'manifest_sha256' in item:
            upstream = WORK / item['directory']
            if sha256(upstream / 'manifest.json') != item['manifest_sha256']:
                raise ValueError('Pinned upstream graph manifest changed')
    if require_selected:
        selected = _journey_reader()
        if _reference(selected.directory) != reference:
            raise ValueError('Step 5 is incompatible with the selected Step 4 cache')
    return cache


def _score(source, policy, housing_district=None):
    """Pure scoring over preserved Step 4 columns; pandas supplies ranking/sorting."""
    if not isinstance(source, gpd.GeoDataFrame) or source.crs is None or source.crs.to_epsg() != 2326:
        raise ValueError('Expected an EPSG:2326 estate GeoDataFrame')
    required = ['id', 'name', 'housing_district']
    for name in COMPONENTS:
        required.extend([COST_COLUMNS[name], name + '_status', name + '_unit'])
    if any(c not in source for c in required):
        raise ValueError('Required estate/subcost field is missing')
    if source.id.isna().any() or source.id.duplicated().any():
        raise ValueError('Estate IDs must be non-null and unique')
    if not source.housing_district.isin(CATEGORIES).all():
        raise ValueError('Unknown or missing estate allocation category')
    result = source.copy().reset_index(drop=True)
    # pandas' deep copy does not copy lists/dicts inside object columns. Return
    # independent destination/warning lists rather than exposing Step 4's cache.
    for column in result.columns:
        if result[column].dtype == object:
            result[column] = result[column].map(
                lambda value: copy.deepcopy(value) if isinstance(value, (list, dict)) else value)
    available = {}
    for name in COMPONENTS:
        status = result[name + '_status']
        if not status.isin(['ok', 'unreachable']).all():
            raise ValueError('Unknown subcost status: ' + name)
        if not result[name + '_unit'].eq(policy['units'][name]).all():
            raise ValueError('Unexpected subcost units: ' + name)
        numeric = pd.to_numeric(result[COST_COLUMNS[name]], errors='raise')
        values = numeric.to_numpy(dtype=float, na_value=np.nan)
        ok = status.eq('ok').to_numpy()
        missing = result[COST_COLUMNS[name]].isna().to_numpy()
        if (ok & (~np.isfinite(values) | (values < 0))).any() or (~ok & ~missing).any():
            raise ValueError('Inconsistent status/cost for ' + name)
        scaled = np.full(len(result), np.nan)
        scaled[ok] = 100 * (values[ok] / (values[ok] + policy['references'][name]))
        result[name + '_scaled_cost'] = pd.array(scaled, dtype='Float64')
        available[name] = ok
    active = policy['active_components']
    count = np.sum([available[name] for name in active], axis=0, dtype=int)
    complete = count == len(active)
    total = np.full(len(result), np.nan)
    total[complete] = 0.
    # Do not multiply missing inactive values by zero. Positive supplied weights
    # remain required even if their normalised floating-point value underflows.
    for name in active:
        values = result[name + '_scaled_cost'].to_numpy(dtype=float, na_value=np.nan)
        total[complete] += values[complete] * policy['normalised_weights'][name]
    # Bound only floating-point accumulation noise; raw journey costs stay intact.
    total[complete] = np.clip(total[complete], 0., 100.)
    result['required_component_count'] = pd.array([len(active)] * len(result), dtype='Int64')
    result['available_required_component_count'] = pd.array(count, dtype='Int64')
    result['missing_components'] = [[name for name in active if not available[name][i]]
                                    for i in range(len(result))]
    result['ranking_status'] = np.where(complete, 'complete', 'incomplete')
    result['final_cost'] = pd.array(total, dtype='Float64')
    if housing_district is not None:
        result = result.loc[result.housing_district == housing_district].copy()
    result['rank'] = result.final_cost.rank(method='min', na_option='keep').astype('Int64')
    english = result['name_en'] if 'name_en' in result else result['name']
    display = english.where(english.notna() & english.ne(''), result['name']).fillna('')
    ordering = pd.DataFrame(dict(incomplete=result.ranking_status.eq('incomplete'),
        cost=result.final_cost, count=result.available_required_component_count,
        name=display.astype(str).str.casefold(), id=result.id), index=result.index)
    order = ordering.sort_values(['incomplete', 'cost', 'count', 'name', 'id'],
        ascending=[True, True, False, True, True], kind='stable', na_position='last').index
    result = result.loc[order].reset_index(drop=True)
    result.attrs.update(scoring_policy=policy, housing_district_filter=housing_district)
    return result


def rank_estates(housing_district=None, wheelchair=False, hospital_id=None, scenario='primary',
                 weights=None, step_4_directory=None):
    """Return ranked estates with raw/scaled costs, provenance and nullable ranks."""
    _options(wheelchair, scenario, housing_district, hospital_id)
    policy = scoring_policy(weights)
    cache, reference = _freeze_source(step_4_directory)
    source = read_subcosts(bool(wheelchair), hospital_id, scenario, directory=cache.directory)
    result = _score(source, policy, housing_district)
    result.attrs.update(step_4=reference, requested_hospital_id=hospital_id,
                        mode='wheelchair' if wheelchair else 'general', scenario=scenario)
    return result


def _layer(wheelchair, scenario):
    return scenario + ('_wheelchair' if wheelchair else '_general')


def _write_views(directory, views):
    schema = dict(schema_version=1, layers={})
    for layer, frame in views.items():
        saved = frame.copy()
        fields = {}
        for name in frame.columns:
            if name == frame.geometry.name:
                continue
            encoded = frame[name].map(lambda value: isinstance(value, (list, dict))).any()
            fields[name] = dict(dtype=str(frame[name].dtype), json_encoded=bool(encoded))
            if encoded:
                saved[name] = frame[name].map(lambda value: json.dumps(
                    value if isinstance(value, (list, dict)) or pd.notna(value) else None,
                    ensure_ascii=False, allow_nan=False))
        schema['layers'][layer] = dict(rows=len(frame), columns=list(frame.columns), fields=fields,
            crs=frame.crs.to_string(), metadata=frame.attrs)
        saved.to_file(Path(directory) / 'rankings.gpkg', layer=layer, engine='pyogrio')
    write_json(Path(directory) / 'schema.json', schema)


def _read_view(directory, layer):
    definition = read_json(Path(directory) / 'schema.json')['layers'][layer]
    result = gpd.read_file(Path(directory) / 'rankings.gpkg', layer=layer, engine='pyogrio')
    if (list(result.columns.drop(result.geometry.name)) !=
        [c for c in definition['columns'] if c != result.geometry.name] or
        len(result) != definition['rows'] or
        result.crs.to_string() != definition['crs']):
        raise ValueError('Saved ranking schema/CRS differs')
    # GeoPackage readers put geometry last; the public object preserves its
    # original column position as well as every attribute's type and value.
    result = result.loc[:, definition['columns']]
    for name, field in definition['fields'].items():
        if field['json_encoded']:
            result[name] = result[name].map(json.loads)
        result[name] = result[name].astype(field['dtype'])
    result.attrs.update(definition['metadata'])
    return result


def read_rankings(wheelchair=False, scenario='primary', directory=None):
    """Read a saved whole-candidate view; explicit directories reopen history."""
    _options(wheelchair, scenario)
    explicit = directory is not None
    path = Path(directory or WORK / 'precomputed/outputs/step_5/current').resolve(strict=True)
    manifest, success = read_json(path / 'manifest.json'), read_json(path / 'SUCCESS.json')
    if (manifest['schema_version'] != 1 or success['validation'] != 'passed' or
        success['run_id'] != manifest['run_id'] or path.name != success['run_id']):
        raise ValueError('Unsuccessful or unsupported Step 5 output')
    verify_hashes(path, manifest['artifacts'])
    frozen = read_json(path / 'frozen_inputs.json')
    if frozen != manifest['frozen_inputs']:
        raise ValueError('Step 5 frozen references differ')
    source = _verify_source(frozen['step_4'], require_selected=not explicit)
    if source.frozen != frozen['frozen_pair']:
        raise ValueError('Step 5 frozen graph pair differs')
    policy = read_json(path / 'scoring_policy.json')
    if policy != scoring_policy(policy['supplied_weights']) or policy != manifest['policy']:
        raise ValueError('Unsupported or inconsistent scoring policy')
    result = _read_view(path, _layer(wheelchair, scenario))
    if (result.attrs['step_4'] != frozen['step_4'] or result.attrs['scoring_policy'] != policy or
        result.attrs['mode'] != ('wheelchair' if wheelchair else 'general') or
        result.attrs['scenario'] != scenario):
        raise ValueError('Saved ranking metadata differs')
    result.attrs.update(step_5_run_id=manifest['run_id'])
    return result


def run(output_root=None, hospital_id=None, weights=None, step_4_directory=None):
    """Stage, reopen, verify and atomically select four spatial ranking views."""
    start = time.perf_counter()
    root = Path(output_root or WORK / 'precomputed/outputs/step_5')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    directory = WORK / 'cache/step_5_staging' / run_id
    directory.mkdir(parents=True)
    code = [Path(__file__), Path(__file__).with_name('step_4.py')]
    hashes = {p.name: sha256(p) for p in code}
    try:
        _options(hospital_id=hospital_id)
        policy = scoring_policy(weights)
        source, reference = _freeze_source(step_4_directory)
        frozen = dict(step_4=reference, frozen_pair=source.frozen)
        write_json(directory / 'frozen_inputs.json', frozen)
        write_json(directory / 'scoring_policy.json', policy)
        views = {}
        print('Score four views from frozen Step 4 ' + reference['run_id'], flush=True)
        for scenario in SCENARIOS:
            for wheelchair in (False, True):
                frame = rank_estates(wheelchair=wheelchair, hospital_id=hospital_id, scenario=scenario,
                                     weights=weights, step_4_directory=source.directory)
                if frame.attrs['step_4'] != reference or len(frame) != len(source.estates):
                    raise ValueError('Source identity or estate accounting changed during scoring')
                views[_layer(wheelchair, scenario)] = frame
        _write_views(directory, views)
        counts = {}
        shared = None
        for layer, expected in views.items():
            actual = _read_view(directory, layer)
            assert_frame_equal(expected, actual, check_exact=True)
            if expected.attrs != actual.attrs:
                raise ValueError('Ranking metadata changed during save/reopen')
            hospital = actual.set_index('id')[['hospital_distance_m', 'hospital_scaled_cost',
                                               'hospital_target_ids', 'hospital_status']].sort_index()
            if shared is not None:
                assert_frame_equal(hospital, shared, check_exact=True)
            shared = hospital
            counts[layer] = dict(rows=len(actual), complete=int(actual.ranking_status.eq('complete').sum()),
                incomplete=int(actual.ranking_status.eq('incomplete').sum()),
                missing_by_component={name: int(actual[name + '_status'].ne('ok').sum()) for name in COMPONENTS})
        _verify_source(reference, require_selected=step_4_directory is None)
        for item in source.frozen.values():
            if isinstance(item, dict) and 'manifest_sha256' in item:
                upstream = WORK / item['directory']
                verify_hashes(upstream, read_json(upstream / 'manifest.json')['artifacts'])
        if any(sha256(p) != hashes[p.name] for p in code):
            raise ValueError('Implementation changed during Step 5 build')
        report = dict(status='passed', run_id=run_id, views=counts, source_step_4=reference,
            routing_searches=0, raw_costs_and_geometry_preserved=True, all_fields_exact_roundtrip=True,
            shared_hospital_results_identical=True, runtime_seconds=time.perf_counter() - start,
            payload_bytes=sum(p.stat().st_size for p in directory.iterdir()))
        write_json(directory / 'validation_report.json', report)
        write_json(directory / 'SUCCESS.json', dict(run_id=run_id, validation='passed',
            completed_utc=datetime.now(timezone.utc).isoformat()))
        write_json(directory / 'manifest.json', dict(schema_version=1, run_id=run_id,
            frozen_inputs=frozen, policy=policy, implementation_sha256=hashes,
            artifacts={p.name: dict(sha256=sha256(p), bytes=p.stat().st_size)
                       for p in sorted(directory.iterdir()) if p.is_file()}))
        for scenario in SCENARIOS:
            for wheelchair in (False, True):
                actual = read_rankings(wheelchair, scenario, directory)
                expected = views[_layer(wheelchair, scenario)]
                assert_frame_equal(actual, expected, check_exact=True)
        _verify_source(reference, require_selected=step_4_directory is None)
        target = root / 'runs' / run_id
        target.parent.mkdir(parents=True, exist_ok=True)
        directory.rename(target)
        publish_run(target, root / 'current')
        print('Published Step 5: ' + str(target), flush=True)
        return target
    except BaseException:
        if directory.exists():
            write_json(directory / 'FAILURE.json', dict(run_id=run_id, traceback=traceback.format_exc()))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hospital-id')
    for name in COMPONENTS:
        parser.add_argument('--' + name + '-weight', type=float, default=1.)
    parser.add_argument('--step-4-directory', type=Path)
    parser.add_argument('--output-root', type=Path)
    args = parser.parse_args()
    from contextlib import ExitStack
    with ExitStack() as stack:
        for name in ('rebuild', 'step_4', 'step_5'):
            path = WORK / 'cache' / (name + '.lock')
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context(path.open('a'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.output_root, args.hospital_id, {k: getattr(args, k + '_weight') for k in COMPONENTS},
            args.step_4_directory)


if __name__ == '__main__':
    main()
