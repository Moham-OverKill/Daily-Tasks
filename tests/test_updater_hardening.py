"""
Automated Regression Test Suite for In-App Updater Resilience & Hardening.
Tests rate-limit bypass, web redirect fallback, silent check non-interference,
watchdog timeout recovery, and SettingsPanel browser escape hatch.
"""

import sys
import os
import unittest
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from src.constants import APP_VERSION, GITHUB_RELEASES_PAGE_URL
from src.updater import (
    UpdateManager,
    is_newer_version,
    parse_version,
    _check_github_latest_web,
)
import src.updater as updater_mod
from src.qt_components import SettingsPanel


class TestUpdaterHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_version_parsing_and_comparison(self):
        self.assertEqual(parse_version("1.5.0"), (1, 5, 0))
        self.assertEqual(parse_version("v1.5.1"), (1, 5, 1))
        self.assertEqual(parse_version("v2.0.0-beta.1"), (2, 0, 0))
        self.assertTrue(is_newer_version("1.5.1", "1.5.0"))
        self.assertFalse(is_newer_version("1.5.0", "1.5.0"))
        self.assertFalse(is_newer_version("1.4.9", "1.5.0"))

    def test_web_redirect_fallback(self):
        res = _check_github_latest_web(timeout=8)
        self.assertIsNotNone(res)
        self.assertIn("tag_name", res)
        self.assertIn("asset_url", res)
        self.assertIn("html_url", res)

    def test_rate_limit_fallback_in_update_manager(self):
        mgr = UpdateManager()
        results = []
        mgr.up_to_date.connect(lambda v: results.append(("up_to_date", v)))
        mgr.update_available.connect(lambda v, u, h: results.append(("update_available", v, u, h)))
        mgr.check_failed.connect(lambda err: results.append(("check_failed", err)))

        orig_http = updater_mod._http_get_json
        try:
            # Simulate GitHub 403 Rate Limit (returns None)
            updater_mod._http_get_json = lambda *a, **kw: None
            mgr.check_for_updates(silent=False)

            start = time.time()
            while not results and time.time() - start < 10:
                self.app.processEvents()
                time.sleep(0.05)

            self.assertTrue(len(results) > 0, "Signal must be emitted via web fallback")
            self.assertIn(results[0][0], ("up_to_date", "update_available"))
        finally:
            updater_mod._http_get_json = orig_http

    def test_silent_check_non_interference(self):
        mgr = UpdateManager()
        started = []
        mgr.check_started.connect(lambda: started.append(True))

        mgr.check_for_updates(silent=True)
        self.assertEqual(len(started), 0, "Silent checks must NOT emit check_started")

    def test_watchdog_timeout_recovery(self):
        mgr = UpdateManager()
        results = []
        mgr.check_failed.connect(lambda err: results.append(("check_failed", err)))
        mgr.up_to_date.connect(lambda v: results.append(("up_to_date", v)))

        orig_http = updater_mod._http_get_json
        orig_web = updater_mod._check_github_latest_web
        try:
            updater_mod._http_get_json = lambda *a, **kw: time.sleep(10)
            updater_mod._check_github_latest_web = lambda *a, **kw: time.sleep(10)

            mgr.check_for_updates(silent=False)
            mgr._watchdog_timer.start(500)  # 500ms for fast test

            start = time.time()
            while not results and time.time() - start < 5:
                self.app.processEvents()
                time.sleep(0.05)

            self.assertTrue(len(results) > 0)
            self.assertEqual(results[0][0], "check_failed")
            self.assertIn("timed out", results[0][1])
            self.assertFalse(mgr._checking)
        finally:
            updater_mod._http_get_json = orig_http
            updater_mod._check_github_latest_web = orig_web

    def test_settings_panel_browser_escape_hatch(self):
        panel = SettingsPanel(None)
        self.assertTrue(panel.update_action_btn.isEnabled())

        panel.set_update_state("error", message="Connection error")
        self.assertTrue(panel.update_action_btn.isEnabled())
        self.assertEqual(panel.update_action_btn.text(), "Retry")
        self.assertIn("Download in browser", panel.update_status_label.text())
        self.assertTrue(panel.update_status_label.openExternalLinks())

        panel.set_update_state("up_to_date")
        self.assertTrue(panel.update_action_btn.isEnabled())
        self.assertEqual(panel.update_action_btn.text(), "Check for Updates")
        self.assertFalse(panel.update_status_label.openExternalLinks())


if __name__ == "__main__":
    unittest.main()
