"""Whole-build selection, immutable dependencies and rollback."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from estate_ranking.run_registry import publish_pair, selected_run
from estate_ranking.step_2 import publish_run


def pair(root,label):
    paths=[]
    for stage in ['step_2','step_3']:
        p=root/'precomputed/outputs'/stage/'runs'/label;p.mkdir(parents=True)
        (p/'SUCCESS.json').write_text(json.dumps({'run_id':label,'validation':'passed'}))
        (p/'manifest.json').write_text(json.dumps({'run_id':label}))
        paths.append(p)
    (paths[1]/'frozen_inputs.json').write_text(json.dumps({'step_2':{
        'run_id':label,'directory':str(paths[0].relative_to(root))}}))
    return paths


class PairPublicationTests(unittest.TestCase):
    def test_select_pair_and_validate_manifest_on_read(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();a,b=pair(root,'candidate')
            publish_pair(a,b,root)
            self.assertEqual(selected_run('step_2',root),a)
            self.assertEqual(selected_run('step_3',root),b)
            (a/'manifest.json').write_text('{}')
            with self.assertRaises(ValueError):selected_run('step_2',root)

    def test_second_selection_failure_restores_old_pair(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();old=pair(root,'old');new=pair(root,'new')
            publish_pair(*old,work=root)
            # Allow rollback of the old Step 3 link; only reject the new one.
            def reject_new(directory,current):
                if Path(directory)==new[1]:raise OSError('injected publication failure')
                publish_run(directory,current)
            with patch('estate_ranking.step_2.publish_run',side_effect=reject_new):
                with self.assertRaises(OSError):publish_pair(*new,work=root)
            self.assertEqual(selected_run('step_2',root),old[0])
            self.assertEqual(selected_run('step_3',root),old[1])
            self.assertEqual((root/'precomputed/outputs/step_2/current').resolve(),old[0])

    def test_mismatched_upstream_does_not_select(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();old=pair(root,'old');new=pair(root,'new')
            publish_pair(*old,work=root)
            with self.assertRaises(ValueError):publish_pair(new[0],old[1],root)
            self.assertEqual(selected_run('step_2',root),old[0])


if __name__=='__main__':unittest.main()
