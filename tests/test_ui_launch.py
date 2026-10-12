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
        # Force offscreen QPA platform and isolated temp APPDATA for headless GUI verification
        import tempfile
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls._orig_appdata = os.environ.get("APPDATA")
        cls._temp_appdata = tempfile.mkdtemp(prefix="dailytasks_test_")
        os.environ["APPDATA"] = cls._temp_appdata
        import src.task_manager as tm_mod
        cls._orig_data_file = tm_mod.DATA_FILE
        tm_mod.DATA_FILE = tm_mod.get_data_file_path()
        cls.app = QApplication.instance() or QApplication(sys.argv)

    @classmethod
    def tearDownClass(cls):
        import shutil
        import time
        import src.task_manager as tm_mod
        time.sleep(0.05)
        tm_mod.DATA_FILE = cls._orig_data_file
        if cls._orig_appdata is not None:
            os.environ["APPDATA"] = cls._orig_appdata
        shutil.rmtree(cls._temp_appdata, ignore_errors=True)

    def setUp(self):
        self.window = DailyTasksWindow()

    def tearDown(self):
        if hasattr(self, 'window') and self.window:
            if hasattr(self.window, 'update_timer') and self.window.update_timer is not None:
                self.window.update_timer.stop()
            if hasattr(self.window, 'particles') and self.window.particles is not None:
                self.window.particles.stop()
            if hasattr(self.window, 'sound_manager') and self.window.sound_manager is not None:
                self.window.sound_manager.close()
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
        """Verify theme dropdown menu, all 10 theme presets, hover item delegate, and settings saving."""
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QPixmap, QPainter
        from PySide6.QtWidgets import QStyle, QStyleOptionViewItem
        from src.qt_components import THEME_OPTIONS, get_theme_spec

        self.window._toggle_simple_mode(True)
        self.assertTrue(self.window.simple_mode_enabled)
        self.window._toggle_simple_mode(False)
        self.assertFalse(self.window.simple_mode_enabled)

        panel = self.window.settings_panel
        self.assertIsNotNone(panel.theme_combo)
        self.assertEqual(panel.theme_combo.count(), len(THEME_OPTIONS))

        delegate = panel.theme_combo.itemDelegate()
        model = panel.theme_combo.model()

        # Verify all 10 themes can be selected via dropdown and applied cleanly
        for idx, (theme_id, label) in enumerate(THEME_OPTIONS):
            self.assertEqual(panel.theme_combo.itemData(idx), theme_id)
            self.assertEqual(panel.theme_combo.itemText(idx), label)
            panel.theme_combo.setCurrentIndex(idx)
            self.assertEqual(self.window.current_theme, theme_id)
            self.assertEqual(self.window.particles.theme, theme_id)
            spec = get_theme_spec(theme_id)
            self.assertIn(spec['title_fg'], self.window.title_bar.title_label.styleSheet())
            panel.theme_combo.grab()

            # Verify dropdown item delegate paints both normal and hovered items cleanly
            pix = QPixmap(260, 34)
            painter = QPainter(pix)
            opt = QStyleOptionViewItem()
            opt.rect = QRect(0, 0, 260, 34)
            opt.state = QStyle.State_Enabled | QStyle.State_MouseOver | QStyle.State_Selected
            delegate.paint(painter, opt, model.index(0, 0))
            opt.state = QStyle.State_Enabled
            delegate.paint(painter, opt, model.index(idx, 0))
            painter.end()

            # Trigger particle burst & render pass to verify palette integrity
            self.window.particles.burst_confetti(120, 120, count=5)
            self.window.grab()

    def test_audio_feedback_system(self):
        """Verify hover, click, and typing audio cues, memory caching, latency, and settings control."""
        import time
        from PySide6.QtCore import Qt, QEvent, QPointF
        from PySide6.QtGui import QEnterEvent, QMouseEvent, QKeyEvent
        from PySide6.QtWidgets import QLineEdit

        sm = self.window.sound_manager
        # Wait briefly for background daemon preload if still running
        deadline = time.perf_counter() + 1.0
        while not sm._cache_ready and time.perf_counter() < deadline:
            time.sleep(0.01)

        self.assertTrue(sm._cache_ready)
        for key in ('hover.wav', 'click.wav', 'type_1.wav', 'type_2.wav', 'type_3.wav', 'type_space.wav', 'undo.wav'):
            self.assertIn(key, sm._raw_pcm.keys())
            self.assertIn(key, sm._scaled_pcm.keys())
            self.assertGreater(len(sm._scaled_pcm[key]), 1000)

        # Ensure start.wav (new task / new day chime) and done.wav exist and are distinct audio files
        start_wav_path = os.path.join(sm.sounds_dir, 'start.wav')
        done_wav_path = os.path.join(sm.sounds_dir, 'done.wav')
        self.assertTrue(os.path.exists(start_wav_path))
        self.assertTrue(os.path.exists(done_wav_path))
        with open(start_wav_path, 'rb') as f_start, open(done_wav_path, 'rb') as f_done:
            self.assertNotEqual(f_start.read(), f_done.read())

        # Verify sub-millisecond non-blocking UI call latency
        t0 = time.perf_counter()
        sm.play_hover(widget_id=101)
        sm.play_click()
        sm.play_type(Qt.Key_A)
        sm.play_type(Qt.Key_Space)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(elapsed_ms, 5.0)

        # Verify independent UI sound settings (mute and volume) and SettingsPanel order
        panel = self.window.settings_panel
        self.assertIsNotNone(panel.ui_sounds_checkbox)
        self.assertIsNotNone(panel.ui_vol_slider)
        self.assertIsNotNone(panel.hide_non_today_checkbox)

        # Verify SettingsPanel visual hierarchy order from top to bottom
        vbox = panel.layout()
        ordered_widgets = [vbox.itemAt(i).widget() for i in range(vbox.count()) if vbox.itemAt(i).widget() is not None]
        expected_sequence = [
            panel.theme_combo,
            panel.simple_checkbox,
            panel.hide_non_today_checkbox,
            panel.sep,
            panel.hardcore_checkbox,
            panel.prayer_checkbox,
            panel.sep_audio,
            panel.dnd_checkbox,
            panel.ui_sounds_checkbox,
            panel.ui_vol_container,
            panel.sep_update,
            panel.update_container,
        ]
        indices = [ordered_widgets.index(w) for w in expected_sequence]
        self.assertEqual(indices, sorted(indices))

        # Verify "Today's Tasks Only" (hide_non_today_enabled) filtering
        from datetime import datetime
        today_wd = datetime.now().weekday()
        tomorrow_wd = (today_wd + 1) % 7
        t_today = self.window.task_manager.add_task(
            "Today Task", None, None, None, repeat_days=[today_wd], page_id=self.window.active_page_id
        )
        t_tomorrow = self.window.task_manager.add_task(
            "Tomorrow Task", None, None, None, repeat_days=[tomorrow_wd], page_id=self.window.active_page_id
        )
        try:
            self.window._toggle_hide_non_today(False)
            self.assertIn(t_today['id'], self.window.task_cards)
            self.assertIn(t_tomorrow['id'], self.window.task_cards)

            self.window._toggle_hide_non_today(True)
            self.assertIn(t_today['id'], self.window.task_cards)
            self.assertNotIn(t_tomorrow['id'], self.window.task_cards)
        finally:
            self.window._toggle_hide_non_today(False)
            self.window.task_manager.delete_task(t_today['id'])
            self.window.task_manager.delete_task(t_tomorrow['id'])
            self.window._load_tasks()

        self.window._on_ui_volume_changed(40)
        self.assertEqual(self.window.ui_volume, 40)
        self.assertAlmostEqual(sm.ui_volume, 0.40, places=2)

        # Dynamic Volume Slider Visibility Logic:
        # 1. DND=False, UI Sounds=True -> Volume slider SHOWN
        self.window._toggle_dnd(False)
        self.window._toggle_ui_sounds(True)
        self.assertFalse(panel.ui_vol_container.isHidden())
        self.assertEqual(panel.height(), panel._EXPANDED_HEIGHT)

        # 2. DND=False, UI Sounds=False -> Volume slider HIDDEN
        self.window._toggle_ui_sounds(False)
        self.assertFalse(self.window.ui_sounds_enabled)
        self.assertFalse(sm.ui_sounds_enabled)
        self.assertFalse(self.window.dnd_enabled)  # Core task alerts remain active
        self.assertTrue(panel.ui_vol_container.isHidden())
        self.assertEqual(panel.height(), panel._COLLAPSED_HEIGHT)

        # 3. DND=True, UI Sounds=True -> Volume slider HIDDEN (since DND mutes sounds)
        self.window._toggle_ui_sounds(True)
        self.assertFalse(panel.ui_vol_container.isHidden())
        self.window._toggle_dnd(True)
        self.assertTrue(panel.ui_vol_container.isHidden())
        self.assertEqual(panel.height(), panel._COLLAPSED_HEIGHT)

        # 4. Restore DND=False, UI Sounds=True -> Volume slider SHOWN
        self.window._toggle_dnd(False)
        self.assertTrue(self.window.ui_sounds_enabled)
        self.assertTrue(sm.ui_sounds_enabled)
        self.assertFalse(panel.ui_vol_container.isHidden())
        self.assertEqual(panel.height(), panel._EXPANDED_HEIGHT)

        # Verify eventFilter dispatch on button hover/press and QLineEdit typing
        btn = self.window.sidebar.settings_btn
        enter_ev = QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5))
        QApplication.sendEvent(btn, enter_ev)

        line_edit = QLineEdit()
        key_ev = QKeyEvent(QEvent.KeyPress, Qt.Key_T, Qt.NoModifier, "t")
        QApplication.sendEvent(line_edit, key_ev)

    def test_global_button_micro_interactions(self):
        """Verify global hover & click micro-animations and layout geometry stability."""
        from PySide6.QtCore import Qt, QEvent, QPointF
        from PySide6.QtGui import QEnterEvent, QMouseEvent
        from src.qt_components import AnimatedPushButton, PageButton, TaskCard

        # 1. Verify global AnimatedPushButton inheritance across header, sidebar, and settings
        for btn in (
            self.window.title_bar.min_btn,
            self.window.title_bar.max_btn,
            self.window.title_bar.close_btn,
            self.window.sidebar.settings_btn,
            self.window.sidebar._add_page_btn,
            self.window.settings_panel.close_btn,
            self.window.settings_panel.dark_btn,
            self.window.settings_panel.light_btn,
        ):
            self.assertIsInstance(btn, AnimatedPushButton)

        # Ensure initial window layout activation has completed
        self.window.grab()

        # 2. Verify AnimatedPushButton hover & press animations + geometry invariance
        btn = self.window.sidebar.settings_btn
        initial_geom = btn.geometry()
        enter_ev = QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5))
        QApplication.sendEvent(btn, enter_ev)
        self.assertIsNotNone(btn._hover_anim)
        self.assertEqual(btn._hover_anim.duration(), 145)
        btn._on_hover_step(0.65)
        btn.grab()  # Force paintEvent execution during mid-hover cross-fade
        self.assertEqual(btn.geometry(), initial_geom)

        press_ev = QMouseEvent(
            QEvent.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
        QApplication.sendEvent(btn, press_ev)
        self.assertIsNotNone(btn._press_anim)
        self.assertEqual(btn._press_anim.duration(), 70)
        btn._on_press_step(1.0)
        btn.grab()  # Force paintEvent execution during full press compression
        self.assertEqual(btn.geometry(), initial_geom)

        release_ev = QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(5, 5), QPointF(5, 5),
            Qt.LeftButton, Qt.NoButton, Qt.NoModifier
        )
        QApplication.sendEvent(btn, release_ev)
        self.assertEqual(btn._press_anim.duration(), 135)
        self.assertEqual(btn.geometry(), initial_geom)

        # 3. Verify PageButton hover & press animations + geometry invariance
        page_btns = list(self.window.sidebar._page_buttons.values())
        if page_btns:
            pbtn = page_btns[0]
            self.assertIsInstance(pbtn, PageButton)
            p_geom = pbtn.geometry()
            QApplication.sendEvent(pbtn, enter_ev)
            pbtn._on_hover_step(1.0)
            pbtn._on_press_step(0.8)
            pbtn.grab()
            self.assertEqual(pbtn.geometry(), p_geom)

        # 4. Verify TaskCard hover & press micro-animations + sizeHint/geometry invariance + 0% edge clipping
        from PySide6.QtGui import QImage, QPaintEvent
        card = TaskCard({
            'id': 'anim-test-1',
            'name': 'Micro Animation Task',
            'start_time': '00:00',
            'end_time': '23:59',
            'status': 'active',
            'repeat_days': [0, 1, 2, 3, 4, 5, 6]
        })
        card.resize(240, 250)
        c_geom = card.geometry()
        c_hint = card.sizeHint()
        card._set_hover(True)
        card._hover_t = 1.0
        card._press_t = 0.0

        # Render TaskCard at full hover into a transparent QImage and verify 0px edge clipping at boundaries
        card_img = QImage(card.width(), card.height(), QImage.Format_ARGB32_Premultiplied)
        card_img.fill(0)
        card.render(card_img)
        mid_x, mid_y = card.width() // 2, card.height() // 2
        self.assertEqual(card_img.pixel(0, mid_y) >> 24, 0)
        self.assertEqual(card_img.pixel(card.width() - 1, mid_y) >> 24, 0)
        self.assertEqual(card_img.pixel(mid_x, 0) >> 24, 0)
        self.assertEqual(card_img.pixel(mid_x, card.height() - 1) >> 24, 0)

        card._on_press_step(1.0)
        card.grab()
        self.assertEqual(card.geometry(), c_geom)
        self.assertEqual(card.sizeHint(), c_hint)
        card._on_press_step(0.0)
        card._set_hover(False)
        card.deleteLater()

        # 5. Verify both '+' buttons (Sidebar AddPageButton and Grid AddTaskCard) render seamless dashed borders with 0% edge clipping
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QRegion
        from PySide6.QtWidgets import QWidget
        from src.qt_components import AddPageButton
        add_page_btn = self.window.sidebar._add_page_btn
        self.assertIsInstance(add_page_btn, AddPageButton)
        add_page_btn.resize(212, 40)
        for ht in (0.0, 0.5, 1.0):
            add_page_btn._on_hover_step(ht)
            p_img = QImage(add_page_btn.width(), add_page_btn.height(), QImage.Format_ARGB32_Premultiplied)
            p_img.fill(0)
            add_page_btn.render(p_img, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
            self.assertEqual(p_img.pixel(0, 20) >> 24, 0)
            self.assertEqual(p_img.pixel(add_page_btn.width() - 1, 20) >> 24, 0)
            self.assertEqual(p_img.pixel(106, 0) >> 24, 0)
            self.assertEqual(p_img.pixel(106, add_page_btn.height() - 1) >> 24, 0)
        add_page_btn._on_hover_step(0.0)

        add_card = self.window._add_task_card
        self.assertIsNotNone(add_card)
        add_card.resize(240, 250)
        for ht in (0.0, 0.5, 1.0):
            add_card._hover_t = ht
            ac_img = QImage(add_card.width(), add_card.height(), QImage.Format_ARGB32_Premultiplied)
            ac_img.fill(0)
            add_card.render(ac_img, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
            self.assertEqual(ac_img.pixel(0, 125) >> 24, 0)
            self.assertEqual(ac_img.pixel(add_card.width() - 1, 125) >> 24, 0)
            self.assertEqual(ac_img.pixel(120, 0) >> 24, 0)
            self.assertEqual(ac_img.pixel(120, add_card.height() - 1) >> 24, 0)
        add_card._hover_t = 0.0

    def test_dialogs_follow_all_themes(self):
        """Verify AddTaskDialog (add, edit, icon picker) and ModernDialogs render with exact theme colors across all 10 themes."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QDialog
        from src.qt_components import AddTaskDialog, ModernDialogs, THEME_OPTIONS, get_theme_spec
        from src.constants import ICON_CATEGORIES

        sample_task = {
            'id': 'edit-test-1',
            'name': 'Theme Test Task',
            'start_time': '09:00',
            'end_time': '10:00',
            'repeat_days': [0, 1, 2, 3, 4, 5, 6],
        }

        add_dlg = AddTaskDialog(None, icon_categories=ICON_CATEGORIES, theme=self.window.current_theme)
        edit_dlg = AddTaskDialog(None, task_data=sample_task, icon_categories=ICON_CATEGORIES, theme=self.window.current_theme)
        mod_dlg = QDialog(None)
        mod_dlg.setFixedSize(320, 160)

        for theme_key, _ in THEME_OPTIONS:
            self.window._apply_theme(theme_key, save=False)
            spec = get_theme_spec(theme_key)
            expected_bg = spec["dialog_bg"].upper()
            expected_input_bg = spec["input_bg"].upper()

            # 1. AddTaskDialog (Add mode + Icon Picker view)
            add_dlg._show_form()
            add_dlg.apply_theme(theme_key)

            dlg_img = add_dlg.grab().toImage()
            actual_bg = dlg_img.pixelColor(10, 10).name().upper()
            self.assertEqual(actual_bg, expected_bg, f"AddTaskDialog bg mismatch on theme {theme_key}")

            inp_img = add_dlg.name_input.grab().toImage()
            actual_inp_bg = inp_img.pixelColor(add_dlg.name_input.width() - 15, add_dlg.name_input.height() // 2).name().upper()
            self.assertEqual(actual_inp_bg, expected_input_bg, f"AddTaskDialog input_bg mismatch on theme {theme_key}")

            add_dlg._show_icon_picker()
            picker_img = add_dlg.grab().toImage()
            self.assertEqual(picker_img.pixelColor(10, 10).name().upper(), expected_bg)

            # 2. AddTaskDialog (Edit mode)
            edit_dlg.apply_theme(theme_key)
            edit_img = edit_dlg.grab().toImage()
            self.assertEqual(edit_img.pixelColor(10, 10).name().upper(), expected_bg, f"EditTaskDialog bg mismatch on theme {theme_key}")

            # 3. ModernDialogs
            ModernDialogs._apply_style(mod_dlg, theme_key)
            mod_img = mod_dlg.grab().toImage()
            self.assertEqual(mod_img.pixelColor(10, 10).name().upper(), expected_bg, f"ModernDialogs bg mismatch on theme {theme_key}")

        add_dlg.deleteLater()
        edit_dlg.deleteLater()
        mod_dlg.deleteLater()

    def test_updater_and_settings_update_ui(self):
        """Verify semantic version comparison, lazy update state caching, Sidebar indicator, and SettingsPanel update states."""
        from src.constants import APP_VERSION
        from src.updater import parse_version, is_newer_version, UpdateManager
        from src.qt_components import THEME_OPTIONS

        # 1. Verify semantic version parsing and comparison
        self.assertEqual(APP_VERSION, "1.4.1")
        self.assertEqual(parse_version("v1.3.0"), (1, 3, 0))
        self.assertEqual(parse_version("1.2"), (1, 2, 0))
        self.assertEqual(parse_version("v2.0.1-beta"), (2, 0, 1))
        self.assertTrue(is_newer_version("1.3.1", "1.3.0"))
        self.assertTrue(is_newer_version("v1.4.0", "1.3.0"))
        self.assertTrue(is_newer_version("2.0.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.3.0", "1.3.0"))
        self.assertFalse(is_newer_version("v1.2.0", "1.3.0"))

        # 2. Verify lazy SettingsPanel state caching BEFORE panel is constructed
        self.assertIsNone(self.window._settings_panel)
        self.window._on_update_available("1.4.0", "https://example.com/DailyTasksSetup.exe", "Release notes")
        self.assertIsNone(self.window._settings_panel)  # Still lazy!
        self.assertTrue(self.window.sidebar._update_available)
        self.assertIn("Update", self.window.sidebar.settings_btn.text())

        # Now open settings panel for the first time and verify cached state was applied
        panel = self.window.settings_panel
        self.assertEqual(panel._update_state, "update_available")
        self.assertEqual(panel.update_action_btn.text(), "Install v1.4.0")
        self.assertIn("v1.4.0 available", panel.update_status_label.text())
        self.assertTrue(panel.update_progress_bar.isHidden())

        # 3. Verify all update states and theme transitions
        self.window._on_update_check_started()
        self.assertEqual(panel._update_state, "checking")
        self.assertFalse(panel.update_action_btn.isEnabled())

        self.window._on_update_download_started("1.4.0")
        self.window._on_update_download_progress(65)
        self.assertEqual(panel._update_state, "downloading")
        self.assertFalse(panel.update_progress_bar.isHidden())
        self.assertEqual(panel.update_progress_bar.value(), 65)

        self.window._on_update_check_failed("Network error")
        self.assertEqual(panel._update_state, "error")
        self.assertEqual(panel.update_action_btn.text(), "Retry")
        self.assertTrue(panel.update_action_btn.isEnabled())

        self.window._on_update_up_to_date(APP_VERSION)
        self.assertEqual(panel._update_state, "up_to_date")
        self.assertEqual(panel.update_action_btn.text(), "Check for Updates")
        self.assertFalse(self.window.sidebar._update_available)
        self.assertEqual(self.window.sidebar.settings_btn.text(), "⚙️ Settings")

        for theme_key, _ in THEME_OPTIONS:
            panel.apply_theme(theme_key)
            panel.grab()

    def test_optional_start_end_time_toggles(self):
        """Verify optional Start/End time toggles (default OFF for new tasks), All-Day tasks, Start-Only tasks, and Share ID encoding."""
        from datetime import datetime, timedelta
        from src.qt_components import AddTaskDialog, TaskCard
        from src.constants import ICON_CATEGORIES
        from src import share_handler

        # 1. New task dialog must default both Start and End toggles to OFF
        new_dlg = AddTaskDialog(None, icon_categories=ICON_CATEGORIES, theme=self.window.current_theme)
        self.assertFalse(new_dlg.start_toggle.isChecked())
        self.assertFalse(new_dlg.end_toggle.isChecked())
        self.assertFalse(new_dlg.end_toggle.isEnabled())
        self.assertFalse(new_dlg.start_picker_widget.isEnabled())
        self.assertFalse(new_dlg.end_picker_widget.isEnabled())
        self.assertEqual(new_dlg.start_toggle.text(), "OFF")
        self.assertEqual(new_dlg.end_toggle.text(), "OFF")

        new_dlg.name_input.setText("All Day Task")
        self.assertTrue(new_dlg.save_btn.isEnabled())
        data_all_day = new_dlg.get_task_data()
        self.assertIsNone(data_all_day['start_time'])
        self.assertIsNone(data_all_day['end_time'])

        # 2. Toggling Start ON enables End toggle (which remains OFF until toggled)
        new_dlg.start_toggle.setChecked(True)
        self.assertTrue(new_dlg.start_toggle.isChecked())
        self.assertEqual(new_dlg.start_toggle.text(), "ON")
        self.assertTrue(new_dlg.start_picker_widget.isEnabled())
        self.assertTrue(new_dlg.end_toggle.isEnabled())
        self.assertFalse(new_dlg.end_toggle.isChecked())
        self.assertFalse(new_dlg.end_picker_widget.isEnabled())

        new_dlg.start_hour.setText("09")
        new_dlg.start_min.setText("30")
        new_dlg.start_ampm.setText("AM")
        new_dlg._validate_form()
        self.assertTrue(new_dlg.save_btn.isEnabled())
        data_start_only = new_dlg.get_task_data()
        self.assertEqual(data_start_only['start_time'], "09:30")
        self.assertIsNone(data_start_only['end_time'])

        # 3. Toggling End ON enables End picker; toggling Start back OFF resets and disables End
        new_dlg.end_toggle.setChecked(True)
        self.assertTrue(new_dlg.end_picker_widget.isEnabled())
        new_dlg.end_hour.setText("11")
        new_dlg.end_min.setText("00")
        new_dlg.end_ampm.setText("AM")
        new_dlg._validate_form()
        data_both = new_dlg.get_task_data()
        self.assertEqual(data_both['start_time'], "09:30")
        self.assertEqual(data_both['end_time'], "11:00")

        new_dlg.start_toggle.setChecked(False)
        self.assertFalse(new_dlg.end_toggle.isChecked())
        self.assertFalse(new_dlg.end_toggle.isEnabled())
        self.assertFalse(new_dlg.start_picker_widget.isEnabled())
        self.assertFalse(new_dlg.end_picker_widget.isEnabled())
        new_dlg.deleteLater()

        # 4. Verify TaskCard time_label formatting for untimed (empty), Start-Only, and Full Window
        card_all_day = TaskCard({
            'id': 'c-all-day', 'name': 'All Day', 'start_time': None, 'end_time': None,
            'status': 'active', 'repeat_days': [0, 1, 2, 3, 4, 5, 6]
        })
        self.assertEqual(card_all_day.time_label.text(), "")

        card_start_only = TaskCard({
            'id': 'c-start-only', 'name': 'Start Only', 'start_time': '14:15', 'end_time': None,
            'status': 'active', 'repeat_days': [0, 1, 2, 3, 4, 5, 6]
        })
        self.assertEqual(card_start_only.time_label.text(), "Starts 2:15 PM")
        card_all_day.deleteLater()
        card_start_only.deleteLater()

        # 5. Verify TaskManager state transitions and click/reset behavior
        tm = self.window.task_manager
        t_all_day = tm.add_task("All Day Test", None, None, "📝", repeat_days=[0, 1, 2, 3, 4, 5, 6], page_id=self.window.active_page_id)
        self.assertEqual(t_all_day['status'], 'active')

        # Clicking active All-Day task -> done; clicking again -> active (even in Hardcore Mode)
        self.window.hardcore_mode_enabled = True
        self.window._on_task_clicked(t_all_day)
        self.assertEqual(t_all_day['status'], 'done')
        self.window._on_task_clicked(t_all_day)
        self.assertEqual(t_all_day['status'], 'active')

        # Editing a DONE or FAILED task to start in the future (with no end time) must reset it to PENDING and make it unclickable
        future_dt = datetime.now() + timedelta(minutes=10)
        if future_dt.date() == datetime.now().date():
            future_str = future_dt.strftime("%H:%M")
            self.window.hardcore_mode_enabled = False
            tm.update_task_status(t_all_day['id'], 'done')
            tm.update_task_details(t_all_day['id'], "All Day Test", future_str, None, "📝", [0, 1, 2, 3, 4, 5, 6])
            self.assertEqual(tm.get_task_by_id(t_all_day['id'])['status'], 'pending')
            self.window._on_task_clicked(tm.get_task_by_id(t_all_day['id']))
            self.assertEqual(tm.get_task_by_id(t_all_day['id'])['status'], 'pending')

            tm.update_task_status(t_all_day['id'], 'failed')
            tm.update_task_details(t_all_day['id'], "All Day Test", future_str, None, "📝", [0, 1, 2, 3, 4, 5, 6])
            self.assertEqual(tm.get_task_by_id(t_all_day['id'])['status'], 'pending')
            self.window._on_task_clicked(tm.get_task_by_id(t_all_day['id']))
            self.assertEqual(tm.get_task_by_id(t_all_day['id'])['status'], 'pending')

            # Reset back to untimed active for subsequent checks
            tm.update_task_details(t_all_day['id'], "All Day Test", None, None, "📝", [0, 1, 2, 3, 4, 5, 6])
            self.assertEqual(tm.get_task_by_id(t_all_day['id'])['status'], 'active')

        # Start-only task in the past -> immediately active and never fails
        past_dt = datetime.now() - timedelta(minutes=5)
        past_str = past_dt.strftime("%H:%M")
        t_start_only = tm.add_task("Start Only Past", past_str, None, "📝", repeat_days=[0, 1, 2, 3, 4, 5, 6], page_id=self.window.active_page_id)
        if past_dt.date() == datetime.now().date():
            self.assertEqual(t_start_only['status'], 'active')
            tm.synchronize_task_statuses()
            self.assertEqual(t_start_only['status'], 'active')

        # Daily reset resets yesterday's completed tasks and re-evaluates consistency
        tm.update_task_status(t_all_day['id'], 'done')
        t_all_day['completed_at'] = (datetime.now() - timedelta(days=1)).isoformat()
        tm.update_task_status(t_start_only['id'], 'done')
        t_start_only['completed_at'] = (datetime.now() - timedelta(days=1)).isoformat()
        tm.reset_daily_tasks()
        self.assertEqual(tm.get_task_by_id(t_all_day['id'])['status'], 'active')
        if past_dt.date() == datetime.now().date():
            self.assertEqual(tm.get_task_by_id(t_start_only['id'])['status'], 'active')

        # 6. Verify Share ID round-trip preserves None for start_time and end_time
        encoded = share_handler.encode_tasks([t_all_day, t_start_only], page_name="TestShare")
        decoded_page, decoded_tasks = share_handler.decode_tasks(encoded)
        self.assertEqual(decoded_page, "TestShare")
        self.assertEqual(len(decoded_tasks), 2)
        self.assertIsNone(decoded_tasks[0]['start_time'])
        self.assertIsNone(decoded_tasks[0]['end_time'])
        self.assertEqual(decoded_tasks[1]['start_time'], past_str)
        self.assertIsNone(decoded_tasks[1]['end_time'])

        # Clean up test tasks
        tm.delete_task(t_all_day['id'])
        tm.delete_task(t_start_only['id'])
        self.window.hardcore_mode_enabled = False

    def test_resilience_cache_cleanup_and_backup_recovery(self):
        """Verify orphaned custom image cleanup, .bak recovery on corrupt JSON, sleep/wake recovery, and LRU pixmap bounds."""
        import tempfile
        import time
        from src.task_manager import TaskManager
        from src.qt_components import TaskCard

        with tempfile.TemporaryDirectory(prefix="dt_resilience_") as tmpdir:
            cache_dir = os.path.join(tmpdir, "cache")
            os.makedirs(cache_dir, exist_ok=True)

            active_img = os.path.join(cache_dir, "custom_active123.png")
            orphan_img = os.path.join(cache_dir, "custom_orphan999.png")
            with open(active_img, "wb") as f:
                f.write(b"fake_png_active")
            with open(orphan_img, "wb") as f:
                f.write(b"fake_png_orphan")

            tm = TaskManager(data_dir=tmpdir)
            t1 = tm.add_task("Custom Icon Task", None, None, image_path=os.path.join("cache", "custom_active123.png"))
            tm._save_queue.join()

            # 1. Orphan cleanup removes custom_orphan999.png while keeping custom_active123.png
            removed = tm.cleanup_orphaned_cache_images()
            self.assertEqual(removed, 1)
            self.assertTrue(os.path.exists(active_img))
            self.assertFalse(os.path.exists(orphan_img))

            # 2. Second save creates tasks.json.bak
            tm.update_task_status(t1['id'], 'done')
            tm._save_queue.join()
            self.assertTrue(os.path.exists(tm._data_file + ".bak"))

            # 3. Corrupt tasks.json and verify load_tasks() recovers from tasks.json.bak
            with open(tm._data_file, "w", encoding="utf-8") as f:
                f.write("{corrupted_json_syntax")
            tm.load_tasks()
            tm._save_queue.join()
            recovered_tasks = tm.get_tasks()
            self.assertEqual(len(recovered_tasks), 1)
            self.assertEqual(recovered_tasks[0]['name'], "Custom Icon Task")

            # 4. Deleting the task prunes custom_active123.png from cache/
            tm.delete_task(t1['id'])
            tm._save_queue.join()
            self.assertFalse(os.path.exists(active_img))

        # 5. Verify sleep/wake and tray re-registration handlers execute cleanly
        self.window._on_system_resume_or_time_change()
        self.window._re_register_tray_icon()
        self.window.sound_manager.reset_audio_devices()

        # 6. Verify TaskCard.cleanup() stops timers/animations and disconnects signals cleanly
        card = TaskCard({
            'id': 'cleanup-test', 'name': 'Cleanup Card', 'start_time': '09:00', 'end_time': '10:00',
            'status': 'active', 'repeat_days': [0, 1, 2, 3, 4, 5, 6]
        })
        card.start_urgent_flashing()
        card.start_active_pulse()
        card.cleanup()
        self.assertIsNone(card.flash_timer)
        self.assertIsNone(card.pulse_timer)
        card.deleteLater()

    def test_share_handler_compact_v4_v5_and_legacy_v1_v2_v3(self):
        """Verify compact V4/V5 Share IDs preserve start/end ON/OFF toggles, reduce length significantly, and decode legacy V1/V2/V3 codes."""
        import struct
        import base64
        import tempfile
        from src import share_handler
        from src.constants import ALL_ICONS
        from src.task_manager import TaskManager

        routine_tasks = [
            # 1. All-Day task (both start and end OFF, default icon, all 7 days)
            {'id': '1', 'name': 'Read', 'image_path': '📝', 'start_time': None, 'end_time': None, 'repeat_days': [0, 1, 2, 3, 4, 5, 6], 'enabled': True},
            # 2. Start-Only task on 15-min boundary (start ON, end OFF)
            {'id': '2', 'name': 'Gym', 'image_path': '🏋️', 'start_time': '09:00', 'end_time': None, 'repeat_days': [0, 2, 4], 'enabled': True},
            # 3. Start-Only task on arbitrary minute (start ON, end OFF)
            {'id': '3', 'name': 'Standup Call', 'image_path': '💻', 'start_time': '10:13', 'end_time': None, 'repeat_days': [0, 1, 2, 3, 4], 'enabled': True},
            # 4. Full-Window task on 15-min boundaries (both start and end ON)
            {'id': '4', 'name': 'Deep Work', 'image_path': '🧠', 'start_time': '13:00', 'end_time': '16:30', 'repeat_days': [0, 1, 2, 3, 4, 5, 6], 'enabled': True},
            # 5. Full-Window task on arbitrary minutes + disabled repeat_days=[]
            {'id': '5', 'name': 'Night Review', 'image_path': '🌙', 'start_time': '21:05', 'end_time': '22:47', 'repeat_days': [], 'enabled': True},
        ]

        # Compare V3 length vs new V4/V5 length
        v3_code = share_handler._encode_tasks_v3(routine_tasks, page_name="Default")
        v4_code = share_handler.encode_tasks(routine_tasks, page_name="Default")
        self.assertLess(len(v4_code), len(v3_code))

        # Round-trip decode of new V4/V5 code
        dec_page, dec_tasks = share_handler.decode_tasks(v4_code)
        self.assertEqual(dec_page, "Default")
        self.assertEqual(len(dec_tasks), 5)
        for orig, dec in zip(routine_tasks, dec_tasks):
            self.assertEqual(dec['name'], orig['name'])
            self.assertEqual(dec['image_path'], orig['image_path'])
            self.assertEqual(dec['start_time'], orig['start_time'])
            self.assertEqual(dec['end_time'], orig['end_time'])
            self.assertEqual(dec['repeat_days'], orig['repeat_days'])

        # Verify legacy V3 code still decodes with 100% fidelity
        v3_page, v3_tasks = share_handler.decode_tasks(v3_code)
        self.assertEqual(v3_page, "Default")
        self.assertEqual(len(v3_tasks), 5)
        for orig, dec in zip(routine_tasks, v3_tasks):
            self.assertEqual(dec['name'], orig['name'])
            self.assertEqual(dec['image_path'], orig['image_path'])
            self.assertEqual(dec['start_time'], orig['start_time'])
            self.assertEqual(dec['end_time'], orig['end_time'])
            self.assertEqual(dec['repeat_days'], orig['repeat_days'])

        # Verify legacy V2 binary packet compatibility
        v2_buf = bytearray([2, 1])  # Version 2, 1 task
        packed_v2 = (540 << 21) | (600 << 10) | ALL_ICONS.index('💻')
        v2_buf.extend(struct.pack('>I', packed_v2))
        v2_buf.append(0b0010101)  # Mon, Wed, Fri
        v2_buf.append(4)
        v2_buf.extend(b'Code')
        v2_code = base64.urlsafe_b64encode(v2_buf).decode('ascii')
        v2_page, v2_tasks = share_handler.decode_tasks(v2_code)
        self.assertIsNone(v2_page)
        self.assertEqual(len(v2_tasks), 1)
        self.assertEqual(v2_tasks[0]['name'], 'Code')
        self.assertEqual(v2_tasks[0]['start_time'], '09:00')
        self.assertEqual(v2_tasks[0]['end_time'], '10:00')
        self.assertEqual(v2_tasks[0]['repeat_days'], [0, 2, 4])

        # Verify legacy V1 binary packet compatibility
        v1_buf = bytearray([1, 1])  # Version 1, 1 task
        v1_buf.extend(struct.pack('>I', packed_v2))
        v1_buf.append(4)
        v1_buf.extend(b'Code')
        v1_code = base64.urlsafe_b64encode(v1_buf).decode('ascii')
        v1_page, v1_tasks = share_handler.decode_tasks(v1_code)
        self.assertIsNone(v1_page)
        self.assertEqual(len(v1_tasks), 1)
        self.assertEqual(v1_tasks[0]['repeat_days'], [0, 1, 2, 3, 4, 5, 6])

        # Verify larger multi-task routine uses V5 Deflate compression and is much shorter than V3
        large_routine = [
            {'id': str(i), 'name': f'Daily Habit Task #{i}', 'image_path': '📝', 'start_time': None, 'end_time': None, 'repeat_days': [0, 1, 2, 3, 4, 5, 6], 'enabled': True}
            for i in range(12)
        ]
        v3_large = share_handler._encode_tasks_v3(large_routine, page_name="Morning & Evening")
        v5_large = share_handler.encode_tasks(large_routine, page_name="Morning & Evening")
        self.assertLess(len(v5_large), int(len(v3_large) * 0.55))
        lp, lt = share_handler.decode_tasks(v5_large)
        self.assertEqual(lp, "Morning & Evening")
        self.assertEqual(len(lt), 12)

        # Verify TaskManager.import_tasks_as_page initializes imported task states accurately
        with tempfile.TemporaryDirectory(prefix="dt_import_") as tmpdir:
            tm = TaskManager(data_dir=tmpdir)
            imported_page = tm.import_tasks_as_page(dec_page, dec_tasks)
            tm._save_queue.join()
            page_tasks = tm.get_tasks(page_id=imported_page['id'])
            by_name = {t['name']: t for t in page_tasks}
            self.assertEqual(by_name['Read']['status'], 'active')          # All-Day -> immediately active
            self.assertEqual(by_name['Night Review']['status'], 'disabled') # repeat_days=[] -> disabled

    def test_architecture_and_performance_invariants(self):
        """Enforce 60 FPS fluidity, zero-reflow delta rendering, background I/O isolation, and timer/CPU throttling."""
        import time
        from src.qt_components import TaskCard

        # 1. Verify AddTaskCard singleton reuse and sub-5ms zero-reflow delta _load_tasks()
        self.window._load_tasks()
        add_card_before = self.window._add_task_card
        self.assertIsNotNone(add_card_before)

        t0 = time.perf_counter()
        self.window._load_tasks()
        delta_ms = (time.perf_counter() - t0) * 1000.0
        self.assertIs(self.window._add_task_card, add_card_before)
        self.assertLess(delta_ms, 5.0)

        # 2. Verify main-thread save_tasks() and save_settings() are non-blocking (< 2.0ms)
        t0 = time.perf_counter()
        self.window.task_manager.save_tasks()
        self.window.save_settings()
        save_enqueue_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(save_enqueue_ms, 2.0)

        # 3. Verify precision single-shot wake timer (no aggressive polling loops)
        if getattr(self.window, 'update_timer', None) is None:
            self.window._deferred_startup()
        self.assertTrue(self.window.update_timer.isSingleShot())
        self.assertGreaterEqual(self.window.update_timer.interval(), 1000)

        # 4. Verify particle render loop stays active across idle frames while window is open, and pauses immediately when hidden
        self.window.show()
        self.assertTrue(self.window.particles.timer.isActive())
        for _ in range(200):
            self.window.particles.animate()
        self.assertTrue(self.window.particles.timer.isActive())
        self.window.hide()
        self.assertFalse(self.window.particles.timer.isActive())

        # 5. Verify bounded LRU pixmap cache invariant
        self.assertLessEqual(len(TaskCard._PIXMAP_CACHE), TaskCard._PIXMAP_CACHE_MAX)


if __name__ == '__main__':
    unittest.main()






