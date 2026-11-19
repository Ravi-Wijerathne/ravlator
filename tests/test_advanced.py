"""
Unit tests for Advanced Features: Diagnostics, PE Icon Extraction, Wine Tools, and DLL Overrides.
Verifies compliance with FR-06, FR-07, FR-09, FR-11, FR-20, and FR-23.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ravlator.core.config import Config
from ravlator.core.bottle import BottleManager
from ravlator.core.diagnostics import DiagnosticsManager, SystemDiagnostics
from ravlator.core.icon_extractor import IconExtractor
from ravlator.core.models import PresetType, WindowsVersion
from ravlator.core.tools import WineToolsManager


class TestAdvancedFeatures(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_adv_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_system_diagnostics_detection(self):
        """[FR-07, FR-11] Verify host diagnostics returns valid metrics."""
        diag = DiagnosticsManager.get_system_diagnostics()
        self.assertIsInstance(diag, SystemDiagnostics)
        self.assertTrue(len(diag.macos_version) > 0)
        self.assertGreater(diag.memory_gb, 0)
        self.assertIn("macOS", diag.macos_name)

        summary = DiagnosticsManager.get_diagnostic_summary()
        self.assertIn("Hardware:", summary)
        self.assertIn("OS:", summary)

    def test_windows_version_toggle(self):
        """[FR-06] Verify switching bottle reported Windows version."""
        bottle = BottleManager.create_bottle("WinVerTest", preset=PresetType.GAMING)
        self.assertEqual(bottle.windows_version, WindowsVersion.WIN10)

        # Set to Windows 11
        WineToolsManager.set_windows_version(bottle, WindowsVersion.WIN11)
        reloaded = BottleManager.get_bottle(bottle.id)
        self.assertEqual(reloaded.windows_version, WindowsVersion.WIN11)

    def test_dll_overrides_manipulation(self):
        """[FR-09] Verify adding, editing, and deleting DLL overrides."""
        bottle = BottleManager.create_bottle("DllTest", preset=PresetType.GAMING)
        # Default gaming overrides
        self.assertIn("d3d11", bottle.dll_overrides)

        # Add custom override
        bottle.dll_overrides["xinput1_3"] = "native"
        BottleManager.save_bottle_config(bottle)

        reloaded = BottleManager.get_bottle(bottle.id)
        self.assertEqual(reloaded.dll_overrides["xinput1_3"], "native")

        # Delete override
        del reloaded.dll_overrides["xinput1_3"]
        BottleManager.save_bottle_config(reloaded)

        re_reloaded = BottleManager.get_bottle(bottle.id)
        self.assertNotIn("xinput1_3", re_reloaded.dll_overrides)

    def test_icon_extractor_graceful_fallback(self):
        """[FR-23] Verify icon extractor handles invalid paths gracefully."""
        res = IconExtractor.extract_icon(Path("/non/existent/game.exe"))
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
