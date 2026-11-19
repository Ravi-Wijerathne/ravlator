# AGENTS.md — Development Guidelines & Instructions for AI Agents
## Project: Ravlator (macOS Windows Gaming & Wine Prefix Manager)

This document establishes the binding rules, operational constraints, and engineering protocols for all AI agents, subagents, and human contributors developing **Ravlator**.

---

## 1. Single Source of Truth: The SRS Documentation
All functional requirements, architectural contracts, non-functional targets, and environment schemas are formally defined in:
- **Primary Specification:** [`docs/SRS_Documentation.md`](file:///Users/ravi/Documents/SLIIT/Projects/ravlator/docs/SRS_Documentation.md)

### Agent Compliance Rules:
1. **Never Deviate from Requirement IDs:** When implementing or modifying features, explicitly map code modules, pull requests, and commit messages to their corresponding `FR-xx` or `NFR-xx` IDs defined in the SRS (e.g., `[FR-01] Implement atomic bottle initialization`).
2. **Consult Schema Definitions:** Directory structures (`drive_c`, `dosdevices`, `bottle.json`), environment variables (`WINEMSYNC`, `MTL_HUD_ENABLED`), and recipe formats must strictly adhere to the specifications in Section 3, Section 4, and Appendix C of the SRS.
3. **No Unapproved Framework Swaps:** The frontend is strictly **PySide6 (Qt 6)**. Do not introduce alternative UI frameworks (such as Electron, PyWebView, Tkinter, or Flet) without an explicit amendment to the SRS.

---

## 2. Architectural Principles & Coding Standards

### 2.1 Decoupled Core vs. Presentation
- **Headless Core:** The core engine (`ravlator.core`) **must never import `PySide6` or any GUI widget**. All bottle management, runner extraction, dependency resolution, and process management logic must be fully functional from a headless terminal or CLI (`ravlator-cli`).
- **GUI as an Observer:** The presentation layer (`ravlator.gui`) observes state transitions and communicates with the core engine solely through Qt Signals, Slots, and thread-safe callbacks.

### 2.2 Threading & Non-Blocking Execution
- **Zero GUI Freezing:** Under no circumstances should `time.sleep()` or synchronous `subprocess.run()` be executed on the Qt main GUI thread.
- **Worker Concurrency:** Long-running tasks (Wine execution, archive downloads, runner extraction, dependency installation) must execute inside `QThread`, `QThreadPool` (`QRunnable`), or Python's `asyncio` event loop integrated via `qasync`.
- **Stream Output:** Wine `stdout` and `stderr` must be captured asynchronously line-by-line and emitted via Qt signals to prevent buffer overflows or unresponsive interfaces.

### 2.3 Subprocess & macOS Execution Rules
- **No Elevated Privileges:** Never run Wine, `wineserver`, or helper scripts with `sudo` or as `root`.
- **Environment Isolation:** Never pollute the global `os.environ`. Always construct a clean dictionary copy (`env = os.environ.copy()`) explicitly declaring `WINEPREFIX`, `WINEMSYNC`, `DYLD_FALLBACK_LIBRARY_PATH`, and runner binary paths.
- **Quarantine Attribute Removal:** Any executable downloaded from remote sources (runners, tools) must have Apple quarantine flags removed:
  ```bash
  xattr -dr com.apple.quarantine <extracted_path>
  ```
- **Steam Client Protection:** When launching or generating shortcuts for Steam, always inject the required CEF stability arguments:
  `-no-cef-sandbox -cef-disable-gpu -noverifyfiles -allossearch`

---

## 3. UI Iconography & Design System: Lucide Icons

### 3.1 Standard Icon Pack
- **Selected Icon Set:** **Lucide Icons** (ISC / MIT License).
- **Style Language:** Modern 24x24 grid, 2px rounded stroke vectors, visually aligned with Apple's macOS Human Interface Guidelines (SF Symbols aesthetic).
- **Source Repository:** `assets/icons/lucide/` (raw vector `.svg` files).

### 3.2 Icon Rendering Rules in PySide6
- Do not rely on plain raster icons. All icons must be rendered dynamically via `QSvgRenderer` onto a `QPixmap` or converted to `QIcon` to ensure crisp rendering on Apple Retina displays.
- **Dynamic Dark/Light Mode Tinting:** Icons must adapt dynamically to the active macOS theme palette (`#FFFFFF` / `#F5F5F7` in dark mode, `#1D1D1F` in light mode, or `#007AFF` for active macOS accent highlights).

#### Standard Icon Loader Implementation (`ravlator.gui.utils.icons`):
```python
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer

def get_lucide_icon(icon_name: str, color: QColor = None, size: QSize = QSize(20, 20)) -> QIcon:
    """
    Renders a crisp, dynamically-tinted Lucide SVG icon for macOS Retina displays.
    """
    svg_path = f"assets/icons/lucide/{icon_name}.svg"
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        return QIcon()

    pixmap = QPixmap(size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)

    if color and color.isValid():
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
    painter.end()

    return QIcon(pixmap)
```

---

## 4. Runner & Asset Distribution Rules
1. **GitHub Release CDN as Default:** Runners (Wine-CX, Apple GPTK 2 runtimes) and dependency installers must be fetched from verified remote GitHub releases / CDN manifests.
2. **Checksum Verification:** Every downloaded artifact must be verified against its SHA-256 hash before unpacking. Corrupted or mismatched archives must be deleted immediately.
3. **Local Import Support:** The UI must always maintain a secondary option allowing power users to manually select and import a local pre-extracted runner directory.

---

## 5. Verification & Testing Protocol for Agents
Before concluding any implementation task, the agent must verify:
1. **Syntax & Type Safety:** Run `ruff check .` or `flake8`, and `mypy` on the Python codebase.
2. **Headless Execution:** Verify that `python -m ravlator.core` or CLI tests run without requiring a display server / active Qt window.
3. **Atomic Operations:** Confirm that aborted or failing operations do not leave half-written files in `~/Library/Application Support/Ravlator/`.
4. **Documentation Updates:** If an implementation detail changes any interface or data model, update `docs/SRS_Documentation.md` in tandem.
