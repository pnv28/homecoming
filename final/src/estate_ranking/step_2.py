"""Build, verify and atomically publish Step 2 from one frozen successful Step 1."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time
import traceback
import uuid

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import shapely
from scipy.sparse.csgraph import connected_components, dijkstra

from .export import write_json
from .graph import (WORK, build_physical_graph, connectivity, read_physical,
                    _read_routing, routing_graph, save_physical, save_routing, validate_physical)
from .ingest import read_json, sha256
from .graph_regressions import check_lift_connections
from .graph_audit import prepare_audit, audit_routing, audit_summary, audit_markdown
from .graph_cluster_audit import check_repaired_endpoint_cluster
from .policy import load_policy
from .time_fallback import derived_policy, routing_prefix


def progress(message):
    print(message,flush=True)


def publish_run(directory, current):
    directory,current = Path(directory),Path(current)
    if not (directory/'SUCCESS.json').exists():
        raise ValueError('Only a validated successful run may be selected')
    if os.path.lexists(current) and not current.is_symlink():
        raise ValueError('Current graph must be absent or a managed symlink')
    current.parent.mkdir(parents=True,exist_ok=True)
    temporary = current.with_name('.current-'+uuid.uuid4().hex)
    try:
        temporary.symlink_to(os.path.relpath(directory,current.parent),target_is_directory=True)
        os.replace(temporary,current)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def freeze_input(directory):
    # Resolve current once: later Step 1 publications cannot change this input.
    directory = Path(directory).resolve(strict=True)
    if not (directory/'SUCCESS.json').is_file():
        raise ValueError('Step 2 requires a successful Step 1 snapshot')
    success = read_json(directory/'SUCCESS.json')
    names = ['SUCCESS.json','harmonised.gpkg','schema.json','reference_tables.sqlite',
             'source_manifest.json','model_policy.json','validation_report.json']
    manifest = read_json(directory/'source_manifest.json')
    if manifest['run_id'] != success['run_id']:
        raise ValueError('Step 1 manifest/success identity mismatch')
    if read_json(directory/'validation_report.json')['errors'] != 0:
        raise ValueError('Step 1 snapshot failed validation')
    return directory, {'run_id':success['run_id'],'directory':os.path.relpath(directory,WORK),
        'files':{name:sha256(directory/name) for name in names},
        'original_source_hashes':{k:v['sha256'] for k,v in manifest['sources'].items()},
        'policy':read_json(directory/'model_policy.json')}


def verify_spatial(expected, actual):
    checked = {}
    for name in ('nodes','edges','sources'):
        a,b = getattr(expected,name),getattr(actual,name)
        if not isinstance(b,gpd.GeoDataFrame) or a.crs != b.crs:
            raise AssertionError('GeoDataFrame type/CRS changed')
        if not np.array_equal(shapely.to_wkb(a.geometry),shapely.to_wkb(b.geometry)):
            raise AssertionError('XYZ geometry changed: '+name)
        assert_frame_equal(a.drop(columns='geometry'),b.drop(columns='geometry'),check_exact=True)
        if b.attrs['vertical_crs'] != 'EPSG:5738':
            raise AssertionError('HKPD metadata lost')
        checked[name] = {'records':len(a),'all_attributes_and_nulls':True,'xyz_wkb_exact':True,
                         'actual_type':'geopandas.GeoDataFrame','horizontal_crs':'EPSG:2326',
                         'vertical_crs':'EPSG:5738'}
    # Float precision must survive text storage for alignment and split measures.
    assert_frame_equal(expected.memberships,actual.memberships,check_exact=True)
    return checked


def verify_evidence(directory, name, expected):
    """Compare JSON values; tuples are arrays in the persisted JSON contract."""
    count = 0
    with (Path(directory)/(name+'.jsonl')).open() as stream:
        for value in expected:
            line = stream.readline()
            wanted = json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False))
            if not line or json.loads(line) != wanted:
                raise AssertionError('Evidence changed on reopen: '+name)
            count += 1
        if stream.readline():
            raise AssertionError('Extra stored evidence: '+name)
    return count


def annotate_components(graph, directory):
    active = np.zeros(len(graph.states),dtype=bool)
    active[np.r_[graph.transitions.from_state,graph.transitions.to_state].astype(int)] = True
    for connection in ('weak','strong'):
        _,labels = connected_components(graph.matrix,directed=True,connection=connection)
        graph.states[connection+'_component'] = labels
    graph.states['active'] = active
    prefix = routing_prefix(graph.wheelchair, graph.metric, getattr(graph, 'scenario', 'primary'))
    # Full region accounting, with EPSG:2326 bounding boxes. Physical geometry
    # is referenced through states.node_index rather than duplicated here.
    positions = shapely.get_coordinates(graph.nodes.geometry)
    table = graph.states.loc[active,['node_index','weak_component']].drop_duplicates()
    if len(table):
        table['x'] = positions[table.node_index,0]
        table['y'] = positions[table.node_index,1]
        regions = table.groupby('weak_component').agg(nodes=('node_index','nunique'),
                      min_x=('x','min'),min_y=('y','min'),max_x=('x','max'),max_y=('y','max'))
        regions.to_csv(Path(directory)/(prefix+'_regions.csv'))
    summary = connectivity(graph)
    if graph.metric == 'time':
        allowed = graph.edges.loc[graph.edges['allow_wheelchair' if graph.wheelchair else 'allow_general']]
        reasons = []
        for direction,column,status in [(1,'time_forward_s','time_forward_status'),
                                        (-1,'time_reverse_s','time_reverse_status')]:
            unavailable = allowed.loc[allowed.direction.isin([0,direction]) & allowed[column].isna()]
            reasons.extend(unavailable[status].tolist())
        summary['unavailable_physical_time_directions'] = dict(Counter(reasons))
    return summary


def verify_routing(expected, actual):
    if not np.array_equal(expected.matrix.indptr,actual.matrix.indptr) or not np.array_equal(expected.matrix.indices,actual.matrix.indices):
        raise AssertionError('CSR structure changed')
    if not np.array_equal(expected.matrix.data,actual.matrix.data):
        raise AssertionError('CSR costs changed')
    assert_frame_equal(expected.states,actual.states,check_dtype=False,check_exact=True)
    assert_frame_equal(expected.transitions,actual.transitions,check_dtype=False,check_exact=True)
    if len(expected.transitions):
        degrees = np.diff(expected.matrix.indptr)
        active = np.flatnonzero(degrees)
        roots = sorted(set([int(active[0]),int(active[len(active)//2]),int(np.argmax(degrees))]))
        before = dijkstra(expected.matrix,indices=roots,directed=True)
        after = dijkstra(actual.matrix,indices=roots,directed=True)
        if not np.array_equal(before,after):
            raise AssertionError('Reopened shortest paths differ')
        # Every available finite relaxation must satisfy the shortest-path bound.
        a = expected.transitions.from_state.to_numpy(dtype=int)
        b = expected.transitions.to_state.to_numpy(dtype=int)
        for distances in before:
            with np.errstate(over='ignore',invalid='ignore'):
                bound = distances[a]+expected.transitions.cost.to_numpy()
            finite = np.isfinite(bound)
            if np.any(distances[b[finite]] > bound[finite]*(1+1e-12)+1e-8):
                raise AssertionError('Shortest-path edge relaxation failed')
        return {'dijkstra_sources':roots,'save_reopen_costs_exact':True,'relaxation_checks':True}
    return {'save_reopen_costs_exact':True,'dijkstra_sources':[]}


def write_report(directory,report):
    write_json(Path(directory)/'validation_report.json',report)
    lines = ['# Step 2 validation report','', 'Status: **'+report['status']+'**.','',
             '## Explanation for the team','',
             'Connections use endpoint evidence, horizontal distance and HKPD height. '
             'Separate directed matrices minimise metres or seconds. Lift identity states '
             'charge 30 seconds on entry and retain zero-cost continuations. '
             'Components describe this model’s connected regions; estates and targets are attached in Step 3.','',
             '## Steps we will take','']
    for name,value in report.items():
        if name != 'status':
            lines.append('- [X] **{}**: {}'.format(name,json.dumps(value,ensure_ascii=False)))
    (Path(directory)/'validation_report.md').write_text('\n'.join(lines)+'\n')


def run(input_directory=None, output_root=None, select=True):
    start = time.perf_counter()
    code_paths = [Path(__file__).with_name(name) for name in
                  ['step_2.py','graph.py','graph_costs.py','graph_topology.py','graph_regressions.py','policy.py',
                   'graph_audit.py','graph_cluster_audit.py','graph_vertical_audit.py','graph_gradient_audit.py',
                   'time_fallback.py', 'run_registry.py', 'rebuild.py']]
    code_hashes = {p.name:sha256(p) for p in code_paths}
    output_root = Path(output_root or WORK/'precomputed/outputs/step_2')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    directory = WORK/'cache/step_2_staging'/run_id
    directory.mkdir(parents=True)
    previous = (output_root/'current').resolve() if (output_root/'current').exists() else None
    previous_report = (read_json(previous/'validation_report.json')
                       if previous and (previous/'validation_report.json').exists() else None)
    try:
        progress('1/6 Freeze the successful Step 1 run and policy')
        source,frozen = freeze_input(input_directory or WORK/'precomputed/outputs/current')
        policy = derived_policy(frozen['policy'], load_policy(WORK/'config/routing_policy.json'))
        write_json(directory/'frozen_input.json',frozen)
        progress('2/6 Build source costs and height-aware physical topology')
        physical = build_physical_graph(source,policy=policy,progress=progress)
        report = {'status':'passed','frozen_step_1_run':frozen['run_id'],
                  'physical':validate_physical(physical)}
        if len(physical.sources)==465892:
            if (int(physical.sources.allow_general.sum()),int(physical.sources.allow_wheelchair.sum())) != (465861,430496):
                raise AssertionError('Eligible source counts differ from agreed snapshot')
        progress('Audit original source evidence and remaining junction/cost diagnostics')
        audit = prepare_audit(physical, source, frozen)
        progress('3/6 Save and reopen every physical geometry, attribute, null and correction')
        save_physical(directory,physical)
        reopened = read_physical(directory)
        report['spatial_roundtrip'] = verify_spatial(physical,reopened)
        # Reopen profiles/review as streamed JSON, comparing every evidence row.
        for name,expected in [('profiles',(p.evidence() for p in physical.profiles)),('review',iter(physical.review))]:
            report[name+'_roundtrip_rows'] = verify_evidence(directory,name,expected)
        report['derived_profiles_roundtrip_rows'] = verify_evidence(directory, 'derived_profiles',
            (p.derived_evidence() for p in physical.profiles if p.fallback))
        report['fallback'] = {'reviewed_sources': len(policy['transport_time'].get('fallback', {}).get('review', {}).get('sources', {})),
            'estimated_intervals': sum(len(p.fallback or {}) for p in physical.profiles),
            'estimated_physical_pieces': int(physical.edges.uses_estimated_time.sum()),
            'original_evidence_preserved': True, 'source_geometry_corrected': False}
        report['routing'] = {}
        for wheelchair in (False,True):
            for metric, scenario in [('distance','primary'), ('time','primary'), ('time','baseline')]:
                key = routing_prefix(wheelchair, metric, scenario)
                progress('4/6 Build, save and validate '+key)
                graph = routing_graph(physical,wheelchair,metric,scenario)
                summary = annotate_components(graph,directory)
                save_routing(directory,graph)
                loaded = _read_routing(directory,reopened,wheelchair,metric,scenario)
                summary['validation'] = verify_routing(graph,loaded)
                if metric=='time' and len(physical.sources)==465892:
                    summary['real_lift_regressions'] = check_lift_connections(loaded)
                if len(physical.sources)==465892:
                    summary['real_endpoint_preference_regression'] = check_repaired_endpoint_cluster(loaded)
                progress('Audit source-ID-based routes in reopened '+key)
                audit['routing'][key] = audit_routing(loaded, audit)
                report['routing'][key] = summary
                del graph,loaded
                gc.collect()
        progress('5/6 Recheck frozen hashes and write validation/manifest')
        write_json(directory/'source_routing_audit.json',audit)
        if read_json(directory/'source_routing_audit.json') != audit:
            raise AssertionError('Source/routing audit changed on reopen')
        (directory/'source_routing_audit.md').write_text(audit_markdown(audit))
        report['source_routing_audit'] = audit_summary(audit)
        report['source_routing_audit_roundtrip'] = True
        for name,digest in frozen['files'].items():
            if sha256(source/name) != digest:
                raise ValueError('Frozen Step 1 artifact changed during build: '+name)
        for name, item in audit['inputs'].items():
            if sha256(WORK/item['path']) != item['sha256']:
                raise ValueError('Original audit input changed during build: '+name)
        if read_json(directory/'model_policy.json') != policy:
            raise AssertionError('Graph policy differs from recorded derived policy')
        if any(sha256(p) != code_hashes[p.name] for p in code_paths):
            raise ValueError('Implementation changed during build')
        if previous_report:
            keys = ['nodes','physical_pieces','source_rows','general_eligible_sources','wheelchair_eligible_sources']
            comparison = {'previous_run':previous.name,
                          'previous_report_sha256':sha256(previous/'validation_report.json'),
                          'physical':{k:{'before':previous_report['physical'][k],
                                         'after':report['physical'][k],
                                         'delta':report['physical'][k]-previous_report['physical'][k]} for k in keys},
                          'routing':{}}
            for key,value in report['routing'].items():
                if key not in previous_report['routing']:
                    continue
                comparison['routing'][key] = {k:{'before':previous_report['routing'][key][k],
                                                 'after':value[k],
                                                 'delta':value[k]-previous_report['routing'][key][k]}
                                              for k in ['states','active_states','weak_components','strong_components',
                                                        'stored_entries','stored_zero_cost_entries']}
            report['comparison_to_previous'] = comparison
            write_json(directory/'comparison_to_previous.json',comparison)
        report['implementation_hashes_rechecked'] = True
        report['frozen_hashes_rechecked'] = True
        report['audit_input_hashes_rechecked'] = True
        report['runtime_seconds'] = round(time.perf_counter()-start,3)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report['peak_process_memory_mib'] = round(peak/(1024**2 if sys.platform=='darwin' else 1024),3)
        report['limitations'] = ['Ambiguous inferred merges remain declined; source_routing_audit.json distinguishes existing paths from missing routes.',
            'Reviewed original failures use flagged distance-height estimates in primary time graphs; baseline retains original exclusions. Geometry is not corrected.',
            'Connection height tolerance is a modelling rule, not source elevation accuracy.',
            'Wheelchair times use the agreed shared Tobler assumption, not measured wheelchair speeds.',
            'No estate/destination snapping, journey subcosts or final ranking in Step 2.',
            'Missing supporting references are preserved; site/distance-post lookups are not needed for graph topology.']
        write_report(directory,report)
        write_json(directory/'review_record.json',{
            'review_type':'automated_full_build_validation',
            'status':'passed_with_retained_model_limitations',
            'accepted_source_decisions':frozen['policy']['source_review'],
            'topology_review_counts':report['physical']['review_counts'],
            'all_sources_accounted_for':True,'all_spatial_values_reopened':True,
            'all_profiles_and_review_reopened':True,'all_four_matrices_reopened':True,
            'shortest_path_validation_passed':True,'input_and_code_hashes_rechecked':True,
            'real_lift_regressions':{k:v['real_lift_regressions'] for k,v in report['routing'].items()
                                     if 'real_lift_regressions' in v},
            'source_routing_audit':report['source_routing_audit'],
            'limitations':report['limitations']})
        write_json(directory/'SUCCESS.json',{'run_id':run_id,'validation':'passed',
                    'completed_utc':datetime.now(timezone.utc).isoformat()})
        manifest = {'run_id':run_id,'frozen_step_1':frozen,'python':platform.python_version(),
                    'implementation_sha256':code_hashes,
                    'software':{p:importlib.metadata.version(p) for p in ['numpy','scipy','shapely','geopandas','pyogrio','pandas']},
                    'artifacts':{p.name:{'sha256':sha256(p),'bytes':p.stat().st_size}
                                 for p in sorted(directory.iterdir()) if p.is_file()}}
        write_json(directory/'manifest.json',manifest)
        progress('6/6 Publish only the validated run')
        destination = output_root/'runs'/run_id
        destination.parent.mkdir(parents=True,exist_ok=True)
        os.replace(directory,destination)
        directory = destination
        if select:
            publish_run(directory,output_root/'current')
        progress('Complete: '+str(output_root/'current'))
        progress(json.dumps({'physical':report['physical'],'runtime_seconds':report['runtime_seconds'],
                             'peak_process_memory_mib':report['peak_process_memory_mib']}))
        return 0 if select else destination
    except Exception as exc:
        write_json(directory/'failure.json',{'run_id':run_id,'exception':type(exc).__name__,'message':str(exc)})
        (directory/'failure_traceback.txt').write_text(traceback.format_exc())
        progress('Step 2 failed; previous current graph is unchanged. Diagnostics: '+str(directory))
        progress(type(exc).__name__+': '+str(exc))
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=WORK/'precomputed/outputs/current')
    parser.add_argument('--output-root',type=Path,default=WORK/'precomputed/outputs/step_2')
    args = parser.parse_args(argv)
    lock_path = WORK/'cache/step_2.lock'
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another Step 2 build is active')
        return run(args.input,args.output_root)


if __name__=='__main__':
    sys.exit(main())
