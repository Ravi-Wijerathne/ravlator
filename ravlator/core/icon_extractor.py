"""
[FR-23] Windows Executable Icon Extraction Engine.
Extracts embedded RT_GROUP_ICON and RT_ICON resources from Windows PE (.exe) binaries
and converts them into crisp PNG and macOS .icns assets using pefile and Pillow.
Decoupled from GUI frameworks.
"""

import io
import struct
from pathlib import Path
from typing import Optional
from PIL import Image

try:
    import pefile
except ImportError:
    pefile = None


class IconExtractor:
    """Extracts Windows executable icons directly from PE headers."""

    @classmethod
    def extract_icon(cls, exe_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        [FR-23] Parses the PE resources of an .exe file, extracts the highest resolution icon,
        and saves it as a high-DPI PNG.
        """
        if not exe_path.exists() or not pefile:
            return None

        if not output_path:
            output_path = exe_path.with_suffix(".png")

        try:
            pe = pefile.PE(str(exe_path), fast_load=True)
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
            )

            if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
                return None

            rt_icon_idx = pefile.RESOURCE_TYPE["RT_ICON"]
            rt_group_idx = pefile.RESOURCE_TYPE["RT_GROUP_ICON"]

            icon_entries = {}
            group_entries = []

            for resource_type in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                if resource_type.id == rt_icon_idx:
                    # Collect individual icon raw payloads
                    for entry in resource_type.directory.entries:
                        for sub_entry in entry.directory.entries:
                            data_rva = sub_entry.data.struct.OffsetToData
                            size = sub_entry.data.struct.Size
                            raw_data = pe.get_data(data_rva, size)
                            icon_entries[entry.id] = raw_data

                elif resource_type.id == rt_group_idx:
                    # Group icon directory headers
                    for entry in resource_type.directory.entries:
                        for sub_entry in entry.directory.entries:
                            data_rva = sub_entry.data.struct.OffsetToData
                            size = sub_entry.data.struct.Size
                            group_entries.append(pe.get_data(data_rva, size))

            if not group_entries or not icon_entries:
                # Fallback: inspect raw icon entries directly
                if icon_entries:
                    best_data = max(icon_entries.values(), key=len)
                    return cls._save_raw_icon(best_data, output_path)
                return None

            # Parse primary group icon to find highest resolution entry
            group_data = group_entries[0]
            if len(group_data) < 6:
                return None

            _, _, count = struct.unpack("<HHH", group_data[:6])
            best_id = None
            max_size = 0

            for i in range(count):
                offset = 6 + (i * 14)
                if offset + 14 > len(group_data):
                    break
                w, h, _, _, _, _, _, n_id = struct.unpack("<BBBBHHIH", group_data[offset:offset + 14])
                width = 256 if w == 0 else w
                height = 256 if h == 0 else h
                size = width * height
                if size > max_size and n_id in icon_entries:
                    max_size = size
                    best_id = n_id

            if best_id and best_id in icon_entries:
                return cls._save_raw_icon(icon_entries[best_id], output_path)

        except Exception:
            return None

        return None

    @classmethod
    def _save_raw_icon(cls, raw_data: bytes, output_path: Path) -> Optional[Path]:
        """Saves icon bytes as PNG, handling embedded PNG headers and DIB bitmaps."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Check if payload is already a valid PNG
            if raw_data.startswith(b"\x89PNG\r\n\x1a\n"):
                with open(output_path, "wb") as f:
                    f.write(raw_data)
                return output_path

            # If BMP/DIB, wrap with standard ICO header
            # ICO Header: 6 bytes + 1 directory entry (16 bytes) + raw_data
            ico_header = struct.pack("<HHH", 0, 1, 1)
            # DIB dimensions
            if len(raw_data) >= 8:
                width, raw_height = struct.unpack("<II", raw_data[4:12])
                height = raw_height // 2  # DIB height contains XOR and AND masks
                w_byte = 0 if width >= 256 else width
                h_byte = 0 if height >= 256 else height
                entry = struct.pack("<BBBBHHI", w_byte, h_byte, 0, 0, 1, 32, len(raw_data))
                offset = struct.pack("<I", 22)
                ico_payload = ico_header + entry + offset + raw_data

                img = Image.open(io.BytesIO(ico_payload))
                img.save(output_path, format="PNG")
                return output_path

        except Exception:
            pass

        return None
