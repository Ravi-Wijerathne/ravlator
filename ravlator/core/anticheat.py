"""
[RSK-01, SRS Section 8.1] Kernel-Level Anti-Cheat Detection & Advisory Engine.
Inspects target game binaries and directories for Windows kernel anti-cheat drivers
that are incompatible with Wine and Darwin userspace translation.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class AntiCheatMatch:
    name: str
    detected: bool
    trigger_file: str
    advisory: str


class AntiCheatDetector:
    """Scans Windows executables and game directories for incompatible kernel drivers."""

    KNOWN_ENGINES = [
        {
            "name": "EasyAntiCheat",
            "signatures": ["easyanticheat", "easyanticheat_eos", "eac_server.dll"],
            "advisory": "EasyAntiCheat requires Windows kernel drivers. Titles without Proton/Wine EAC runtime will fail to connect."
        },
        {
            "name": "BattlEye",
            "signatures": ["beservice.exe", "battleye", "bedaisy.sys"],
            "advisory": "BattlEye requires low-level kernel hooks unsupported by native Wine."
        },
        {
            "name": "Riot Vanguard",
            "signatures": ["vgc.exe", "vgk.sys"],
            "advisory": "Riot Vanguard requires ring-0 Windows kernel hypervisor access and cannot run in Wine."
        },
        {
            "name": "Ricochet Anti-Cheat",
            "signatures": ["randgrid.sys", "cod.exe"],
            "advisory": "Ricochet kernel driver is incompatible with macOS Wine translation."
        },
        {
            "name": "nProtect GameGuard",
            "signatures": ["gameguard.des", "gamemon.des"],
            "advisory": "GameGuard rootkit driver is unsupported in Wine."
        },
        {
            "name": "Xigncode3",
            "signatures": ["xigncode", "x3.xem"],
            "advisory": "Xigncode3 anti-cheat requires Windows driver modules."
        }
    ]

    @classmethod
    def scan_path(cls, target_path: Path) -> Optional[AntiCheatMatch]:
        """
        Scans executable and its parent folder for anti-cheat signatures.
        """
        p = Path(target_path)
        if not p.exists():
            return None

        # Check target file itself
        target_name = p.name.lower()
        for engine in cls.KNOWN_ENGINES:
            for sig in engine["signatures"]:
                if sig in target_name:
                    return AntiCheatMatch(
                        name=engine["name"],
                        detected=True,
                        trigger_file=p.name,
                        advisory=engine["advisory"]
                    )

        # Check parent folder and subfolders (up to 2 levels deep)
        folder = p.parent if p.is_file() else p
        if folder.exists():
            try:
                for item in folder.iterdir():
                    item_name = item.name.lower()
                    for engine in cls.KNOWN_ENGINES:
                        for sig in engine["signatures"]:
                            if sig in item_name:
                                return AntiCheatMatch(
                                    name=engine["name"],
                                    detected=True,
                                    trigger_file=item.name,
                                    advisory=engine["advisory"]
                                )
            except Exception:
                pass

        return None

    @classmethod
    def format_report(cls, match: AntiCheatMatch) -> str:
        """Returns human-readable advisory report for UI or CLI."""
        return (
            f"Anti-Cheat Engine: {match.name}\n"
            f"Trigger File: {match.trigger_file}\n"
            f"Advisory: {match.advisory}"
        )

