"""Codex adapter regressions using isolated synthetic Codex SQLite stores only."""
import copy
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import progress as p


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name);self.home=self.root/'history';self.home.mkdir()
        self.env=patch.dict(os.environ,{'CODEX_SQLITE_HOME':str(self.home)})
        self.env.start()
        self.state=sqlite3.connect(self.home/'state_5.sqlite')
        self.state.execute('create table threads(id text,rollout_path text,source text,created_at integer,updated_at integer)')
        self.items=sqlite3.connect(self.home/'thread_history_1.sqlite')
        self.items.execute('create table thread_items(thread_id text,rollout_ordinal integer,created_at_ms integer,turn_id text,item_json text)')
        self.add_session('human')
        self.add('human',1,'userMessage','Please repair the counter so empty input returns zero.','task')
        self.add('human',2,'commandExecution','Two checks passed.','task')
        self.add('human',3,'agentMessage','The requested behaviour is verified.','task')
        self.history=p.History(self.home)
        self.store=p.Store(self.root/'data',write=True,create=True)
        self.store.put_setting('history_home',str(self.home));self.store.put_setting('excluded_sessions',{})
        self.store.put_setting('baseline_record',self.baseline_record(0));self.store.db.commit()

    def tearDown(self):
        self.store.db.close();self.state.close();self.items.close();self.env.stop();self.tmp.cleanup()

    def baseline_record(self,episodes):
        zero=dict.fromkeys(p.COUNTS,0)
        return dict(coverage=dict(task_episodes=episodes),traits=[dict(trait_id=t['id'],measurement_status='unmeasured',counts=zero) for t in p.rubric()['traits']],indicators=[dict(indicator_id=i,measurement_status='unmeasured',counts=zero) for t in p.rubric()['traits'] for i in t['indicators']])

    def add_session(self,sid,source='cli'):
        self.state.execute('insert into threads values (?,?,?,?,?)',(sid,'',source,1,1));self.state.commit()

    def add(self,sid,n,kind,text,turn):
        if kind=='userMessage':item=dict(type=kind,content=[dict(type='text',text=text)])
        elif kind=='agentMessage':item=dict(type=kind,text=text)
        else:item=dict(type=kind,command='python synthetic_check.py',aggregatedOutput=text,exitCode=0)
        self.items.execute('insert into thread_items values (?,?,?,?,?)',(sid,n,1793000000000+n*1000,turn,p.canon(item)));self.items.commit()

    def payload(self,sid='human'):
        draft=p.prepare(self.store,self.history,sid)['draft']
        for e in draft['episodes']:
            if e['summary']=='REVIEW_REQUIRED':
                e.update(summary='Repair a synthetic counter with a concrete result.',work_class='bug-fix')
                for j in list(e['traits'].values())+list(e['indicators'].values()):
                    j.update(state='ineligible',reason='This isolated task does not offer the qualifying opportunity.')
                for j in (e['traits']['T01'],e['indicators']['outcome-stated-at-opening']):
                    j.update(state='applied',reason='The user specified the expected empty-input result.',evidence_refs=['U001'])
        return draft

    def db_hash(self):
        return hashlib.sha256((self.store.root/'progress.sqlite').read_bytes()).hexdigest()

    def test_replay_is_noop_and_does_not_add_snapshot(self):
        draft=self.payload();p.commit(self.store,self.history,draft)
        count=self.store.db.execute('select count(*) from snapshots').fetchone()[0]
        before=self.db_hash();result=p.commit(self.store,self.history,draft)
        self.assertEqual(result['status'],'unchanged');self.assertEqual(before,self.db_hash())
        self.assertEqual(count,self.store.db.execute('select count(*) from snapshots').fetchone()[0])

    def test_old_chat_reopened_is_found_and_replaces_contribution(self):
        p.commit(self.store,self.history,self.payload())
        self.add('human',4,'userMessage','Also preserve negative values in the same repair.','repair')
        draft=p.prepare(self.store,self.history,'human')['draft'];draft['episodes'][0]['end_ordinal']=4
        self.assertEqual(p.scan(self.store,self.history)['pending'][0]['reason'],'changed/reopened')
        p.commit(self.store,self.history,draft)
        self.assertEqual(p.aggregate(self.store.all_reviews())['episodes'],1)
        self.assertEqual(p.aggregate(self.store.all_reviews())['traits']['T01']['applied'],1)

    def test_new_objective_in_same_chat_adds_one_episode(self):
        p.commit(self.store,self.history,self.payload())
        self.add('human',4,'userMessage','Now document how to start the sample application.','new')
        draft=p.prepare(self.store,self.history,'human')['draft']
        second=copy.deepcopy(draft['episodes'][0]);second.update(id='ep-4',start_ordinal=4,end_ordinal=4,summary='Document a synthetic local startup workflow.',work_class='documentation')
        for j in list(second['traits'].values())+list(second['indicators'].values()):
            if j['evidence_refs']:j['evidence_refs']=['U002']
        draft['episodes'].append(second);p.commit(self.store,self.history,draft)
        self.assertEqual(p.aggregate(self.store.all_reviews())['episodes'],2)

    def test_invalid_reference_rolls_back_counts_cursor_audit(self):
        draft=self.payload();draft['episodes'][0]['traits']['T01']['evidence_refs']=['U999']
        before=self.db_hash()
        with self.assertRaises(ValueError):p.commit(self.store,self.history,draft)
        self.assertEqual(before,self.db_hash());self.assertIsNone(self.store.review('human'))

    def test_source_prefix_edit_rejects_stale_review(self):
        draft=self.payload()
        self.items.execute('update thread_items set item_json=? where rollout_ordinal=2',(p.canon(dict(type='commandExecution',exitCode=1,aggregatedOutput='Failure')),));self.items.commit()
        before=self.db_hash()
        with self.assertRaises(ValueError):p.commit(self.store,self.history,draft)
        self.assertEqual(before,self.db_hash())

    def test_competing_review_cannot_overwrite_newer_judgments(self):
        p.commit(self.store,self.history,self.payload())
        first=p.prepare(self.store,self.history,'human')['draft'];second=copy.deepcopy(first)
        first['episodes'][0]['summary']='First independent reviewed interpretation of the task.'
        second['episodes'][0]['summary']='Second stale reviewer must not overwrite the prior review.'
        p.commit(self.store,self.history,first)
        with self.assertRaises(ValueError):p.commit(self.store,self.history,second)
        self.assertEqual(self.store.review('human')['episodes'][0]['summary'],first['episodes'][0]['summary'])

    def test_assistant_only_actions_cannot_be_user_applied(self):
        draft=self.payload();draft['episodes'][0]['traits']['T01']['evidence_refs']=['A001']
        with self.assertRaises(ValueError):p.commit(self.store,self.history,draft)

    def test_assistant_success_claim_cannot_verify_outcome(self):
        draft=self.payload();draft['episodes'][0]['traits']['T01'].update(verified_outcome=True,outcome_refs=['A001'])
        with self.assertRaises(ValueError):p.commit(self.store,self.history,draft)

    def test_below_threshold_counts_survive_and_declines_do_not_reduce_rate(self):
        for n,state in enumerate(['applied','applied','declined']):
            sid='example'+str(n);self.add_session(sid)
            self.add(sid,1,'userMessage','A synthetic task with a recorded deliberate choice.','task')
            draft=self.payload(sid)
            draft['episodes'][0]['traits']['T01']['state']=state
            p.commit(self.store,self.history,draft)
            counts=p.aggregate(self.store.all_reviews())['traits']['T01']
            self.assertEqual(counts['eligible'],n+1)
        self.assertEqual(counts['measurement_status'],'measured');self.assertEqual(counts['rate'],1.0)

    def test_automatic_guardians_are_never_pending(self):
        self.add_session('guardian','{"subagent":{"other":"guardian"}}')
        self.add('guardian',1,'userMessage','Evaluate synthetic shell approval.','review')
        result=p.scan(self.store,self.history)
        self.assertNotIn('guardian',[x['session_id'] for x in result['pending']])
        with self.assertRaises(ValueError):p.prepare(self.store,self.history,'guardian')

    def test_mixed_tracker_and_real_task_is_not_hidden(self):
        self.add_session('mixed')
        self.add('mixed',1,'userMessage','Use $codex-progress to update; also repair the synthetic counter.','mixed')
        source=self.history.source('mixed')
        self.assertFalse(source['events'][0]['administrative'])
        self.assertIn('mixed',[x['session_id'] for x in p.scan(self.store,self.history)['pending']])

    def test_natural_farewell_update_does_not_reopen_its_own_work(self):
        text='We completed a coding task, good night. Update my private progress; tomorrow review this conversation with references.'
        self.add('human',4,'userMessage',text,'farewell')
        p.commit(self.store,self.history,self.payload())
        self.add('human',5,'commandExecution','Private progress was updated.','farewell')
        self.add('human',6,'agentMessage','Your progress was saved. Good night.','farewell')
        self.assertEqual(p.scan(self.store,self.history)['pending'],[])

    def test_coaching_helpers_do_not_mutate_tracker(self):
        p.commit(self.store,self.history,self.payload());before=self.db_hash()
        readonly=p.Store(self.store.root)
        p.packet(self.history.source('human'),before=3)
        readonly.review('human');readonly.db.close()
        self.assertEqual(before,self.db_hash())

    def test_baseline_mtime_cannot_swallow_unreviewed_task(self):
        baseline=self.root/'baseline';baseline.mkdir()
        (baseline/'assessment-record.json').write_text(p.canon(self.baseline_record(1)))
        names=[t['id'] for t in p.rubric()['traits']];indicators=[i for t in p.rubric()['traits'] for i in t['indicators']]
        annotation=lambda:dict(applied=[],declined=[],missed=[],verified_outcome=[])
        ledger=dict(episodes=[dict(id='E1',session_id='human',user_evidence_ordinals=[1],ordinal_first=1,ordinal_end_exclusive=4,end_ms=1793000003000,start_ms=1793000001000,work_class='bug-fix',label='An already reviewed synthetic repair.')],trait_annotations={k:annotation() for k in names},indicator_annotations={k:annotation() for k in indicators})
        (baseline/'evidence-ledger.json').write_text(p.canon(ledger))
        self.add('human',4,'userMessage','Add a separate synthetic export feature.','later')
        os.utime(baseline/'assessment-record.json',(1793100000,1793100000))
        destination=self.root/'import'
        p.initialize(destination,baseline,self.history,[]);imported=p.Store(destination)
        self.assertEqual(imported.review('human')['reviewed_through_ordinal'],3)
        self.assertIn('human',[x['session_id'] for x in p.scan(imported,self.history)['pending']])
        imported.db.close()

    def test_plain_thanks_is_not_an_automatic_closing_trigger(self):
        self.assertFalse(p.closing('Thanks. Can you also fix the last error?'))
        self.assertFalse(p.admin_message('Thanks'))
        self.assertTrue(p.admin_message('Dobranoc!'))

    def test_derived_prose_rejects_private_identifiers(self):
        draft=self.payload();draft['episodes'][0]['summary']='Read the private file C:\\private\\client.json before changing it.'
        with self.assertRaises(ValueError):p.commit(self.store,self.history,draft)
        self.assertIsNone(self.store.review('human'))

    def test_weekly_counts_and_cohort_filter_do_not_mix_course_and_general(self):
        draft=self.payload();draft['episodes'][0]['cohort']='mega-dev'
        p.commit(self.store,self.history,draft)
        course=p.aggregate(self.store.all_reviews(),'course');general=p.aggregate(self.store.all_reviews(),'general')
        self.assertEqual(course['episodes'],1);self.assertEqual(general['episodes'],0)
        week=next(iter(course['weekly_traits'].values()))
        self.assertEqual(week['T01']['applied'],1);self.assertEqual(week['T01']['measurement_status'],'unmeasured')


if __name__=='__main__':
    unittest.main()
