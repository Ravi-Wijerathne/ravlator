"""
[FR-26, FR-27, FR-28] Game Store Integration & Known Workarounds Manager.
Supports guided deployment of official store installers (Steam, Epic Games, GOG Galaxy, EA App, Battle.net),
automatic stability argument injection (CEF workarounds), and native macOS Steam credential synchronization.
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
    website_url: str = ""


SUPPORTED_STORES: Dict[str, StoreDefinition] = {
    "steam": StoreDefinition(
        id="steam",
        name="Steam",
        download_url="https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe",
        installer_filename="SteamSetup.exe",
        relative_exe_path="Program Files (x86)/Steam/steam.exe",
        # [FR-27, Appendix B] Mandatory Chromium Embedded Framework workaround flags
        recommended_arguments="-no-cef-sandbox -cef-disable-gpu -noverifyfiles -allossearch",
        installer_args=["/S"],
        website_url="https://store.steampowered.com/about/"
    ),
    "epic": StoreDefinition(
        id="epic",
        name="Epic Games Launcher",
        download_url="https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncherInstaller.msi",
        installer_filename="EpicGamesLauncherInstaller.msi",
        relative_exe_path="Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win64/EpicGamesLauncher.exe",
        recommended_arguments="-SkipBuildPatchPrereq",
        installer_args=["/q"],
        website_url="https://store.epicgames.com/download"
    ),
    "gog": StoreDefinition(
        id="gog",
        name="GOG Galaxy",
        download_url="https://webinstallers.gog-statics.com/GOG_Galaxy_Setup.exe",
        installer_filename="GOGGalaxySetup.exe",
        relative_exe_path="Program Files (x86)/GOG Galaxy/GalaxyClient.exe",
        recommended_arguments="",
        installer_args=["/SILENT"],
        website_url="https://www.gog.com/galaxy"
    ),
    "ea": StoreDefinition(
        id="ea",
        name="EA App",
        download_url="https://origin-a.akamaihd.net/EA-Desktop-Client-Download/installer-releases/EAappInstaller.exe",
        installer_filename="EAappInstaller.exe",
        relative_exe_path="Program Files/Electronic Arts/EA Desktop/EA Desktop/EADesktop.exe",
        recommended_arguments="",
        installer_args=[],
        website_url="https://www.ea.com/ea-app"
    ),
    "battlenet": StoreDefinition(
        id="battlenet",
        name="Battle.net",
        download_url="https://www.battle.net/download/getInstaller?os=win&installer=Battle.net-Setup.exe",
        installer_filename="Battle.net-Setup.exe",
        relative_exe_path="Program Files (x86)/Battle.net/Battle.net.exe",
        recommended_arguments="",
        installer_args=[],
        website_url="https://download.battle.net/en-us/desktop"
    )
}


class StoreManager:
    """Orchestrates store client management, shortcuts, installer launching, and stability flags."""

    @classmethod
    def list_supported_stores(cls) -> List[StoreDefinition]:
        return list(SUPPORTED_STORES.values())

    @classmethod
    def get_store(cls, store_id: str) -> Optional[StoreDefinition]:
        return SUPPORTED_STORES.get(store_id.lower())

    @classmethod
    def get_store_exe_path(cls, bottle: BottleConfig, store_id: str) -> Optional[Path]:
        """Resolves the absolute path of a store executable in the bottle if it exists."""
        store = cls.get_store(store_id)
        if not store:
            return None
        b_dir = BottleManager.get_bottle_dir(bottle.id)
        primary = b_dir / "drive_c" / store.relative_exe_path
        if primary.exists():
            return primary

        # Alternate 64-bit / 32-bit path check
        if "Program Files (x86)" in store.relative_exe_path:
            alt = b_dir / "drive_c" / store.relative_exe_path.replace("Program Files (x86)", "Program Files")
            if alt.exists():
                return alt
        elif "Program Files" in store.relative_exe_path:
            alt = b_dir / "drive_c" / store.relative_exe_path.replace("Program Files", "Program Files (x86)")
            if alt.exists():
                return alt

        return None

    @classmethod
    def is_store_installed(cls, bottle: BottleConfig, store_id: str) -> bool:
        """Checks if the store client executable exists in the bottle's virtual C: drive."""
        return cls.get_store_exe_path(bottle, store_id) is not None

    @classmethod
    def detect_installed_stores(cls, bottle: BottleConfig) -> List[ProgramEntry]:
        """
        Scans bottle's drive_c for known installed game store clients.
        If found and not yet registered in bottle.programs, registers them with recommended flags.
        """
        detected: List[ProgramEntry] = []
        for store in cls.list_supported_stores():
            if cls.is_store_installed(bottle, store.id):
                entry = cls.register_store_program(bottle, store.id)
                detected.append(entry)
        return detected

    @classmethod
    def register_store_program(cls, bottle: BottleConfig, store_id: str) -> ProgramEntry:
        """Creates a ProgramEntry in bottle.programs for the store client with stability flags."""
        store = cls.get_store(store_id)
        if not store:
            raise ValueError(f"Unknown store '{store_id}'")

        exe_path = cls.get_store_exe_path(bottle, store_id)
        if not exe_path:
            b_dir = BottleManager.get_bottle_dir(bottle.id)
            abs_exe_path = str(b_dir / "drive_c" / store.relative_exe_path)
        else:
            abs_exe_path = str(exe_path)

        # Check if already registered
        for p in bottle.programs:
            if p.name.lower() == store.name.lower() or p.exe_path == abs_exe_path:
                # Ensure recommended arguments are present if currently empty
                if not p.arguments and store.recommended_arguments:
                    p.arguments = store.recommended_arguments
                    BottleManager.save_bottle_config(bottle)
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
    def launch_store_installer(cls, bottle: BottleConfig, installer_path: Path):
        """
        [FR-26, FR-28] Launches an official store installer (.exe or .msi) interactively
        inside the Wine environment with proper GUI feedback.
        """
        if not installer_path.exists():
            raise FileNotFoundError(f"Installer file not found at: {installer_path}")

        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        if not wine_bin.exists():
            raise RuntimeError(
                f"Wine runner '{bottle.runner_id}' is not installed locally.\n"
                "Please download it in 'Manage Runners' before executing installers."
            )

        return WineProcessManager.launch_process(bottle, installer_path)

    @classmethod
    def install_store(
        cls,
        bottle_id: str,
        store_id: str,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> ProgramEntry:
        """
        [FR-26, FR-27] Downloads the store setup binary, verifies runner availability,
        executes the installer, and registers the program entry with stability flags.
        """
        bottle = BottleManager.get_bottle(bottle_id)
        if not bottle:
            raise ValueError(f"Bottle '{bottle_id}' not found.")

        store = cls.get_store(store_id)
        if not store:
            raise ValueError(f"Unsupported store client '{store_id}'.")

        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        if not wine_bin.exists():
            raise RuntimeError(
                f"Wine runner '{bottle.runner_id}' is not installed locally. "
                "Please download the runner in 'Manage Runners' first."
            )

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
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)
        import subprocess
        cmd = [str(wine_bin), str(installer_path)] + store.installer_args
        subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Register Program Entry
        return cls.register_store_program(bottle, store_id)

    @classmethod
    def sync_native_steam_login(cls, bottle: BottleConfig) -> bool:
        """
        [SRS Section 8.2, Appendix B] Copies existing authentication tokens, configuration,
        registry hive, and userdata from native macOS Steam to bypass CEF black screens / login prompts.
        """
        mac_steam_dir = Path.home() / "Library" / "Application Support" / "Steam"
        if not mac_steam_dir.exists():
            raise FileNotFoundError(
                "Native macOS Steam directory was not found.\n"
                "Please install and log into the Mac Steam app first to populate the login cache."
            )

        bottle_dir = BottleManager.get_bottle_dir(bottle.id)
        p86_steam = bottle_dir / "drive_c" / "Program Files (x86)" / "Steam"
        p64_steam = bottle_dir / "drive_c" / "Program Files" / "Steam"

        target_dirs = []
        if p86_steam.exists():
            target_dirs.append(p86_steam)
        if p64_steam.exists():
            target_dirs.append(p64_steam)
        if not target_dirs:
            p86_steam.mkdir(parents=True, exist_ok=True)
            target_dirs.append(p86_steam)

        import shutil
        copied_any = False

        for b_steam_dir in target_dirs:
            # 1. Sync config/ directory (login tokens and user accounts)
            mac_config = mac_steam_dir / "config"
            b_config = b_steam_dir / "config"
            if mac_config.exists():
                b_config.mkdir(parents=True, exist_ok=True)
                for item in ["config.vdf", "loginusers.vdf", "DialogConfig.vdf"]:
                    src_file = mac_config / item
                    if src_file.exists():
                        shutil.copy2(src_file, b_config / item)
                        copied_any = True

            # 2. Sync registry.vdf (Valve's AutoLoginUser registry hive mapping)
            mac_reg = mac_steam_dir / "registry.vdf"
            if mac_reg.exists():
                shutil.copy2(mac_reg, b_steam_dir / "registry.vdf")
                copied_any = True

            # 3. Sync userdata/ directory
            mac_userdata = mac_steam_dir / "userdata"
            b_userdata = b_steam_dir / "userdata"
            if mac_userdata.exists():
                if b_userdata.exists():
                    shutil.rmtree(b_userdata, ignore_errors=True)
                shutil.copytree(mac_userdata, b_userdata, symlinks=True)
                copied_any = True

        # If Steam executable exists in the bottle, ensure it is registered in bottle.programs with CEF stability flags
        if cls.is_store_installed(bottle, "steam"):
            cls.register_store_program(bottle, "steam")

        return copied_any
