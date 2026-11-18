"""
[FR-12, FR-13, FR-14, FR-15, FR-16, FR-21, FR-27, FR-30, FR-31]
Process & Environment Execution Engine for Wine and macOS Darwin.
Decoupled from GUI frameworks.
"""

import os
import subprocess
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Callable

from ravlator.core.config import Config
from ravlator.core.models import BottleConfig, RunnerInfo


class WineEnvironmentBuilder:
    """Constructs isolated environment variables adhering to Appendix A & SRS Section 7.4."""

    @classmethod
    def build_env(cls, bottle: BottleConfig, runner_path: Path) -> Dict[str, str]:
        env = os.environ.copy()
        
        # Mandatory Wine Prefix Isolation [Appendix C]
        prefix_dir = Config.get_bottles_dir() / bottle.id
        env["WINEPREFIX"] = str(prefix_dir)
        env["WINEARCH"] = "win64"
        
        # Synchronization Primitives [FR-14, FR-15]
        env["WINEMSYNC"] = "1" if bottle.msync else "0"
        env["WINEESYNC"] = "1" if bottle.esync else "0"
        
        # macOS Graphics Translation Flags [FR-12, FR-13, FR-16]
        env["MTL_HUD_ENABLED"] = "1" if bottle.metal_hud else "0"
        env["WINE_DPI_AWARE"] = "1" if bottle.retina else "0"
        if bottle.dxvk_hud:
            env["DXVK_HUD"] = bottle.dxvk_hud
            
        env["WINEDEBUG"] = bottle.wine_debug or "fixme-all"

        # Construct DLL Overrides string [FR-09]
        if bottle.dll_overrides:
            override_entries = [f"{dll}={mode}" for dll, mode in bottle.dll_overrides.items()]
            env["WINEDLLOVERRIDES"] = ";".join(override_entries)

        # Dynamic Linker Path for Apple D3DMetal & MoltenVK [SRS Section 7.4]
        lib_dirs = [
            str(runner_path / "lib"),
            str(runner_path / "lib64"),
            "/usr/lib"
        ]
        env["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(lib_dirs)
        
        return env


class WineProcessManager:
    """Manages spawning, streaming, and terminating Wine processes."""

    @classmethod
    def inject_steam_cef_workaround(cls, exe_path: str, args: List[str]) -> List[str]:
        """
        [FR-27, Appendix B] Automatically injects Chromium Embedded Framework (CEF)
        crash mitigation flags when launching Steam.
        """
        if "steam.exe" in exe_path.lower():
            cef_flags = ["-no-cef-sandbox", "-cef-disable-gpu", "-noverifyfiles", "-allossearch"]
            # Append flags if not already present
            merged = list(args)
            for flag in cef_flags:
                if flag not in merged:
                    merged.append(flag)
            return merged
        return args

    @classmethod
    def get_wine_bin(cls, runner_path: Path) -> Path:
        """Locates the 64-bit Wine executable in the runner directory."""
        candidates = [
            runner_path / "bin" / "wine64",
            runner_path / "bin" / "wine"
        ]
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]

    @classmethod
    def get_wineserver_bin(cls, runner_path: Path) -> Path:
        """Locates the wineserver executable."""
        candidates = [
            runner_path / "bin" / "wineserver"
        ]
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]

    @classmethod
    def stop_bottle(cls, bottle: BottleConfig, runner_path: Path) -> int:
        """[FR-30] Gracefully signals running Windows apps to terminate via wineboot -s."""
        wine_bin = cls.get_wine_bin(runner_path)
        env = WineEnvironmentBuilder.build_env(bottle, runner_path)
        wineboot = wine_bin.parent / "wineboot"
        
        cmd = [str(wineboot if wineboot.exists() else wine_bin), "wineboot", "-s"]
        try:
            res = subprocess.run(cmd, env=env, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode
        except Exception:
            return -1

    @classmethod
    def force_kill_bottle(cls, bottle: BottleConfig, runner_path: Path) -> int:
        """[FR-31] Immediately terminates the wineserver socket and all child processes."""
        wineserver = cls.get_wineserver_bin(runner_path)
        env = WineEnvironmentBuilder.build_env(bottle, runner_path)
        
        cmd = [str(wineserver), "-k"]
        try:
            res = subprocess.run(cmd, env=env, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode
        except Exception:
            return -1
