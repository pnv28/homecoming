"""Evidence audits must reveal source defects without rewriting source records."""
import copy
import unittest
from unittest.mock import patch

import numpy as np
from shapely.geometry import LineString

from estate_ranking.graph import build_physical_graph
from estate_ranking.graph_vertical_audit import audit_source_provenance, audit_vertical_sources
from test_step_2 import network


class VerticalAuditTests(unittest.TestCase):
    def test_original_vertical_interval_and_healthy_portion_are_distinguished(self):
        physical = build_physical_graph(network([
            ([(0, 0, 0), (0, 0, 5), (10, 0, 6)], {'id': 100, 'gradient': .1})]))
        original = physical.sources.geometry.iloc[0].wkb
        audit = audit_vertical_sources(physical)
        self.assertEqual(audit['source_count'], 1)
        self.assertEqual(audit['original_vertical_interval_count'], 1)
        source = audit['sources'][0]
        self.assertEqual(source['vertical_intervals'][0]['height_change_metres'], 5)
        self.assertEqual(source['healthy_profile_horizontal_metres'], 10)
        self.assertEqual(source['healthy_profile_interval_count'], 1)
        self.assertFalse(source['automatic_source_correction_supported'])
        self.assertEqual(physical.sources.geometry.iloc[0].wkb, original)
        # Reopened PhysicalGraph intentionally omits CostProfile objects.
        reopened = copy.copy(physical)
        reopened.profiles = []
        self.assertEqual(audit_vertical_sources(reopened), audit)

    def test_lift_vertical_and_identical_vertices_are_not_source_defects(self):
        physical = build_physical_graph(network([
            ([(0, 0, 0), (0, 0, 5)], {'id': 100, 'kind': 'Lift'}),
            ([(20, 0, 0), (20, 0, 0), (30, 0, 0)], {'id': 200})]))
        self.assertEqual(audit_vertical_sources(physical)['source_count'], 0)

    def test_inconsistent_profile_evidence_is_rejected(self):
        physical = build_physical_graph(network([
            ([(0, 0, 0), (0, 0, 5), (10, 0, 6)], {'id': 100, 'gradient': .1})]))
        physical.profiles[0].gradient = .2
        with self.assertRaisesRegex(AssertionError, 'Profile/source evidence mismatch'):
            audit_vertical_sources(physical)

    def test_multiple_vertical_intervals_in_one_source_are_all_recorded(self):
        physical = build_physical_graph(network([
            ([(0, 0, 5), (10, 0, 6), (10, 0, 7), (10, 0, 6.5)], {'id': 100})]))
        audit = audit_vertical_sources(physical)
        self.assertEqual(audit['source_count'], 1)
        self.assertEqual(audit['original_vertical_interval_count'], 2)
        self.assertEqual([r['location'] for r in audit['sources'][0]['vertical_intervals']],
                         ['interior', 'end'])

    def test_source_provenance_checks_xyz_and_attributes_without_rounding(self):
        original = network([([(0, 0, 0), (10, 0, 1)], {'id': 100, 'gradient': .1})])
        physical = build_physical_graph(original)
        with patch('estate_ranking.graph_vertical_audit.pyogrio.read_dataframe',
                   side_effect=[original.copy(), original.copy()]):
            audit = audit_source_provenance(physical, ['100'], '/unused', '/unused.gdb')
        self.assertEqual(audit['sources_checked'], 1)
        self.assertTrue(audit['all_match'])
        changed = original.copy()
        changed.loc[0, 'Gradient'] = np.nextafter(.1, np.inf)
        with patch('estate_ranking.graph_vertical_audit.pyogrio.read_dataframe',
                   side_effect=[changed, original.copy()]):
            with self.assertRaisesRegex(AssertionError, 'Gradient'):
                audit_source_provenance(physical, ['100'], '/unused', '/unused.gdb')
        changed = original.copy()
        changed.loc[0, 'geometry'] = LineString([(0, 0, 0), (10, 0, 1.01)])
        with patch('estate_ranking.graph_vertical_audit.pyogrio.read_dataframe',
                   side_effect=[changed, original.copy()]):
            with self.assertRaisesRegex(AssertionError, 'geometry=False'):
                audit_source_provenance(physical, ['100'], '/unused', '/unused.gdb')

    def test_source_provenance_checks_dates_as_instants_and_preserves_nulls(self):
        original = network([([(0, 0, 0), (10, 0, 1)], {'id': 100})])
        original['CreationDate'] = ['2026/10/14 00:00:00+00']
        physical = build_physical_graph(original)
        raw = original.copy()
        import pandas as pd
        raw['CreationDate'] = [pd.Timestamp('2026-10-14T00:00:00Z')]
        with patch('estate_ranking.graph_vertical_audit.pyogrio.read_dataframe',
                   side_effect=[raw, original.copy()]):
            self.assertTrue(audit_source_provenance(physical, ['100'], '/unused', '/unused.gdb')['all_match'])


if __name__ == '__main__':
    unittest.main()
