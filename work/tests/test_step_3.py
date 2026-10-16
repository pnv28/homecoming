"""Step 3 geometry, directional routing, evidence and publication contracts."""
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import Point

from estate_ranking.attachments import (attach_points, attached_routing_graph,
    read_attached_graph, read_attached_points, save_attached, save_attached_routing)
from estate_ranking.graph import build_physical_graph, save_physical
from estate_ranking.graph_costs import tobler_seconds
from estate_ranking.step_2 import publish_run
from estate_ranking.step_3 import validate_attachments, validate_terminals, verify_frames, run
from test_step_2 import network


def physical(paths, locations=None):
    frame = network(paths)
    frame['Location_label'] = locations or ['Outdoor'] * len(frame)
    return build_physical_graph(frame, audit_crossings=False)


def points(kind, coords, eligible=None):
    rows = []
    for i, xy in enumerate(coords):
        rows.append(dict(id=kind + ':' + str(i), name='Point ' + str(i),
            original_attribute=None, geometry=Point(xy),
            general_mode_candidate=True if eligible is None else eligible[i][0],
            wheelchair_mode_candidate=True if eligible is None else eligible[i][1],
            general_boarding_candidate=True if eligible is None else eligible[i][0],
            wheelchair_boarding_candidate=True if eligible is None else eligible[i][1]))
    return gpd.GeoDataFrame(rows, crs=2326)


def row(attached, kind='estate', mode='general', metric='time', i=0):
    return attached.attachments.loc[(attached.attachments.entity_id == kind + ':' + str(i)) &
        (attached.attachments['mode'] == mode) & (attached.attachments.metric == metric)].iloc[0]


