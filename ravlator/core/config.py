"""
[NFR-04, NFR-06] Central Configuration and Path Management for Ravlator.
Handles filesystem paths adhering to macOS standards (~/Library/Application Support/Ravlator).
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import json


class Config:
    """Manages application paths and persistent global settings."""
    
    # Environment variable override for automated testing
    ENV_DATA_DIR = "RAVLATOR_DATA_DIR"
    
    @classmethod
    def get_base_dir(cls) -> Path:
        """Returns the root data directory for Ravlator on macOS."""
        override = os.environ.get(cls.ENV_DATA_DIR)
        if override:
            base = Path(override).expanduser().resolve()
        else:
            base = Path("~/Library/Application Support/Ravlator").expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def get_bottles_dir(cls) -> Path:
        path = cls.get_base_dir() / "Bottles"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_runners_dir(cls) -> Path:
        path = cls.get_base_dir() / "Runners"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_cache_dir(cls) -> Path:
        path = cls.get_base_dir() / "Cache"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_recipes_dir(cls) -> Path:
        path = cls.get_base_dir() / "Recipes"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_config_file(cls) -> Path:
        return cls.get_base_dir() / "config.json"

    @classmethod
    def load_global_settings(cls) -> Dict[str, Any]:
        cfg_file = cls.get_config_file()
        if not cfg_file.exists():
            default_settings = {
                "default_runner": "gptk-2.0",
                "check_updates": True,
                "theme_mode": "light",
                "active_bottle_id": None
            }
            cls.save_global_settings(default_settings)
            return default_settings
        
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def save_global_settings(cls, settings: Dict[str, Any]) -> None:
        """Atomic write of global settings to prevent corruption."""
        cfg_file = cls.get_config_file()
        tmp_file = cfg_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        tmp_file.replace(cfg_file)
