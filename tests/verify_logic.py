"""
BUG-11 FIX: Rewritten against the current pages-based TaskManager API.
The old tests used self.mgr.tasks = [] (removed flat list) and DATA_FILE
(removed module-level constant).  This version uses add_page / add_task /
get_tasks(page_id=...) and a temporary file path for isolation.
"""

import sys
import os
import json
import shutil
import tempfile
from datetime import datetime
import unittest

# Run from project root: python tests/verify_logic.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.task_manager import TaskManager


def _make_manager(tmp_dir):
    """Create a fresh, isolated TaskManager backed by a temp file."""
    mgr = TaskManager(data_dir=tmp_dir)
    return mgr


class TestDailyTasksLogic(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='dt_tests_')
        self.mgr = _make_manager(self.tmp_dir)

        # Create a default page to work with
        self.page = self.mgr.add_page("Test Page")
        self.page_id = self.page['id']

    def tearDown(self):
        if hasattr(self, 'mgr') and hasattr(self.mgr, '_save_queue'):
            self.mgr._save_queue.join()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ─────────────────────────────────────────────────────────────────────
    # Prayer time logic
    # ─────────────────────────────────────────────────────────────────────

    def test_prayer_time_logic_fajr(self):
        """Verify Fajr ends at Sunrise, not at Dhuhr, after sync."""
        mock_prayers = {
            'Fajr': '05:00',
            'Sunrise': '06:30',
            'Dhuhr': '12:00',
            'Asr': '15:00',
            'Maghrib': '17:30',
            'Isha': '19:00',
        }

        # Patch the handler so no real network call is made
        self.mgr.prayer_handler.get_prayer_times = lambda: mock_prayers

        success = self.mgr.sync_prayer_times()
        self.assertTrue(success, "sync_prayer_times should return True with mocked data")

        # Keys are 'global_Fajr', 'global_Dhuhr', etc. (preserves name case)
        fajr = self.mgr.global_prayers.get('global_Fajr')
        self.assertIsNotNone(fajr, "global_Fajr should exist after sync")
        self.assertEqual(fajr['end_time'], '06:30',
                         f"Fajr should end at Sunrise (06:30), got {fajr.get('end_time')}")

        # Dhuhr ends at Asr (next prayer)
        dhuhr = self.mgr.global_prayers.get('global_Dhuhr')
        self.assertIsNotNone(dhuhr, "global_Dhuhr should exist after sync")
        self.assertEqual(dhuhr['end_time'], '15:00',
                         f"Dhuhr should end at Asr (15:00), got {dhuhr.get('end_time')}")

    def test_prayer_toggle_cleanup(self):
        """Verify remove_synced_tasks removes all synced/global prayer tasks."""
        mock_prayers = {'Fajr': '05:00', 'Sunrise': '06:30',
                        'Dhuhr': '12:00', 'Asr': '15:00',
                        'Maghrib': '17:30', 'Isha': '19:00'}
        self.mgr.prayer_handler.get_prayer_times = lambda: mock_prayers
        self.mgr.sync_prayer_times()

        # Prayers should be visible
        all_tasks = self.mgr.get_tasks(page_id=self.page_id)
        prayers_before = [t for t in all_tasks if t.get('is_synced')]
        self.assertGreater(len(prayers_before), 0, "Prayers should exist after sync")

        # Remove them
        self.mgr.remove_synced_tasks()

        # remove_synced_tasks sets enabled=False (keeps in global_prayers, hides from UI)
        for prayer in self.mgr.global_prayers.values():
            self.assertFalse(prayer.get('enabled'),
                             f"Prayer '{prayer.get('name')}' should be disabled after remove_synced_tasks")

    # ─────────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────────

    def test_add_task_persists(self):
        """Verify add_task writes to disk and reloads correctly."""
        self.mgr.add_task("Test Task", "10:00", "11:00", page_id=self.page_id)
        self.mgr._save_queue.join()

        # Reload from the same directory
        mgr2 = _make_manager(self.tmp_dir)
        tasks = mgr2.get_tasks(page_id=self.page_id)
        # Filter out prayers
        custom = [t for t in tasks if not t.get('is_synced')]
        self.assertEqual(len(custom), 1, "Should have exactly 1 custom task after reload")
        self.assertEqual(custom[0]['name'], "Test Task")

    def test_get_task_by_id(self):
        """Verify get_task_by_id returns the correct task dict."""
        self.mgr.add_task("Alpha", "08:00", "09:00", page_id=self.page_id)
        self.mgr.add_task("Beta",  "10:00", "11:00", page_id=self.page_id)

        tasks = self.mgr.get_tasks(page_id=self.page_id)
        custom = [t for t in tasks if not t.get('is_synced')]
        target = custom[0]

        found = self.mgr.get_task_by_id(target['id'])
        self.assertIsNotNone(found)
        self.assertEqual(found['id'], target['id'])

    # ─────────────────────────────────────────────────────────────────────
    # Status synchronization — new return type (BUG-OPT-01)
    # ─────────────────────────────────────────────────────────────────────

    def test_synchronize_returns_tuple(self):
        """synchronize_task_statuses must return (bool, list) after OPT-01 fix."""
        result = self.mgr.synchronize_task_statuses()
        self.assertIsInstance(result, tuple, "Should return a tuple")
        self.assertEqual(len(result), 2, "Tuple should have 2 elements")
        modified, changes = result
        self.assertIsInstance(modified, bool)
        self.assertIsInstance(changes, list)

    # ─────────────────────────────────────────────────────────────────────
    # check_daily_reset (BUG-17)
    # ─────────────────────────────────────────────────────────────────────

    def test_check_daily_reset_delegates(self):
        """check_daily_reset() must delegate to reset_daily_tasks (BUG-17 fix)."""
        self.mgr.add_task("Morning", "06:00", "07:00", page_id=self.page_id)
        # Mark task as done with completed_at set to YESTERDAY so reset_daily_tasks
        # will not skip it (it only skips tasks completed TODAY)
        tasks = self.mgr.get_tasks(page_id=self.page_id)
        custom = [t for t in tasks if not t.get('is_synced')]
        if custom:
            t = custom[0]
            t['status'] = 'done'
            t['completed_at'] = '2000-01-01T00:00:00'  # past date guarantees reset
            self.mgr.save_tasks()

        # call check_daily_reset — should reset to pending
        self.mgr.check_daily_reset()

        tasks_after = self.mgr.get_tasks(page_id=self.page_id)
        custom_after = [t for t in tasks_after if not t.get('is_synced')]
        for t in custom_after:
            self.assertNotEqual(t.get('status'), 'done',
                                "Tasks completed on a past day should be reset to pending")


if __name__ == '__main__':
    unittest.main()
