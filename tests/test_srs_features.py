"""
Unit tests for newly completed SRS requirements:
- [FR-11] Rosetta 2 Auto-Verification & Trigger
- [FR-17, NFR-12] Expanded Dependency Catalog & YAML/JSON Recipes
- [FR-19] Dependency Uninstallation & Override Cleanup
- [FR-20] Winetricks CLI & Terminal Runner Integration
- [FR-30, FR-31] Graceful vs Force Stop
- [RSK-01] Kernel-Level Anti-Cheat Scanner & Advisory
- [RSK-05] Rolling Automated Registry Hive Backups
- [Section 9 Phase 4] Cloud Save Synchronization
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ravlator.core.config import Config
from ravlator.core.models import BottleConfig, PresetType, WindowsVersion
from ravlator.core.bottle import BottleManager
from ravlator.core.anticheat import AntiCheatDetector, AntiCheatMatch
from ravlator.core.cloud_saves import CloudSaveManager
from ravlator.core.dependencies import DependencyManager, BUILTIN_RECIPES
from ravlator.core.tools import WineToolsManager
from ravlator.core.diagnostics import DiagnosticsManager
from ravlator.core.process import WineProcessManager


class TestSRSFeatures(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_srs_test_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir
        Config.get_bottles_dir().mkdir(parents=True, exist_ok=True)
        Config.get_recipes_dir().mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_anticheat_detection(self):
        """[RSK-01] Verify detection of kernel anti-cheat engines."""
        game_dir = Path(self.test_dir) / "game_eac"
        game_dir.mkdir(parents=True, exist_ok=True)
        eac_binary = game_dir / "easyanticheat_eos.exe"
        eac_binary.write_text("mock binary")

        match = AntiCheatDetector.scan_path(eac_binary)
        self.assertIsNotNone(match)
        self.assertEqual(match.name, "EasyAntiCheat")
        self.assertTrue(match.detected)

        # Test folder scan
        game_exe = game_dir / "game.exe"
        game_exe.write_text("game binary")
        folder_match = AntiCheatDetector.scan_path(game_exe)
        self.assertIsNotNone(folder_match)
        self.assertEqual(folder_match.name, "EasyAntiCheat")

        # Clean game test
        clean_dir = Path(self.test_dir) / "game_clean"
        clean_dir.mkdir(parents=True, exist_ok=True)
        clean_exe = clean_dir / "indie_game.exe"
        clean_exe.write_text("clean binary")
        self.assertIsNone(AntiCheatDetector.scan_path(clean_exe))

        # Advisory format check
        report = AntiCheatDetector.format_report(match)
        self.assertIn("EasyAntiCheat", report)

    def test_registry_rolling_backup(self):
        """[RSK-05] Verify automated registry hive backups."""
        bottle = BottleManager.create_bottle("RegTest", PresetType.GAMING, WindowsVersion.WIN10)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        # Simulate existing registry hives
        sys_reg = b_dir / "system.reg"
        user_reg = b_dir / "user.reg"
        sys_reg.write_text("mock system reg")
        user_reg.write_text("mock user reg")

        success = BottleManager.backup_registry(bottle.id)
        self.assertTrue(success)

        sys_bak = b_dir / "system.reg.bak"
        user_bak = b_dir / "user.reg.bak"
        self.assertTrue(sys_bak.exists())
        self.assertTrue(user_bak.exists())
        self.assertEqual(sys_bak.read_text(), "mock system reg")
        self.assertEqual(user_bak.read_text(), "mock user reg")

    def test_cloud_save_synchronization(self):
        """[Section 9 Phase 4] Verify cloud save symlink enable and disable flow."""
        bottle = BottleManager.create_bottle("SaveSyncTest", PresetType.GAMING, WindowsVersion.WIN10)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        # Create mock user save folder
        saved_games = b_dir / "drive_c" / "users" / "crossover" / "Saved Games"
        saved_games.mkdir(parents=True, exist_ok=True)
        test_save = saved_games / "slot1.dat"
        test_save.write_text("progress: 100%")

        # Mock cloud providers
        mock_cloud = Path(self.test_dir) / "MockiCloud"
        mock_cloud.mkdir(parents=True, exist_ok=True)

        with patch.object(CloudSaveManager, "get_cloud_providers", return_value={"iCloud Drive": mock_cloud}):
            self.assertFalse(CloudSaveManager.is_sync_enabled(bottle))

            # Enable sync
            cloud_root = CloudSaveManager.enable_sync(bottle, "iCloud Drive")
            self.assertTrue(CloudSaveManager.is_sync_enabled(bottle))
            self.assertTrue(saved_games.is_symlink())

            # Verify save file migrated to cloud folder
            cloud_saved_file = cloud_root / "Saved Games" / "slot1.dat"
            self.assertTrue(cloud_saved_file.exists())
            self.assertEqual(cloud_saved_file.read_text(), "progress: 100%")

            # Disable sync
            reverted = CloudSaveManager.disable_sync(bottle)
            self.assertTrue(reverted)
            self.assertFalse(CloudSaveManager.is_sync_enabled(bottle))
            self.assertFalse(saved_games.is_symlink())
            self.assertTrue((saved_games / "slot1.dat").exists())

    def test_yaml_dependency_recipe_loading(self):
        """[FR-17, NFR-12] Verify loading of declarative YAML dependency recipes."""
        yaml_content = """
