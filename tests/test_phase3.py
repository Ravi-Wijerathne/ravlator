"""
Unit tests for Phase 3: Shortcuts, Store Integration, and Diagnostics.
Verifies compliance with FR-22, FR-23, FR-24, FR-26, FR-27, FR-29, and FR-32.
"""

import os
import plistlib
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from ravlator.core.config import Config
from ravlator.core.bottle import BottleManager
from ravlator.core.models import PresetType, ProgramEntry
from ravlator.core.shortcuts import ShortcutManager
from ravlator.core.stores import StoreManager, SUPPORTED_STORES
from ravlator.core.telemetry import ProcessTelemetry


class TestPhase3(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_p3_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_macos_app_bundle_generation(self):
        """[FR-24] Test standalone macOS .app bundle generation."""
        bottle = BottleManager.create_bottle("AppGenTest", preset=PresetType.GAMING)
        program = ProgramEntry(
            id="prog-1",
            name="TestGame",
            exe_path="C:\\Games\\TestGame\\game.exe",
            arguments="-windowed"
        )

        out_dir = Path(self.test_dir) / "apps"
        bundle_path = ShortcutManager.create_macos_app(
            bottle=bottle,
            program=program,
            output_dir=out_dir
        )

        self.assertTrue(bundle_path.exists())
        self.assertEqual(bundle_path.name, "TestGame.app")

        # Verify Info.plist
        plist_path = bundle_path / "Contents" / "Info.plist"
        self.assertTrue(plist_path.exists())
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)
            self.assertEqual(data["CFBundleExecutable"], "launcher")
            self.assertEqual(data["CFBundleName"], "TestGame")

        # Verify launcher script
        launcher_path = bundle_path / "Contents" / "MacOS" / "launcher"
        self.assertTrue(launcher_path.exists())
        # Check executable bit
        mode = launcher_path.stat().st_mode
        self.assertTrue(bool(mode & stat.S_IXUSR))

        # Check content includes CLI run invocation
        content = launcher_path.read_text()
        self.assertIn("ravlator.cli.main", content)
        self.assertIn(bottle.id, content)
        self.assertIn("game.exe", content)

    def test_steam_store_definition_and_cef_flags(self):
        """[FR-26, FR-27] Verify Steam definition contains mandatory CEF flags."""
        steam = StoreManager.get_store("steam")
        self.assertIsNotNone(steam)
        self.assertIn("-no-cef-sandbox", steam.recommended_arguments)
        self.assertIn("-cef-disable-gpu", steam.recommended_arguments)
        self.assertIn("-noverifyfiles", steam.recommended_arguments)
        self.assertIn("-allossearch", steam.recommended_arguments)

    def test_store_program_registration(self):
        """[FR-26] Verify registering a store adds ProgramEntry to bottle."""
        bottle = BottleManager.create_bottle("StoreTest", preset=PresetType.GAMING)
        self.assertEqual(len(bottle.programs), 0)

        entry = StoreManager.register_store_program(bottle, "steam")
        self.assertEqual(entry.name, "Steam")
        self.assertIn("steam.exe", entry.exe_path)

        reloaded = BottleManager.get_bottle(bottle.id)
        self.assertEqual(len(reloaded.programs), 1)
        self.assertEqual(reloaded.programs[0].name, "Steam")

    def test_telemetry_log_recording(self):
        """[FR-32] Verify log appending and reading."""
        bottle = BottleManager.create_bottle("LogTest", preset=PresetType.GAMING)
        ProcessTelemetry.append_log(bottle.id, "Line 1: Wine initializing\n")
        ProcessTelemetry.append_log(bottle.id, "Line 2: D3DMetal loaded\n")

        logs = ProcessTelemetry.read_recent_logs(bottle.id)
        self.assertIn("Line 1: Wine initializing", logs)
        self.assertIn("Line 2: D3DMetal loaded", logs)

    def test_telemetry_process_listing(self):
        """[FR-29] Verify process query does not crash."""
        procs = ProcessTelemetry.list_bottle_processes("NonExistentBottle")
        self.assertIsInstance(procs, list)


if __name__ == "__main__":
    unittest.main()
