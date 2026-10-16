"""Cache separate hospital distances and transport times from one frozen build pair.

Run: PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_4
Readers never execute a shortest-path search. Explicit directories reopen history.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
import uuid

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra

from .attachments import read_attached_graph, read_attached_points
from .export import write_json
from .graph import WORK
from .ingest import read_json, sha256
from .routes import check_cost, ordered_sections, path_transitions, predecessor_states, transition_index
from .step_2 import publish_run
from .step_3 import verify_hashes, validate_terminals
from .time_fallback import routing_prefix

POLICY = dict(hospital_cache='shared_general_distance', ties='exact_unrounded_equality',
    paths='one_optimal_path_per_destination', transport_units='seconds', hospital_units='metres',
    connector_policy='consume_saved_scenario_attachments_including_expanded_search',
    transport_cost='walking_and_connectors_only', scoring='deferred',
    hospital_origin_overrides='reviewed_snapshot_pinned_hospital_only')


def digest_value(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def freeze_pair(work=None):
    work = Path(work or WORK)
    pair = read_json(work / 'precomputed/outputs/rebuild/current.json')
    if pair['status'] != 'passed':
        raise ValueError('Selected build pair did not pass')
    directories = {}
    for stage in ('step_2', 'step_3'):
        item = pair[stage]
        directory = (work / item['directory']).resolve(strict=True)
        manifest = read_json(directory / 'manifest.json')
        success = read_json(directory / 'SUCCESS.json')
        if (directory.name != item['run_id'] or manifest['run_id'] != item['run_id'] or
            success['run_id'] != item['run_id'] or success['validation'] != 'passed' or
            sha256(directory / 'manifest.json') != item['manifest_sha256'] or
            read_json(directory / 'validation_report.json')['status'] != 'passed'):
            raise ValueError('Incompatible or unsuccessful frozen reference: ' + stage)
        verify_hashes(directory, manifest['artifacts'])
        directories[stage] = directory
    second = read_json(directories['step_3'] / 'frozen_inputs.json')
    upstream = second['step_2']
    if ((work / upstream['directory']).resolve() != directories['step_2'] or
        upstream['run_id'] != pair['step_2']['run_id'] or
        upstream['files']['manifest.json'] != pair['step_2']['manifest_sha256']):
        raise ValueError('Step 3 does not reference the selected Step 2 exactly')
    verify_hashes(directories['step_2'], upstream['files'])
    network = read_json(directories['step_2'] / 'model_policy.json')
    if second['network_policy'] != network or read_json(directories['step_3'] / 'model_policy.json') != network:
        raise ValueError('Frozen network policies differ')
    fallback = network['transport_time']['fallback']
    review = fallback['review']
    if (not fallback['enabled'] or fallback['uphill_seconds_per_metre'] != 6 or
        fallback['downhill_seconds_per_metre'] != 2 or not review['sources'] or
        fallback['wheelchair'] != 'same_coefficients_explicit_approximation'):
        raise ValueError('Unsupported or unreviewed fallback policy')
    # Verify original failure evidence against each approved profile digest.
    from .time_fallback import profile_digest
    with (directories['step_2'] / 'profiles.jsonl').open() as stream:
        for line in stream:
            profile = json.loads(line)
            approved = review['sources'].get(profile['source_id'])
            if approved and profile_digest(profile) != approved['original_profile_sha256']:
                raise ValueError('Fallback review/profile mismatch')
    return pair, directories


def winners(costs, terminals, kind):
    eligible = terminals.loc[(terminals.entity_type == kind) & (terminals.status == 'attached')]
    values = costs[eligible.state_index.to_numpy(dtype=int)]
    finite = np.isfinite(values)
    if not finite.any():
        return None, []
    minimum = float(values[finite].min())
    return minimum, sorted(eligible.loc[values == minimum, 'entity_id'].tolist())


class SearchCache:
    """One graph's shared pruned trees, and fast physical path provenance."""
    def __init__(self, graph, key):
        self.graph, self.key = graph, key
        self.terminals = graph.terminals.set_index('entity_id')
        self.attachments = graph.attachments.set_index('attachment_id', drop=False)
        self.edge_index = graph.transitions.edge_index.to_numpy(dtype=int)
        self.direction = graph.transitions.direction.to_numpy(dtype=int)
        self.cost = graph.transitions.cost.to_numpy()
        self.sources = graph.transitions.source_id.to_numpy()
        self.edges = graph.edges[[c for c in ('source_id', 'start_position', 'end_position', 'uses_estimated_time', 'fallback_review_ids', 'time_model_warning', 'original_time_forward_status', 'original_time_reverse_status', 'time_forward_status', 'time_reverse_status') if c in graph.edges]].to_dict('records')
        self.searches, self.blocks, self.routes = [], [], []
        self.origin_overrides = {}

    def attachment(self, entity):
        if entity in self.origin_overrides:
            return self.origin_overrides[entity]['attachment']
        a = self.attachments.loc[self.terminals.loc[entity, 'attachment_id']]
        return dict(entity_id=entity, attachment_id=a.attachment_id, status=a.status, reason=a.reason,
                    source_id=a.source_id, source_position=None if pd.isna(a.source_position) else float(a.source_position),
                    position=None if a.geometry is None else list(a.geometry.coords[0]),
                    distance_m=None if pd.isna(a.distance_m) else float(a.distance_m),
                    warnings=a.warnings.split(';') if a.warnings else [])

    def describe(self, links, estate, target):
        tokens, estimated, reviews, failures, model_warnings = [], [], set(), set(), set()
        if estate in self.origin_overrides:
            a = self.attachment(estate)
            tokens.append(('connector', estate, 'departure', a['source_id'],
                           a['source_position'], a['position'], a['distance_m']))
        for index in links:
            ei, direction = self.edge_index[index], self.direction[index]
            if ei < 0:
                a = self.attachments.loc[self.sources[index]]
                tokens.append(('connector', a.entity_id, a.role, a.source_id,
                               float(a.source_position), list(a.geometry.coords[0]), float(a.distance_m)))
            else:
                e = self.edges[ei]
                tokens.append(('network', str(e['source_id']), int(direction),
                               float(e['start_position']), float(e['end_position'])))
                if (self.graph.metric == 'time' and self.graph.scenario == 'primary' and
                    e.get('time_' + ('forward' if direction == 1 else 'reverse') + '_status') == 'estimated_distance_height'):
                    estimated.append(float(self.cost[index]))
                    reviews.update(filter(None, e.get('fallback_review_ids', '').split(';')))
                    model_warnings.update(filter(None, e.get('time_model_warning', '').split(';')))
                    failures.add(e.get('original_time_' + ('forward' if direction == 1 else 'reverse') + '_status', ''))
        attachments = [self.attachment(estate), self.attachment(target)]
        identity = [{k: a[k] for k in ('entity_id', 'status', 'source_id', 'source_position', 'position', 'distance_m')} for a in attachments]
        return dict(path_identity=digest_value(tokens), attachment_identity=digest_value(identity),
            attachments=attachments, warnings=sorted({w for a in attachments for w in a['warnings']} | model_warnings),
            uses_estimated_time=bool(estimated), estimated_seconds=sum(estimated),
            estimated_sections=len(estimated), fallback_review_ids=sorted(reviews),
            original_failure_reasons=sorted(failures), model_warnings=sorted(model_warnings))

    def retain_search(self, root_entity, requested, reverse=False, origin_override=None):
        """requested: (estate, target, purposes); comparisons precede pruning."""
        graph = self.graph
        if origin_override is not None:
            if reverse or self.key != 'general_distance' or origin_override['estate_id'] != root_entity:
                raise ValueError('Origin overrides apply only to forward shared hospital searches')
            self.origin_overrides[root_entity] = origin_override
        root = int(origin_override['state_index'] if origin_override is not None else
                   self.terminals.loc[root_entity, 'state_index'])
        offset = origin_override['attachment']['distance_m'] if origin_override is not None else 0.
        matrix = graph.matrix.T.tocsr() if reverse else graph.matrix
        costs, predecessors = dijkstra(matrix, directed=True, indices=root, return_predecessors=True)
        search_id = self.key + (':amendment:' if origin_override is not None else ':') + root_entity
        self.searches.append(dict(search_id=search_id, graph=self.key, root_entity=root_entity,
            root_state=root, direction='reverse' if reverse else 'forward', block=len(self.blocks),
            mode='wheelchair' if graph.wheelchair else 'general', scenario=graph.scenario))
        if origin_override is not None:
            self.searches[-1]['origin_override'] = origin_override
        retained = {}
        deduplicated = {}
        for estate, target, purposes in requested(costs):
            pair = (estate, target)
            if pair in deduplicated:
                deduplicated[pair]['purposes'] = sorted(set(deduplicated[pair]['purposes']) | set(purposes))
                continue
            endpoint = int(self.terminals.loc[estate if reverse else target, 'state_index'])
            value = float(costs[endpoint]) + offset
            status = 'ok' if np.isfinite(value) else 'unreachable'
            if status != 'ok':
                missing = [self.attachment(e) for e in (estate, target) if self.terminals.loc[e, 'status'] != 'attached']
                reason = ';'.join(a['entity_id'] + ':' + (a['reason'] or a['status']) for a in missing) or 'no_directed_path'
                info = dict(path_identity=None, attachment_identity=None,
                    attachments=[self.attachment(estate), self.attachment(target)],
                    warnings=[], uses_estimated_time=False, estimated_seconds=0., estimated_sections=0,
                    fallback_review_ids=[], original_failure_reasons=[], model_warnings=[])
                info['warnings'] = sorted({w for a in info['attachments'] for w in a['warnings']})
            else:
                reason = ''
                links = path_transitions(graph, predecessors, root, endpoint, reverse)
                check_cost([*self.cost[links], offset], value)
                info = self.describe(links, estate, target)
                # Each retained state shares its parent and transition with all routes.
                for state in predecessor_states(predecessors, root, endpoint):
                    if state in retained:
                        break
                    parent = int(predecessors[state])
                    transition = transition_index(graph.matrix, state, parent) if reverse else transition_index(graph.matrix, parent, state)
                    retained[state] = (parent, transition)
            row = dict(route_id=self.key + ':' + estate + ':' + target, graph=self.key,
                estate_id=estate, target_id=target, search_id=search_id, endpoint_state=endpoint,
                status=status, reason=reason, cost=value if status == 'ok' else None,
                unit='metres' if graph.metric == 'distance' else 'seconds', purposes=sorted(set(purposes)), **info)
            if origin_override is not None:
                row['origin_override'] = origin_override
            self.routes.append(row)
            deduplicated[pair] = row
        block = np.array([(s, *retained[s]) for s in sorted(retained)], dtype=np.int64).reshape(-1, 3)
        self.blocks.append(block)
        return costs, deduplicated

    def save(self, directory):
        np.savez_compressed(Path(directory) / (self.key + '_links.npz'),
                            **{'s' + str(i): block for i, block in enumerate(self.blocks)})


