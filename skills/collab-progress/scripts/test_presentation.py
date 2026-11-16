"""Snapshot arithmetic, archive integrity and local-viewer regressions with synthetic data."""
import copy
import hashlib
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import progress as tracker
import progress_present as view


def counts(applied=3, eligible=4, declined=0):
    denominator = eligible - declined
    return dict(eligible=eligible, applied=applied, declined=declined,
                missed=eligible-applied-declined, verified_outcome=min(applied, 1), unobserved=0,
                measurement_status='measured' if eligible >= 3 else 'unmeasured',
                rate=applied/denominator if eligible >= 3 and denominator else None)


def views():
    rule = tracker.rubric()['traits']
    aggregate = dict(episodes=4, sessions=1, distinct_active_days=1, window_days=1,
                     first_date='2026-10-01', last_date='2026-10-01',
                     traits={t['id']: counts() for t in rule},
                     indicators={i: counts() for t in rule for i in t['indicators']},
                     weekly={'2026-09-28': 4}, weekly_traits={'2026-09-28': {t['id']: counts() for t in rule}},
                     languages={}, work_mix={})
    return {scope: dict(cohort=scope, generated_at='2026-10-01T12:00:00+00:00',
                        baseline=dict(traits=[dict(trait_id=t['id'], counts=counts()) for t in rule]),
                        cumulative=copy.deepcopy(aggregate), since_baseline=copy.deepcopy(aggregate),
                        recent_10=copy.deepcopy(aggregate), previous_10=copy.deepcopy(aggregate))
            for scope in view.SCOPES}


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rate_arrows_use_percentage_points_and_exclude_declines(self):
        self.assertEqual(view.movement(counts(4, 5), counts(3, 5))['delta_pp'], 20)
        self.assertEqual(view.movement(counts(2, 5), counts(3, 5))['direction'], 'down')
        self.assertEqual(view.usable_rate(counts(3, 5, 2)), 1)
        self.assertEqual(view.movement(counts(6, 8), counts(3, 4))['direction'], 'flat')

    def test_unmeasured_and_zero_denominator_are_not_directional(self):
        self.assertIsNone(view.usable_rate(counts(2, 2)))
        self.assertIsNone(view.usable_rate(counts(0, 3, 3)))
        self.assertEqual(view.movement(counts(3, 3), counts(2, 2))['direction'], 'newly-measured')
        self.assertEqual(view.movement(counts(2, 2), counts(3, 3))['direction'], 'below-threshold')
        self.assertIsNone(view.movement(counts(), None)['delta_pp'])

    def test_tiny_real_rate_change_does_not_print_zero(self):
        result=view.movement(counts(9999, 10000), counts(9998, 9999))
        self.assertEqual(result['direction'], 'up')
        self.assertIn('<0.01', result['label'])

    def test_every_invocation_keeps_another_report_even_without_new_data(self):
        one=view.create_snapshot(self.root, views())
        original=Path(one['snapshot']).read_bytes()
        two=view.create_snapshot(self.root, views())
        self.assertNotEqual(one['snapshot'], two['snapshot'])
        self.assertEqual(Path(one['snapshot']).read_bytes(), original)
        self.assertEqual(len(list((self.root/'reports/history').glob('*.md'))), 2)
        saved=json.loads(Path(two['snapshot_data']).read_text(encoding='utf-8'))
        self.assertTrue(all(x['direction']=='flat' for x in saved['comparison']['all']['traits'].values()))

    def test_unchanged_runs_carry_the_last_real_change_forward(self):
        def with_t01(applied):
            v=views()
            for scope in v.values():scope['cumulative']['traits']['T01']=counts(applied, 4)
            return v
        first=view.create_snapshot(self.root, with_t01(4))
        dropped=view.create_snapshot(self.root, with_t01(3))
        again=view.create_snapshot(self.root, with_t01(3))
        third=view.create_snapshot(self.root, with_t01(3))
        for result in (dropped, again, third):
            saved=json.loads(Path(result['snapshot_data']).read_text(encoding='utf-8'))
            self.assertEqual(saved['comparison']['all']['traits']['T01']['direction'],'down')
            self.assertEqual(saved['compared_with']['all']['id'],first['snapshot_id'])
        self.assertEqual(saved['previous_id'],again['snapshot_id'])
        self.assertIn('Compared with: '+first['snapshot_id'],Path(third['snapshot']).read_text(encoding='utf-8'))

    def test_previous_alias_is_preserved_as_a_labelled_import(self):
        reports=self.root/'reports';reports.mkdir()
        (reports/'latest.json').write_text(json.dumps(views()['all']))
        (reports/'latest.md').write_text('Actual earlier saved status.\n')
        result=view.create_snapshot(self.root, views())
        history=view.load_snapshots(reports/'history')
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['origin'], 'previous-saved-report')
        self.assertEqual((reports/'history'/(history[0]['id']+'.md')).read_text(encoding='utf-8'), 'Actual earlier saved status.\n')
        self.assertEqual(history[1]['origin'], 'skill-run')

    def test_same_cohort_and_indicators_are_compared_independently(self):
        first=views();view.create_snapshot(self.root, first)
        second=views();second['all']['cumulative']['traits']['T01']=counts(4, 4)
        second['all']['cumulative']['indicators']['outcome-stated-at-opening']=counts(2, 4)
        result=view.create_snapshot(self.root, second);saved=json.loads(Path(result['snapshot_data']).read_text(encoding='utf-8'))
        self.assertEqual(saved['comparison']['all']['traits']['T01']['direction'], 'up')
        self.assertEqual(saved['comparison']['all']['indicators']['outcome-stated-at-opening']['direction'], 'down')
        self.assertEqual(saved['comparison']['course']['traits']['T01']['direction'], 'flat')
        text=Path(result['snapshot']).read_text(encoding='utf-8')
        self.assertIn('↑ +25.00 pp',text);self.assertIn('↓ -25.00 pp',text)

    def test_viewer_is_offline_and_escapes_script_terminators(self):
        rule=tracker.rubric();rule=copy.deepcopy(rule)
        rule['traits'][0]['name']='</script><img src=x onerror=alert(1)>'
        with patch.object(view,'rubric',return_value=rule):
            result=view.create_snapshot(self.root, views())
        reports=Path(result['dashboard']).parent
        page=Path(result['dashboard']).read_text(encoding='utf-8')
        self.assertIn("connect-src 'none'",page)
        # Only the two local companions are loaded; nothing remote, no statistics in the page itself.
        self.assertEqual(re.findall(r'<script src="([^"]+)"',page),['dashboard-data.js','dashboard.js'])
        self.assertNotIn('://',''.join(re.findall(r'src="([^"]+)"',page)))
        self.assertNotIn(rule['traits'][0]['name'],page)
        self.assertEqual(page,(Path(view.__file__).resolve().parents[1]/'assets'/'dashboard.html').read_text(encoding='utf-8'))
        self.assertTrue((reports/'dashboard.js').is_file())
        data_text=(reports/view.DATA_FILE).read_text(encoding='utf-8')
        self.assertNotIn('</script><img src=x',data_text);self.assertNotIn('<',data_text.split('window.PROGRESS_DATA = ',1)[1])
        self.assertEqual(view.load_dashboard_data(reports/view.DATA_FILE)['rubric'][0]['name'],rule['traits'][0]['name'])

    def test_snapshot_order_survives_clock_moving_back(self):
        reports=self.root/'reports';reports.mkdir()
        old=views()['all'];old['generated_at']='2099-10-01T12:00:00+00:00'
        (reports/'latest.json').write_text(json.dumps(old))
        one=view.create_snapshot(self.root, views());two=view.create_snapshot(self.root, views())
        saved=json.loads(Path(two['snapshot_data']).read_text(encoding='utf-8'))
        self.assertEqual(saved['previous_id'],one['snapshot_id'])

    def test_dashboard_rebuild_does_not_create_an_invocation(self):
        view.create_snapshot(self.root, views());history=self.root/'reports/history'
        before={p.name:p.read_bytes() for p in history.glob('*.md')}
        view.refresh_viewer(self.root)
        self.assertEqual(before,{p.name:p.read_bytes() for p in history.glob('*.md')})

    def test_missing_markdown_companion_is_recoverable(self):
        result=view.create_snapshot(self.root, views());Path(result['snapshot']).unlink()
        view.refresh_viewer(self.root)
        self.assertTrue(Path(result['snapshot']).is_file())

    def test_active_lock_does_not_overwrite_reports(self):
        result=view.create_snapshot(self.root, views());before=Path(result['snapshot']).read_bytes()
        lock=self.root/'reports/.snapshot.lock';lock.write_text('occupied')
        with patch.object(view.time,'monotonic',side_effect=[0,11]):
            with self.assertRaises(ValueError):view.create_snapshot(self.root, views())
        self.assertEqual(Path(result['snapshot']).read_bytes(),before)

    def test_snapshot_does_not_write_scoring_database(self):
        from test_progress_claude import TrackerTests
        fixture=TrackerTests();fixture.setUp()
        try:
            tracker.commit(fixture.store, fixture.history, fixture.payload())
            db=fixture.store.root/'progress.sqlite';before=hashlib.sha256(db.read_bytes()).digest()
            count=fixture.store.db.execute('select count(*) from snapshots').fetchone()[0]
            payload={scope:tracker.dashboard(fixture.store,scope) for scope in view.SCOPES}
            view.create_snapshot(fixture.store.root,payload)
            self.assertEqual(before,hashlib.sha256(db.read_bytes()).digest())
            self.assertEqual(count,fixture.store.db.execute('select count(*) from snapshots').fetchone()[0])
        finally:fixture.tearDown()

    def test_documented_report_before_first_snapshot_keeps_actual_prior_rate(self):
        from test_progress_claude import TrackerTests
        fixture=TrackerTests();fixture.setUp()
        try:
            tracker.commit(fixture.store, fixture.history, fixture.payload())
            prior=views();prior['all']['cumulative']['traits']['T01']=counts(3,3)
            reports=fixture.store.root/'reports';reports.mkdir()
            (reports/'latest.json').write_text(json.dumps(prior['all']),encoding='utf-8')
            (reports/'latest.md').write_text('The actual prior report.\n',encoding='utf-8')
            tracker.render(fixture.store)
            tracker.render(fixture.store,'course')
            payload=views();payload['all']['cumulative']['traits']['T01']=counts(3,4)
            result=view.create_snapshot(fixture.store.root,payload)
            snapshot=json.loads(Path(result['snapshot_data']).read_text(encoding='utf-8'))
            self.assertEqual(snapshot['comparison']['all']['traits']['T01']['delta_pp'],-25)
            history=view.load_snapshots(reports/'history')
            self.assertEqual((reports/'history'/(history[0]['id']+'.md')).read_text(encoding='utf-8'),'The actual prior report.\n')
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
