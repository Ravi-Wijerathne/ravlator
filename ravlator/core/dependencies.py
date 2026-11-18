"""
[FR-17, FR-18, FR-19] Automated Dependency & Runtime Package Manager.
Provides declarative recipe-based installation of Windows runtimes (Visual C++, .NET, DirectX, Fonts).
Decoupled from GUI frameworks.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Callable

from ravlator.core.bottle import BottleManager
from ravlator.core.config import Config
from ravlator.core.downloader import FileDownloader, DownloadProgress
from ravlator.core.models import DependencyRecipe, BottleConfig
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.runner import RunnerManager


# Standard built-in recipes for essential gaming runtimes
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
        id="corefonts",
        name="Microsoft TrueType Core Fonts",
        category="Media & Fonts",
        description="Arial, Times New Roman, Courier New, Verdana, and Tahoma fonts.",
        download_url="",  # Handled via winetricks or system font linking
        sha256="",
        installer_args=[],
        required_dll_overrides={},
        dependencies=[]
    )
]


class DependencyManager:
    """Manages parsing recipes and executing silent dependency installations."""

    @classmethod
    def get_available_recipes(cls) -> List[DependencyRecipe]:
        """Loads built-in and external JSON/YAML recipes from disk."""
        recipes = list(BUILTIN_RECIPES)
        recipes_dir = Config.get_recipes_dir()
        
        # Load custom community recipes
        if recipes_dir.exists():
            for item in recipes_dir.glob("*.json"):
                try:
                    with open(item, "r", encoding="utf-8") as f:
                        data = json.load(f)
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