id: custom_yaml_dep
name: Custom YAML Dependency
category: Audio Libraries
description: A mock audio library defined in YAML.
download_url: https://example.com/audio.exe
sha256: ""
installer_args:
  - /quiet
required_dll_overrides:
  xaudio2_7: native,builtin
dependencies: []
"""
        yaml_file = Config.get_recipes_dir() / "custom_dep.yaml"
        yaml_file.write_text(yaml_content)

        recipes = DependencyManager.get_available_recipes()
        recipe_ids = [r.id for r in recipes]
        self.assertIn("custom_yaml_dep", recipe_ids)
        custom_r = next(r for r in recipes if r.id == "custom_yaml_dep")
        self.assertEqual(custom_r.required_dll_overrides.get("xaudio2_7"), "native,builtin")

    def test_dependency_uninstallation(self):
        """[FR-19] Verify dependency removal and DLL override cleanup."""
        bottle = BottleManager.create_bottle("DepRemoveTest", PresetType.GAMING, WindowsVersion.WIN10)
        bottle.installed_dependencies.append("directx9")
        bottle.dll_overrides["d3dx9_43"] = "native,builtin"
        bottle.dll_overrides["xinput1_3"] = "native,builtin"
        BottleManager.save_bottle_config(bottle)

        # Uninstall dependency
        DependencyManager.uninstall_dependency(bottle.id, "directx9")

        updated = BottleManager.get_bottle(bottle.id)
        self.assertNotIn("directx9", updated.installed_dependencies)
        self.assertNotIn("d3dx9_43", updated.dll_overrides)
        self.assertNotIn("xinput1_3", updated.dll_overrides)

    def test_expanded_recipes_present(self):
        """[FR-17] Verify newly added built-in recipes exist."""
        builtin_ids = [r.id for r in BUILTIN_RECIPES]
        self.assertIn("vcredist2013_x64", builtin_ids)
        self.assertIn("vcredist2013_x86", builtin_ids)
        self.assertIn("vcredist2010_x86", builtin_ids)
        self.assertIn("directplay", builtin_ids)
        self.assertIn("wine_mono", builtin_ids)
        self.assertIn("dotnet48", builtin_ids)
        self.assertIn("openal", builtin_ids)
        self.assertIn("physx", builtin_ids)

    def test_winetricks_discovery_and_script_gen(self):
        """[FR-20] Verify winetricks path discovery and terminal launch script generation."""
        mock_runner = Path(self.test_dir) / "mock_runner"
        mock_bin = mock_runner / "bin"
        mock_bin.mkdir(parents=True, exist_ok=True)
        mock_wt = mock_bin / "winetricks"
        mock_wt.write_text("#!/bin/sh\necho winetricks")
        mock_wt.chmod(0o755)

        found_path = WineToolsManager.get_winetricks_path(mock_runner)
        self.assertEqual(found_path, mock_wt)

        # Test launch script generation
        bottle = BottleManager.create_bottle("WTTest", PresetType.GAMING, WindowsVersion.WIN10)
        with patch.object(WineToolsManager, "get_winetricks_path", return_value=mock_wt), patch("subprocess.run") as mock_run:
            WineToolsManager.launch_winetricks_terminal(bottle, ["vcrun2015"])
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertEqual(args[0], "open")
            self.assertEqual(args[1], "-a")
            self.assertEqual(args[2], "Terminal")

            # Check generated script exists
            script = BottleManager.get_bottle_dir(bottle.id) / "launch_winetricks.sh"
            self.assertTrue(script.exists())
            content = script.read_text()
            self.assertIn("WINEPREFIX", content)
            self.assertIn("vcrun2015", content)

    def test_graceful_stop_invokes_wineboot(self):
        """[FR-30] Verify graceful stop executes wineboot -s."""
        bottle = BottleManager.create_bottle("StopTest", PresetType.GAMING, WindowsVersion.WIN10)
        runner_dir = Path(self.test_dir) / "runner"

        with patch("subprocess.run") as mock_run, patch("ravlator.core.process.WineEnvironmentBuilder.build_env", return_value={}):
            WineProcessManager.stop_bottle(bottle, runner_dir)
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            self.assertIn("-s", called_cmd)


if __name__ == "__main__":
    unittest.main()
