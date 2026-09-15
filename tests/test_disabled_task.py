import unittest
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.task_manager import TaskManager

class TestDisabledTask(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.tm = TaskManager(data_dir=self.temp_dir)
        if not self.tm.pages:
            self.tm.add_page("Default Page")
        self.page_id = self.tm.pages[0]['id']

    def test_deselect_all_days_disables_task(self):
        # Add a task with all days selected
        task = self.tm.add_task(
            name="Test Day Deselect",
            start_time="08:00",
            end_time="20:00",
            repeat_days=[0, 1, 2, 3, 4, 5, 6],
            page_id=self.page_id
        )
        task_id = task['id']
        self.assertNotEqual(task['status'], 'disabled')

        # Update task details to unselect all days (empty list)
        self.tm.update_task_details(task_id=task_id, name=task['name'], start_time=task['start_time'], end_time=task['end_time'], repeat_days=[])
        updated_task = self.tm.get_task_by_id(task_id)

        # Verify repeat_days is empty list and NOT reset to all 7 days
        self.assertEqual(updated_task['repeat_days'], [])

        # Verify check_state_consistency assigns 'disabled' status
        status, changed = self.tm.check_state_consistency(updated_task)
        self.assertEqual(status, 'disabled')
        self.assertEqual(updated_task['status'], 'disabled')

if __name__ == '__main__':
    unittest.main()