class AttachmentTests(unittest.TestCase):
    def test_outdoor_preferred_and_indoor_fallback(self):
        graph = physical([[(0, 10, 3), (10, 10, 3)], [(0, 0, 4), (10, 0, 4)]],
                         ['Outdoor', 'Indoor'])
        a = attach_points(graph, {'estate': points('estate', [(5, 1), (5, -195)])})
        self.assertEqual(row(a).source_id, '1')
        self.assertEqual(row(a, i=1).source_id, '2')
        self.assertIn('indoor_fallback', row(a, i=1).warnings)
        self.assertIn('long_connector', row(a, i=1).warnings)
        validate_attachments(a)

    def test_inclusive_limits_and_immediately_outside(self):
        graph = physical([[(0, 0, 0), (10, 0, 0)]])
        a = attach_points(graph, {'estate': points('estate', [(5, 200), (5, 200.000001)]),
            'bus_stop': points('bus_stop', [(5, 50), (5, 50.000001)])})
        self.assertEqual(row(a).status, 'attached')
        self.assertEqual(row(a, i=1).status, 'attached')
        self.assertTrue(row(a, i=1).connector_above_threshold)
        self.assertIn('connector_above_threshold', row(a, i=1).warnings)
        self.assertEqual(row(a, 'bus_stop').status, 'attached')
        self.assertEqual(row(a, 'bus_stop', i=1).status, 'attached')
        self.assertTrue(row(a, 'bus_stop', i=1).connector_above_threshold)

    def test_flat_cost_zero_connector_and_height_interpolation(self):
        graph = physical([[(0, 0, 10), (10, 0, 20)]])
        a = attach_points(graph, {'estate': points('estate', [(4, 3), (4, 0)])})
        r = row(a)
        self.assertEqual(r.geometry.z, 14.)
        self.assertEqual(r.distance_m, 3.)
        self.assertAlmostEqual(r.time_s, 3 * 3.6 / (6 * math.exp(-.175)))
        self.assertEqual(row(a, i=1).time_s, 0.)
        self.assertTrue(row(a, i=1).zero_distance)
        self.assertEqual(len(a.connectors.loc[a.connectors.attachment_id.isin(
            a.attachments.loc[a.attachments.scenario == 'primary', 'attachment_id'])]), 4)
        self.assertEqual(a.physical.nodes.geometry.has_z.all(), True)
        self.assertFalse(a.entities['estate'].geometry.has_z.any())
        validate_attachments(a)

    def test_exact_tie_lower_height_and_level_warning(self):
        graph = physical([[(0, 0, 10), (10, 0, 10)], [(0, 2, 0), (10, 2, 0)]])
        a = attach_points(graph, {'estate': points('estate', [(5, 1)])})
        r = row(a)
        self.assertEqual(r.source_id, '2')
        self.assertEqual(r.tied_count, 2)
        self.assertTrue(r.alternative_level)
        self.assertIn('distance_tie_lower_height_assumption', r.warnings)
        self.assertEqual(int(a.candidates.loc[~a.candidates.attachment_id.str.endswith(':baseline'), 'selected'].sum()), 4)

    def test_repeated_path_visits_keep_original_segment_height(self):
        graph = physical([[(-10, 0, 10), (10, 0, 10), (10, 10, 10),
                           (-10, 10, 0), (-10, 0, 0), (10, 0, 0)]])
        a = attach_points(graph, {'estate': points('estate', [(0, 0)])})
        r = row(a)
        self.assertEqual(r.source_position, 4.5)
        self.assertEqual(r.height_m, 0.)
        self.assertTrue(r.alternative_level)
        selected = a.physical.nodes.iloc[int(r.node_index)]
        self.assertEqual(selected.member_count, 1)

    def test_nearby_level_and_known_floor_warnings(self):
        graph = physical([([(0, 0, 0), (10, 0, 0)], {'floor': 1, 'building': 7}),
            ([(0, 2.5, 1), (10, 2.5, 1)], {'floor': 2, 'building': 7})])
        a = attach_points(graph, {'estate': points('estate', [(5, 1)])})
        self.assertTrue(row(a).alternative_level)
        self.assertEqual(row(a).source_id, '1')

    def test_closer_indoor_level_outside_one_metre_window(self):
        graph = physical([[(-5, 10, 0), (5, 10, 0)], [(-5, 0, 20), (5, 0, 20)]],
                         ['Outdoor', 'Indoor'])
        a = attach_points(graph, {'estate': points('estate', [(0, 0)])})
        self.assertEqual(row(a).distance_m, 10.)
        self.assertFalse(row(a).alternative_level)

    def test_unknown_location_and_legacy_ordinary_type(self):
        graph = physical([([(0, 0, 0), (10, 0, 0)], {}),
            ([(0, 5, 0), (10, 5, 0)], {'kind': 'M_Footway'})], [None, 'Outdoor'])
        a = attach_points(graph, {'estate': points('estate', [(5, 0)])})
        self.assertEqual(row(a).source_id, '2')

    def test_deterministic_identity_tie_and_height_reuse_tolerance(self):
        graph = physical([[(0, 0, 0), (10, 0, 10)], [(0, 0, 0), (10, 0, 10)]])
        a = attach_points(graph, {'estate': points('estate', [(.05, 0)])})
        self.assertEqual(row(a).source_id, '1')
        self.assertFalse(row(a).reused_node)  # XY < .10; Z > .025.

    def test_reuse_height_boundary_uses_step_2_inclusive_comparison(self):
        graph = physical([[(0, 0, 100), (1, 0, 101)]])
        a = attach_points(graph, {'estate': points('estate', [(.025, 0)])})
        self.assertEqual(row(a).height_m, 100.025)
        self.assertTrue(row(a).reused_node)
        self.assertEqual(len(a.physical.nodes), len(graph.nodes))

    def test_mode_exclusion_disabled_and_unsafe_feature_types(self):
        graph = physical([([(0, 0, 0), (10, 0, 0)], {'barrier': True}),
            ([(0, 5, 0), (10, 5, 0)], {}),
            ([(0, 1, 0), (10, 1, 0)], {'kind': 'Footbridge'}),
            ([(0, 2, 0), (10, 2, 0)], {'enabled': False})])
        a = attach_points(graph, {'estate': points('estate', [(5, 0)]),
            'mtr_access': points('mtr_access', [(5, 0), (5, 0)], [(False, True), (True, False)])})
        self.assertEqual(row(a).source_id, '1')
        self.assertEqual(row(a, mode='wheelchair').source_id, '2')
        self.assertEqual(row(a, 'mtr_access').status, 'excluded')
        self.assertEqual(row(a, 'mtr_access', mode='wheelchair', i=1).status, 'excluded')
        for wheelchair in (False, True):
            validate_terminals(attached_routing_graph(a, wheelchair))

    def test_vertical_segments_not_automatic_attachment(self):
        graph = physical([[(0, 0, 0), (0, 0, 10)]])
        a = attach_points(graph, {'estate': points('estate', [(0, 0)])})
        self.assertEqual(row(a, metric='distance').status, 'unattached')
        self.assertEqual(row(a).status, 'unattached')

    def test_unavailable_time_directions_distance_still_allowed(self):
        graph = physical([([(0, 0, 0), (10, 0, 1)], {'gradient': math.pi / 2}),
                           [(0, 10, 0), (10, 10, 0)]])
        a = attach_points(graph, {'estate': points('estate', [(5, 0)])})
        self.assertEqual(row(a).source_id, '2')
        self.assertEqual(row(a, metric='distance').source_id, '1')

    def test_one_way_endpoint_suitability(self):
        graph = physical([([(0, 0, 0), (10, 0, 0)], {'direction': 1})])
        a = attach_points(graph, {'estate': points('estate', [(10, 0), (0, 0)]),
            'hospital': points('hospital', [(0, 0), (10, 0)])})
        self.assertEqual(row(a).status, 'unattached')
        self.assertEqual(row(a, i=1).status, 'attached')
        self.assertEqual(row(a, 'hospital', metric='distance').status, 'unattached')
        self.assertEqual(row(a, 'hospital', metric='distance', i=1).status, 'attached')

    def test_reuse_tolerances_and_no_cross_path_junction(self):
        graph = physical([[(-10, 0, 0), (10, 0, 0)], [(0, -10, 0), (0, 10, 0)]])
        before = len(graph.nodes)
        a = attach_points(graph, {'estate': points('estate', [(0, 0), (-9.95, 0)])})
        self.assertEqual(len(a.physical.nodes), before + 1)
        self.assertTrue(row(a, i=1).reused_node)
        self.assertEqual(a.physical.nodes.iloc[int(row(a).node_index)].member_count, 1)
        chosen_source = row(a).source_id
        self.assertEqual(len(a.physical.edges.loc[a.physical.edges.source_id != chosen_source]), 1)

    def test_subdivision_preserves_sampling_and_direction_costs(self):
        graph = physical([([(0, 0, 0), (5, 0, 5), (10, 0, 0)], {'gradient': .3, 'direction': -1})])
        a = attach_points(graph, {'estate': points('estate', [(2, 1), (7, 1)])})
        self.assertEqual(a.physical.profiles[0].evidence(), graph.profiles[0].evidence())
        self.assertTrue((a.physical.edges.direction == -1).all())
        for column in ('distance_m', 'time_forward_s', 'time_reverse_s'):
            self.assertAlmostEqual(a.physical.edges[column].sum(), graph.edges[column].sum())

    def test_healthy_sections_preserved_beside_vertical_intervals(self):
        graph = physical([[(-10, 0, 0), (0, 0, 0), (0, 0, 10), (10, 0, 10)]])
        a = attach_points(graph, {'estate': points('estate', [(-5, 1), (5, 1)])})
        self.assertEqual(row(a).status, 'attached')
        self.assertEqual(row(a, i=1).status, 'attached')
        self.assertEqual(int(a.physical.edges.time_forward_s.isna().sum()), 1)
        validate_attachments(a)