def comparisons(groups, routes):
    lookup = {(g['mode'], g['scenario'], g['estate_id'], g['group']): g for g in groups}
    route_lookup = {r['route_id']: r for r in routes}
    group_rows, target_rows = [], []
    for primary in groups:
        if primary['scenario'] != 'primary':
            continue
        mode, estate, kind = primary['mode'], primary['estate_id'], primary['group']
        baseline = lookup[mode, 'baseline', estate, kind]
        path_changed, attachment_changed = False, False
        for target in primary['target_ids']:
            p = route_lookup[mode + '_time:' + estate + ':' + target]
            b = route_lookup[mode + '_time_baseline:' + estate + ':' + target]
            changed = p['path_identity'] != b['path_identity']
            # Compare attachments even when the journey is unavailable.
            def attachment_positions(r):
                return [{k: a[k] for k in ('entity_id', 'status', 'source_id', 'source_position', 'position', 'distance_m')} for a in r['attachments']]
            attached = attachment_positions(p) != attachment_positions(b)
            path_changed |= changed
            attachment_changed |= attached
            target_rows.append(dict(estate_id=estate, mode=mode, group=kind, target_id=target,
                primary_cost=p['cost'], baseline_cost=b['cost'], primary_status=p['status'], baseline_status=b['status'],
                baseline_reason=b['reason'], delta_seconds=None if b['cost'] is None else p['cost'] - b['cost'],
                path_changed=changed, attachment_changed=attached,
                primary_route_id=p['route_id'], baseline_route_id=b['route_id'],
                uses_estimated_time=p['uses_estimated_time'], estimated_seconds=p['estimated_seconds'],
                warnings=sorted(set(p['warnings'] + b['warnings']))))
        # Group paths include each winner, so changed destination sets change the collection.
        primary_paths = [route_lookup[r]['path_identity'] for r in primary['route_ids']]
        baseline_paths = [route_lookup[r]['path_identity'] for r in baseline['route_ids']]
        group_rows.append(dict(estate_id=estate, mode=mode, group=kind, unit='seconds',
            primary_cost=primary['cost'], baseline_cost=baseline['cost'],
            primary_status=primary['status'], baseline_status=baseline['status'],
            primary_target_ids=primary['target_ids'], baseline_target_ids=baseline['target_ids'],
            reachability_changed=primary['status'] != baseline['status'],
            winners_changed=primary['target_ids'] != baseline['target_ids'],
            cost_changed=primary['cost'] != baseline['cost'],
            delta_seconds=None if primary['cost'] is None or baseline['cost'] is None else primary['cost'] - baseline['cost'],
            selected_paths_changed=sorted(primary_paths) != sorted(baseline_paths),
            same_target_path_changed=path_changed, attachment_changed=attachment_changed,
            warnings=sorted(set(primary['warnings'] + baseline['warnings']))))
    return group_rows, target_rows


