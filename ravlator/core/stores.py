"""
[FR-26, FR-27, FR-28] Game Store Integration & Known Workarounds Manager.
Supports automated 1-click deployment of Steam, Epic Games, and GOG Galaxy.
Decoupled from GUI frameworks.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Callable
import uuid

from ravlator.core.bottle import BottleManager
from ravlator.core.config import Config
from ravlator.core.downloader import FileDownloader, DownloadProgress
from ravlator.core.models import BottleConfig, ProgramEntry
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.runner import RunnerManager


@dataclass
class StoreDefinition:
    id: str
    name: str
    download_url: str
    installer_filename: str
    relative_exe_path: str
    recommended_arguments: str
    installer_args: List[str]


SUPPORTED_STORES: Dict[str, StoreDefinition] = {
    "steam": StoreDefinition(
        id="steam",
        name="Steam",
        download_url="https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe",
        installer_filename="SteamSetup.exe",
        relative_exe_path="Program Files (x86)/Steam/steam.exe",
        # [FR-27, Appendix B] Mandatory Chromium Embedded Framework workaround flags
        recommended_arguments="-no-cef-sandbox -cef-disable-gpu -noverifyfiles -allossearch",
        installer_args=["/S"]
    ),
    "epic": StoreDefinition(
        id="epic",
        name="Epic Games Launcher",
        download_url="https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncherInstaller.msi",
        installer_filename="EpicGamesLauncherInstaller.msi",
        relative_exe_path="Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win64/EpicGamesLauncher.exe",
        recommended_arguments="-SkipBuildPatchPrereq",
        installer_args=["/q"]
    ),
    "gog": StoreDefinition(
        id="gog",
        name="GOG Galaxy",
        download_url="https://webinstallers.gog-statics.com/GOG_Galaxy_Setup.exe",
        installer_filename="GOGGalaxySetup.exe",
        relative_exe_path="Program Files (x86)/GOG Galaxy/GalaxyClient.exe",
        recommended_arguments="",
        installer_args=["/SILENT"]
    )
}


class StoreManager:
    """Orchestrates store client installation, shortcuts, and stability flags."""

    @classmethod
    def list_supported_stores(cls) -> List[StoreDefinition]:
        return list(SUPPORTED_STORES.values())

    @classmethod
    def get_store(cls, store_id: str) -> Optional[StoreDefinition]:
        return SUPPORTED_STORES.get(store_id.lower())

    @classmethod
    def is_store_installed(cls, bottle: BottleConfig, store_id: str) -> bool:
        """Checks if the store client executable exists in the bottle's virtual C: drive."""
        store = cls.get_store(store_id)
        if not store:
            return False
        b_dir = BottleManager.get_bottle_dir(bottle.id)
        exe_path = b_dir / "drive_c" / store.relative_exe_path
        return exe_path.exists()

    @classmethod
    def register_store_program(cls, bottle: BottleConfig, store_id: str) -> ProgramEntry:
        """Creates a ProgramEntry in bottle.programs for the store client."""
        store = cls.get_store(store_id)
        if not store:
            raise ValueError(f"Unknown store '{store_id}'")

        b_dir = BottleManager.get_bottle_dir(bottle.id)
        abs_exe_path = str(b_dir / "drive_c" / store.relative_exe_path)

        # Check if already registered
        for p in bottle.programs:
            if p.name.lower() == store.name.lower() or p.exe_path == abs_exe_path:
                return p

        entry = ProgramEntry(
            id=f"{store.id}-{uuid.uuid4().hex[:6]}",
            name=store.name,
            exe_path=abs_exe_path,
            arguments=store.recommended_arguments,
            working_dir=str(Path(abs_exe_path).parent)
        )
        bottle.programs.append(entry)
        BottleManager.save_bottle_config(bottle)
        return entry

    @classmethod
    def install_store(
        cls,
        bottle_id: str,
        store_id: str,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> ProgramEntry:
        """
        [FR-26, FR-27] Downloads the store setup binary, runs installation inside Wine,
        and registers the program entry with necessary stability flags.
        """
        bottle = BottleManager.get_bottle(bottle_id)
        if not bottle:
            raise ValueError(f"Bottle '{bottle_id}' not found.")

        store = cls.get_store(store_id)
        if not store:
            raise ValueError(f"Unsupported store client '{store_id}'.")

        cache_dir = Config.get_cache_dir() / "stores"
        installer_path = cache_dir / store.installer_filename

        # 1. Download Store Setup Binary
        FileDownloader.download_file(
            url=store.download_url,
            dest_path=installer_path,
            progress_callback=progress_callback,
            cancel_check=cancel_check
        )

        # 2. Run installer via Wine
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)

        if wine_bin.exists():
            import subprocess
            cmd = [str(wine_bin), str(installer_path)] + store.installer_args
            subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Register Program Entry
        return cls.register_store_program(bottle, store_id)
