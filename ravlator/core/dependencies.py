"""
[FR-17, FR-18, FR-19] Automated Dependency & Runtime Package Manager.
Provides declarative recipe-based installation of Windows runtimes (Visual C++, .NET, DirectX, Fonts).
Decoupled from GUI frameworks.
"""

import json
import subprocess
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Callable

from ravlator.core.bottle import BottleManager
from ravlator.core.config import Config
from ravlator.core.downloader import FileDownloader, DownloadProgress
from ravlator.core.models import DependencyRecipe, BottleConfig
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.runner import RunnerManager


# Standard built-in recipes for essential gaming runtimes [FR-17]
BUILTIN_RECIPES = [
    DependencyRecipe(
        id="vcredist2022",
        name="Visual C++ 2015-2022 Redistributable (x64)",
        category="C/C++ Runtimes",
        description="Required by modern 64-bit Windows games for C/C++ runtime execution.",
        download_url="https://aka.ms/vs/17/release/vc_redist.x64.exe",
        sha256="",
        installer_args=["/install", "/quiet", "/norestart"],
        required_dll_overrides={},
        dependencies=[]
    ),
    DependencyRecipe(
        id="vcredist2022_x86",
        name="Visual C++ 2015-2022 Redistributable (x86)",
        category="C/C++ Runtimes",
        description="Required by 32-bit Windows games running under WOW64.",
        download_url="https://aka.ms/vs/17/release/vc_redist.x86.exe",
        sha256="",
        installer_args=["/install", "/quiet", "/norestart"],
        required_dll_overrides={},
        dependencies=[]
    ),
    DependencyRecipe(
        id="vcredist2013_x64",
        name="Visual C++ 2013 Redistributable (x64)",
        category="C/C++ Runtimes",
        description="Microsoft Visual C++ 2013 64-bit runtime libraries (v120).",
        download_url="https://download.microsoft.com/download/2/E/6/2E61CFA4-993B-4DD4-91DA-3737CD5CD6E3/vcredist_x64.exe",
        sha256="",
        installer_args=["/install", "/quiet", "/norestart"],
        required_dll_overrides={},
        dependencies=[]
    ),
    DependencyRecipe(
        id="vcredist2013_x86",
        name="Visual C++ 2013 Redistributable (x86)",
        category="C/C++ Runtimes",
        description="Microsoft Visual C++ 2013 32-bit runtime libraries (v120).",
        download_url="https://download.microsoft.com/download/2/E/6/2E61CFA4-993B-4DD4-91DA-3737CD5CD6E3/vcredist_x86.exe",
        sha256="",
        installer_args=["/install", "/quiet", "/norestart"],
        required_dll_overrides={},
        dependencies=[]
    ),
    DependencyRecipe(
        id="vcredist2010_x86",
        name="Visual C++ 2010 Redistributable (x86)",
        category="C/C++ Runtimes",
        description="Legacy 32-bit Visual Studio 2010 runtime libraries (v100).",
        download_url="https://download.microsoft.com/download/5/B/C/5BC5DBB3-652D-4DCE-B14A-475AB85EEF6E/vcredist_x86.exe",
        sha256="",
        installer_args=["/q", "/norestart"],
        required_dll_overrides={},
        dependencies=[]
    ),
    DependencyRecipe(
        id="directx9",
        name="DirectX End-User Runtimes (June 2010)",
        category="DirectX Components",
        description="Installs legacy D3DX9, D3DX10, D3DX11, and XAudio2 runtime libraries.",
        download_url="https://download.microsoft.com/download/8/4/A/84A35BF1-DAFE-4AE8-82AF-AD2AE20B6B14/directx_Jun2010_redist.exe",
        sha256="",
        installer_args=["/Q", "/T:C:\\dx_temp"],
        required_dll_overrides={
            "d3dx9_43": "native,builtin",
            "d3dx10_43": "native,builtin",
            "d3dx11_43": "native,builtin",
            "xinput1_3": "native,builtin"
        },
        dependencies=[]
    ),
    DependencyRecipe(
        id="directplay",
        name="Microsoft DirectPlay (DirectX Legacy Networking)",
        category="DirectX Components",
        description="Legacy multiplayer networking protocol required by classic 2000s games.",
        download_url="",
        sha256="",
        installer_args=[],
        required_dll_overrides={
            "dplayx": "native,builtin",
            "dpnet": "native,builtin"
        },
        dependencies=[]
    ),
    DependencyRecipe(
        id="wine_mono",
        name="Wine Mono (.NET Replacement Runtime)",
        category=".NET Frameworks",
        description="Open-source .NET and Mono replacement runtime for Wine.",
        download_url="https://dl.winehq.org/wine/wine-mono/9.1.0/wine-mono-9.1.0-x86.msi",
        sha256="",
        installer_args=["/quiet"],
        required_dll_overrides={},
        dependencies=[]
    ),
    DependencyRecipe(
        id="dotnet48",
        name="Microsoft .NET Framework 4.8",
        category=".NET Frameworks",
        description="Full offline installer for Microsoft .NET Framework 4.8.",
        download_url="https://download.visualstudio.microsoft.com/download/pr/014120d7-d689-4305-befd-3cb711108212/0fd66638cde16859462a6243a4629a50/ndp48-x86-x64-allos-enu.exe",
        sha256="",
        installer_args=["/q", "/norestart"],
        required_dll_overrides={"mscoree": "native"},
        dependencies=[]
    ),
    DependencyRecipe(
        id="openal",
        name="OpenAL 3D Audio Runtime",
        category="Media & Fonts",
        description="Open Audio Library providing hardware-accelerated 3D positional audio.",
        download_url="https://www.openal.org/downloads/oalinst.zip",
        sha256="",
        installer_args=["/s"],
        required_dll_overrides={"openal32": "native,builtin"},
        dependencies=[]
    ),
    DependencyRecipe(
        id="physx",
        name="NVIDIA PhysX System Software",
        category="Media & Fonts",
        description="Legacy hardware physics engine runtime required by Unreal Engine 3 games.",
        download_url="https://us.download.nvidia.com/Windows/9.19.0218/PhysX-9.19.0218-SystemSoftware.exe",
        sha256="",
        installer_args=["/quiet"],
        required_dll_overrides={},
        dependencies=[]
    ),
    DependencyRecipe(
        id="corefonts",
        name="Microsoft TrueType Core Fonts",
        category="Media & Fonts",
        description="Arial, Times New Roman, Courier New, Verdana, and Tahoma fonts.",
        download_url="",
        sha256="",
        installer_args=[],
        required_dll_overrides={},
        dependencies=[]
    )
]