def calculate(attached, graph_loader, directory, progress=print):
    estates = sorted(attached.entities['estate'].id)
    hospitals = sorted(attached.entities['hospital'].id)
    groups, routes, searches = [], [], []
    for wheelchair in (False, True):
        mode = 'wheelchair' if wheelchair else 'general'
        primary_targets = {}
        for scenario in ('primary', 'baseline'):
            key = routing_prefix(wheelchair, 'time', scenario)
            progress('Search and retain ' + key, flush=True)
            graph = graph_loader(wheelchair, 'time', scenario)
            validate_terminals(graph)
            cache = SearchCache(graph, key)
            for estate in estates:
                def requested(costs):
                    wanted = []
                    for kind in ('bus_stop', 'mtr_access'):
                        value, targets = winners(costs, graph.terminals, kind)
                        if scenario == 'primary':
                            primary_targets[estate, kind] = targets
                        groups.append(dict(estate_id=estate, mode=mode, scenario=scenario, group=kind,
                            cost=value, unit='seconds', status='ok' if value is not None else 'unreachable',
                            reason='' if value is not None else ('estate_unattached' if cache.terminals.loc[estate, 'status'] != 'attached' else 'no_reachable_eligible_destination'),
                            target_ids=targets, route_ids=[key + ':' + estate + ':' + t for t in targets]))
                        wanted.extend((estate, t, ['winner']) for t in targets)
                        if scenario == 'baseline':
                            wanted.extend((estate, t, ['primary_winner_comparison']) for t in primary_targets[estate, kind])
                    return wanted
                cache.retain_search(estate, requested)
            cache.save(directory)
            routes.extend(cache.routes)
            searches.extend(cache.searches)
            del cache, graph
    progress('Search transposed shared general_distance (44 hospital roots)', flush=True)
    graph = graph_loader(False, 'distance', 'primary')
    validate_terminals(graph)
    cache = SearchCache(graph, 'general_distance')
    for hospital in hospitals:
        cache.retain_search(hospital, lambda costs: [(e, hospital, ['hospital_pair']) for e in estates], reverse=True)
    cache.save(directory)
    routes.extend(cache.routes)
    searches.extend(cache.searches)
    route_lookup = {r['route_id']: r for r in routes}
    for group in groups:
        group['warnings'] = sorted({w for rid in group['route_ids'] for w in route_lookup[rid]['warnings']})
        if not group['route_ids']:
            # Preserve origin warnings even if no destination can be reached.
            selected = attached.attachments
            rows = selected.loc[(selected.entity_id == group['estate_id']) &
                (selected['mode'] == group['mode']) & (selected.metric == 'time') &
                (selected.scenario == group['scenario'])]
            group['warnings'] = sorted({w for text in rows.warnings for w in text.split(';') if w})
    group_comparison, target_comparison = comparisons(groups, routes)
    return dict(groups=groups, routes=routes, searches=searches,
                group_comparisons=group_comparison, target_comparisons=target_comparison)


