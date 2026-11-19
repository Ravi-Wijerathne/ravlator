"""
Unit tests for GUI presentation and layout structure.
Verifies compliance with Section 5.1, NFR-01, FR-06, FR-12 to FR-16.
"""

import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from ravlator.gui.styles import get_stylesheet
from ravlator.gui.main_window import MainWindow
from ravlator.core.models import PresetType, WindowsVersion
from ravlator.core.bottle import BottleManager


class TestGUIStructure(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(get_stylesheet("light"))

    def test_stylesheet_generation(self):
        """[Section 5.1] Verify light theme stylesheet contains expected selectors."""
        sheet = get_stylesheet("light")
        self.assertIn("#sidebar", sheet)
        self.assertIn("#contentArea", sheet)
        self.assertIn("QTabWidget::pane", sheet)
        self.assertIn("QCheckBox::indicator", sheet)
        self.assertIn("#primaryAction", sheet)
        self.assertIn("#utilityBtn", sheet)

    def test_main_window_tabs_and_controls(self):
        """[NFR-01] Verify MainWindow initializes with 4 tabs and full controls."""
        win = MainWindow()
        self.assertEqual(win.tab_widget.count(), 4)

        tab_names = [win.tab_widget.tabText(i) for i in range(4)]
        self.assertIn("Programs", tab_names)
        self.assertIn("Configuration", tab_names)
        self.assertIn("Tools && Stores", tab_names)
        self.assertIn("Maintenance", tab_names)

        # Check configuration controls exist
        self.assertIsNotNone(win.runner_combo)
        self.assertIsNotNone(win.win_ver_combo)
        self.assertIsNotNone(win.chk_msync)
        self.assertIsNotNone(win.chk_metal_hud)
        self.assertIsNotNone(win.chk_retina)
        self.assertIsNotNone(win.chk_virtual_desktop)
        self.assertIsNotNone(win.res_combo)
        self.assertIsNotNone(win.dxvk_hud_combo)

        # Check utility and maintenance actions exist
        self.assertIsNotNone(win.btn_install_store)
        self.assertIsNotNone(win.btn_dependencies)
        self.assertIsNotNone(win.btn_winecfg)
        self.assertIsNotNone(win.btn_regedit)
        self.assertIsNotNone(win.btn_terminal)
        self.assertIsNotNone(win.btn_dll_overrides)
        self.assertIsNotNone(win.btn_task_mgr)
        self.assertIsNotNone(win.btn_logs)
        self.assertIsNotNone(win.btn_snapshots)
        self.assertIsNotNone(win.btn_export)
        self.assertIsNotNone(win.btn_clone)
        self.assertIsNotNone(win.btn_reset)
        self.assertIsNotNone(win.btn_delete)


if __name__ == "__main__":
    unittest.main()
