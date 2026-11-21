"""
Security and Vulnerability Hardening Tests for Ravlator.
Verifies protections against:
- [VULN-01] Zip Slip / Tar Slip Path Traversal during bottle archive import
- [VULN-02] Shell Command Injection in standalone macOS .app bundles
- [VULN-03] Command & Environment Variable Injection in Terminal launch scripts
- [GAP-01] Drive Z: Filesystem Sandbox Isolation (mitigating host root access)
- [GAP-02] Insecure HTTP transport rejection
"""

import io
import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ravlator.core.config import Config
from ravlator.core.models import BottleConfig, ProgramEntry, PresetType, WindowsVersion
from ravlator.core.bottle import BottleManager
from ravlator.core.downloader import FileDownloader
from ravlator.core.portability import PortabilityManager
from ravlator.core.shortcuts import ShortcutManager
from ravlator.core.tools import WineToolsManager


class TestSecurityHardening(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_sec_test_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir
        Config.get_bottles_dir().mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_zip_slip_path_traversal_rejected(self):
        """[VULN-01] Test that Zip Slip path traversal archives are strictly blocked."""
        evil_zip_path = Path(self.test_dir) / "evil_bottle.zip"
        escape_file = Path(self.test_dir) / "escaped_pwn.txt"

        # Construct a zip archive with a path traversal entry
        with zipfile.ZipFile(evil_zip_path, "w") as zf:
            zf.writestr("bottle.json", '{"id": "evil", "name": "Evil"}')
            zf.writestr("../../escaped_pwn.txt", "MALICIOUS PAYLOAD")

        with self.assertRaises((RuntimeError, PermissionError)) as ctx:
            PortabilityManager.import_bottle(evil_zip_path)

        self.assertIn("Security Alert", str(ctx.exception))
        self.assertFalse(escape_file.exists(), "Zip Slip wrote file outside destination directory!")

    def test_tar_slip_path_traversal_rejected(self):
        """[VULN-01] Test that Tar Slip path traversal archives are strictly blocked."""
        evil_tar_path = Path(self.test_dir) / "evil_bottle.tar.gz"
        escape_file = Path(self.test_dir) / "escaped_tar_pwn.txt"

        # Construct a tar archive with a path traversal entry
        with tarfile.open(evil_tar_path, "w:gz") as tf:
            payload = b"MALICIOUS PAYLOAD"
            ti = tarfile.TarInfo(name="../../escaped_tar_pwn.txt")
            ti.size = len(payload)
            tf.addfile(ti, io.BytesIO(payload))

        with self.assertRaises((RuntimeError, PermissionError)) as ctx:
            PortabilityManager.import_bottle(evil_tar_path)

        self.assertIn("Security Alert", str(ctx.exception))
        self.assertFalse(escape_file.exists(), "Tar Slip wrote file outside destination directory!")

    def test_shell_injection_prevented_in_app_bundle(self):
        """[VULN-02] Test that standalone macOS .app bundle launcher properly escapes metacharacters."""
        bottle = BottleManager.create_bottle("SecurityTestBottle", preset=PresetType.GAMING)
        prog = ProgramEntry(
            id="p-injection",
            name="InjectedGame",
            exe_path="/path/with spaces/game.exe",
            arguments='-windowed; touch /tmp/pwned_test; echo $(whoami) "nested quotes"'
        )

        out_dir = Path(self.test_dir) / "Apps"
        app_bundle = ShortcutManager.create_macos_app(bottle, prog, output_dir=out_dir)
        launcher_file = app_bundle / "Contents" / "MacOS" / "launcher"

        self.assertTrue(launcher_file.exists())
        launcher_content = launcher_file.read_text()

        # Verify that arguments are safely quoted and not raw unescaped shell commands
        self.assertIn("pwned_test", launcher_content)
        # Shell command delimiter `; touch` must be quoted safely inside a string token
        self.assertNotIn("; touch /tmp/pwned_test;", launcher_content)
        self.assertIn("'-windowed;'", launcher_content)

    def test_shell_injection_prevented_in_winetricks_script(self):
        """[VULN-03] Test that Terminal scripts quote verbs and environment variables."""
        bottle = BottleManager.create_bottle("Malicious;Name$(id)", preset=PresetType.GAMING)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        evil_verbs = ["vcrun2015", "; touch /tmp/hacked_wt; #"]

        with patch.object(WineToolsManager, "get_winetricks_path", return_value=Path("/opt/homebrew/bin/winetricks")), \
             patch("subprocess.run") as mock_open:
            WineToolsManager.launch_winetricks_terminal(bottle, verbs=evil_verbs)
            script_path = b_dir / "launch_winetricks.sh"
            self.assertTrue(script_path.exists())
            content = script_path.read_text()

            # Verify that verbs and name are quoted safely
            self.assertIn("'; touch /tmp/hacked_wt; #'", content)
            self.assertNotIn("vcrun2015 ; touch", content)

    def test_sandbox_drive_z_isolation(self):
        """[GAP-01] Test that sandbox mode restricts drive Z: from accessing host root '/'."""
        bottle = BottleManager.create_bottle("SandboxTest", preset=PresetType.GAMING)
        b_dir = BottleManager.get_bottle_dir(bottle.id)
        z_link = b_dir / "dosdevices" / "z:"

        # Default policy: sandbox_drive_z is True -> maps to drive_c, NOT /
        self.assertTrue(bottle.sandbox_drive_z)
        self.assertTrue(z_link.is_symlink())
        target = os.readlink(z_link)
        self.assertNotEqual(target, "/", "Drive Z: must not link to host macOS root '/' in sandbox mode!")
        self.assertEqual(target, "../drive_c")

        # Disable sandbox mode and apply policy
        bottle.sandbox_drive_z = False
        BottleManager.apply_sandbox_policy(bottle)
        self.assertEqual(os.readlink(z_link), "/")

        # Re-enable sandbox mode
        bottle.sandbox_drive_z = True
        BottleManager.apply_sandbox_policy(bottle)
        self.assertEqual(os.readlink(z_link), "../drive_c")

    def test_insecure_http_transport_rejected(self):
        """[GAP-02] Test that plain HTTP downloads are rejected in favor of HTTPS/TLS."""
        dummy_dest = Path(self.test_dir) / "out.bin"
        with self.assertRaises(ValueError) as ctx:
            FileDownloader.download_file("http://insecure-server.com/malicious.tar.gz", dummy_dest)
        self.assertIn("Insecure transport protocol rejected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
