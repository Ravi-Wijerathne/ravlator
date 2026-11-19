"""
Unit tests for Phase 4: Snapshot Engine, Rollback, and Portable Import/Export.
Verifies compliance with FR-33, FR-34, FR-35, FR-36, and NFR-04.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from ravlator.core.config import Config
from ravlator.core.bottle import BottleManager
from ravlator.core.models import PresetType
from ravlator.core.snapshots import SnapshotManager
from ravlator.core.portability import PortabilityManager


class TestPhase4(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ravlator_p4_")
        os.environ[Config.ENV_DATA_DIR] = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if Config.ENV_DATA_DIR in os.environ:
            del os.environ[Config.ENV_DATA_DIR]

    def test_snapshot_lifecycle(self):
        """[FR-33, FR-34] Test snapshot creation, listing, rollback, and deletion."""
        bottle = BottleManager.create_bottle("SnapshotTest", preset=PresetType.GAMING)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        # Create dummy registry file
        reg_file = b_dir / "system.reg"
        reg_file.write_text("[System\\Initial]\n\"Key\"=\"Val1\"\n")

        # 1. Take snapshot
        snap = SnapshotManager.create_snapshot(bottle.id, "Initial State", "Before registry change")
        self.assertEqual(snap.name, "Initial State")

        # 2. List snapshots
        snaps = SnapshotManager.list_snapshots(bottle.id)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].id, snap.id)

        # 3. Modify registry and bottle config
        reg_file.write_text("[System\\Corrupted]\n\"Bad\"=\"True\"\n")
        bottle.msync = False
        BottleManager.save_bottle_config(bottle)

        modified_bottle = BottleManager.get_bottle(bottle.id)
        self.assertFalse(modified_bottle.msync)
        self.assertIn("Bad", reg_file.read_text())

        # 4. Rollback
        success = SnapshotManager.rollback_snapshot(bottle.id, snap.id)
        self.assertTrue(success)

        # Verify rollback restored config and registry
        restored_bottle = BottleManager.get_bottle(bottle.id)
        self.assertTrue(restored_bottle.msync)
        self.assertIn("Val1", reg_file.read_text())

        # 5. Delete snapshot
        del_success = SnapshotManager.delete_snapshot(bottle.id, snap.id)
        self.assertTrue(del_success)
        self.assertEqual(len(SnapshotManager.list_snapshots(bottle.id)), 0)

    def test_bottle_export_and_import_roundtrip(self):
        """[FR-35, FR-36, NFR-04] Test bottle export to .tar.gz and import into new prefix."""
        bottle = BottleManager.create_bottle("ExportSource", preset=PresetType.GAMING)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        # Create a game file in drive_c
        game_file = b_dir / "drive_c" / "game_save.dat"
        game_file.write_text("100% completed save file")

        # 1. Export bottle
        export_out = Path(self.test_dir) / "ExportSource_backup.tar.gz"
        archive_path = PortabilityManager.export_bottle(bottle.id, dest_path=export_out, format="tar.gz")
        self.assertTrue(archive_path.exists())

        # 2. Import into a new bottle
        imported = PortabilityManager.import_bottle(archive_path, custom_name="ImportedBottle")
        self.assertEqual(imported.name, "ImportedBottle")
        self.assertEqual(imported.preset, PresetType.GAMING)

        imp_dir = BottleManager.get_bottle_dir(imported.id)
        self.assertTrue(imp_dir.exists())

        # Verify drive_c contents and game save persisted
        imp_game_file = imp_dir / "drive_c" / "game_save.dat"
        self.assertTrue(imp_game_file.exists())
        self.assertEqual(imp_game_file.read_text(), "100% completed save file")

        # Verify dosdevices symlinks are intact
        c_link = imp_dir / "dosdevices" / "c:"
        self.assertTrue(c_link.is_symlink())
        self.assertTrue((imp_dir / "dosdevices" / "z:").is_symlink())


if __name__ == "__main__":
    unittest.main()
