"""Maintenance-turn detection shared by every harness."""
import unittest
import progress_core as c


class AdminMessageTests(unittest.TestCase):
    def test_codex_skill_link_is_maintenance(self):
        self.assertTrue(c.admin_message(r'[$codex-progress](C:\Users\u\.agents\skills\codex-progress\SKILL.md)'))
        self.assertTrue(c.admin_message('[$collab-coach](/home/u/.agents/skills/collab-coach/SKILL.md)'))

    def test_skill_link_with_real_work_stays_visible(self):
        self.assertFalse(c.admin_message(r'[$collab-progress](C:\x\SKILL.md) and also repair the counter'))

    def test_other_links_are_not_rewritten(self):
        self.assertFalse(c.admin_message('see [docs](README.md)'))

    def test_claude_slash_command_is_maintenance(self):
        self.assertTrue(c.admin_message('/collab-progress'))

    def test_tracking_needs_a_progress_word(self):
        self.assertFalse(c.admin_message('show me the latest report'))
        self.assertTrue(c.admin_message('show my latest progress report'))


class TimezoneTests(unittest.TestCase):
    MS = 1793100000000

    def setUp(self):
        self.saved = c.os.environ.pop('COLLAB_PROGRESS_TZ', None)
        self.addCleanup(lambda: c.os.environ.update({'COLLAB_PROGRESS_TZ': self.saved}) if self.saved else c.os.environ.pop('COLLAB_PROGRESS_TZ', None))

    def test_no_hardcoded_zone_unknown_falls_back_to_local(self):
        c.os.environ['COLLAB_PROGRESS_TZ'] = 'Not/AZone'
        local = c.dt.datetime.fromtimestamp(self.MS / 1000, c.dt.timezone.utc).astimezone().date()
        self.assertIsNone(c.timezone_name())
        self.assertEqual(c.timezone_label(), 'local time')
        self.assertEqual(c.local_date(self.MS), local)

    def test_named_zone_is_used_when_available(self):
        if c._zone('Pacific/Kiritimati') is None:
            self.skipTest('no IANA tz database (install tzdata)')
        c.os.environ['COLLAB_PROGRESS_TZ'] = 'Pacific/Kiritimati'  # UTC+14
        self.assertEqual(str(c.local_date(1793145600000)), '2026-10-28')  # 2026-10-27 22:40 UTC


if __name__ == '__main__':
    unittest.main()
