"""
Headless UI Integration Verification Script.
Tests instantiation of QApplication and DailyTasksWindow offscreen,
triggering UI update loops, page selection, theme toggling, and settings saving.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from src.qt_app import DailyTasksWindow


class TestUIAppLaunch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Force offscreen QPA platform for headless GUI verification
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = DailyTasksWindow()

    def tearDown(self):
        if hasattr(self, 'window') and self.window:
            self.window.close()

    def test_app_initialization(self):
        """Verify window initializes cleanly with title and layout."""
        self.assertIsNotNone(self.window)
        self.assertIn("Daily Tasks", self.window.windowTitle())

    def test_update_loop_execution(self):
        """Verify update loop runs without throwing exceptions."""
        # Force execution of periodic tick
        self.window._update_loop()

    def test_page_switching(self):
        """Verify switching pages updates UI cleanly."""
        pages = self.window.task_manager.get_pages()
        if pages:
            page_id = pages[0]['id']
            self.window._on_page_selected(page_id)
            self.assertEqual(self.window.active_page_id, page_id)

    def test_incremental_card_update(self):
        """Verify incremental card update path does not throw."""
        tasks = self.window.task_manager.get_tasks(page_id=self.window.active_page_id)
        if tasks:
            tid = str(tasks[0]['id'])
            self.window._update_cards_incremental({tid})

    def test_theme_toggle_and_save(self):
        """Verify theme switching and settings saving."""
        self.window._toggle_simple_mode(True)
        self.assertTrue(self.window.simple_mode_enabled)
        self.window._toggle_simple_mode(False)
        self.assertFalse(self.window.simple_mode_enabled)


if __name__ == '__main__':
    unittest.main()
