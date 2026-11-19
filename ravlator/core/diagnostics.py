"""
[FR-07, FR-11] Host System & Hardware Diagnostics Engine.
Inspects Apple Silicon GPU/CPU generation, macOS version, Rosetta 2, AVX2, and Ray Tracing capabilities.
Decoupled from GUI frameworks.
"""

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SystemDiagnostics:
    macos_version: str
    macos_name: str
    cpu_brand: str
    is_apple_silicon: bool
    chip_generation: str
    memory_gb: float
    has_rosetta2: bool
    has_avx2_emulation: bool
    has_hardware_raytracing: bool


class DiagnosticsManager:
    """Detects host capabilities to advise on optimal gaming presets."""

    @classmethod
    def get_system_diagnostics(cls) -> SystemDiagnostics:
        # 1. macOS Version
        mac_ver = platform.mac_ver()[0]
        major_ver = int(mac_ver.split(".")[0]) if mac_ver else 14

        macos_name = "macOS Sequoia" if major_ver >= 15 else "macOS Sonoma" if major_ver == 14 else "macOS"

        # 2. CPU and Architecture
        arch = platform.machine()
        is_arm = arch.lower() in ("arm64", "aarch64")

        cpu_brand = "Apple Silicon"
        try:
            res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, check=False)
            if res.stdout.strip():
                cpu_brand = res.stdout.strip()
        except Exception:
            pass

        # 3. Memory
        memory_gb = 8.0
        try:
            res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False)
            if res.stdout.strip():
                memory_gb = round(int(res.stdout.strip()) / (1024 ** 3), 1)
        except Exception:
            pass

        # 4. Chip Generation & Ray Tracing (M3, M4+ hardware ray tracing)
        chip_gen = "M1/M2"
        has_hw_rt = False
        brand_lower = cpu_brand.lower()
        if "m3" in brand_lower:
            chip_gen = "Apple M3"
            has_hw_rt = True
        elif "m4" in brand_lower:
            chip_gen = "Apple M4"
            has_hw_rt = True
        elif "m5" in brand_lower:
            chip_gen = "Apple M5"
            has_hw_rt = True
        elif "m2" in brand_lower:
            chip_gen = "Apple M2"
        elif "m1" in brand_lower:
            chip_gen = "Apple M1"

        # 5. AVX2 Emulation [FR-07]
        # Enabled by Apple in macOS 15.0+ (Sequoia) via updated Rosetta 2
        has_avx2 = is_arm and major_ver >= 15

        # 6. Rosetta 2 Verification [FR-11]
        rosetta_path = Path("/Library/Apple/usr/share/rosetta/rosetta")
        has_rosetta = rosetta_path.exists()
        if not has_rosetta and is_arm:
            # Check via arch test
            try:
                res = subprocess.run(["arch", "-x86_64", "/usr/bin/true"], capture_output=True, check=False)
                has_rosetta = (res.returncode == 0)
            except Exception:
                pass

        return SystemDiagnostics(
            macos_version=mac_ver,
            macos_name=macos_name,
            cpu_brand=cpu_brand,
            is_apple_silicon=is_arm,
            chip_generation=chip_gen,
            memory_gb=memory_gb,
            has_rosetta2=has_rosetta,
            has_avx2_emulation=has_avx2,
            has_hardware_raytracing=has_hw_rt
        )

    @classmethod
    def get_diagnostic_summary(cls) -> str:
        d = cls.get_system_diagnostics()
        return (
            f"OS: {d.macos_name} ({d.macos_version})\n"
            f"Hardware: {d.cpu_brand} | {d.memory_gb} GB Unified Memory\n"
            f"Rosetta 2 Runtime: {'Installed' if d.has_rosetta2 else 'Missing'}\n"
            f"AVX2 Instruction Set (macOS 15+): {'Supported' if d.has_avx2_emulation else 'Requires macOS 15+'}\n"
            f"Hardware Ray Tracing: {'Supported (M3/M4+)' if d.has_hardware_raytracing else 'Unsupported on this chip'}"
        )
