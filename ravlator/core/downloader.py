"""
[FR-08, NFR-01] Thread-Safe Chunked HTTP Streaming Downloader.
Supports live progress reporting, speed estimation, and on-the-fly SHA-256 verification.
Decoupled from GUI frameworks.
"""

import hashlib
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional


class DownloadProgress:
    def __init__(self, downloaded_bytes: int, total_bytes: int, speed_bps: float):
        self.downloaded_bytes = downloaded_bytes
        self.total_bytes = total_bytes
        self.speed_bps = speed_bps

    @property
    def percentage(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100.0)


class FileDownloader:
    """Streams remote files over HTTPS with chunked buffering and checksum calculation."""

    CHUNK_SIZE = 64 * 1024  # 64 KB

    @classmethod
    def download_file(
        cls,
        url: str,
        dest_path: Path,
        expected_sha256: Optional[str] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Path:
        """
        Downloads a remote file synchronously to a temporary file, verifying SHA-256 before moving.
        Designed to be called inside worker threads (QThread / ThreadPool).
        """
        if not url.lower().startswith("https://"):
            raise ValueError(f"Insecure transport protocol rejected: '{url}'. Ravlator requires TLS/HTTPS.")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest_path.with_suffix(f"{dest_path.suffix}.tmp")

        hasher = hashlib.sha256() if expected_sha256 else None
        headers = {"User-Agent": "Ravlator/0.1.0 (Macintosh; Apple Silicon)"}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            start_time = time.time()
            last_report_time = start_time

            with open(tmp_path, "wb") as out_file:
                while True:
                    if cancel_check and cancel_check():
                        if tmp_path.exists():
                            tmp_path.unlink()
                        raise InterruptedError("Download cancelled by user.")

                    chunk = response.read(cls.CHUNK_SIZE)
                    if not chunk:
                        break

                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if hasher:
                        hasher.update(chunk)

                    now = time.time()
                    if progress_callback and (now - last_report_time >= 0.1 or downloaded == total_size):
                        elapsed = max(0.001, now - start_time)
                        speed = downloaded / elapsed
                        progress_callback(DownloadProgress(downloaded, total_size, speed))
                        last_report_time = now

        # Validate checksum if required [FR-08]
        if expected_sha256:
            actual_sha = hasher.hexdigest().lower()
            if actual_sha != expected_sha256.lower():
                if tmp_path.exists():
                    tmp_path.unlink()
                raise ValueError(
                    f"SHA-256 checksum mismatch for {url}.\n"
                    f"Expected: {expected_sha256}\n"
                    f"Got:      {actual_sha}"
                )

        # Atomic replacement to finalized path
        tmp_path.replace(dest_path)
        return dest_path
