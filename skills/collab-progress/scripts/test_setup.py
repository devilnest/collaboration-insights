"""First-run data location: nothing hardcoded, user choice recorded, private by default."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import progress as p
import progress_core as core


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.skill = self.root / 'skill'; self.skill.mkdir()
        values = dict(SKILL_DIR=self.skill, CONFIG_PATH=self.skill / 'config.json', DEFAULT_DATA=self.skill / 'data')
        self.patches = [patch.object(m, k, v) for m in (core, p) for k, v in values.items()]
        self.patches.append(patch.dict(os.environ, {}, clear=False)); [x.start() for x in self.patches]
        os.environ.pop('COLLAB_PROGRESS_HOME', None)
        empty = self.root / 'no-history'
        self.homes = ['codex=' + str(empty), 'claude=' + str(empty)]

    def tearDown(self):
        [x.stop() for x in reversed(self.patches)]; self.tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = p.main([*sum((['--history-home', h] for h in self.homes), []), *args])
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_unconfigured_commands_ask_for_setup(self):
        code, result = self.run_cli('scan')
        self.assertEqual(code, 2); self.assertTrue(result['needs_setup'])
        self.assertEqual(result['default_data_dir'], str(self.skill / 'data'))
        code, info = self.run_cli('where')
        self.assertEqual(code, 0); self.assertFalse(info['configured']); self.assertIn('ask the user', info['next_step'])

    def test_default_setup_is_inside_skill_and_relocatable(self):
        code, result = self.run_cli('setup', '--default')
        self.assertEqual(code, 0); self.assertEqual(result['action'], 'started a new empty tracker')
        self.assertEqual(json.loads((self.skill / 'config.json').read_text())['data_dir'], 'data')
        data = self.skill / 'data'
        self.assertTrue((data / 'progress.sqlite').exists()); self.assertTrue((data / 'coaching').is_dir())
        self.assertEqual((data / '.gitignore').read_text().splitlines()[-1], '*')
        self.assertIn('data/', (self.skill / '.gitignore').read_text())
        self.assertEqual(self.run_cli('scan')[0], 0)

    def test_custom_location_and_copy_keep_the_source(self):
        first = self.root / 'first'; self.run_cli('setup', '--data', str(first))
        before = (first / 'progress.sqlite').read_bytes()
        code, result = self.run_cli('setup', '--data', str(self.root / 'second'), '--copy-from', str(first))
        self.assertEqual(code, 0); self.assertTrue(result['action'].startswith('copied'))
        self.assertEqual(before, (first / 'progress.sqlite').read_bytes())
        self.assertEqual(self.run_cli('where')[1]['data_dir'], str((self.root / 'second').resolve()))

    def test_setup_refuses_to_overwrite_or_take_over_a_foreign_folder(self):
        target = self.root / 'busy'; target.mkdir(); (target / 'notes.txt').write_text('x')
        self.assertEqual(self.run_cli('setup', '--data', str(target))[0], 1)
        good = self.root / 'good'; self.run_cli('setup', '--data', str(good))
        self.assertEqual(self.run_cli('setup', '--data', str(good), '--copy-from', str(good))[0], 1)
        self.assertEqual(self.run_cli('setup', '--data', str(good))[1]['action'], 'reused existing tracker')

    def test_environment_variable_wins(self):
        os.environ['COLLAB_PROGRESS_HOME'] = str(self.root / 'env')
        self.assertEqual(self.run_cli('where')[1]['chosen_by'], 'env:COLLAB_PROGRESS_HOME')


if __name__ == '__main__':
    unittest.main()
