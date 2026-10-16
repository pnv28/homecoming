r"""Find the fastest modelled walk between two WGS84 coordinates and draw a PNG.

Example (latitude, longitude order):
  .venv/bin/python work/examples/walking_route.py \
      --start 22.280111 114.130386 --end 22.28113 114.12856
Run without coordinate arguments to enter the two pairs interactively.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
import shapely
from shapely.geometry import LineString, Point, box
from scipy.sparse.csgraph import dijkstra

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'src'))
from estate_ranking.attachments import (AttachedPoints, attached_routing_graph,
    read_attached_points, select_attachments, split_attachments)
from estate_ranking.graph import PhysicalGraph
from estate_ranking.ingest import read_json
from estate_ranking.step_3 import validate_terminals, verify_hashes
from estate_ranking.routes import path_transitions, ordered_sections, check_cost

DEFAULT_GRAPH = WORK / 'precomputed/outputs/step_3/current'
DEFAULT_OUTPUT = WORK / 'precomputed/demos/coordinate_route/route.png'
ROUTE_COLUMNS = ['sequence', 'kind', 'source_id', 'direction', 'distance_m', 'time_s',
                 'lift_id', 'time_model', 'time_model_warning', 'fallback_review_ids', 'geometry']


def coordinates(values):
    """Validate a latitude/longitude pair, including NaN and infinity."""
    latitude, longitude = map(float, values)
    if not (math.isfinite(latitude) and -90 <= latitude <= 90 and
            math.isfinite(longitude) and -180 <= longitude <= 180):
        raise ValueError('Use finite latitude [-90, 90] and longitude [-180, 180].')
    return latitude, longitude


def prompt_coordinates(label):
    while True:
        try:
            values = input(label + ' latitude, longitude: ').replace(',', ' ').split()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit('\nCoordinate entry cancelled.')
        if len(values) == 2:
            try:
                return coordinates(values)
            except ValueError as error:
                print(error)
        else:
            print('Enter two numbers, for example: 22.280111, 114.130386')


def empty_route():
    return gpd.GeoDataFrame(columns=ROUTE_COLUMNS, crs=2326)


def connector_geometry(start, end):
    """Keep exact zero-cost connections as mappings, not degenerate lines."""
    return None if start.equals(end) else LineString([start, end])


def endpoint_attachments(physical, start, end, wheelchair=False):
    indices = np.unique(np.r_[
        physical.edges.sindex.query(start, predicate='dwithin', distance=200.),
        physical.edges.sindex.query(end, predicate='dwithin', distance=200.)]).astype(int)
    edges = physical.edges.iloc[indices].copy()
    sources = physical.sources.loc[physical.sources.PedestrianRouteID.astype(str).isin(edges.source_id)]
    local = PhysicalGraph(physical.nodes, edges, sources, physical.memberships,
                          physical.profiles, [], physical.policy)
    origin = gpd.GeoDataFrame([dict(id='point:start', geometry=start)], crs=2326)
    destination = gpd.GeoDataFrame([dict(id='point:end', geometry=end,
        general_mode_candidate=True, wheelchair_mode_candidate=True)], crs=2326)
    # Reuse the existing departure/arrival selectors. The MTR selector supplies
    # a time-based arrival role here; the destination remains an arbitrary point.
    selections, candidates = select_attachments(local, {'estate': origin, 'mtr_access': destination})
    mode = 'wheelchair' if wheelchair else 'general'
    selected = selections.loc[(selections['mode'] == mode) & (selections.metric == 'time')].copy()
    selected['entity_type'] = selected.entity_id.map({'point:start': 'start', 'point:end': 'destination'})
    return selected, candidates.loc[candidates.attachment_id.isin(selected.attachment_id)].copy()


def find_route(physical, start, end, wheelchair=False, evidence_directory=None):
    """Subdivide both selected positions together, then run directed Dijkstra.

    No source elevations are assigned to the supplied 2D points. Both terminal
    roles are one-way, and the original physical graph is left unchanged.
    """
    empty_attachments = gpd.GeoDataFrame(columns=['entity_id', 'status', 'geometry'], crs=2326)
    if start.equals(end):
        return {'status': 'ok', 'message': 'Start and destination are the same coordinate.',
                'distance_m': 0., 'time_s': 0.}, empty_route(), empty_attachments
    selected, candidates = endpoint_attachments(physical, start, end, wheelchair)
    if not (selected.status == 'attached').all():
        missing = ['start' if row.entity_id == 'point:start' else 'destination'
                   for row in selected.loc[selected.status != 'attached'].itertuples()]
        return {'status': 'unattached', 'message': 'No suitable path in the dataset for ' +
                ' and '.join(missing) + '.', 'distance_m': None, 'time_s': None}, empty_route(), selected
    augmented, validation = split_attachments(physical, selected, evidence_directory)
    points = {'point:start': start, 'point:end': end}
    connectors = []
    for row in selected.itertuples():
        geometry = connector_geometry(points[row.entity_id], shapely.force_2d(row.geometry))
        if geometry is not None:
            connectors.append(dict(attachment_id=row.attachment_id, geometry=geometry))
    attached = AttachedPoints(augmented, {}, selected,
        gpd.GeoDataFrame(connectors, columns=['attachment_id', 'geometry'], crs=2326), candidates, validation)
    graph = attached_routing_graph(attached, wheelchair, 'time')
    validate_terminals(graph)
    terminals = graph.terminals.set_index('entity_id')
    start_state = int(terminals.loc['point:start', 'state_index'])
    end_state = int(terminals.loc['point:end', 'state_index'])
    costs, predecessors = dijkstra(graph.matrix, directed=True, indices=start_state,
                                   return_predecessors=True)
    if not np.isfinite(costs[end_state]):
        return {'status': 'unreachable', 'message': 'Both points attached, but no permitted walking route connects them.',
                'distance_m': None, 'time_s': None, 'subdivision_validation': validation}, empty_route(), selected
    indices = path_transitions(graph, predecessors, start_state, end_state)
    route = ordered_sections(graph, indices, points)
    check_cost(route.time_s, costs[end_state])
    return {'status': 'ok', 'message': 'Fastest route under the saved walking model.',
            'distance_m': float(route.distance_m.sum()), 'time_s': float(costs[end_state]),
            'estimated_network_sections': int(route.time_model.eq('distance_height_estimate').sum()),
            'subdivision_validation': validation, 'route_cost_sum_verified': True}, route, selected


def render_png(physical, start, end, route, result, output, wheelchair=False,
               start_label='Start', end_label='Destination'):
    os.environ['MPLCONFIGDIR'] = str(WORK / 'cache/matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    geometries = route.loc[route.geometry.notna()].copy()
    bounds = np.array([min(start.x, end.x), min(start.y, end.y),
                       max(start.x, end.x), max(start.y, end.y)])
    if len(geometries):
        b = geometries.total_bounds
        bounds = np.array([min(bounds[0], b[0]), min(bounds[1], b[1]),
                           max(bounds[2], b[2]), max(bounds[3], b[3])])
    margin = max(60., .08 * max(bounds[2] - bounds[0], bounds[3] - bounds[1]))
    extent = box(bounds[0] - margin, bounds[1] - margin, bounds[2] + margin, bounds[3] + margin)
    background = physical.edges.iloc[physical.edges.sindex.query(extent, predicate='intersects')]
    background = background.loc[background['allow_wheelchair' if wheelchair else 'allow_general']]
    fig, ax = plt.subplots(figsize=(10, 8))
    if len(background):
        background.plot(ax=ax, color='#d6dce1', linewidth=.7, zorder=1)
    network = geometries.loc[geometries.kind == 'network']
    connectors = geometries.loc[geometries.kind != 'network']
    if len(network):
        network.plot(ax=ax, color='#0969da', linewidth=3, zorder=3)
    if len(connectors):
        connectors.plot(ax=ax, color='#d97706', linewidth=2.5, linestyle='--', zorder=4)
    for point, label, color, offset in [(start, start_label, '#111827', (10, -25)),
                                       (end, end_label, '#16803c', (10, 10))]:
        ax.scatter([point.x], [point.y], color=color, s=70, zorder=5)
        ax.annotate(label, (point.x, point.y), xytext=offset, textcoords='offset points', fontsize=10)
    mode = 'Wheelchair' if wheelchair else 'General walking'
    subtitle = (f'{result["distance_m"]:.0f} m; {result["time_s"] / 60:.1f} minutes (model estimate)'
                if result['status'] == 'ok' else result['message'])
    ax.set_title(mode + ': ' + start_label + ' to ' + end_label + '\n' + subtitle, fontsize=12)
    ax.set_xlim(extent.bounds[0], extent.bounds[2])
    ax.set_ylim(extent.bounds[1], extent.bounds[3])
    ax.set_aspect('equal')
    ax.set_xlabel('HK1980 easting (metres)')
    ax.set_ylabel('HK1980 northing (metres)')
    ax.legend(handles=[Line2D([0], [0], color='#0969da', lw=3, label='Network route'),
                       Line2D([0], [0], color='#d97706', lw=2.5, linestyle='--', label='Assumed connectors'),
                       Line2D([0], [0], color='#d6dce1', lw=1, label='Supplied pedestrian paths')], loc='best')
    fig.text(.5, .02, 'Times use the saved Tobler/lift model. Traffic-light waits and temporary closures are excluded.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .035, 1, 1))
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--start', nargs=2, type=float, metavar=('LAT', 'LON'), help='Starting latitude and longitude')
    parser.add_argument('--end', nargs=2, type=float, metavar=('LAT', 'LON'), help='Destination latitude and longitude')
    parser.add_argument('--wheelchair', action='store_true', help='Use the saved wheelchair eligibility rules')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='PNG filename (JSON and CSV are saved beside it)')
    parser.add_argument('--graph-directory', type=Path, default=DEFAULT_GRAPH, help='Successful Step 3 run or current directory')
    parser.add_argument('--start-label', default='Start')
    parser.add_argument('--end-label', default='Destination')
    args = parser.parse_args(argv)
    try:
        start_latlon = coordinates(args.start) if args.start is not None else prompt_coordinates('Start')
        end_latlon = coordinates(args.end) if args.end is not None else prompt_coordinates('Destination')
    except ValueError as error:
        parser.error(str(error))
    directory = args.graph_directory.resolve(strict=True)
    output = args.output.resolve()
    if output.suffix.lower() != '.png':
        parser.error('--output must end in .png')
    manifest = read_json(directory / 'manifest.json')
    upstream = WORK / manifest['frozen_inputs']['step_2']['directory']
    if output.is_relative_to(directory) or output.is_relative_to(upstream):
        parser.error('Choose an output path outside the saved input runs.')
    if read_json(directory / 'SUCCESS.json')['validation'] != 'passed':
        parser.error('The selected graph did not pass validation.')
    print('Verifying and loading the saved pedestrian network...', flush=True)
    verify_hashes(directory, manifest['artifacts'])
    physical = read_attached_points(directory).physical
    transform = Transformer.from_crs(4326, 2326, always_xy=True)
    start = Point(transform.transform(start_latlon[1], start_latlon[0]))
    end = Point(transform.transform(end_latlon[1], end_latlon[0]))
    print('Attaching the two points and finding the fastest permitted route...', flush=True)
    verify_hashes(upstream, {name: manifest['frozen_inputs']['step_2']['files'][name]
                           for name in ['graph.gpkg', 'profiles.jsonl', 'model_policy.json']})
    result, route, attachments = find_route(physical, start, end, args.wheelchair, upstream)
    result.update(start={'latitude': start_latlon[0], 'longitude': start_latlon[1], 'height': None},
        end={'latitude': end_latlon[0], 'longitude': end_latlon[1], 'height': None},
        mode='wheelchair' if args.wheelchair else 'general', step_3_run=directory.name,
        created_utc=datetime.now(timezone.utc).isoformat(),
        assumptions=['Nearest suitable outdoor path; indoor fallback within 200 m.',
                     'Unknown endpoint heights; straight flat connectors.',
                     'Saved Tobler, reviewed estimated times and lift entry charges; no crossing waits or live access checks.'])
    result['attachments'] = []
    for row in attachments.itertuples():
        attached = row.status == 'attached'
        result['attachments'].append(dict(point=row.entity_id, status=row.status, reason=row.reason,
            warnings=row.warnings, source_id=row.source_id,
            connector_m=float(row.distance_m) if attached else None,
            attachment_height_hkpd_m=float(row.height_m) if attached else None))
    output.parent.mkdir(parents=True, exist_ok=True)
    render_png(physical, start, end, route, result, output, args.wheelchair, args.start_label, args.end_label)
    output.with_suffix('.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    route.drop(columns='geometry').to_csv(output.with_suffix('.csv'), index=False)
    if result['status'] == 'ok':
        seconds = round(result['time_s'])
        print(f'Fastest route: {result["distance_m"]:.1f} m; {seconds // 60} min {seconds % 60:02d} sec')
    else:
        print(result['message'])
    if result.get('estimated_network_sections', 0):
        print('Includes estimated traversal time on ' + str(result['estimated_network_sections']) + ' network sections; see route details.')
    warning_labels = {'level_uncertain': 'path level is assumed',
        'long_connector': 'connection to the network is longer than 50 m',
        'indoor_fallback': 'uses an indoor path',
        'alternative_level': 'another nearby path is on a different level',
        'distance_tie_lower_height_assumption': 'equally close paths; the lower level was chosen'}
    for attachment in result['attachments']:
        if attachment['warnings']:
            label = args.start_label if attachment['point'] == 'point:start' else args.end_label
            print(label + ': ' + '; '.join(warning_labels.get(w, w)
                  for w in attachment['warnings'].split(';')))
    print('PNG: ' + str(output))
    print('Details: ' + str(output.with_suffix('.json')))
    return 0 if result['status'] == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
