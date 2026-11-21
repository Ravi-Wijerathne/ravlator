"""
[FR-35, FR-36, NFR-04] Portable Bottle Export and Import Engine.
Packages isolated prefixes into compressed archives (.tar.gz / .zip) for transfer across macOS systems.
Decoupled from GUI frameworks.
"""

import json
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Optional, Callable
import uuid

from ravlator.core.bottle import BottleManager
from ravlator.core.config import Config
from ravlator.core.models import BottleConfig


class PortabilityManager:
    """Manages full prefix export to and import from portable archives."""

    @classmethod
    def export_bottle(
        cls,
        bottle_id: str,
        dest_path: Optional[Path] = None,
        format: str = "tar.gz"
    ) -> Path:
        """
        [FR-35] Compresses a complete bottle into an exportable archive.
        """
        bottle = BottleManager.get_bottle(bottle_id)
        if not bottle:
            raise ValueError(f"Bottle '{bottle_id}' not found.")

        b_dir = BottleManager.get_bottle_dir(bottle_id)
        if not b_dir.exists():
            raise ValueError(f"Bottle directory '{b_dir}' does not exist.")

        if not dest_path:
            downloads_dir = Path.home() / "Downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)
            ext = ".zip" if format == "zip" else ".tar.gz"
            dest_path = downloads_dir / f"{bottle.id}_export{ext}"

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_archive = dest_path.with_suffix(".tmp")

        if format == "zip":
            with zipfile.ZipFile(tmp_archive, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in b_dir.rglob("*"):
                    # Skip volatile logs, temporary caches, and host-specific dosdevices
                    if "logs" in file_path.parts or "dosdevices" in file_path.parts:
                        continue
                    arcname = file_path.relative_to(b_dir)
                    zipf.write(file_path, arcname)
        else:
            with tarfile.open(tmp_archive, "w:gz") as tar:
                for item in b_dir.iterdir():
                    # dosdevices and logs are recreated dynamically on import
                    if item.name in ("logs", "dosdevices"):
                        continue
                    tar.add(item, arcname=item.name)

        tmp_archive.replace(dest_path)
        return dest_path

    @classmethod
    def import_bottle(
        cls,
        archive_path: Path,
        custom_name: Optional[str] = None
    ) -> BottleConfig:
        """
        [FR-36, NFR-04] Extracts and registers a portable bottle archive.
        """
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive file not found: {archive_path}")

        # Determine target bottle name & ID
        base_name = custom_name or archive_path.stem.replace("_export", "").replace(".tar", "")
        target_id = BottleManager.sanitize_name(base_name)
        dest_dir = BottleManager.get_bottle_dir(target_id)

        if dest_dir.exists():
            target_id = f"{target_id}-{uuid.uuid4().hex[:4]}"
            dest_dir = BottleManager.get_bottle_dir(target_id)

        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract archive with Zip Slip / Tar Slip path traversal guards [VULN-01]
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as zipf:
                    cls._safe_extract_zip(zipf, dest_dir)
            elif tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, "r:*") as tar:
                    cls._safe_extract_tar(tar, dest_dir)
            else:
                raise ValueError("Unsupported archive format. Expected .tar.gz, .tar.xz, or .zip.")

            # Fix or recreate dosdevices symlinks [Appendix C, GAP-01]
            dosdevices = dest_dir / "dosdevices"
            dosdevices.mkdir(parents=True, exist_ok=True)
            c_link = dosdevices / "c:"
            if c_link.is_symlink() or c_link.exists():
                c_link.unlink()
            c_link.symlink_to("../drive_c")

            # Update bottle.json with new target ID and name
            cfg_file = dest_dir / "bottle.json"
            if cfg_file.exists():
                with open(cfg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config = BottleConfig(**data)
                config.id = target_id
                if custom_name:
                    config.name = custom_name
            else:
                # Synthesize default configuration if missing
                config = BottleConfig(
                    id=target_id,
                    name=base_name
                )

            # Apply security sandbox policy for drive Z:
            BottleManager.apply_sandbox_policy(config)

            BottleManager.save_bottle_config(config)
            return config

        except Exception as e:
            # Clean up on failure [NFR-04]
            if dest_dir.exists():
                shutil.rmtree(dest_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to import bottle archive: {e}") from e

    @classmethod
    def _safe_extract_zip(cls, zipf: zipfile.ZipFile, dest_dir: Path) -> None:
        """[VULN-01] Safely extracts zip archives preventing Zip Slip directory traversal."""
        resolved_dest = dest_dir.resolve()
        for member in zipf.infolist():
            target_path = (resolved_dest / member.filename).resolve()
            if not target_path.is_relative_to(resolved_dest):
                raise PermissionError(
                    f"Security Alert: Directory traversal detected in zip archive: '{member.filename}'"
                )
            zipf.extract(member, resolved_dest)

    @classmethod
    def _safe_extract_tar(cls, tar: tarfile.TarFile, dest_dir: Path) -> None:
        """[VULN-01] Safely extracts tar archives preventing Tar Slip directory traversal and link escapes."""
        resolved_dest = dest_dir.resolve()
        for member in tar.getmembers():
            target_path = (resolved_dest / member.name).resolve()
            if not target_path.is_relative_to(resolved_dest):
                raise PermissionError(
                    f"Security Alert: Directory traversal detected in tar archive: '{member.name}'"
                )
            if member.issym() or member.islnk():
                link_target = (target_path.parent / member.linkname).resolve()
                if not link_target.is_relative_to(resolved_dest):
                    # Skip symlinks pointing outside prefix destination
                    continue

            if hasattr(tarfile, "data_filter"):
                tar.extract(member, resolved_dest, filter="data")
            else:
                tar.extract(member, resolved_dest)
