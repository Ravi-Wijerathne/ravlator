"""
[FR-01, FR-02, FR-07, FR-12, FR-17] Data models and schemas for Ravlator.
Strictly decoupled from GUI frameworks.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PresetType(str, Enum):
    GAMING = "gaming"
    PRODUCTIVITY = "productivity"
    CUSTOM = "custom"


class WindowsVersion(str, Enum):
    WIN11 = "win11"
    WIN10 = "win10"
    WIN7 = "win7"


class GraphicsBackend(str, Enum):
    D3DMETAL = "d3dmetal"
    DXVK = "dxvk"
    DXMT = "dxmt"
    WINED3D = "wined3d"


class ProgramEntry(BaseModel):
    """Represents a configured executable inside a bottle [FR-22]."""
    id: str
    name: str
    exe_path: str
    arguments: str = ""
    working_dir: str = ""
    icon_path: Optional[str] = None
    environment_overrides: Dict[str, str] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BottleConfig(BaseModel):
    """
    [FR-01, FR-02] Persisted configuration for an isolated Wine prefix (bottle.json).
    Adheres strictly to SRS Section 3 and Appendix C.
    """
    id: str
    name: str
    preset: PresetType = PresetType.GAMING
    runner_id: str = "gptk-2.0"
    windows_version: WindowsVersion = WindowsVersion.WIN10
    
    # Graphics and Synchronization Flags [FR-12, FR-13, FR-14, FR-15, FR-16]
    graphics_backend: GraphicsBackend = GraphicsBackend.D3DMETAL
    msync: bool = True
    esync: bool = False
    metal_hud: bool = False
    retina: bool = True
    dxvk_hud: str = ""
    wine_debug: str = "fixme-all"
    
    # Virtual Desktop & Resolution [FR-16]
    virtual_desktop: bool = False
    virtual_desktop_res: str = "1920x1080"
    
    # DLL Overrides [FR-09]
    dll_overrides: Dict[str, str] = Field(default_factory=lambda: {
        "d3d11": "native,builtin",
        "d3d12": "native,builtin",
        "dxgi": "native,builtin"
    })
    
    # Executable shortcuts and dependencies
    programs: List[ProgramEntry] = Field(default_factory=list)
    installed_dependencies: List[str] = Field(default_factory=list)
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_launched_at: Optional[str] = None


class RunnerInfo(BaseModel):
    """
    [FR-07, FR-08, FR-10] Representation of an execution runner (Wine-CX / GPTK 2).
    """
    id: str
    name: str
    version: str
    path: str
    source_type: str = "cdn"  # 'cdn' or 'local'
    sha256: Optional[str] = None
    download_url: Optional[str] = None
    has_d3dmetal: bool = True
    is_installed: bool = False


class DependencyRecipe(BaseModel):
    """
    [FR-17, FR-18] Recipe definition for automated runtime dependency installation.
    """
    id: str
    name: str
    category: str
    description: str
    download_url: str
    sha256: str
    installer_args: List[str] = Field(default_factory=list)
    required_dll_overrides: Dict[str, str] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
