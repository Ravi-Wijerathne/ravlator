"""
[FR-07, FR-08, FR-09, FR-10, FR-11] Runner & Translation Engine Manager.
Handles downloading, checksum validation, unpacking, and quarantine removal for Wine distributions.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import List, Optional, Callable

from ravlator.core.config import Config
from ravlator.core.downloader import FileDownloader, DownloadProgress
from ravlator.core.models import RunnerInfo


# Default verified official & community CDN catalog manifests
DEFAULT_RUNNERS = [
    RunnerInfo(
        id="gptk-2.0",
        name="Apple Game Porting Toolkit 2.1 (Wine-CX)",
        version="2.1.0",
        path="",
        source_type="cdn",
        sha256="",  # Empty skips strict sha enforcement if dynamically updated
        download_url="https://github.com/Gcenx/game-porting-toolkit/releases/download/Game-Porting-Toolkit-2.1/game-porting-toolkit-2.1.tar.xz",
        fallback_urls=[
            "https://github.com/Gcenx/game-porting-toolkit/releases/download/Game-Porting-Toolkit-3.0-3/game-porting-toolkit-3.0-3.tar.xz"
        ],
        has_d3dmetal=True,
        is_installed=False
    ),
    RunnerInfo(
        id="wine-cx-24",
        name="Wine-CX 23.7.1 (Heroic / CrossOver)",
        version="23.7.1",
        path="",
        source_type="cdn",
        sha256="",
        download_url="https://github.com/Heroic-Games-Launcher/wine-crossover/releases/download/23.7.1-1/Wine-Crossover-23.7.1-1.tar.xz",
        fallback_urls=[
            "https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.21/wine-staging-11.21-osx64.tar.xz"
        ],
        has_d3dmetal=True,
        is_installed=False
    )
]


class RunnerManager:
    """Manages local and remote Wine / GPTK runners."""

    @classmethod
    def get_runner_dir(cls, runner_id: str) -> Path:
        return Config.get_runners_dir() / runner_id

    @classmethod
    def list_installed_runners(cls) -> List[RunnerInfo]:
        """Detects runners installed locally in ~/Library/Application Support/Ravlator/Runners."""
        installed = []
        runners_dir = Config.get_runners_dir()
        if not runners_dir.exists():
            return installed

        for item in runners_dir.iterdir():
            if item.is_dir():
                wine_bin = item / "bin" / "wine64"
                if not wine_bin.exists():
                    wine_bin = item / "bin" / "wine"
                
                info_json = item / "runner.json"
                if info_json.exists():
                    try:
                        with open(info_json, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            runner = RunnerInfo(**data)
                            runner.path = str(item)
                            runner.is_installed = True
                            installed.append(runner)
                            continue
                    except Exception:
                        pass
                
                if wine_bin.exists():
                    installed.append(RunnerInfo(
                        id=item.name,
                        name=item.name.replace("-", " ").title(),
                        version="Custom",
                        path=str(item),
                        source_type="local",
                        has_d3dmetal=True,
                        is_installed=True
                    ))
        return installed

    @classmethod
    def get_available_runners(cls) -> List[RunnerInfo]:
        """Returns catalog of runners, marking whether each is installed locally."""
        installed_map = {r.id: r for r in cls.list_installed_runners()}
        results = []

        for default_r in DEFAULT_RUNNERS:
            if default_r.id in installed_map:
                results.append(installed_map[default_r.id])
            else:
                clone = default_r.model_copy()
                clone.path = str(cls.get_runner_dir(default_r.id))
                clone.is_installed = False
                results.append(clone)

        # Append any custom local runners not in the default catalog
        for r_id, r in installed_map.items():
            if not any(d.id == r_id for d in DEFAULT_RUNNERS):
                results.append(r)

        return results

    @classmethod
    def get_runner(cls, runner_id: str) -> Optional[RunnerInfo]:
        for r in cls.get_available_runners():
            if r.id == runner_id:
                return r
        return None

    @classmethod
    def strip_quarantine(cls, path: Path) -> None:
        """[FR-08, AGENTS.md 2.3] Removes Apple Gatekeeper quarantine flags."""
        try:
            subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    @classmethod
    def make_binaries_executable(cls, runner_path: Path) -> None:
        """Applies chmod +x to all binaries in bin/."""
        bin_dir = runner_path / "bin"
        if bin_dir.exists():
            for item in bin_dir.iterdir():
                if item.is_file():
                    item.chmod(item.stat().st_mode | 0o111)

    @classmethod
    def normalize_runner_structure(cls, dest_dir: Path) -> None:
        """
        Normalizes unpacked runner directory so bin/wine64 and lib/ are directly
        located under dest_dir, resolving nested .app bundles or top-level wrapper directories.
        """
        # If bin/wine64 or bin/wine already exists directly under dest_dir, we're good
        if (dest_dir / "bin" / "wine64").exists() or (dest_dir / "bin" / "wine").exists():
            return

        # Look for nested wine directories (e.g. *.app/Contents/Resources/wine or nested-dir/bin/wine64)
        found_bins = list(dest_dir.glob("**/bin/wine64")) or list(dest_dir.glob("**/bin/wine"))
        if not found_bins:
            return

        # found_bins[0] is .../bin/wine64; its parent.parent is the root containing bin, lib, share
        nested_wine_root = found_bins[0].parent.parent
        if nested_wine_root == dest_dir:
            return

        temp_dir = dest_dir.parent / f"{dest_dir.name}_temp_norm"
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        shutil.move(str(nested_wine_root), str(temp_dir))
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.move(str(temp_dir), str(dest_dir))

    @classmethod
    def download_and_extract_runner(
        cls,
        runner_id: str,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> RunnerInfo:
        """
        [FR-08] Streams runner from verified CDN, extracts, normalizes directory structure,
        and clears Apple Gatekeeper quarantine attributes.
        """
        runner = cls.get_runner(runner_id)
        if not runner:
            raise ValueError(f"Runner '{runner_id}' not found in catalog.")

        urls_to_try = []
        if runner.download_url:
            urls_to_try.append(runner.download_url)
        if hasattr(runner, "fallback_urls") and runner.fallback_urls:
            urls_to_try.extend(runner.fallback_urls)

        if not urls_to_try:
            raise ValueError(f"Runner '{runner_id}' has no download URLs configured.")

        dest_dir = cls.get_runner_dir(runner_id)
        download_success = False
        last_error = None
        cache_archive = None

        # 1. Download from primary or fallback CDN mirrors
        for url in urls_to_try:
            try:
                archive_name = Path(url).name
                cache_archive = Config.get_cache_dir() / "runners" / archive_name
                FileDownloader.download_file(
                    url=url,
                    dest_path=cache_archive,
                    expected_sha256=runner.sha256 if runner.sha256 else None,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
                download_success = True
                break
            except Exception as e:
                last_error = e
                continue

        if not download_success or not cache_archive or not cache_archive.exists():
            raise RuntimeError(f"Failed to download runner '{runner_id}' from CDN: {last_error}")

        # 2. Extract into destination directory
        dest_dir.mkdir(parents=True, exist_ok=True)
        extracted = False

        # Attempt extraction via macOS native tar (fastest and preserves Darwin symlinks)
        try:
            res = subprocess.run(
                ["tar", "-xf", str(cache_archive), "-C", str(dest_dir)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if res.returncode == 0:
                extracted = True
        except Exception:
            pass

        if not extracted:
            try:
                shutil.unpack_archive(str(cache_archive), str(dest_dir))
            except Exception:
                try:
                    with tarfile.open(cache_archive) as tar:
                        tar.extractall(dest_dir)
                except Exception as e:
                    shutil.rmtree(dest_dir, ignore_errors=True)
                    raise RuntimeError(f"Failed to unpack runner archive: {e}") from e

        # 3. Normalize directory structure (flatten nested .app or subfolders)
        cls.normalize_runner_structure(dest_dir)

        # 4. Apply permissions and strip quarantine
        cls.make_binaries_executable(dest_dir)
        cls.strip_quarantine(dest_dir)

        # 5. Save metadata
        runner.path = str(dest_dir)
        runner.is_installed = True
        with open(dest_dir / "runner.json", "w", encoding="utf-8") as f:
            json.dump(runner.model_dump(), f, indent=2)

        return runner

    @classmethod
    def register_local_runner(cls, path: Path, name: Optional[str] = None) -> RunnerInfo:
        """[FR-10] Registers a custom pre-extracted Wine directory."""
        if not path.is_dir():
            raise ValueError(f"Path is not a valid directory: {path}")

        wine_bin = path / "bin" / "wine64"
        if not wine_bin.exists():
            wine_bin = path / "bin" / "wine"
        if not wine_bin.exists():
            raise ValueError(f"No Wine binary found in '{path}/bin/wine64' or '{path}/bin/wine'")

        runner_id = path.name.lower().replace(" ", "-")
        runner_name = name or path.name

        cls.strip_quarantine(path)
        cls.make_binaries_executable(path)

        runner = RunnerInfo(
            id=runner_id,
            name=runner_name,
            version="Local",
            path=str(path.resolve()),
            source_type="local",
            has_d3dmetal=True,
            is_installed=True
        )

        with open(path / "runner.json", "w", encoding="utf-8") as f:
            json.dump(runner.model_dump(), f, indent=2)

        # Link into Runners directory so it is discovered uniformly
        link_path = cls.get_runner_dir(runner_id)
        if not link_path.exists():
            try:
                link_path.symlink_to(path.resolve())
            except Exception:
                pass

        return runner

    @classmethod
    def uninstall_runner(cls, runner_id: str) -> bool:
        """Deletes an installed runner."""
        target = cls.get_runner_dir(runner_id)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            return True
        return False
