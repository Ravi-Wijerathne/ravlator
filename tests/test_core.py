"""
Unit tests for Ravlator Core Engine.
Verifies compliance with FR-01, FR-02, FR-03, FR-04, FR-27, and NFR-04.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ravlator.core.config import Config
from ravlator.core.models import PresetType, WindowsVersion
from ravlator.core.bottle import BottleManager
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager


class TestRavlatorCore(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_test_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_bottle_creation_gaming_preset(self):
        """[FR-01, FR-02] Test gaming preset defaults."""
        bottle = BottleManager.create_bottle("RPG Test", preset=PresetType.GAMING)
        self.assertEqual(bottle.name, "RPG Test")
        self.assertTrue(bottle.msync)
        self.assertTrue(bottle.retina)
        self.assertFalse(bottle.metal_hud)
        self.assertIn("d3d11", bottle.dll_overrides)

        b_dir = BottleManager.get_bottle_dir(bottle.id)
        self.assertTrue(b_dir.exists())
        self.assertTrue((b_dir / "drive_c").exists())
        self.assertTrue((b_dir / "bottle.json").exists())

    def test_bottle_cloning(self):
        """[FR-03] Test bottle duplication."""
        original = BottleManager.create_bottle("Base", preset=PresetType.GAMING)
        cloned = BottleManager.duplicate_bottle(original.id, "Base Clone")
        
        self.assertEqual(cloned.name, "Base Clone")
        self.assertEqual(cloned.msync, original.msync)
        self.assertTrue(BottleManager.get_bottle_dir(cloned.id).exists())

    def test_bottle_deletion(self):
        """[FR-04] Test bottle deletion."""
        bottle = BottleManager.create_bottle("ToDelete")
        self.assertTrue(BottleManager.get_bottle_dir(bottle.id).exists())
        
        deleted = BottleManager.delete_bottle(bottle.id)
        self.assertTrue(deleted)
        self.assertFalse(BottleManager.get_bottle_dir(bottle.id).exists())

    def test_environment_builder(self):
        """[FR-12, FR-14, FR-16] Test environment variable compilation."""
        bottle = BottleManager.create_bottle("EnvTest", preset=PresetType.GAMING)
        fake_runner = Path(self.test_dir) / "fake_runner"
        fake_runner.mkdir(parents=True, exist_ok=True)

        env = WineEnvironmentBuilder.build_env(bottle, fake_runner)
        self.assertEqual(env["WINEMSYNC"], "1")
        self.assertEqual(env["WINEARCH"], "win64")
        self.assertEqual(env["WINE_DPI_AWARE"], "1")
        self.assertIn(str(BottleManager.get_bottle_dir(bottle.id)), env["WINEPREFIX"])

    def test_steam_cef_mitigation(self):
        """[FR-27, Appendix B] Verify CEF crash prevention flags are injected."""
        raw_args = ["-silent"]
        fixed_args = WineProcessManager.inject_steam_cef_workaround("C:\\Steam\\steam.exe", raw_args)
        
        self.assertIn("-no-cef-sandbox", fixed_args)
        self.assertIn("-cef-disable-gpu", fixed_args)
        self.assertIn("-noverifyfiles", fixed_args)
        self.assertIn("-allossearch", fixed_args)


if __name__ == "__main__":
    unittest.main()