def _spatial(rows, estates):
    frame = pd.DataFrame(rows)
    geometry = frame.estate_id.map(estates.set_index('id').geometry)
    return gpd.GeoDataFrame(frame, geometry=geometry, crs=estates.crs)


class JourneyCache:
    def __init__(self, directory=None):
        explicit = directory is not None
        self.directory = Path(directory or WORK / 'precomputed/outputs/step_4/current').resolve(strict=True)
        self.manifest = read_json(self.directory / 'manifest.json')
        success = read_json(self.directory / 'SUCCESS.json')
        if success['validation'] != 'passed' or success['run_id'] != self.manifest['run_id'] or self.directory.name != success['run_id']:
            raise ValueError('Unsuccessful Step 4 cache')
        verify_hashes(self.directory, self.manifest['artifacts'])
        self.frozen = self.manifest['frozen_pair']
        if not explicit and read_json(WORK / 'precomputed/outputs/rebuild/current.json') != self.frozen:
            raise ValueError('Step 4 cache is incompatible with the selected build pair; rebuild or open an explicit saved directory')
        for item in (self.frozen['step_2'], self.frozen['step_3']):
            upstream = WORK / item['directory']
            if sha256(upstream / 'manifest.json') != item['manifest_sha256']:
                raise ValueError('Frozen upstream manifest changed')
            verify_hashes(upstream, read_json(upstream / 'manifest.json')['artifacts'])
        self.data = read_json(self.directory / 'results.json')
        self.estates = gpd.read_file(self.directory / 'results.gpkg', layer='estates', engine='pyogrio')
        self.routes = {r['route_id']: r for r in self.data['routes']}
        self.searches = {s['search_id']: s for s in self.data['searches']}
        self._attached = None
        self._graphs = {}
        self._links = {}

    def graph(self, key):
        if key not in self._graphs:
            upstream = WORK / self.frozen['step_3']['directory']
            if self._attached is None:
                self._attached = read_attached_points(upstream)
            self._graphs[key] = read_attached_graph(upstream, key.startswith('wheelchair'),
                'distance' if key == 'general_distance' else 'time', self._attached,
                'baseline' if key.endswith('baseline') else 'primary')
        return self._graphs[key]

    def indices(self, row):
        search = self.searches[row['search_id']]
        key = row['graph']
        if key not in self._links:
            with np.load(self.directory / (key + '_links.npz'), allow_pickle=False) as archive:
                self._links[key] = {k: archive[k] for k in archive.files}
        block = self._links[key]['s' + str(search['block'])]
        root, state = search['root_state'], row['endpoint_state']
        indices, seen = [], set()
        while state != root:
            if state in seen:
                raise ValueError('Cyclic cached predecessor links')
            seen.add(state)
            offset = int(np.searchsorted(block[:, 0], state))
            if offset >= len(block) or block[offset, 0] != state:
                raise ValueError('Missing cached comparison/path link')
            _, state, transition = map(int, block[offset])
            indices.append(transition)
        return indices if search['direction'] == 'reverse' else indices[::-1]

    def route(self, estate_id, target_id, wheelchair=False, scenario='primary'):
        if scenario not in ('primary', 'baseline'):
            raise ValueError('scenario must be primary or baseline')
        if estate_id not in set(self.estates.id):
            raise KeyError('Unknown estate ID: ' + str(estate_id))
        hospitals = {r['target_id'] for r in self.data['routes'] if r['graph'] == 'general_distance'}
        if target_id in hospitals:
            key = 'general_distance'
        else:
            key = routing_prefix(wheelchair, 'time', scenario)
            # Full terminal mapping distinguishes unknown from uncached requests.
            graph = self.graph(key)
            if target_id not in set(graph.terminals.entity_id):
                raise KeyError('Unknown target ID: ' + str(target_id))
        rid = key + ':' + estate_id + ':' + target_id
        if rid not in self.routes:
            raise KeyError('Transport journey was not cached: ' + rid)
        row = self.routes[rid]
        route = ordered_sections(self.graph(key), self.indices(row) if row['status'] == 'ok' else [],
                                 origin_override=row.get('origin_override') if row['status'] == 'ok' else None)
        if row['status'] == 'ok':
            check_cost(route.cost, row['cost'])
        route.attrs.update(row, hospital_cache='shared_general_distance' if key == 'general_distance' else None)
        return route


