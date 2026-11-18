"""
[FR-01, FR-02, FR-03, FR-04, FR-05, FR-06] Bottle Lifecycle Manager.
Pure Python, strictly decoupled from GUI. Manages WINEPREFIX directories.
"""

import json
import re
import shutil
from pathlib import Path
from typing import List, Optional
import uuid

from ravlator.core.config import Config
from ravlator.core.models import BottleConfig, PresetType, WindowsVersion, GraphicsBackend


class BottleManager:
    """Manages the creation, cloning, deletion, and configuration of Wine bottles."""

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitizes bottle name for safe filesystem usage."""
        sanitized = re.sub(r'[^\w\s-]', '', name).strip()
        sanitized = re.sub(r'[-\s]+', '-', sanitized)
        return sanitized or f"bottle-{uuid.uuid4().hex[:6]}"

    @classmethod
    def get_bottle_dir(cls, bottle_id: str) -> Path:
        return Config.get_bottles_dir() / bottle_id

    @classmethod
    def get_bottle_config_path(cls, bottle_id: str) -> Path:
        return cls.get_bottle_dir(bottle_id) / "bottle.json"

    @classmethod
    def list_bottles(cls) -> List[BottleConfig]:
        """Scans the Bottles directory and returns all valid bottle configurations."""
        bottles = []
        bottles_dir = Config.get_bottles_dir()
        if not bottles_dir.exists():
            return bottles

        for item in bottles_dir.iterdir():
            if item.is_dir():
                cfg_path = item / "bottle.json"
                if cfg_path.exists():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            bottles.append(BottleConfig(**data))
                    except Exception:
                        continue
        return sorted(bottles, key=lambda b: b.name.lower())

    @classmethod
    def get_bottle(cls, bottle_id: str) -> Optional[BottleConfig]:
        cfg_path = cls.get_bottle_config_path(bottle_id)
        if not cfg_path.exists():
            return None
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return BottleConfig(**data)
        except Exception:
            return None

    @classmethod
    def save_bottle_config(cls, config: BottleConfig) -> None:
        """Atomic write of bottle.json [NFR-04]."""
        b_dir = cls.get_bottle_dir(config.id)
        b_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = b_dir / "bottle.json"
        tmp_path = cfg_path.with_suffix(".tmp")
        
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2)
        tmp_path.replace(cfg_path)

    @classmethod
    def create_bottle(
        cls,
        name: str,
        preset: PresetType = PresetType.GAMING,
        runner_id: str = "gptk-2.0",
        windows_version: WindowsVersion = WindowsVersion.WIN10
    ) -> BottleConfig:
        """
        [FR-01, FR-02] Creates a new isolated bottle directory hierarchy.
        """
        bottle_id = cls.sanitize_name(name)
        b_dir = cls.get_bottle_dir(bottle_id)
        
        if b_dir.exists():
            # If already exists, append unique suffix
            bottle_id = f"{bottle_id}-{uuid.uuid4().hex[:4]}"
            b_dir = cls.get_bottle_dir(bottle_id)

        # Apply preset configurations [FR-02]
        if preset == PresetType.GAMING:
            msync = True
            esync = False
            metal_hud = False
            retina = True
            backend = GraphicsBackend.D3DMETAL
            dll_overrides = {
                "d3d11": "native,builtin",
                "d3d12": "native,builtin",
                "dxgi": "native,builtin"
            }
        elif preset == PresetType.PRODUCTIVITY:
            msync = False
            esync = False
            metal_hud = False
            retina = True
            backend = GraphicsBackend.WINED3D
            dll_overrides = {}
        else:  # Custom
            msync = True
            esync = False
            metal_hud = False
            retina = True
            backend = GraphicsBackend.D3DMETAL
            dll_overrides = {}

        config = BottleConfig(
            id=bottle_id,
            name=name,
            preset=preset,
            runner_id=runner_id,
            windows_version=windows_version,
            graphics_backend=backend,
            msync=msync,
            esync=esync,
            metal_hud=metal_hud,
            retina=retina,
            dll_overrides=dll_overrides
        )

        try:
            # Create prefix skeleton [Appendix C]
            b_dir.mkdir(parents=True, exist_ok=True)
            drive_c = b_dir / "drive_c"
            drive_c.mkdir(parents=True, exist_ok=True)
            (drive_c / "Program Files").mkdir(parents=True, exist_ok=True)
            (drive_c / "Program Files (x86)").mkdir(parents=True, exist_ok=True)
            (drive_c / "users" / "crossover").mkdir(parents=True, exist_ok=True)
            (drive_c / "windows" / "system32").mkdir(parents=True, exist_ok=True)

            # dosdevices directory
            dosdevices = b_dir / "dosdevices"
            dosdevices.mkdir(parents=True, exist_ok=True)
            c_link = dosdevices / "c:"
            if not c_link.exists():
                c_link.symlink_to("../drive_c")
            z_link = dosdevices / "z:"
            if not z_link.exists():
                z_link.symlink_to("/")

            cls.save_bottle_config(config)
            return config
        except Exception as e:
            # Cleanup corrupt partial files [NFR-04]
            if b_dir.exists():
                shutil.rmtree(b_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to initialize bottle '{name}': {e}") from e

    @classmethod
    def delete_bottle(cls, bottle_id: str) -> bool:
        """[FR-04] Permanently deletes a bottle directory."""
        b_dir = cls.get_bottle_dir(bottle_id)
        if b_dir.exists():
            shutil.rmtree(b_dir, ignore_errors=True)
            return True
        return False

    @classmethod
    def duplicate_bottle(cls, source_id: str, new_name: str) -> BottleConfig:
        """[FR-03] Clones an existing bottle to a new independent prefix."""
        source = cls.get_bottle(source_id)
        if not source:
            raise ValueError(f"Source bottle '{source_id}' does not exist.")

        new_config = cls.create_bottle(
            name=new_name,
            preset=source.preset,
            runner_id=source.runner_id,
            windows_version=source.windows_version
        )
        
        # Copy drive_c contents over
        src_drive_c = cls.get_bottle_dir(source_id) / "drive_c"
        dst_drive_c = cls.get_bottle_dir(new_config.id) / "drive_c"
        if src_drive_c.exists():
            shutil.rmtree(dst_drive_c, ignore_errors=True)
            shutil.copytree(src_drive_c, dst_drive_c, symlinks=True)

        # Retain source configuration overrides and programs
        new_config.graphics_backend = source.graphics_backend
        new_config.msync = source.msync
        new_config.esync = source.esync
        new_config.metal_hud = source.metal_hud
        new_config.retina = source.retina
        new_config.dll_overrides = dict(source.dll_overrides)
        new_config.programs = list(source.programs)
        new_config.installed_dependencies = list(source.installed_dependencies)
        cls.save_bottle_config(new_config)
        return new_config
