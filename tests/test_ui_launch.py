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
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        cls._settings_path = os.path.join(appdata, 'DailyTasks', 'settings.json')
        cls._backup_settings = None
        if os.path.exists(cls._settings_path):
            with open(cls._settings_path, 'rb') as f:
                cls._backup_settings = f.read()

    @classmethod
    def tearDownClass(cls):
        if cls._backup_settings is not None:
            import time
            time.sleep(0.05)
            with open(cls._settings_path, 'wb') as f:
                f.write(cls._backup_settings)

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

        # Verify SettingsPanel visual hierarchy order from top to bottom
        vbox = panel.layout()
        ordered_widgets = [vbox.itemAt(i).widget() for i in range(vbox.count()) if vbox.itemAt(i).widget() is not None]
        expected_sequence = [
            panel.theme_combo,
            panel.simple_checkbox,
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
        self.assertEqual(APP_VERSION, "1.3.0")
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


if __name__ == '__main__':
    unittest.main()




