"""Reviewed hospital-only origin overrides; reuse frozen graph and transport cache."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shutil
import time
import traceback
import uuid

import numpy as np
import pandas as pd

from .attachments import ORDINARY_TYPES, _can_use
from .export import write_json
from .graph import WORK
from .ingest import read_json, sha256
from .routes import check_cost
from .step_2 import publish_run
from .step_3 import verify_hashes


def load_overrides(pair, path=None):
    policy = read_json(path or WORK / 'config/step_4_hospital_overrides.json')
    reference = pair['step_3']
    if (policy['schema_version'] != 1 or
        policy['scope'] != 'hospital_only_shared_general_distance' or
        policy['step_3_run_id'] != reference['run_id'] or
        policy['step_3_manifest_sha256'] != reference['manifest_sha256']):
        raise ValueError('Hospital overrides require review for the selected Step 3 snapshot')
    ids = [r['estate_id'] for r in policy['overrides']]
    if len(ids) != len(set(ids)) or set(ids) & set(policy['unchanged_unavailable_estates']):
        raise ValueError('Duplicate or excluded hospital override estate')
    return policy


def resolve_override(graph, specification, original):
    """Verify the reviewed node/source and derive a horizontal map-point connector."""
    if graph.metric != 'distance' or graph.wheelchair:
        raise ValueError('Hospital overrides require the shared general-distance graph')
    ni, sid = int(specification['node_index']), specification['source_id']
    nodes = graph.nodes.loc[graph.nodes.node_index == ni]
    if len(nodes) != 1 or nodes.iloc[0].node_id != specification['node_id']:
        raise ValueError('Hospital override node identity differs')
    position = list(nodes.geometry.iloc[0].coords[0])
    if not np.allclose(position, specification['position'], rtol=0, atol=1e-8):
        raise ValueError('Hospital override node coordinates differ')
    source = graph.physical.sources.loc[graph.physical.sources.PedestrianRouteID.astype(str) == sid]
    if (len(source) != 1 or source.iloc[0].FeatureType_label not in ORDINARY_TYPES or
        source.iloc[0].Location_label != 'Outdoor'):
        raise ValueError('Hospital override is not a reviewed ordinary outdoor source')
    edges = graph.edges.loc[(graph.edges.source_id == sid) & graph.edges.allow_general &
                            ((graph.edges.from_node == ni) | (graph.edges.to_node == ni))]
    positions = set()
    for edge in edges.itertuples():
        for node, value in ((edge.from_node, edge.start_position), (edge.to_node, edge.end_position)):
            if node == ni and _can_use(edge, value, 'departure', 'distance'):
                positions.add(float(value))
    if len(positions) != 1:
        raise ValueError('Missing or ambiguous permitted override source position')
    states = graph.states.loc[(graph.states.node_index == ni) & graph.states.lift_id.isna() &
                              (graph.states.state_kind == 'physical')]
    if len(states) != 1:
        raise ValueError('Hospital override has no unique ordinary physical state')
    entity = graph.entities['estate'].set_index('id').loc[specification['estate_id']]
    distance = float(np.hypot(entity.geometry.x - position[0], entity.geometry.y - position[1]))
    warnings = sorted({
        'reviewed_hospital_origin_override', 'map_point_approximation',
        'point_height_unknown', 'entrance_and_level_unverified'})
    attachment = dict(entity_id=specification['estate_id'],
        attachment_id='hospital-override:' + specification['estate_id'], status='attached', reason='',
        source_id=sid, source_position=positions.pop(), position=position, distance_m=distance,
        warnings=warnings)
    return dict(**specification, state_index=int(states.iloc[0].state_index),
                original_attachment=original, attachment=attachment,
                reason='Reviewed hospital-only connection replacing an isolated map-point attachment')


def apply_overrides(data, graph, directory, policy):
    """Replace only specified hospital pairs; append two shared predecessor blocks."""
    from .step_4 import SearchCache
    directory = Path(directory)
    cache = SearchCache(graph, 'general_distance')
    hospitals = sorted(graph.terminals.loc[graph.terminals.entity_type == 'hospital', 'entity_id'])
    old_routes = {r['route_id']: r for r in data['routes']}
    overridden, before = [], {}
    # Resolve all specifications before calculating or writing anything.
    for specification in policy['overrides']:
        estate = specification['estate_id']
        rows = [r for r in data['routes'] if r['graph'] == 'general_distance' and r['estate_id'] == estate]
        if len(rows) != len(hospitals) or {r['target_id'] for r in rows} != set(hospitals):
            raise ValueError('Hospital override estate does not have every cached hospital pair')
        original = rows[0].get('origin_override', {}).get('original_attachment') or cache.attachment(estate)
        overridden.append(resolve_override(graph, specification, original))
        before[estate] = sum(r['status'] == 'ok' for r in rows)
    for override in overridden:
        estate = override['estate_id']
        cache.retain_search(estate, lambda costs: [(estate, h, ['hospital_pair']) for h in hospitals],
                            origin_override=override)
    link_path = directory / 'general_distance_links.npz'
    with np.load(link_path, allow_pickle=False) as archive:
        blocks = {key: archive[key] for key in archive.files}
    offset = len(blocks)
    if set(blocks) != {'s' + str(i) for i in range(offset)}:
        raise ValueError('Non-contiguous existing hospital predecessor blocks')
    for i, block in enumerate(cache.blocks):
        blocks['s' + str(offset + i)] = block
        cache.searches[i]['block'] += offset
    replacements = {r['route_id']: r for r in cache.routes}
    if not set(replacements) <= set(old_routes):
        raise ValueError('Hospital amendment unexpectedly creates a new pair identity')
    data['routes'] = [replacements.get(r['route_id'], r) for r in data['routes']]
    replaced_search_ids = {s['search_id'] for s in cache.searches}
    data['searches'] = [s for s in data['searches'] if s['search_id'] not in replaced_search_ids] + cache.searches
    np.savez_compressed(link_path, **blocks)
    results = []
    for override in overridden:
        rows = [r for r in cache.routes if r['estate_id'] == override['estate_id']]
        finite = [r['cost'] for r in rows if r['cost'] is not None]
        if not finite:
            raise ValueError('Reviewed replacement still cannot reach any hospital')
        results.append(dict(estate_id=override['estate_id'], estate_name=override['estate_name'],
            node_index=override['node_index'], connection_m=override['attachment']['distance_m'],
            reachable_pairs_before=before[override['estate_id']],
            reachable_pairs_after=len(finite), nearest_hospital_m=min(finite)))
    return dict(production_searches=len(overridden), updated_pairs=len(replacements), estates=results,
                unchanged_unavailable_estates=policy['unchanged_unavailable_estates'])


def _write_hospital_layer(directory, data, estates):
    from .step_4 import _spatial
    frame = _spatial([r for r in data['routes'] if r['graph'] == 'general_distance'], estates)
    for col in frame:
        if col != 'geometry' and frame[col].map(lambda x: isinstance(x, (list, dict))).any():
            import json
            frame[col] = frame[col].map(lambda x: json.dumps(
                x if isinstance(x, (list, dict)) or pd.notna(x) else None,
                ensure_ascii=False, allow_nan=False))
    frame.to_file(Path(directory) / 'results.gpkg', layer='hospital_costs', engine='pyogrio')


def amend(output_root=None):
    """Publish a derived Step 4 cache with two searches and no graph rebuild."""
    from .step_4 import (JourneyCache, freeze_pair, validate_saved, read_subcosts,
                         read_hospital_costs, _opened)
    started = time.perf_counter()
    pair, upstream = freeze_pair()
    policy = load_overrides(pair)
    root = Path(output_root or WORK / 'precomputed/outputs/step_4')
    parent = JourneyCache(root / 'current') if output_root else JourneyCache()
    if parent.frozen != pair:
        raise ValueError('Parent Step 4 cache uses a different frozen pair')
    parent_manifest = sha256(parent.directory / 'manifest.json')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    directory = WORK / 'cache/step_4_staging' / run_id
    directory.mkdir(parents=True)
    code = [Path(__file__).with_name(name) for name in ('step_4.py', 'routes.py', 'hospital_amendment.py')]
    hashes = {path.name: sha256(path) for path in code}
    try:
        for path in parent.directory.iterdir():
            if path.is_file() and path.name not in ('manifest.json', 'SUCCESS.json', 'validation_report.json'):
                shutil.copy2(path, directory / path.name)
        write_json(directory / 'hospital_overrides.json', policy)
        write_json(directory / 'amendment_parent.json', dict(run_id=parent.directory.name,
            directory=str(parent.directory.relative_to(WORK)), manifest_sha256=parent_manifest))
        data = read_json(directory / 'results.json')
        print('Recalculate only the two reviewed hospital origins', flush=True)
        amendment = apply_overrides(data, parent.graph('general_distance'), directory, policy)
        old = parent.data
        affected = {r['estate_id'] for r in policy['overrides']}
        keep = lambda r: r['graph'] != 'general_distance' or r['estate_id'] not in affected
        if [r for r in data['routes'] if keep(r)] != [r for r in old['routes'] if keep(r)]:
            raise ValueError('Hospital amendment changed an unaffected route')
        for key in ('groups', 'group_comparisons', 'target_comparisons'):
            if data[key] != old[key]:
                raise ValueError('Hospital amendment changed transport results')
        if sum(r['graph'] == 'general_distance' for r in data['routes']) != 10736:
            raise ValueError('Hospital-pair accounting changed')
        for estate in policy['unchanged_unavailable_estates']:
            rows = [r for r in data['routes'] if r['graph'] == 'general_distance' and r['estate_id'] == estate]
            if len(rows) != 44 or any(r['status'] == 'ok' for r in rows):
                raise ValueError('Excluded island hospital results unexpectedly changed')
        write_json(directory / 'results.json', data)
        _write_hospital_layer(directory, data, parent.estates)
        reopened = read_json(directory / 'results.json')
        if reopened != data:
            raise ValueError('Amended results changed during JSON roundtrip')
        def loader(key):
            parent._graphs.clear()
            return parent.graph(key)
        print('Validate saved paths and independent hospital searches', flush=True)
        checks = validate_saved(directory, reopened, loader)
        report = read_json(parent.directory / 'validation_report.json')
        report.update(checks)
        report.update(status='passed', run_id=run_id, amendment=amendment,
            parent_run_id=parent.directory.name, production_searches=amendment['production_searches'],
            retained_searches=len(data['searches']),
            reachability=dict(Counter(r['graph'] + '/' + r['status'] for r in data['routes'])),
            connector_warnings=dict(Counter(w for r in data['routes']
                                            for a in r['attachments'] for w in a['warnings'])),
            unaffected_results_preserved=True, upstream_artifacts_unchanged=True,
            runtime_seconds=time.perf_counter() - started,
            payload_bytes=sum(p.stat().st_size for p in directory.iterdir() if p.is_file()),
            limitations=['Accepted straight flat connectors and unknown point heights.',
                'Two hospital origins use reviewed map-point overrides, not verified entrances.',
                'Wheelchair time uses the shared walking model and explicit fallback approximation.',
                'Final ranking settings are recorded in the Step 5 plan; ranking is not implemented here.'])
        cache_policy = read_json(directory / 'cache_policy.json')
        cache_policy['hospital_origin_overrides'] = 'reviewed_snapshot_pinned_hospital_only'
        write_json(directory / 'cache_policy.json', cache_policy)
        # Original Step 3 attachment policy remains unchanged; overrides are separate evidence.
        if read_json(WORK / 'precomputed/outputs/rebuild/current.json') != pair:
            raise ValueError('Selected build pair changed during hospital amendment')
        for stage, source in upstream.items():
            if sha256(source / 'manifest.json') != pair[stage]['manifest_sha256']:
                raise ValueError('Upstream manifest changed during hospital amendment')
            verify_hashes(source, read_json(source / 'manifest.json')['artifacts'])
        if sha256(parent.directory / 'manifest.json') != parent_manifest:
            raise ValueError('Parent cache manifest changed during amendment')
        verify_hashes(parent.directory, parent.manifest['artifacts'])
        if (root / 'current').resolve() != parent.directory:
            raise ValueError('Parent cache selection changed during amendment')
        if any(sha256(path) != hashes[path.name] for path in code):
            raise ValueError('Implementation changed during amendment')
        if load_overrides(pair) != policy:
            raise ValueError('Hospital override policy changed during amendment')
        write_json(directory / 'validation_report.json', report)
        write_json(directory / 'SUCCESS.json', dict(run_id=run_id, validation='passed',
                   completed_utc=datetime.now(timezone.utc).isoformat()))
        write_json(directory / 'manifest.json', dict(run_id=run_id, frozen_pair=pair,
            parent_step_4=read_json(directory / 'amendment_parent.json'),
            implementation_sha256=hashes, policy=cache_policy,
            artifacts={p.name: dict(sha256=sha256(p), bytes=p.stat().st_size)
                       for p in sorted(directory.iterdir()) if p.is_file()}))
        print('Verify amended GeoDataFrame readers without rerouting', flush=True)
        candidate = JourneyCache(directory)
        for specification in policy['overrides']:
            for row in [r for r in data['routes'] if r['graph'] == 'general_distance' and
                        r['estate_id'] == specification['estate_id'] and r['status'] == 'ok']:
                frame = candidate.route(row['estate_id'], row['target_id'])
                check_cost(frame.cost, row['cost'])
                check_cost([frame.geometry.iloc[0].length], frame.distance_m.iloc[0])
        if len(read_hospital_costs(directory)) != 10736:
            raise ValueError('Amended public hospital reader accounting failed')
        shared = None
        for wheelchair in (False, True):
            for scenario in ('primary', 'baseline'):
                frame = read_subcosts(wheelchair, scenario=scenario, directory=directory)
                current = frame[['id', 'hospital_distance_m', 'hospital_target_ids', 'hospital_status']]
                if shared is not None:
                    pd.testing.assert_frame_equal(current, shared, check_exact=True)
                shared = current
        _opened.cache_clear()
        if read_json(WORK / 'precomputed/outputs/rebuild/current.json') != pair:
            raise ValueError('Selected build pair changed before amendment publication')
        if (root / 'current').resolve() != parent.directory:
            raise ValueError('Parent cache selection changed before amendment publication')
        target = root / 'runs' / run_id
        target.parent.mkdir(parents=True, exist_ok=True)
        directory.rename(target)
        publish_run(target, root / 'current')
        print('Published amended Step 4: ' + str(target), flush=True)
        return target
    except BaseException:
        if directory.exists():
            write_json(directory / 'FAILURE.json', dict(run_id=run_id, traceback=traceback.format_exc()))
        raise
