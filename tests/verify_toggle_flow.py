"""
BUG-11 FIX: Rewritten against the current pages-based TaskManager API.
Old version used self.mgr.tasks = [] (removed flat list) and
DATA_FILE (removed module-level constant).  This version uses add_page /
add_task / get_tasks(page_id=...) and a temporary directory for isolation.
"""

import sys
import os
import unittest
import shutil
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.task_manager import TaskManager


def _make_manager(tmp_dir):
    return TaskManager(data_dir=tmp_dir)


class TestToggleFlow(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='dt_toggle_')
        self.mgr = _make_manager(self.tmp_dir)

        # Create a default page
        self.page = self.mgr.add_page("Test Page")
        self.page_id = self.page['id']

    def tearDown(self):
        if hasattr(self, 'mgr') and hasattr(self.mgr, '_save_queue'):
            self.mgr._save_queue.join()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_disable_enable_flow(self):
        """Full prayer toggle: sync → disable → re-sync → verify re-enabled."""

        # 1. Sync prayer tasks (mocked)
        mock_times = {'Fajr': '05:00', 'Sunrise': '06:30',
                      'Dhuhr': '12:00', 'Asr': '15:00',
                      'Maghrib': '17:30', 'Isha': '19:00'}
        self.mgr.prayer_handler.get_prayer_times = lambda: mock_times

        success = self.mgr.sync_prayer_times()
        self.assertTrue(success, "sync_prayer_times should succeed with mocked data")

        # Verify prayers are visible
        all_tasks = self.mgr.get_tasks(page_id=self.page_id)
        # Disable (remove synced tasks)
        self.mgr.remove_synced_tasks()

        # remove_synced_tasks sets enabled=False (keeps entries, hides from UI via get_tasks filter)
        for prayer in self.mgr.global_prayers.values():
            self.assertFalse(prayer.get('enabled'),
                             f"Prayer '{prayer.get('name')}' should be disabled")

        # get_tasks_for_monitoring should no longer include them
        monitoring = self.mgr.get_tasks_for_monitoring()
        prayer_tasks = [t for t in monitoring if t.get('is_synced')]
        self.assertEqual(len(prayer_tasks), 0, "Disabled prayers should not appear in monitoring")

        # 3. Re-sync to re-enable
        self.mgr.prayer_handler.get_prayer_times = lambda: mock_times
        success2 = self.mgr.sync_prayer_times()
        self.assertTrue(success2)

        # 4. Prayers should be visible again
        tasks_after = self.mgr.get_tasks(page_id=self.page_id)
        prayers_after = [t for t in tasks_after if t.get('is_synced')]
        self.assertGreater(len(prayers_after), 0,
                           "Prayers should reappear after second sync")

    def test_custom_tasks_survive_prayer_toggle(self):
        """Custom tasks should not be removed when prayer sync is disabled."""
        self.mgr.add_task("My Routine", "09:00", "10:00", page_id=self.page_id)

        mock_times = {'Fajr': '05:00', 'Sunrise': '06:30'}
        self.mgr.prayer_handler.get_prayer_times = lambda: mock_times
        self.mgr.sync_prayer_times()

        # Disable prayers
        self.mgr.remove_synced_tasks()

        # Custom task should still exist
        tasks = self.mgr.get_tasks(page_id=self.page_id)
        custom = [t for t in tasks if not t.get('is_synced')]
        self.assertEqual(len(custom), 1, "Custom task should survive prayer toggle")
        self.assertEqual(custom[0]['name'], "My Routine")

    def test_status_update_and_retrieve(self):
        """update_task_status + get_task_by_id should reflect new status."""
        self.mgr.add_task("Work Block", "09:00", "10:00", page_id=self.page_id)
        tasks = self.mgr.get_tasks(page_id=self.page_id)
        custom = [t for t in tasks if not t.get('is_synced')]
        self.assertEqual(len(custom), 1)

        tid = custom[0]['id']
        self.mgr.update_task_status(tid, 'done')

        task = self.mgr.get_task_by_id(tid)
        self.assertIsNotNone(task)
        self.assertEqual(task['status'], 'done', "Status should be 'done' after update")


if __name__ == '__main__':
    unittest.main()