@lru_cache(maxsize=3)
def _opened(directory, signature):
    return JourneyCache(directory)


def _reader(directory=None):
    # Resolve/recheck the current pair on every default call, even with an open cache.
    path = Path(directory or WORK / 'precomputed/outputs/step_4/current').resolve(strict=True)
    signature = sha256(path / 'manifest.json')
    cache = _opened(str(path), signature)
    if directory is None and read_json(WORK / 'precomputed/outputs/rebuild/current.json') != cache.frozen:
        raise ValueError('Step 4 cache is incompatible with the selected build pair')
    return cache


def read_hospital_costs(directory=None):
    cache = _reader(directory)
    result = _spatial([r for r in cache.data['routes'] if r['graph'] == 'general_distance'], cache.estates)
    result.attrs.update(hospital_cache='shared_general_distance', unit='metres', frozen_pair=cache.frozen)
    return result


def read_transport_comparisons(wheelchair=False, directory=None):
    cache = _reader(directory)
    mode = 'wheelchair' if wheelchair else 'general'
    return tuple(_spatial([r for r in cache.data[key] if r['mode'] == mode], cache.estates)
                 for key in ('group_comparisons', 'target_comparisons'))


def read_subcosts(wheelchair=False, hospital_id=None, scenario='primary', directory=None):
    if scenario not in ('primary', 'baseline'):
        raise ValueError('scenario must be primary or baseline')
    cache = _reader(directory)
    mode = 'wheelchair' if wheelchair else 'general'
    hospital = [r for r in cache.data['routes'] if r['graph'] == 'general_distance']
    if hospital_id is not None:
        if hospital_id not in {r['target_id'] for r in hospital}:
            raise KeyError('Unknown hospital ID: ' + str(hospital_id))
        hospital = [r for r in hospital if r['target_id'] == hospital_id]
    result = cache.estates.copy()
    by_estate = {}
    for r in hospital:
        by_estate.setdefault(r['estate_id'], []).append(r)
    groups = {(r['estate_id'], r['group']): r for r in cache.data['groups'] if r['mode'] == mode and r['scenario'] == scenario}
    rows = []
    for estate in result.id:
        row = {}
        candidates = by_estate[estate]
        finite = [r for r in candidates if r['cost'] is not None]
        value = min((r['cost'] for r in finite), default=None)
        selected = [r for r in finite if r['cost'] == value]
        row.update(hospital_distance_m=value, hospital_target_ids=[r['target_id'] for r in selected],
            hospital_status='ok' if value is not None else 'unreachable', hospital_unit='metres',
            hospital_reason='' if finite else ';'.join(sorted({r['reason'] for r in candidates})),
            hospital_warnings=sorted({w for r in selected or candidates for w in r['warnings']}))
        for name, kind in (('bus', 'bus_stop'), ('mtr', 'mtr_access')):
            g = groups[estate, kind]
            for suffix, item in [('time_s', g['cost']), ('target_ids', g['target_ids']),
                ('status', g['status']), ('reason', g['reason']), ('warnings', g['warnings']), ('unit', 'seconds')]:
                row[name + '_' + suffix] = item
        rows.append(row)
    for column in rows[0]:
        result[column] = [r[column] for r in rows]
    result['requested_hospital_id'] = hospital_id
    result.attrs.update(hospital_cache='shared_general_distance', mode=mode, scenario=scenario,
                        requested_hospital_id=hospital_id, frozen_pair=cache.frozen)
    return result


