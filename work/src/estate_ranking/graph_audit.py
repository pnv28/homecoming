"""Reproducible source and routing evidence required before Step 2 publication."""
from collections import Counter
from pathlib import Path

from .graph_cluster_audit import audit_cluster_geometry, audit_cluster_routing
from .graph_gradient_audit import audit_extreme_gradient, gradient_routing_impact
from .graph_vertical_audit import audit_source_provenance, audit_vertical_sources
from .ingest import (read_json, sha256, safe_extract_network,
                     confirm_network_definitions)


def prepare_audit(physical, frozen_directory, frozen):
    """Bind affected graph records to the selected raw archive and dictionary."""
    from .graph import WORK
    clusters = audit_cluster_geometry(physical)
    vertical = audit_vertical_sources(physical)
    unavailable = physical.sources.loc[
        (physical.sources.time_forward_status != 'available') |
        (physical.sources.time_reverse_status != 'available')]
    unavailable_ids = sorted(unavailable.PedestrianRouteID.astype(str))
    overflow_ids = sorted(unavailable.loc[
        (unavailable.time_forward_status == 'unrepresentable_tobler_time') |
        (unavailable.time_reverse_status == 'unrepresentable_tobler_time')
        ].PedestrianRouteID.astype(str))
    source_ids = sorted(set(unavailable_ids) |
                        {s for c in clusters['clusters'] for s in c['source_ids']})
    manifest = read_json(Path(frozen_directory)/'source_manifest.json')
    inputs = {}
    for name in ('network','network_dictionary'):
        path = WORK/manifest['sources'][name]['path']
        digest = sha256(path)
        if digest != frozen['original_source_hashes'][name]:
            raise AssertionError('Audit input differs from frozen source: '+name)
        inputs[name] = {'path':manifest['sources'][name]['path'], 'sha256':digest}
    archive = WORK/inputs['network']['path']
    gdb, extraction = safe_extract_network(archive, WORK/'cache', inputs['network']['sha256'])
    provenance = audit_source_provenance(physical, source_ids, frozen_directory, gdb)
    definitions = confirm_network_definitions(WORK/inputs['network_dictionary']['path'])
    return {
        'scope':'Rejected junction clusters and every source with unavailable time',
        'inputs':inputs, 'frozen_step_1_run':frozen['run_id'],
        'raw_extraction':{'archive_sha256':extraction['archive_sha256'],
                          'verified_file_count':len(extraction['files'])},
        'source_provenance':provenance, 'provider_definitions':definitions,
        'clusters':clusters, 'vertical_sources':vertical,
        'extreme_gradients':[audit_extreme_gradient(physical, source) for source in overflow_ids],
        'unavailable_source_ids':unavailable_ids,
        'source_geometry_or_gradient_replacements':0,
        'cost_boundary_subdivisions':sum(r['kind']=='cost_boundary_split' for r in physical.review),
        'interpretation':'Original geometry and gradients are retained. Cost subdivisions expose '
                         'healthy intervals but create no cross-path junctions. Remaining '
                         'source defects are not asserted to be repaired.',
        'routing':{}}


def audit_routing(graph, audit):
    """Measure actual routes, retaining exclusions instead of invented costs."""
    cluster = audit_cluster_routing(graph, audit['clusters'])
    sources, counts = [], Counter()
    edge_directions = dict(zip(graph.edges.edge_id, graph.edges.direction))
    mode = 'wheelchair' if graph.wheelchair else 'general'
    indexed = graph.physical.sources.set_index(
        graph.physical.sources.PedestrianRouteID.astype(str))
    for source in audit['unavailable_source_ids']:
        if not bool(indexed.loc[source, 'allow_'+mode]):
            sources.append({'source_id':source,'source_mode_eligible':False,
                            'decision':'Excluded by the unchanged mode rules'})
            counts['mode_excluded_sources'] += 1
            continue
        result = gradient_routing_impact(graph, source)
        sources.append(result)
        for piece in result['pieces']:
            for name, direction in [('forward',1),('reverse',-1)]:
                if edge_directions[piece['edge_id']] not in (0,direction):
                    continue
                if piece['time_'+name+'_status']=='available':
                    counts['healthy_piece_directions'] += 1
                elif piece['time_'+name+'_status']=='estimated_distance_height':
                    counts['estimated_piece_directions'] += 1
                else:
                    status = 'reachable' if piece[name]['reachable'] else 'unreachable'
                    counts['unavailable_piece_directions_'+status] += 1
    return {'clusters':cluster,'unavailable_sources':sources,
            'summary':dict(sorted(counts.items())),
            'interpretation':'Per-piece endpoint routes in this mode, metric and scenario. '
                             'Primary routing can use reviewed distance-height estimates; baseline '
                             'retains original time exclusions. Reachability does not establish a source correction.'}


def audit_summary(audit):
    return {'affected_records_verified':audit['source_provenance']['sources_checked'],
            'unavailable_sources':len(audit['unavailable_source_ids']),
            'vertical_sources':audit['vertical_sources']['source_count'],
            'extreme_gradient_sources':len(audit['extreme_gradients']),
            'rejected_clusters':audit['clusters']['summary']['cluster_count'],
            'cost_boundary_subdivisions':audit['cost_boundary_subdivisions'],
            'source_geometry_or_gradient_replacements':0,
            'routing':{key:{'clusters':value['clusters']['summary'],
                             'unavailable_sources':value['summary']}
                       for key,value in audit['routing'].items()}}


def audit_markdown(audit):
    """Keep the human interpretation beside the full source-ID evidence."""
    summary = audit_summary(audit)
    lines = ['# Step 2 autonomous source and routing audit','',
             'Original geometry, attributes and gradients are preserved. A source investigation '
             'does not turn missing or contradictory evidence into a confirmed correction.','',
             '## Explanation for the team','',
             '{} affected source records match the original geodatabase and frozen Step 1. '
             '{} cost-boundary subdivisions preserve usable portions beside invalid intervals. '
             '{} sources still have unavailable time: {} contain vertical intervals and {} '
             'have unrepresentable Tobler costs.'.format(
                 summary['affected_records_verified'],summary['cost_boundary_subdivisions'],
                 summary['unavailable_sources'],summary['vertical_sources'],summary['extreme_gradient_sources']),
             '', 'Rejected clusters are inspected using original endpoint identities. Existing '
             'source routes, routes through other sources, and unreachable directions are '
             'reported separately. No tolerance is relaxed.','',
             '| Graph | Cluster interpretation | Healthy piece directions on affected sources |',
             '|---|---|---:|']
    for key, value in summary['routing'].items():
        classification = '; '.join('{}: {}'.format(k,v) for k,v in value['clusters'].items())
        lines.append('| {} | {} | {} |'.format(key,classification,
                     value['unavailable_sources'].get('healthy_piece_directions',0)))
    lines.extend(['','## Steps we will take','',
                  '- [X] Verify affected XYZ and every original attribute against raw and frozen data.',
                  '- [X] Verify selected archive, extracted files and provider dictionary.',
                  '- [X] Audit source intervals and per-piece routes in both modes and metrics.',
                  '- [X] Preserve evidence in `source_routing_audit.json` and verify JSON save/reopen.',
                  '- [ ] Resolve unsupported original vertical geometry and extreme-gradient time '
                  'limitations; no replacement data is established by this audit.',''])
    return '\n'.join(lines)
