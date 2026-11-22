"""
Unit tests for Virtual Desktop, Native Steam Sync, Bottle Reset, and Global Preferences.
Verifies compliance with FR-05, FR-16, FR-21, FR-27, and NFR-04.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ravlator.core.config import Config
from ravlator.core.models import BottleConfig, PresetType
from ravlator.core.bottle import BottleManager
from ravlator.core.process import WineProcessManager
from ravlator.core.stores import StoreManager


class TestNewFeatures(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_new_features_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_build_launch_command_standard(self):
        """[FR-21] Verify standard command construction."""
        bottle = BottleManager.create_bottle("StandardLaunch", preset=PresetType.GAMING)
        runner_dir = Path(self.test_dir) / "fake_runner" / "bin"
        runner_dir.mkdir(parents=True, exist_ok=True)
        (runner_dir / "wine64").touch()

        cmd = WineProcessManager.build_launch_command(
            runner_path=runner_dir.parent,
            bottle=bottle,
            exe_path="C:\\Games\\test.exe",
            args=["-novid"]
        )

        self.assertIn("wine64", cmd[0])
        self.assertEqual(cmd[1], "C:\\Games\\test.exe")
        self.assertEqual(cmd[2], "-novid")

    def test_build_launch_command_virtual_desktop(self):
        """[FR-16] Verify virtual desktop wrapper command construction."""
        bottle = BottleManager.create_bottle("VDLaunch", preset=PresetType.GAMING)
        bottle.virtual_desktop = True
        bottle.virtual_desktop_res = "2560x1440"

        runner_dir = Path(self.test_dir) / "fake_runner" / "bin"
        runner_dir.mkdir(parents=True, exist_ok=True)
        (runner_dir / "wine64").touch()

        cmd = WineProcessManager.build_launch_command(
            runner_path=runner_dir.parent,
            bottle=bottle,
            exe_path="C:\\Games\\rpg.exe",
            args=["--fullscreen"]
        )

        self.assertIn("wine64", cmd[0])
        self.assertEqual(cmd[1], "explorer.exe")
        self.assertEqual(cmd[2], "/desktop=VDLaunch,2560x1440")
        self.assertEqual(cmd[3], "C:\\Games\\rpg.exe")
        self.assertIn("--fullscreen", cmd)

    def test_build_launch_command_steam_cef_injection(self):
        """[FR-27] Verify Steam CEF flags injected even in virtual desktop mode."""
        bottle = BottleManager.create_bottle("SteamVD", preset=PresetType.GAMING)
        bottle.virtual_desktop = True

        runner_dir = Path(self.test_dir) / "fake_runner" / "bin"
        runner_dir.mkdir(parents=True, exist_ok=True)
        (runner_dir / "wine64").touch()

        cmd = WineProcessManager.build_launch_command(
            runner_path=runner_dir.parent,
            bottle=bottle,
            exe_path="C:\\Program Files (x86)\\Steam\\steam.exe",
            args=["-silent"]
        )

        self.assertIn("-no-cef-sandbox", cmd)
        self.assertIn("-cef-disable-gpu", cmd)
        self.assertIn("-noverifyfiles", cmd)
        self.assertIn("-allossearch", cmd)

    def test_bottle_reset(self):
        """[FR-05] Test prefix reset clears temp files and resets registry while preserving user data."""
        bottle = BottleManager.create_bottle("ResetTest", preset=PresetType.GAMING)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        # Create temporary cache and lock files
        temp_dir = b_dir / "drive_c" / "windows" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / "junk.tmp").write_text("temporary cache junk")
        (b_dir / ".update-timestamp").write_text("lock")

        # Create corrupt registry hive
        reg_file = b_dir / "system.reg"
        reg_file.write_text("CORRUPT_REGISTRY_DATA_HERE")

        # Create user save file
        user_save = b_dir / "drive_c" / "users" / "crossover" / "Saved Games" / "save.dat"
        user_save.parent.mkdir(parents=True, exist_ok=True)
        user_save.write_text("PLAYER_LEVEL_100")

        # Perform reset
        BottleManager.reset_bottle(bottle.id)

        # 1. Temp file and lock removed
        self.assertFalse((temp_dir / "junk.tmp").exists())
        self.assertFalse((b_dir / ".update-timestamp").exists())

        # 2. Registry hive reset to vanilla header and backup created
        self.assertTrue((b_dir / "system.reg.bak").exists())
        with open(reg_file, "r") as f:
            content = f.read()
        self.assertIn("WINE REGISTRY Version 2", content)
        self.assertNotIn("CORRUPT_REGISTRY_DATA_HERE", content)

        # 3. User save data preserved
        self.assertTrue(user_save.exists())
        self.assertEqual(user_save.read_text(), "PLAYER_LEVEL_100")

    def test_global_settings_persistence(self):
        """[NFR-04] Test atomic loading and saving of global preferences."""
        defaults = Config.load_global_settings()
        self.assertIn("theme_mode", defaults)
        self.assertIn("default_runner", defaults)

        defaults["theme_mode"] = "light"
        defaults["default_runner"] = "wine-cx-23.7"
        Config.save_global_settings(defaults)

        reloaded = Config.load_global_settings()
        self.assertEqual(reloaded["theme_mode"], "light")
        self.assertEqual(reloaded["default_runner"], "wine-cx-23.7")

    def test_sync_native_steam_login_not_found(self):
        """[FR-27] Verify exception when native Mac Steam is absent."""
        bottle = BottleManager.create_bottle("SteamSyncTest")
        # Ensure non-existent path raises FileNotFoundError
        real_home = Path.home
        try:
            fake_home = Path(self.test_dir) / "fake_user"
            fake_home.mkdir(parents=True, exist_ok=True)
            Path.home = lambda: fake_home
            with self.assertRaises(FileNotFoundError):
                StoreManager.sync_native_steam_login(bottle)
        finally:
            Path.home = real_home

    def test_sync_native_steam_login_success(self):
        """[FR-27] Verify copying of login tokens and userdata from Mac Steam."""
        bottle = BottleManager.create_bottle("SteamSyncTest2")
        real_home = Path.home
        try:
            fake_home = Path(self.test_dir) / "fake_user"
            mac_steam = fake_home / "Library" / "Application Support" / "Steam"
            (mac_steam / "config").mkdir(parents=True, exist_ok=True)
            (mac_steam / "userdata").mkdir(parents=True, exist_ok=True)
            (mac_steam / "config" / "loginusers.vdf").write_text('"users" { "76561198": { "AccountName": "gamer" } }')
            (mac_steam / "userdata" / "user_settings.bin").write_text("BINARY_USER_DATA")

            Path.home = lambda: fake_home

            copied = StoreManager.sync_native_steam_login(bottle)
            self.assertTrue(copied)

            b_steam = BottleManager.get_bottle_dir(bottle.id) / "drive_c" / "Program Files (x86)" / "Steam"
            self.assertTrue((b_steam / "config" / "loginusers.vdf").exists())
            self.assertTrue((b_steam / "userdata" / "user_settings.bin").exists())
            self.assertEqual((b_steam / "userdata" / "user_settings.bin").read_text(), "BINARY_USER_DATA")
        finally:
            Path.home = real_home

    def test_sync_native_steam_login_includes_registry_vdf(self):
        """[FR-27] Verify copying of registry.vdf containing AutoLoginUser credentials."""
        bottle = BottleManager.create_bottle("SteamSyncTest3")
        real_home = Path.home
        try:
            fake_home = Path(self.test_dir) / "fake_user3"
            mac_steam = fake_home / "Library" / "Application Support" / "Steam"
            (mac_steam / "config").mkdir(parents=True, exist_ok=True)
            (mac_steam / "config" / "loginusers.vdf").write_text('"users" { }')
            (mac_steam / "registry.vdf").write_text('"Registry" { "AutoLoginUser" "testuser" }')

            Path.home = lambda: fake_home

            copied = StoreManager.sync_native_steam_login(bottle)
            self.assertTrue(copied)

            b_steam = BottleManager.get_bottle_dir(bottle.id) / "drive_c" / "Program Files (x86)" / "Steam"
            self.assertTrue((b_steam / "registry.vdf").exists())
            self.assertIn("AutoLoginUser", (b_steam / "registry.vdf").read_text())
        finally:
            Path.home = real_home

    def test_detect_installed_stores_auto_registers_steam(self):
        """[FR-26, FR-27] Verify auto-detection of manually installed stores in Drive C:."""
        bottle = BottleManager.create_bottle("AutoDetectStoreTest")
        b_dir = BottleManager.get_bottle_dir(bottle.id)
        steam_exe = b_dir / "drive_c" / "Program Files (x86)" / "Steam" / "steam.exe"
        steam_exe.parent.mkdir(parents=True, exist_ok=True)
        steam_exe.write_text("MZ_DUMMY_STEAM")

        detected = StoreManager.detect_installed_stores(bottle)
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].name, "Steam")
        self.assertIn("-no-cef-sandbox", detected[0].arguments)
        self.assertIn("-cef-disable-gpu", detected[0].arguments)

    def test_launch_store_installer_missing_files_raises(self):
        """[FR-26] Verify launch_store_installer raises clear errors on missing files/runners."""
        bottle = BottleManager.create_bottle("LaunchInstallerTest")
        with self.assertRaises(FileNotFoundError):
            StoreManager.launch_store_installer(bottle, Path(self.test_dir) / "nonexistent_setup.exe")


if __name__ == "__main__":
    unittest.main()
