"""One tracker over several harnesses: Codex SQLite + Claude Code JSONL fixtures."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import progress as p


class MultiHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.codex = root / 'codex'; self.codex.mkdir()
        state = sqlite3.connect(self.codex / 'state_1.sqlite')
        state.execute('create table threads(id text,rollout_path text,source text,created_at integer,updated_at integer)')
        state.execute("insert into threads values ('codex-chat','', 'cli', 1, 1)"); state.commit(); state.close()
        items = sqlite3.connect(self.codex / 'thread_history_1.sqlite')
        items.execute('create table thread_items(thread_id text,rollout_ordinal integer,created_at_ms integer,turn_id text,item_json text)')
        items.execute("insert into thread_items values ('codex-chat',1,1793000001000,'t',?)", (p.canon(dict(type='userMessage', content=[dict(type='text', text='Repair the counter.')])),))
        items.commit(); items.close()
        self.claude = root / 'claude'; proj = self.claude / 'projects' / 'demo'; proj.mkdir(parents=True)
        self.write_claude(proj / 'claude-chat.jsonl', 'Document the startup steps.')
        self.env = patch.dict(os.environ, {'CODEX_SQLITE_HOME': str(self.codex)}); self.env.start()
        self.history = p.History({'codex': self.codex, 'claude': self.claude})
        self.store = p.Store(root / 'data', write=True, create=True)
        self.store.put_setting('excluded_sessions', {}); self.store.db.commit()

    def tearDown(self):
        self.store.db.close(); self.env.stop(); self.tmp.cleanup()

    @staticmethod
    def write_claude(path, text):
        path.write_text(p.canon(dict(type='user', uuid='u1', promptId='t1', turnOrigin='human', timestamp='2026-11-13T10:00:00Z', message=dict(role='user', content=text))) + '\n', encoding='utf-8')

    def test_scan_sees_both_harnesses(self):
        result = p.scan(self.store, self.history)
        self.assertEqual(result['by_harness'], {'codex': 1, 'claude': 1})
        self.assertEqual(sorted(x['session_id'] for x in result['pending']), ['claude-chat', 'codex-chat'])

    def test_each_source_is_read_by_its_own_adapter(self):
        self.assertTrue(self.history.source('codex-chat')['source_kind'].startswith('codex:'))
        claude = self.history.source('claude-chat')
        self.assertEqual(claude['source_kind'], 'claude:claude-jsonl')
        self.assertEqual(claude['events'][0]['text'], 'Document the startup steps.')

    def test_same_id_in_two_harnesses_is_an_error(self):
        self.write_claude(self.claude / 'projects' / 'demo' / 'codex-chat.jsonl', 'Collide.')
        with self.assertRaises(ValueError):
            self.history.catalog()

    def test_missing_home_is_skipped_not_fatal(self):
        history = p.History({'codex': self.codex, 'claude': Path(self.tmp.name) / 'absent'})
        self.assertEqual([r['id'] for r in history.catalog()], ['codex-chat'])

    def test_current_session_from_either_harness(self):
        with patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'claude-chat'}, clear=False):
            os.environ.pop('CODEX_THREAD_ID', None); os.environ.pop('CODEX_SESSION_ID', None)
            self.assertEqual(p.resolve_session('current'), 'claude-chat')
        with patch.dict(os.environ, {'CODEX_THREAD_ID': 'codex-chat'}, clear=False):
            self.assertEqual(p.resolve_session('current'), 'codex-chat')

    def test_history_home_override_parsing(self):
        homes = p.history_homes(['claude=' + str(self.claude)], {'codex': str(self.codex)})
        self.assertEqual(homes['claude'], self.claude); self.assertEqual(homes['codex'], self.codex)
        with self.assertRaises(ValueError):
            p.history_homes(['cursor=/x'])


if __name__ == '__main__':
    unittest.main()
