"""Hospital-only overlays preserve graphs, transport and historical cache readers."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import numpy as np

from estate_ranking.export import write_json
from estate_ranking.hospital_amendment import load_overrides, resolve_override, apply_overrides, amend
from estate_ranking.step_4 import (JourneyCache, read_subcosts, validate_saved, _opened)
from test_step_4 import fixture, compute, saved


def island_fixture():
    return fixture(paths=[[(0, 0, 0), (1, 0, 0)], [(0, 5, 2), (10, 5, 2)]],
        coords={'estate': [(0, 0)], 'hospital': [(10, 5), (100, 100)],
                'bus_stop': [(10, 5)], 'mtr_access': [(10, 5)]})


def specification(graph):
    node = graph.nodes.loc[graph.nodes.geometry.map(lambda p: list(p.coords[0]) == [0., 5., 2.])].iloc[0]
    return dict(estate_id='estate:0', estate_name='Test Estate', node_index=int(node.node_index),
                node_id=node.node_id, source_id='2', position=list(node.geometry.coords[0]))


class HospitalAmendmentTests(unittest.TestCase):
    def test_only_hospital_pairs_change_and_readers_do_not_reroute(self):
        physical, attached, graphs = island_fixture()
        graph = graphs['general_distance']
        matrix = graph.matrix.copy()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'run').mkdir()
            data = compute(attached, graphs, root/'run')
            original = copy.deepcopy(data)
            policy = dict(overrides=[specification(graph)], unchanged_unavailable_estates=[])
            report = apply_overrides(data, graph, root/'run', policy)
            self.assertEqual(report['production_searches'], 1)
            self.assertEqual(report['updated_pairs'], 2)
            self.assertEqual(report['estates'][0]['reachable_pairs_before'], 0)
            self.assertAlmostEqual(report['estates'][0]['nearest_hospital_m'], 15.)
            for key in ('groups', 'group_comparisons', 'target_comparisons'):
                self.assertEqual(data[key], original[key])
            keep = lambda r: r['graph'] != 'general_distance'
            self.assertEqual(list(filter(keep, data['routes'])), list(filter(keep, original['routes'])))
            self.assertTrue(np.array_equal(graph.matrix.data, matrix.data))
            self.assertTrue(np.array_equal(graph.matrix.indices, matrix.indices))
            checks = validate_saved(root/'run', data, graphs.__getitem__)
            self.assertEqual(checks['hospital_forward_pairs_checked'], 2)
            directory, _ = saved(root, physical, attached, graphs, data)
            with patch('estate_ranking.step_4.dijkstra', side_effect=AssertionError('reader rerouted')):
                cache = JourneyCache(directory)
                route = cache.route('estate:0', 'hospital:0')
                self.assertAlmostEqual(route.cost.sum(), 15.)
                self.assertEqual(route.kind.iloc[0], 'start_connector')
                self.assertEqual(route.cost.iloc[0], 5.)
                self.assertFalse(route.geometry.iloc[0].has_z)
                self.assertTrue(route.loc[route.kind == 'network'].geometry.has_z.all())
                self.assertIn('entrance_and_level_unverified', route.attrs['warnings'])
                for w in (False, True):
                    for scenario in ('primary', 'baseline'):
                        f = read_subcosts(w, scenario=scenario, directory=directory)
                        self.assertEqual(f.hospital_distance_m.iloc[0], 15.)
                        self.assertEqual(f.hospital_target_ids.iloc[0], ['hospital:0'])
                # The original attachments remain untouched by the overlay.
                self.assertEqual(graph.attachments.loc[
                    (graph.attachments.entity_id == 'estate:0') &
                    (graph.attachments.metric == 'distance'), 'source_id'].iloc[0], '1')
            _opened.cache_clear()

    def test_stale_policy_wrong_node_coordinates_and_direction_are_rejected(self):
        _, _, graphs = island_fixture()
        graph = graphs['general_distance']
        from estate_ranking.step_4 import SearchCache
        original = SearchCache(graph, 'general_distance').attachment('estate:0')
        spec = specification(graph)
        for change in ({'node_id': 'wrong'}, {'position': [0, 5, 3]}, {'source_id': '1'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                resolve_override(graph, dict(spec, **change), original)
        with tempfile.TemporaryDirectory() as tmp:
            policy = dict(schema_version=1, scope='hospital_only_shared_general_distance',
                step_3_run_id='old', step_3_manifest_sha256='abc',
                overrides=[spec], unchanged_unavailable_estates=[])
            path = Path(tmp)/'policy.json'; write_json(path, policy)
            with self.assertRaisesRegex(ValueError, 'require review'):
                load_overrides({'step_3': {'run_id': 'new', 'manifest_sha256': 'abc'}}, path)
        # A departure cannot attach to the disallowed end of a directed source.
        graph.edges.loc[graph.edges.source_id == '2', 'direction'] = -1
        with self.assertRaisesRegex(ValueError, 'source position'):
            resolve_override(graph, spec, original)

    def test_unreachable_selected_hospital_keeps_requested_identity(self):
        physical, attached, graphs = fixture(paths=[[(0,0,0),(1,0,0)], [(0,5,0),(10,5,0)]],
            coords={'estate':[(0,0)], 'hospital':[(10,5)],
                    'bus_stop':[(10,5)], 'mtr_access':[(10,5)]})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'run').mkdir()
            data=compute(attached, graphs, root/'run')
            directory,_=saved(root, physical, attached, graphs, data)
            frame=read_subcosts(hospital_id='hospital:0', directory=directory)
            self.assertEqual(frame.hospital_status.iloc[0], 'unreachable')
            self.assertEqual(frame.requested_hospital_id.iloc[0], 'hospital:0')
            self.assertEqual(frame.attrs['requested_hospital_id'], 'hospital:0')
            _opened.cache_clear()

    def test_failure_does_not_change_selected_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); previous=root/'prior';previous.mkdir()
            output=root/'outputs';output.mkdir();(output/'current').symlink_to(previous)
            write_json(previous/'manifest.json', {'run_id':'prior'})
            write_json(previous/'results.json', {})
            pair={'step_3':{}}
            parent=Mock(directory=previous, frozen=pair)
            with patch('estate_ranking.hospital_amendment.WORK',root), \
                 patch('estate_ranking.step_4.freeze_pair',return_value=(pair,{})), \
                 patch('estate_ranking.step_4.JourneyCache',return_value=parent), \
                 patch('estate_ranking.hospital_amendment.load_overrides',return_value={}), \
                 patch('estate_ranking.hospital_amendment.apply_overrides',side_effect=ValueError('rejected override')):
                with self.assertRaisesRegex(ValueError,'rejected override'):
                    amend(output)
            self.assertEqual((output/'current').resolve(),previous.resolve())
            self.assertEqual(len(list((root/'cache/step_4_staging').glob('*/FAILURE.json'))),1)


if __name__ == '__main__':
    unittest.main()
