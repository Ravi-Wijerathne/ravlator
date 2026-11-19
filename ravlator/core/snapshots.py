"""
[FR-33, FR-34, NFR-04] Point-in-Time Bottle Snapshot & Rollback Engine.
Captures lightweight registry and state snapshots before modding or updates.
Decoupled from GUI frameworks.
"""

from datetime import datetime, timezone
import json
import shutil
from pathlib import Path
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field

from ravlator.core.bottle import BottleManager
from ravlator.core.config import Config


class SnapshotInfo(BaseModel):
    id: str
    bottle_id: str
    name: str
    description: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SnapshotManager:
    """Manages snapshot creation, listing, and atomic rollbacks."""

    @classmethod
    def get_snapshots_dir(cls, bottle_id: str) -> Path:
        b_dir = BottleManager.get_bottle_dir(bottle_id)
        s_dir = b_dir / "snapshots"
        s_dir.mkdir(parents=True, exist_ok=True)
        return s_dir

    @classmethod
    def list_snapshots(cls, bottle_id: str) -> List[SnapshotInfo]:
        """Lists all snapshots for a bottle, sorted newest first."""
        s_dir = cls.get_snapshots_dir(bottle_id)
        snapshots = []
        if not s_dir.exists():
            return snapshots

        for item in s_dir.iterdir():
            if item.is_dir():
                meta_path = item / "snapshot.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            snapshots.append(SnapshotInfo(**data))
                    except Exception:
                        continue
        return sorted(snapshots, key=lambda s: s.created_at, reverse=True)

    @classmethod
    def create_snapshot(
        cls,
        bottle_id: str,
        name: str,
        description: str = ""
    ) -> SnapshotInfo:
        """
        [FR-33] Takes a point-in-time snapshot of the bottle's registry and metadata.
        """
        bottle = BottleManager.get_bottle(bottle_id)
        if not bottle:
            raise ValueError(f"Bottle '{bottle_id}' not found.")

        snap_id = f"snap-{uuid.uuid4().hex[:8]}"
        snap_dir = cls.get_snapshots_dir(bottle_id) / snap_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        b_dir = BottleManager.get_bottle_dir(bottle_id)

        # 1. Backup Registry Hives
        registry_files = ["system.reg", "user.reg", "userdef.reg"]
        for reg_file in registry_files:
            src = b_dir / reg_file
            if src.exists():
                shutil.copy2(src, snap_dir / reg_file)

        # 2. Backup bottle.json
        cfg_src = b_dir / "bottle.json"
        if cfg_src.exists():
            shutil.copy2(cfg_src, snap_dir / "bottle.json")

        # 3. Write snapshot metadata
        snap_info = SnapshotInfo(
            id=snap_id,
            bottle_id=bottle_id,
            name=name,
            description=description
        )
        with open(snap_dir / "snapshot.json", "w", encoding="utf-8") as f:
            json.dump(snap_info.model_dump(), f, indent=2)

        return snap_info

    @classmethod
    def rollback_snapshot(cls, bottle_id: str, snapshot_id: str) -> bool:
        """
        [FR-34, NFR-04] Restores registry hives and bottle.json from snapshot.
        """
        snap_dir = cls.get_snapshots_dir(bottle_id) / snapshot_id
        if not snap_dir.exists():
            raise ValueError(f"Snapshot '{snapshot_id}' does not exist.")

        b_dir = BottleManager.get_bottle_dir(bottle_id)

        # Restore registry files
        registry_files = ["system.reg", "user.reg", "userdef.reg"]
        for reg_file in registry_files:
            src = snap_dir / reg_file
            dst = b_dir / reg_file
            if src.exists():
                shutil.copy2(src, dst)

        # Restore bottle.json
        cfg_src = snap_dir / "bottle.json"
        if cfg_src.exists():
            shutil.copy2(cfg_src, b_dir / "bottle.json")

        return True

    @classmethod
    def delete_snapshot(cls, bottle_id: str, snapshot_id: str) -> bool:
        """Removes a snapshot directory."""
        snap_dir = cls.get_snapshots_dir(bottle_id) / snapshot_id
        if snap_dir.exists():
            shutil.rmtree(snap_dir, ignore_errors=True)
            return True
        return False