class TerminalTests(unittest.TestCase):
    def test_roles_coincident_identity_and_routes_include_connectors(self):
        graph = physical([[(0, 0, 0), (10, 0, 0)]])
        a = attach_points(graph, {'estate': points('estate', [(2, 3), (2, 3)]),
                                 'hospital': points('hospital', [(8, 4), (2, 3)])})
        g = attached_routing_graph(a, metric='distance')
        validate_terminals(g)
        costs = g.costs_from_entity('estate:0')
        terminals = g.terminals.set_index('entity_id')
        self.assertAlmostEqual(costs[int(terminals.loc['hospital:0', 'state_index'])], 13.)
        self.assertTrue(np.isinf(costs[int(terminals.loc['estate:1', 'state_index'])]))
        self.assertEqual(len(set(terminals.state_index)), 4)

    def test_lift_arrival_states_and_multiple_lift_entry_cost(self):
        graph = physical([[(0, 0, 0), (1, 0, 0)],
            ([(1, 0, 0), (1, 0, 5)], {'kind': 'Lift', 'id': 20}),
            ([(1, 0, 5), (1, 0, 10)], {'kind': 'Lift', 'id': 21}),
            [(1, 0, 10), (2, 0, 10)]])
        # Exact horizontal ties choose the lower path for the estate. Arrival
        # chooses the high path by a shorter connector at x=2.
        a = attach_points(graph, {'estate': points('estate', [(0, 0)]),
                                 'mtr_access': points('mtr_access', [(2, 0)])})
        g = attached_routing_graph(a)
        terminal = int(g.terminals.loc[g.terminals.entity_id == 'mtr_access:0', 'state_index'].iloc[0])
        self.assertAlmostEqual(g.costs_from_entity('estate:0')[terminal], 60 + 2 * tobler_seconds(1, 0))
        validate_terminals(g)
        # Destination at the upper lift node accepts both base and lift states.
        b = attach_points(graph, {'mtr_access': points('mtr_access', [(1.01, 0)])})
        gb = attached_routing_graph(b)
        validate_terminals(gb)
        links = gb.transitions.loc[gb.transitions.edge_index < 0]
        self.assertGreaterEqual(len(links), 2)
        self.assertTrue(gb.states.loc[links.from_state, 'lift_id'].notna().any())
        self.assertEqual(set(gb.edges.lift_id.dropna()), {'20', '21'})

    def test_roundtrip_geodataframes_unknown_heights_and_csr(self):
        graph = physical([[(0, 0, 2), (10, 0, 4)]])
        a = attach_points(graph, {'estate': points('estate', [(2, 0), (2, 1)]),
                                 'hospital': points('hospital', [(8, 1)])})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / 'upstream'
            save_physical(upstream, graph)
            output = root / 'attached'
            save_attached(output, a, upstream)
            b = read_attached_points(output)
            verify_frames(a, b)
            for wheelchair in (False, True):
                for metric in ('time', 'distance'):
                    g = attached_routing_graph(a, wheelchair, metric)
                    save_attached_routing(output, g)
                    loaded = read_attached_graph(output, wheelchair, metric)
                    self.assertTrue(np.array_equal(g.matrix.data, loaded.matrix.data))
                    assert_frame_equal(g.terminals, loaded.terminals, check_exact=True)
                    validate_terminals(loaded)
                    self.assertEqual(len(loaded.terminals), len(g.terminals))

    def test_recover_saved_profile_evidence_and_reject_corruption(self):
        graph = physical([([(0, 0, 0), (5, 0, 0), (10, 0, 0)], {'gradient': .2})])
        entities = {'estate': points('estate', [(3, 1)])}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            save_physical(path, graph)
            from estate_ranking.graph import read_physical
            loaded = read_physical(path)
            a = attach_points(loaded, entities, path)
            self.assertEqual(a.physical.profiles[0].evidence(), graph.profiles[0].evidence())
            evidence = json.loads((path / 'profiles.jsonl').read_text())
            evidence['samples'][0]['position'] += .001
            (path / 'profiles.jsonl').write_text(json.dumps(evidence) + '\n')
            with self.assertRaises(AssertionError):
                attach_points(loaded, entities, path)

    def test_failed_build_preserves_current_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous = root / 'outputs/runs/prior'
            previous.mkdir(parents=True)
            (previous / 'SUCCESS.json').write_text('{}')
            current = root / 'outputs/current'
            publish_run(previous, current)
            with patch('estate_ranking.step_3.WORK', root), patch(
                    'estate_ranking.step_3.freeze_inputs', side_effect=ValueError('bad hash')):
                with self.assertRaises(ValueError):
                    run(output_root=root / 'outputs')
            self.assertEqual(current.resolve(), previous.resolve())
            self.assertEqual(len(list((root / 'cache/step_3_staging').glob('*/FAILURE.json'))), 1)

    def test_unattached_and_excluded_roundtrip_empty_reviews(self):
        graph = physical([([(0, 0, 0), (10, 0, 0)], {'kind': 'Footbridge'})])
        a = attach_points(graph, {'mtr_access': points('mtr_access', [(5, 300), (5, 300)],
                                                              [(True, True), (False, False)])})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            save_physical(root / 'upstream', graph)
            save_attached(root / 'output', a, root / 'upstream')
            b = read_attached_points(root / 'output')
            verify_frames(a, b)
            graph = attached_routing_graph(a)
            save_attached_routing(root / 'output', graph)
            loaded = read_attached_graph(root / 'output')
            assert_frame_equal(graph.terminals, loaded.terminals, check_exact=True)
            validate_terminals(loaded)
            self.assertEqual(loaded.terminals.status.tolist(), ['unattached', 'excluded'])


if __name__ == '__main__':
    unittest.main()
