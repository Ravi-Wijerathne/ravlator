"""
[SRS Section 9 Phase 4] Cloud Save Synchronization Integration.
Symlinks Wine save game directories (Saved Games, Documents/My Games)
to macOS iCloud Drive, Google Drive, or cloud storage providers.
Decoupled from GUI frameworks.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from ravlator.core.bottle import BottleManager
from ravlator.core.models import BottleConfig


class CloudSaveManager:
    """Manages cross-device game save synchronization with macOS cloud providers."""

    @classmethod
    def get_cloud_providers(cls) -> Dict[str, Path]:
        """Detects active cloud storage services on macOS."""
        home = Path.home()
        providers = {}

        # 1. Apple iCloud Drive
        icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        if icloud.exists():
            providers["iCloud Drive"] = icloud

        # 2. Google Drive / OneDrive / Dropbox in CloudStorage
        cloud_storage = home / "Library" / "CloudStorage"
        if cloud_storage.exists():
            for item in cloud_storage.iterdir():
                if "googledrive" in item.name.lower():
                    providers["Google Drive"] = item
                elif "onedrive" in item.name.lower():
                    providers["OneDrive"] = item
                elif "dropbox" in item.name.lower():
                    providers["Dropbox"] = item

        # Direct folder fallbacks
        if (home / "Google Drive").exists():
            providers["Google Drive"] = home / "Google Drive"
        if (home / "Dropbox").exists():
            providers["Dropbox"] = home / "Dropbox"
        if (home / "OneDrive").exists():
            providers["OneDrive"] = home / "OneDrive"

        return providers

    @classmethod
    def get_save_directories(cls, bottle: BottleConfig) -> List[Path]:
        """Returns standard Windows save game locations in the prefix."""
        b_dir = BottleManager.get_bottle_dir(bottle.id)
        user_dir = b_dir / "drive_c" / "users" / "crossover"
        
        candidates = [
            user_dir / "Saved Games",
            user_dir / "Documents" / "My Games",
            user_dir / "AppData" / "Roaming"
        ]
        return candidates

    @classmethod
    def is_sync_enabled(cls, bottle: BottleConfig) -> bool:
        """Checks if standard save folders in the bottle are symlinked to cloud storage."""
        save_dirs = cls.get_save_directories(bottle)
        for s in save_dirs:
            if s.is_symlink():
                return True
        return False

    @classmethod
    def enable_sync(cls, bottle: BottleConfig, provider_name: str = "iCloud Drive") -> Path:
        """
        [SRS Section 9 Phase 4] Migrates existing save data and creates symlinks
        pointing to the chosen cloud sync provider.
        """
        providers = cls.get_cloud_providers()
        if provider_name not in providers:
            raise FileNotFoundError(f"Cloud provider '{provider_name}' is not active on this Mac.")

        cloud_root = providers[provider_name] / "RavlatorSaves" / bottle.id
        cloud_root.mkdir(parents=True, exist_ok=True)

        save_dirs = cls.get_save_directories(bottle)
        for s_dir in save_dirs[:2]:  # Saved Games and My Games
            s_dir.parent.mkdir(parents=True, exist_ok=True)
            cloud_target = cloud_root / s_dir.name

            if s_dir.is_symlink():
                continue

            if s_dir.exists():
                # Move contents to cloud target if not already present
                if not cloud_target.exists():
                    shutil.copytree(s_dir, cloud_target, symlinks=True)
                shutil.rmtree(s_dir)
            else:
                cloud_target.mkdir(parents=True, exist_ok=True)

            # Create symlink pointing into iCloud Drive
            s_dir.symlink_to(cloud_target)

        return cloud_root

    @classmethod
    def disable_sync(cls, bottle: BottleConfig) -> bool:
        """Reverts cloud symlinks back to local directories inside the bottle."""
        save_dirs = cls.get_save_directories(bottle)
        reverted = False
        for s_dir in save_dirs:
            if s_dir.is_symlink():
                target = s_dir.resolve()
                s_dir.unlink()
                if target.exists():
                    shutil.copytree(target, s_dir, symlinks=True)
                else:
                    s_dir.mkdir(parents=True, exist_ok=True)
                reverted = True
        return reverted
