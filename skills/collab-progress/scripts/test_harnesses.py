"""pi adapter, extra homes per harness, user-owned adapters, doctor and probe."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import progress as p
import progress_core as core
import doctor as doc

SECRET = 'TOP-SECRET-PROMPT-TEXT'


def pi_session(folder, sid, lines):
    folder.mkdir(parents=True, exist_ok=True)
    header = dict(type='session', version=3, id=sid, timestamp='2026-11-13T10:00:00.000Z', cwd='/work/demo')
    rows = [header] + lines
    path = folder / f'2026-11-13T10-00-00-000Z_{sid}.jsonl'
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    return path


def entry(eid, parent, message, kind='message'):
    return dict(type=kind, id=eid, parentId=parent, timestamp='2026-11-13T10:00:01.000Z', message=message)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.pi = self.root / 'pi-agent'
        pi_session(self.pi / 'sessions' / '--work-demo--', 'pi-1', [
            entry('a1', None, dict(role='user', content='Fix the parser so empty input returns [] ' + SECRET, timestamp=1)),
            entry('a2', 'a1', dict(role='assistant', content=[dict(type='thinking', thinking='hidden'),
                                                             dict(type='text', text='Looking at the parser.'),
                                                             dict(type='toolCall', id='c1', name='bash', arguments=dict(command='pytest'))])),
            entry('a3', 'a2', dict(role='toolResult', toolCallId='c1', toolName='bash', content=[dict(type='text', text='2 passed')], isError=False)),
            dict(type='model_change', id='a4', parentId='a3', timestamp='2026-11-13T10:00:02.000Z', provider='x', modelId='y'),
            dict(type='compaction', id='a5', parentId='a4', timestamp='2026-11-13T10:00:03.000Z', summary='s', firstKeptEntryId='a5', tokensBefore=1),
            entry('a6', 'a5', dict(role='custom', content='extension note')),
            entry('a7', 'a2', dict(role='user', content=[dict(type='text', text='Branch: try a different fix')])),
        ])
        self.custom_data = self.root / 'data'; (self.custom_data / 'adapters').mkdir(parents=True)
        self.patches = [patch.object(core, 'locate_data', return_value=(self.custom_data, 'test')),
                        patch.dict(os.environ, {}, clear=False)]
        [x.start() for x in self.patches]
        for k in ('CLAUDE_CODE_SESSION_ID', 'CLAUDECODE', 'CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'HERDR_ENV'):
            os.environ.pop(k, None)

    def tearDown(self):
        [x.stop() for x in reversed(self.patches)]; self.tmp.cleanup()

    def test_pi_transcript_maps_to_shared_events(self):
        history = p.History({'pi': self.pi})
        self.assertEqual([(r['id'], r['harness']) for r in history.catalog()], [('pi-1', 'pi')])
        events = history.source('pi-1')['events']
        users = [e for e in events if e['role'] == 'user']
        self.assertEqual([u['ref'] for u in users], ['U001', 'U002'])
        self.assertIn('Branch: try a different fix', users[1]['text'])
        self.assertEqual([e['text'] for e in events if e['role'] == 'assistant'], ['Looking at the parser.'])
        tools = [e for e in events if e['role'] == 'tool']
        self.assertEqual([t['tool'] for t in tools], ['bash', 'recorded_tool_result:bash', None, 'harness-event:pi-custom'])
        self.assertEqual(tools[2]['tool_type'], 'contextCompaction')
        self.assertTrue(all(e['ref'] != 'hidden' for e in events))

    def test_pi_review_commits_through_the_shared_validator(self):
        store = p.Store(self.root / 'tracker', write=True, create=True)
        store.put_setting('excluded_sessions', {}); store.db.commit()
        history = p.History({'pi': self.pi})
        self.assertEqual([x['session_id'] for x in p.scan(store, history)['pending']], ['pi-1'])
        draft = p.prepare(store, history, 'pi-1')['draft']
        episode = p.blank_episode(history.source('pi-1'))
        episode.update(summary='Repair a parser edge case and compare two approaches.', work_class='bug-fix', cohort='general', closed=True)
        for j in list(episode['traits'].values()) + list(episode['indicators'].values()):
            j.update(state='ineligible', reason='No qualifying opportunity in this synthetic task.')
        episode['traits']['T01'].update(state='applied', evidence_refs=['U001'], reason='The user named the expected empty result.')
        draft['episodes'] = [episode]
        self.assertEqual(p.commit(store, history, draft)['status'], 'updated')
        self.assertEqual(p.scan(store, history)['pending'], [])
        store.db.close()

    def test_several_homes_for_one_harness(self):
        other = self.root / 'pi-work'
        pi_session(other / 'sessions' / '--x--', 'pi-2', [entry('b1', None, dict(role='user', content='Second home task'))])
        history = p.History({'pi': self.pi, 'pi:work': other})
        rows = {r['id']: r for r in history.catalog()}
        self.assertEqual((rows['pi-2']['harness'], rows['pi-2']['home']), ('pi', 'pi:work'))
        self.assertEqual(history.source('pi-2')['events'][0]['text'], 'Second home task')
        pi_session(other / 'sessions' / '--x--', 'pi-1', [entry('c1', None, dict(role='user', content='dup'))])
        with self.assertRaises(ValueError):
            history.catalog()

    def test_homes_are_persisted_and_validated(self):
        store = p.Store(self.root / 'tracker', write=True, create=True)
        result = p.manage_homes(store, ['pi:work=' + str(self.pi)], [])
        self.assertEqual(result['homes']['pi:work'], str(self.pi.resolve()))
        self.assertIn('codex', result['effective'])
        with self.assertRaises(ValueError): p.manage_homes(store, ['cursor=' + str(self.pi)], [])
        with self.assertRaises(ValueError): p.manage_homes(store, ['pi:x=' + str(self.root / 'missing')], [])
        self.assertNotIn('pi:work', p.manage_homes(store, [], ['pi:work'])['homes'])
        store.db.close()

    def test_custom_adapter_is_loaded_from_the_data_folder(self):
        store_dir = self.root / 'toyhome'; (store_dir / 'logs').mkdir(parents=True)
        (store_dir / 'logs' / 'toy-1.json').write_text(json.dumps([['user', 'Add a export button'], ['assistant', 'Done']]))
        (self.custom_data / 'adapters' / 'toy.py').write_text('''
import json
from pathlib import Path
NAME = "toy"; SESSION_ENV = ("TOY_SESSION",)
def default_home(): return Path("/nonexistent/toy")
class ToyHistory:
    def __init__(self, home): self.home = Path(home)
    def catalog(self):
        return [dict(id=p.stem, rollout_path=str(p), source="human", created_at="2026-11-13") for p in sorted((self.home / "logs").glob("*.json"))]
    def raw(self, meta):
        rows = json.loads(Path(meta["rollout_path"]).read_text())
        out = []
        for i, (role, text) in enumerate(rows, start=1):
            item = dict(type="userMessage", content=[dict(type="text", text=text)]) if role == "user" else dict(type="agentMessage", text=text)
            out.append((i, 0, "t%d" % i, item))
        return "toy-json", out
READER = ToyHistory
''')
        (self.custom_data / 'adapters' / 'broken.py').write_text('NAME = "codex"\nSESSION_ENV=()\ndef default_home(): pass\nREADER=object\n')
        history = p.History(p.history_homes(['toy=' + str(store_dir)]))
        self.assertIn('toy', p.adapters())
        self.assertEqual(history.source('toy-1')['events'][0]['text'], 'Add a export button')
        self.assertTrue(any('broken.py' in e.get('adapter', '') for e in history.catalog_errors))
        os.environ['TOY_SESSION'] = 'toy-1'
        self.assertEqual(p.resolve_session('current'), 'toy-1')

    def test_doctor_explains_what_is_missing(self):
        os.environ['HERDR_ENV'] = '1'
        report = doc.doctor(p.History({'pi': self.pi, 'mystery': self.root}), p.python_info(), p.resolve_session, cwd=self.root)
        self.assertEqual([r['harness'] for r in report['running_in']], ['herdr'])
        steps = ' '.join(s['what'] for s in report['next_steps'])
        self.assertIn('hosts other agents', steps)
        self.assertIn('No current-session variable', steps)
        self.assertIn('mystery has no adapter', steps)
        self.assertEqual(report['homes'][0]['chats'], 1)

    def test_probe_reports_structure_never_text(self):
        result = doc.probe(self.pi)
        dump = json.dumps(result)
        self.assertNotIn(SECRET, dump); self.assertNotIn('2 passed', dump); self.assertNotIn('Looking at', dump)
        first = result['jsonl'][0]
        self.assertEqual(first['record_types']['message'], 5)
        self.assertEqual(set(first['roles']), {'user', 'assistant', 'toolResult', 'custom'})
        self.assertIn('toolCall', first['content_blocks'])


if __name__ == '__main__':
    unittest.main()