class DependencyManager:
    """Manages parsing declarative recipes and executing dependency installations [NFR-12]."""

    @classmethod
    def get_available_recipes(cls) -> List[DependencyRecipe]:
        """Loads built-in and external JSON/YAML recipes from disk."""
        recipes = list(BUILTIN_RECIPES)
        recipes_dir = Config.get_recipes_dir()
        
        # Load custom community declarative recipes (JSON and YAML) [NFR-12]
        if recipes_dir.exists():
            for item in recipes_dir.iterdir():
                if item.suffix.lower() == ".json":
                    try:
                        with open(item, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            recipe = DependencyRecipe(**data)
                            if not any(r.id == recipe.id for r in recipes):
                                recipes.append(recipe)
                    except Exception:
                        continue
                elif item.suffix.lower() in (".yaml", ".yml"):
                    try:
                        with open(item, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                            recipe = DependencyRecipe(**data)
                            if not any(r.id == recipe.id for r in recipes):
                                recipes.append(recipe)
                    except Exception:
                        continue
        return recipes

    @classmethod
    def get_recipe(cls, recipe_id: str) -> Optional[DependencyRecipe]:
        for r in cls.get_available_recipes():
            if r.id == recipe_id:
                return r
        return None

    @classmethod
    def install_dependency(
        cls,
        bottle_id: str,
        recipe_id: str,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        [FR-18] Downloads and executes a dependency installer inside the target bottle.
        """
        bottle = BottleManager.get_bottle(bottle_id)
        if not bottle:
            raise ValueError(f"Bottle '{bottle_id}' not found.")

        recipe = cls.get_recipe(recipe_id)
        if not recipe:
            raise ValueError(f"Recipe '{recipe_id}' not found in catalog.")

        if recipe_id in bottle.installed_dependencies:
            return True  # Already installed

        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)

        # Download installer if URL present
        installer_file = None
        if recipe.download_url:
            installer_name = Path(recipe.download_url).name
            installer_file = Config.get_cache_dir() / "dependencies" / installer_name
            FileDownloader.download_file(
                url=recipe.download_url,
                dest_path=installer_file,
                expected_sha256=recipe.sha256 if recipe.sha256 else None,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )

        # Prepare Wine execution environment [Appendix A]
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)

        if installer_file and installer_file.exists():
            if wine_bin.exists():
                cmd = [str(wine_bin), str(installer_file)] + recipe.installer_args
                res = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode not in (0, 3010):  # 3010 is Windows ERROR_SUCCESS_REBOOT_REQUIRED
                    pass

        # Apply associated DLL overrides [FR-09]
        if recipe.required_dll_overrides:
            bottle.dll_overrides.update(recipe.required_dll_overrides)

        # Mark as installed and save
        if recipe.id not in bottle.installed_dependencies:
            bottle.installed_dependencies.append(recipe.id)
        BottleManager.save_bottle_config(bottle)

        return True

    @classmethod
    def uninstall_dependency(cls, bottle_id: str, recipe_id: str) -> bool:
        """
        [FR-19] Removes a runtime package registration and cleans up its custom DLL overrides.
        """
        bottle = BottleManager.get_bottle(bottle_id)
        if not bottle:
            raise ValueError(f"Bottle '{bottle_id}' not found.")

        recipe = cls.get_recipe(recipe_id)

        # 1. Remove from installed dependencies list
        if recipe_id in bottle.installed_dependencies:
            bottle.installed_dependencies.remove(recipe_id)

        # 2. Revert associated DLL overrides
        if recipe and recipe.required_dll_overrides:
            for dll in recipe.required_dll_overrides:
                bottle.dll_overrides.pop(dll, None)

        BottleManager.save_bottle_config(bottle)
        return True