def read_route(estate_id, target_id, wheelchair=False, scenario='primary', directory=None):
    return _reader(directory).route(estate_id, target_id, wheelchair, scenario)


def validate_saved(directory, data, graphs):
    """Validate every retained route using the reopened compressed links."""
    # A staging cache has no success/manifest yet; use only reconstruction methods.
    cache = JourneyCache.__new__(JourneyCache)
    cache.directory, cache._links = Path(directory), {}
    cache.searches = {s['search_id']: s for s in data['searches']}
    checked, reverse_samples = 0, 0
    for key in sorted({r['graph'] for r in data['routes']}):
        graph = graphs(key)
        selected = [r for r in data['routes'] if r['graph'] == key]
        for row in selected:
            if row['status'] != 'ok':
                if row['cost'] is not None:
                    raise ValueError('Unavailable cost must be null')
                continue
            indices = cache.indices(row)
            t = graph.transitions.iloc[indices]
            search = cache.searches[row['search_id']]
            start, end = (row['endpoint_state'], search['root_state']) if search['direction'] == 'reverse' else (search['root_state'], row['endpoint_state'])
            if len(t):
                if (int(t.from_state.iloc[0]) != start or int(t.to_state.iloc[-1]) != end or
                    not np.array_equal(t.to_state.to_numpy()[:-1], t.from_state.to_numpy()[1:])):
                    raise ValueError('Cached transitions are not an ordered directed path')
            elif start != end:
                raise ValueError('Empty path has different endpoints')
            override = row.get('origin_override')
            if override != search.get('origin_override'):
                raise ValueError('Route/search origin override differs')
            offset = override['attachment']['distance_m'] if override else 0.
            check_cost([*t.cost, offset], row['cost'])
            checked += 1
        # Independent forward distance searches validate transposed costs in original direction.
        if key == 'general_distance':
            samples = set(sorted({r['estate_id'] for r in selected})[::61])
            samples.update(r['estate_id'] for r in selected if r.get('origin_override'))
            for estate in sorted(samples):
                terminal = graph.terminals.set_index('entity_id').state_index
                override = next((r['origin_override'] for r in selected
                                 if r['estate_id'] == estate and r.get('origin_override')), None)
                root = int(override['state_index'] if override else terminal[estate])
                offset = override['attachment']['distance_m'] if override else 0.
                costs = dijkstra(graph.matrix, directed=True, indices=root)
                for row in selected:
                    if row['estate_id'] == estate:
                        expected = costs[int(terminal[row['target_id']])] + offset
                        if row['cost'] is None:
                            if np.isfinite(expected):
                                raise ValueError('Reverse/forward reachability differs')
                        else:
                            check_cost([expected], row['cost'])
                        reverse_samples += 1
    counts = Counter(r['graph'] for r in data['routes'])
    return dict(all_reachable_paths_checked=checked, hospital_forward_pairs_checked=reverse_samples,
                route_counts=dict(counts), missing_links=0, predecessor_cycles=0,
                unavailable_routes=sum(r['status'] != 'ok' for r in data['routes']))


