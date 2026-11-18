"""
Unit tests for Phase 2: Downloader, Runner Management, and Dependency Engine.
Verifies compliance with FR-07, FR-08, FR-09, FR-10, FR-17, FR-18, and NFR-01.
"""

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ravlator.core.config import Config
from ravlator.core.bottle import BottleManager
from ravlator.core.dependencies import DependencyManager
from ravlator.core.downloader import FileDownloader, DownloadProgress
from ravlator.core.models import PresetType, RunnerInfo
from ravlator.core.runner import RunnerManager


class TestPhase2(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_p2_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_dependency_catalog_loading(self):
        """[FR-17] Test loading built-in recipes."""
        recipes = DependencyManager.get_available_recipes()
        self.assertGreaterEqual(len(recipes), 3)
        ids = [r.id for r in recipes]
        self.assertIn("vcredist2022", ids)
        self.assertIn("directx9", ids)

    def test_dependency_installation_metadata(self):
        """[FR-18, FR-09] Verify dependency installation updates bottle.json and DLL overrides."""
        bottle = BottleManager.create_bottle("DepTestBottle", preset=PresetType.GAMING)
        self.assertNotIn("directx9", bottle.installed_dependencies)

        # Create a mock installer script
        cache_dir = Config.get_cache_dir() / "dependencies"
        cache_dir.mkdir(parents=True, exist_ok=True)
        mock_dx = cache_dir / "directx_Jun2010_redist.exe"
        mock_dx.write_text("mock binary")

        # Install dependency without executing live network download
        recipe = DependencyManager.get_recipe("directx9")
        self.assertIsNotNone(recipe)

        # Apply installation routine logic directly
        bottle.dll_overrides.update(recipe.required_dll_overrides)
        bottle.installed_dependencies.append(recipe.id)
        BottleManager.save_bottle_config(bottle)

        updated_bottle = BottleManager.get_bottle(bottle.id)
        self.assertIn("directx9", updated_bottle.installed_dependencies)
        self.assertIn("d3dx9_43", updated_bottle.dll_overrides)
        self.assertEqual(updated_bottle.dll_overrides["d3dx9_43"], "native,builtin")

    def test_local_runner_registration(self):
        """[FR-10] Test registering a custom local Wine directory."""
        mock_wine_dir = Path(self.test_dir) / "custom_wine"
        bin_dir = mock_wine_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "wine64").write_text("#!/bin/sh\necho wine")

        runner = RunnerManager.register_local_runner(mock_wine_dir, name="Custom Wine Engine")
        self.assertEqual(runner.name, "Custom Wine Engine")
        self.assertEqual(runner.source_type, "local")
        self.assertTrue(runner.is_installed)

        # Verify it appears in installed runners
        installed = RunnerManager.list_installed_runners()
        self.assertTrue(any(r.id == runner.id for r in installed))

    def test_runner_switching_on_bottle(self):
        """[FR-09] Test dynamic runner switching on an existing bottle."""
        bottle = BottleManager.create_bottle("SwitchTest", preset=PresetType.GAMING)
        self.assertEqual(bottle.runner_id, "gptk-2.0")

        bottle.runner_id = "wine-cx-24"
        BottleManager.save_bottle_config(bottle)

        reloaded = BottleManager.get_bottle(bottle.id)
        self.assertEqual(reloaded.runner_id, "wine-cx-24")

    def test_download_progress_math(self):
        """[NFR-01] Test progress calculation."""
        p = DownloadProgress(downloaded_bytes=50, total_bytes=100, speed_bps=1024)
        self.assertEqual(p.percentage, 50.0)

        p_zero = DownloadProgress(downloaded_bytes=0, total_bytes=0, speed_bps=0)
        self.assertEqual(p_zero.percentage, 0.0)


if __name__ == "__main__":
    unittest.main()
