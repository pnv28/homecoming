"""Build and atomically select validated facility connections from frozen inputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import time
import traceback
import uuid

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import shapely
from scipy.sparse.csgraph import connected_components

from .attachments import (ATTACHMENT_POLICY, LAYERS, attach_points, attached_routing_graph,
    load_entities, read_attached_graph, read_attached_points, save_attached,
    save_attached_routing)
from .export import write_json
from .graph import WORK, connectivity, read_physical
from .graph_regressions import check_lift_connections
from .graph_cluster_audit import check_repaired_endpoint_cluster
from .ingest import read_json, sha256
from .step_2 import publish_run, verify_routing
from .time_fallback import derived_policy, routing_prefix


STEP_2_RUN = '20261014T105436Z-8fe534aa'
STEP_1_RUN = '20261014T090829Z-20d0139c'


def progress(message):
    print(message, flush=True)


def verify_hashes(directory, hashes):
    for name, value in hashes.items():
        digest = value['sha256'] if isinstance(value, dict) else value
        if sha256(Path(directory) / name) != digest:
            raise ValueError('Frozen artifact hash mismatch: ' + str(Path(directory) / name))


def freeze_inputs(step_2_directory):
    step_2 = Path(step_2_directory).resolve(strict=True)
    success = read_json(step_2 / 'SUCCESS.json')
    manifest = read_json(step_2 / 'manifest.json')
    if success['run_id'] != manifest['run_id'] or step_2.name != success['run_id']:
        raise ValueError('Step 2 success/manifest/directory identity mismatch')
    if success['validation'] != 'passed' or read_json(step_2 / 'validation_report.json')['status'] != 'passed':
        raise ValueError('Step 2 did not pass validation')
    verify_hashes(step_2, manifest['artifacts'])
    frozen = read_json(step_2 / 'frozen_input.json')
    step_1 = (WORK / frozen['directory']).resolve(strict=True)
    if frozen['run_id'] != STEP_1_RUN or read_json(step_1 / 'SUCCESS.json')['run_id'] != STEP_1_RUN:
        raise ValueError('Frozen Step 1 identity mismatch')
    if read_json(step_1 / 'validation_report.json')['errors'] != 0:
        raise ValueError('Step 1 did not pass validation')
    verify_hashes(step_1, frozen['files'])
    selected_policy = read_json(step_2 / 'model_policy.json')
    if read_json(step_1 / 'model_policy.json') != frozen['policy']:
        raise ValueError('Frozen source preparation policies differ')
    if derived_policy(frozen['policy'], selected_policy) != selected_policy:
        raise ValueError('Unrecorded derived routing policy')
    result = {'step_2': {'run_id': success['run_id'], 'directory': str(step_2.relative_to(WORK)),
        'files': {**manifest['artifacts'], 'manifest.json': sha256(step_2 / 'manifest.json')}},
        'step_1': {'run_id': STEP_1_RUN, 'directory': str(step_1.relative_to(WORK)),
                   'files': frozen['files']}, 'network_policy': selected_policy,
                   'source_preparation_policy': frozen['policy']}
    return step_2, step_1, result


def validate_attachments(attached, full=False):
    attachments = attached.attachments
    if attachments.attachment_id.duplicated().any():
        raise AssertionError('Duplicate attachment identity')
    expected = sum(len(f) * (4 if kind == 'estate' else 2) for kind, f in attached.entities.items())
    primary = attachments.loc[attachments.scenario == 'primary'] if 'scenario' in attachments else attachments
    if len(primary) != expected:
        raise AssertionError('Missing entity/mode/metric records')
    counts = {kind: len(f) for kind, f in attached.entities.items()}
    if full and counts != {'estate': 244, 'hospital': 44, 'mtr_access': 611, 'bus_stop': 9264}:
        raise AssertionError('Frozen entity counts changed')
    selected = attachments.loc[attachments.status == 'attached']
    if ((selected.distance_m < 0) | ~np.isfinite(selected.distance_m)).any():
        raise AssertionError('Connector distance must be finite and nonnegative')
    above = selected.distance_m > selected.maximum_distance_m
    if not np.array_equal(above, selected.connector_above_threshold):
        raise AssertionError('Beyond-threshold connector flag mismatch')
    if not selected.loc[above, 'warnings'].str.contains('connector_above_threshold').all():
        raise AssertionError('Beyond-threshold connection lacks its warning')
    if not np.allclose(selected.time_s, selected.distance_m * .6 * np.exp(.175), rtol=2e-12, atol=1e-9):
        raise AssertionError('Flat connector cost mismatch')
    if not shapely.has_z(selected.geometry).all() or attachments.loc[attachments.status != 'attached'].geometry.notna().any():
        raise AssertionError('Attachment height/status geometry mismatch')
    if selected.node_index.isna().any() or not selected.node_index.between(0, len(attached.physical.nodes) - 1).all():
        raise AssertionError('Attachment node missing')
    if len(attached.connectors) != int((~selected.zero_distance).sum()):
        raise AssertionError('Zero/positive connector accounting mismatch')
    if (attached.connectors.length <= 0).any() or shapely.has_z(attached.connectors.geometry).any():
        raise AssertionError('Connector must be a positive 2D line')
    if not np.allclose(attached.connectors.length, attached.connectors.distance_m, rtol=2e-12, atol=1e-8):
        raise AssertionError('Connector geometry/cost mismatch')
    for frame in attached.entities.values():
        if shapely.has_z(frame.geometry).any():
            raise AssertionError('Entity height was invented')
    coverage = {}
    for (scenario, kind, mode, metric), rows in attachments.groupby(['scenario', 'entity_type', 'mode', 'metric']):
        distances = rows.loc[rows.status == 'attached', 'distance_m']
        coverage[('baseline/' if scenario == 'baseline' else '') + '/'.join((kind, mode, metric))] = {
            'records': len(rows), 'statuses': dict(Counter(rows.status)),
            'eligible': int((rows.status != 'excluded').sum()),
            'distance_m': {str(p): float(distances.quantile(p)) for p in (0., .5, .9, .95, 1.)}
                          if len(distances) else {},
            'warnings': dict(Counter(w for text in rows.warnings for w in text.split(';') if w))}
    if full:
        for kind, mode, count in [('mtr_access', 'general', 598), ('mtr_access', 'wheelchair', 276),
                ('bus_stop', 'general', 8848), ('bus_stop', 'wheelchair', 4130)]:
            if coverage[kind + '/' + mode + '/time']['eligible'] != count:
                raise AssertionError('Frozen destination eligibility changed')
    return {'source_points': sum(counts.values()), 'counts_by_type': counts,
            'attachment_records': len(primary), 'baseline_attachment_records': len(attachments)-len(primary),
            'all_source_points_accounted_for': True,
            'coverage': coverage, 'zero_distance_attachments': int(selected.zero_distance.sum()),
            'candidate_review_rows': len(attached.candidates), 'unknown_entity_heights_preserved': True,
            **attached.validation}


def validate_terminals(graph):
    states = graph.states
    if states.loc[states.state_kind == 'terminal', 'node_index'].notna().any():
        raise AssertionError('Terminal given a physical node/height')
    rows = graph.transitions
    terminal_set = set(graph.terminals.state_index)
    arrivals = set(graph.terminals.loc[graph.terminals.role == 'arrival', 'state_index'])
    departures = set(graph.terminals.loc[graph.terminals.role == 'departure', 'state_index'])
    if rows.from_state.isin(arrivals).any() or rows.to_state.isin(departures).any():
        raise AssertionError('Terminal permits a shortcut or wrong direction')
    if (rows.from_state.isin(terminal_set) & rows.to_state.isin(terminal_set)).any():
        raise AssertionError('Direct terminal shortcut')
    excluded = set(graph.terminals.loc[graph.terminals.status != 'attached', 'state_index'])
    if rows.from_state.isin(excluded).any() or rows.to_state.isin(excluded).any():
        raise AssertionError('Unattached/excluded terminal has a transition')
    links = rows.loc[rows.edge_index < 0]
    references = graph.attachments.set_index('attachment_id')
    by_aid = {aid: f for aid, f in links.groupby('source_id', sort=False)}
    physical_states = states.loc[states.state_kind == 'physical'].groupby('node_index').state_index.agg(list).to_dict()
    for terminal in graph.terminals.itertuples():
        attachment = references.loc[terminal.attachment_id]
        if terminal.status != 'attached':
            continue
        evidence = by_aid.get(terminal.attachment_id)
        if evidence is None:
            raise AssertionError('Attached terminal has no connector')
        wanted = attachment.distance_m if graph.metric == 'distance' else attachment.time_s
        if not np.allclose(evidence.cost, wanted, rtol=0, atol=0):
            raise AssertionError('Terminal connector cost changed')
        if terminal.role == 'departure':
            if len(evidence) != 1 or states.loc[evidence.to_state, 'lift_id'].notna().any():
                raise AssertionError('Estate enters with a current lift identity')
        elif set(evidence.from_state) != set(physical_states[int(terminal.node_index)]):
            raise AssertionError('Destination omits attachment lift states')
    return {'terminals': len(graph.terminals), 'terminal_statuses': dict(Counter(graph.terminals.status)),
            'connector_transitions': len(links), 'one_way_terminal_roles_verified': True,
            'lift_arrivals_and_departures_verified': True, 'no_terminal_shortcuts': True}


def verify_frames(expected, actual):
    frames = [('nodes', expected.physical.nodes, actual.physical.nodes),
              ('edges', expected.physical.edges, actual.physical.edges),
              ('attachments', expected.attachments, actual.attachments),
              ('connectors', expected.connectors, actual.connectors)]
    frames.extend((kind, frame, actual.entities[kind]) for kind, frame in expected.entities.items())
    for name, a, b in frames:
        if a.crs != b.crs or not np.array_equal(shapely.to_wkb(a.geometry), shapely.to_wkb(b.geometry)):
            raise AssertionError('Spatial roundtrip changed: ' + name)
        assert_frame_equal(a.drop(columns='geometry'), b.drop(columns='geometry'), check_exact=True)
    assert_frame_equal(expected.physical.memberships, actual.physical.memberships, check_exact=True)
    assert_frame_equal(expected.candidates, actual.candidates, check_dtype=False, check_exact=True)
    return {name: len(a) for name, a, _ in frames}


def run(input_directory=None, output_root=None, select=True):
    start = time.perf_counter()
    output_root = Path(output_root or WORK / 'precomputed/outputs/step_3')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    directory = WORK / 'cache/step_3_staging' / run_id
    directory.mkdir(parents=True)
    code_paths = [Path(__file__).with_name(n) for n in
                  ('step_3.py', 'attachments.py', 'graph.py', 'graph_costs.py', 'graph_topology.py', 'time_fallback.py', 'run_registry.py', 'rebuild.py')]
    code_hashes = {p.name: sha256(p) for p in code_paths}
    try:
        progress('1/5 Verify and freeze Step 2 and its referenced Step 1')
        from .run_registry import selected_run
        step_2, step_1, frozen = freeze_inputs(input_directory or selected_run('step_2', WORK))
        write_json(directory / 'frozen_inputs.json', frozen)
        write_json(directory / 'attachment_policy.json', ATTACHMENT_POLICY)
        write_json(directory / 'model_policy.json', frozen['network_policy'])
        progress('2/5 Load original entities and attach to suitable network pieces')
        physical = read_physical(step_2)
        entities = load_entities(step_1)
        attached = attach_points(physical, entities, step_2, progress)
        report = {'status': 'passed', 'run_id': run_id, 'attachments': validate_attachments(attached, full=True)}
        del physical
        gc.collect()
        progress('3/5 Save and reopen every spatial record, attribute and mapping')
        save_attached(directory, attached, step_2)
        reopened = read_attached_points(directory)
        report['spatial_roundtrip'] = verify_frames(attached, reopened)
        report['routing'] = {}
        for wheelchair in (False, True):
            for metric, scenario in [('time', 'primary'), ('distance', 'primary'), ('time', 'baseline')]:
                key = routing_prefix(wheelchair, metric, scenario)
                progress('4/5 Compile and verify ' + key)
                graph = attached_routing_graph(attached, wheelchair, metric, scenario)
                for connection in ('weak', 'strong'):
                    _, labels = connected_components(graph.matrix, directed=True, connection=connection)
                    graph.states[connection + '_component'] = labels
                summary = {**connectivity(graph), **validate_terminals(graph)}
                save_attached_routing(directory, graph)
                loaded = read_attached_graph(directory, wheelchair, metric, reopened, scenario)
                summary['roundtrip'] = verify_routing(graph, loaded)
                assert_frame_equal(graph.terminals, loaded.terminals, check_dtype=False, check_exact=True)
                validate_terminals(loaded)
                summary['upstream_endpoint_regression'] = check_repaired_endpoint_cluster(loaded)
                if metric == 'time':
                    summary['upstream_lift_regressions'] = check_lift_connections(loaded)
                report['routing'][key] = summary
                del graph, loaded
                gc.collect()
        progress('5/5 Recheck input/code hashes and publish successful selection')
        for key, source in [('step_2', step_2), ('step_1', step_1)]:
            verify_hashes(source, frozen[key]['files'])
        if any(sha256(p) != code_hashes[p.name] for p in code_paths):
            raise ValueError('Implementation changed during build')
        report.update(frozen_hashes_rechecked=True, implementation_hashes_rechecked=True,
            runtime_seconds=round(time.perf_counter() - start, 3),
            limitations=['Straight flat connectors are accepted map-point approximations, not surveyed entrances or slopes.',
                'Every attached entity has unknown height; nearest path level is an assumption recorded for review.',
                'Unattached and excluded records remain visible; attachment does not establish estate-to-target reachability.',
                'Estate subcosts and ranking remain Step 4 and later work.'])
        write_json(directory / 'validation_report.json', report)
        (directory / 'validation_report.md').write_text('# Step 3 validation\n\nStatus: passed.\n\n'
            'All input points are retained. Connector assumptions and unattached points remain visible.\n\n'
            + '```json\n' + json.dumps(report, indent=2) + '\n```\n')
        write_json(directory / 'SUCCESS.json', {'run_id': run_id, 'validation': 'passed',
            'completed_utc': datetime.now(timezone.utc).isoformat()})
        manifest = {'run_id': run_id, 'frozen_inputs': frozen, 'implementation_sha256': code_hashes,
            'software': {name: importlib.metadata.version(name) for name in
                ('numpy', 'pandas', 'shapely', 'geopandas', 'pyogrio', 'scipy')},
            'artifacts': {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size}
                          for p in sorted(directory.iterdir()) if p.is_file()}}
        write_json(directory / 'manifest.json', manifest)
        target = output_root / 'runs' / run_id
        target.parent.mkdir(parents=True, exist_ok=True)
        directory.rename(target)
        if select:
            publish_run(target, output_root / 'current')
        progress('Published Step 3: ' + str(target))
        return target
    except BaseException:
        if directory.exists():
            write_json(directory / 'FAILURE.json', {'run_id': run_id, 'traceback': traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-directory')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    lock_path = WORK / 'cache/step_3.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.input_directory, args.output_root)


if __name__ == '__main__':
    main()