def run(output_root=None):
    start = time.perf_counter()
    root = Path(output_root or WORK / 'precomputed/outputs/step_4')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    directory = WORK / 'cache/step_4_staging' / run_id
    directory.mkdir(parents=True)
    code = [Path(__file__), Path(__file__).with_name('routes.py'),
            Path(__file__).with_name('hospital_amendment.py')]
    hashes = {p.name: sha256(p) for p in code}
    try:
        print('Verify and freeze the selected rebuild pair', flush=True)
        pair, upstream = freeze_pair()
        write_json(directory / 'frozen_inputs.json', pair)
        write_json(directory / 'cache_policy.json', POLICY)
        for name in ('model_policy.json', 'attachment_policy.json'):
            write_json(directory / name, read_json(upstream['step_3'] / name))
        attached = read_attached_points(upstream['step_3'])
        def loader(wheelchair, metric, scenario):
            return read_attached_graph(upstream['step_3'], wheelchair, metric, attached, scenario)
        data = calculate(attached, loader, directory)
        from .hospital_amendment import apply_overrides, load_overrides
        override_policy = load_overrides(pair)
        write_json(directory / 'hospital_overrides.json', override_policy)
        amendment = apply_overrides(data, loader(False, 'distance', 'primary'), directory, override_policy)
        if (len([r for r in data['routes'] if r['graph'] == 'general_distance']) != 10736 or
            any(sum(g['scenario'] == s for g in data['groups']) != 976 for s in ('primary', 'baseline')) or
            len(data['searches']) != 1020 + len(override_policy['overrides'])):
            raise ValueError('Full-data accounting changed')
        write_json(directory / 'results.json', data)
        attached.entities['estate'].to_file(directory / 'results.gpkg', layer='estates', engine='pyogrio')
        # Persist spatial result tables too; JSON remains the exact typed/list representation.
        for layer, rows in [('hospital_costs', [r for r in data['routes'] if r['graph'] == 'general_distance']),
                            ('transport_groups', data['groups']), ('group_comparisons', data['group_comparisons']),
                            ('target_comparisons', data['target_comparisons'])]:
            frame = _spatial(rows, attached.entities['estate'])
            for col in frame:
                if col != 'geometry' and frame[col].map(lambda x: isinstance(x, (list, dict))).any():
                    frame[col] = frame[col].map(lambda x: json.dumps(
                        x if isinstance(x, (list, dict)) or pd.notna(x) else None,
                        ensure_ascii=False, allow_nan=False))
            frame.to_file(directory / 'results.gpkg', layer=layer, engine='pyogrio')
        print('Verify every reopened path and independent forward hospital samples', flush=True)
        reopened = read_json(directory / 'results.json')
        if reopened != data:
            raise ValueError('JSON save/reopen changed results')
        report = validate_saved(directory, reopened, lambda key: loader(key.startswith('wheelchair'),
            'distance' if key == 'general_distance' else 'time', 'baseline' if key.endswith('baseline') else 'primary'))
        report.update(status='passed', run_id=run_id, hospital_pairs=10736,
            production_searches=len(data['searches']), hospital_amendment=amendment,
            primary_group_results=976, baseline_group_results=976,
            primary_winner_comparisons=len(data['target_comparisons']),
            reachability=dict(Counter(r['graph'] + '/' + r['status'] for r in data['routes'])),
            estimated_routes=sum(r['uses_estimated_time'] for r in data['routes']),
            comparison_changes={k: sum(r[k] for r in data['group_comparisons']) for k in
                ('reachability_changed', 'winners_changed', 'cost_changed', 'selected_paths_changed', 'attachment_changed')},
            connector_warnings=dict(Counter(w for r in data['routes'] for a in r['attachments'] for w in a['warnings'])),
            upstream_attachment_warnings=dict(Counter(w for text in attached.attachments.warnings for w in text.split(';') if w)),
            transport_group_statuses=dict(Counter(g['mode'] + '/' + g['scenario'] + '/' + g['status'] for g in data['groups'])),
            tied_transport_groups=sum(len(g['target_ids']) > 1 for g in data['groups']),
            cached_routes=len(data['routes']), runtime_seconds=time.perf_counter() - start,
            payload_bytes=sum(p.stat().st_size for p in directory.iterdir()),
            limitations=['Accepted straight flat connectors and unknown point heights.',
                'Wheelchair time uses the shared walking model and explicit fallback approximation.',
                'Final scoring, weights and unreachable-group penalties are deferred.'])
        # Recheck the same registry, frozen hashes and code before publication.
        if read_json(WORK / 'precomputed/outputs/rebuild/current.json') != pair:
            raise ValueError('Selected pair changed during Step 4')
        for stage, source in upstream.items():
            if sha256(source / 'manifest.json') != pair[stage]['manifest_sha256']:
                raise ValueError('Upstream manifest changed during build')
            verify_hashes(source, read_json(source / 'manifest.json')['artifacts'])
        if any(sha256(p) != hashes[p.name] for p in code):
            raise ValueError('Implementation changed during Step 4')
        if load_overrides(pair) != override_policy:
            raise ValueError('Hospital override policy changed during Step 4')
        write_json(directory / 'validation_report.json', report)
        write_json(directory / 'SUCCESS.json', dict(run_id=run_id, validation='passed', completed_utc=datetime.now(timezone.utc).isoformat()))
        write_json(directory / 'manifest.json', dict(run_id=run_id, frozen_pair=pair, implementation_sha256=hashes,
            policy=POLICY, artifacts={p.name: dict(sha256=sha256(p), bytes=p.stat().st_size) for p in sorted(directory.iterdir()) if p.is_file()}))
        # Verify public readers while the candidate is still staged.
        JourneyCache(directory)
        if len(read_hospital_costs(directory)) != 10736:
            raise ValueError('Public hospital reader accounting failed')
        for wheelchair in (False, True):
            for scenario in ('primary', 'baseline'):
                if len(read_subcosts(wheelchair, scenario=scenario, directory=directory)) != 244:
                    raise ValueError('Public subcost reader accounting failed')
        _opened.cache_clear()
        if read_json(WORK / 'precomputed/outputs/rebuild/current.json') != pair:
            raise ValueError('Selected pair changed before publication')
        target = root / 'runs' / run_id
        target.parent.mkdir(parents=True, exist_ok=True)
        directory.rename(target)
        publish_run(target, root / 'current')
        print('Published Step 4: ' + str(target), flush=True)
        return target
    except BaseException:
        if directory.exists():
            write_json(directory / 'FAILURE.json', dict(run_id=run_id, traceback=traceback.format_exc()))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--amend-hospitals', action='store_true',
                        help='Reuse the current cache and recalculate only reviewed hospital origins')
    args = parser.parse_args()
    # Coordinate with the rebuild publisher and other Step 4 builds.
    from contextlib import ExitStack
    with ExitStack() as stack:
        for name in ('rebuild', 'step_4'):
            path = WORK / 'cache' / (name + '.lock')
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context(path.open('a'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.amend_hospitals:
            from .hospital_amendment import amend
            amend(args.output_root)
        else:
            run(args.output_root)


if __name__ == '__main__':
    main()
