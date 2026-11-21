"""
[Section 3.2, 5.1, FR-22, FR-24, FR-26, FR-29, FR-32]
Main Desktop Interface for Ravlator.
Implements the macOS navigation sidebar, bottle dashboard, program launcher,
macOS .app generator, task manager, and store installer.
"""

import sys
import shlex
import subprocess
from pathlib import Path
from typing import Optional
import uuid

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QShortcut, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QCheckBox, QComboBox, QLineEdit, QDialog, QDialogButtonBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QGridLayout, QGroupBox,
    QInputDialog
)

from ravlator.core.bottle import BottleManager
from ravlator.core.config import Config
from ravlator.core.models import BottleConfig, PresetType, WindowsVersion, ProgramEntry
from ravlator.core.runner import RunnerManager
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.shortcuts import ShortcutManager
from ravlator.core.telemetry import ProcessTelemetry
from ravlator.core.snapshots import SnapshotManager
from ravlator.core.portability import PortabilityManager
from ravlator.core.icon_extractor import IconExtractor
from ravlator.core.diagnostics import DiagnosticsManager
from ravlator.core.tools import WineToolsManager
from ravlator.core.anticheat import AntiCheatDetector
from ravlator.core.cloud_saves import CloudSaveManager
from ravlator.gui.utils.icons import get_icon
from ravlator.gui.views.dependencies_dialog import DependenciesDialog
from ravlator.gui.views.runners_dialog import RunnersDialog
from ravlator.gui.views.store_installer_dialog import StoreInstallerDialog
from ravlator.gui.views.task_manager_dialog import TaskManagerDialog
from ravlator.gui.views.log_viewer_dialog import LogViewerDialog
from ravlator.gui.views.snapshots_dialog import SnapshotsDialog
from ravlator.gui.views.dll_overrides_dialog import DllOverridesDialog
from ravlator.gui.views.diagnostics_dialog import DiagnosticsDialog
from ravlator.gui.views.settings_dialog import SettingsDialog


class NewBottleDialog(QDialog):
    """Dialog for creating a new Wine prefix [FR-01, FR-02]."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Bottle")
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. GamingPrefix")
        form.addRow("Bottle Name:", self.name_input)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Gaming (D3DMetal 2, MSync, High-DPI)", PresetType.GAMING)
        self.preset_combo.addItem("Productivity (WineD3D, Standard Sync)", PresetType.PRODUCTIVITY)
        self.preset_combo.addItem("Custom Environment", PresetType.CUSTOM)
        form.addRow("Environment:", self.preset_combo)

        self.version_combo = QComboBox()
        self.version_combo.addItem("Windows 10 (64-bit)", WindowsVersion.WIN10)
        self.version_combo.addItem("Windows 11 (64-bit)", WindowsVersion.WIN11)
        form.addRow("Windows Version:", self.version_combo)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "preset": self.preset_combo.currentData(),
            "version": self.version_combo.currentData()
        }


class AddProgramDialog(QDialog):
    """Dialog to register a new program shortcut inside a bottle [FR-22]."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Program Shortcut")
        self.setFixedWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. My Game")
        form.addRow("Program Name:", self.name_input)

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to .exe file")
        path_layout.addWidget(self.path_input)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_exe)
        path_layout.addWidget(btn_browse)
        form.addRow("Executable:", path_layout)

        self.args_input = QLineEdit()
        self.args_input.setPlaceholderText("Optional command-line arguments")
        form.addRow("Arguments:", self.args_input)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Windows Executable",
            str(Path.home()),
            "Windows Binaries (*.exe *.bat *.msi)"
        )
        if file_path:
            self.path_input.setText(file_path)
            if not self.name_input.text():
                self.name_input.setText(Path(file_path).stem.replace("_", " ").title())

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "exe_path": self.path_input.text().strip(),
            "arguments": self.args_input.text().strip()
        }


class MainWindow(QMainWindow):
    """Primary application window adhering to macOS HIG."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ravlator — Windows Gaming Manager")
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(1060, 720)
        self.setMinimumSize(920, 620)

        self.current_bottle: Optional[BottleConfig] = None

        self._setup_ui()
        self._load_bottles()

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left Navigation Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(10)

        sidebar_title = QLabel("Bottles")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(13)
        sidebar_title.setFont(title_font)
        sidebar_layout.addWidget(sidebar_title)

        self.bottle_list = QListWidget()
        self.bottle_list.setObjectName("bottleList")
        self.bottle_list.currentItemChanged.connect(self._on_bottle_selected)
        sidebar_layout.addWidget(self.bottle_list)

        new_btn = QPushButton(" New Bottle")
        new_btn.setIcon(get_icon("plus"))
        new_btn.clicked.connect(self._create_bottle_dialog)
        sidebar_layout.addWidget(new_btn)

        runners_btn = QPushButton(" Manage Runners")
        runners_btn.setIcon(get_icon("settings"))
        runners_btn.clicked.connect(self._open_runners_dialog)
        sidebar_layout.addWidget(runners_btn)

        import_btn = QPushButton(" Import Bottle...")
        import_btn.clicked.connect(self._import_bottle_dialog)
        sidebar_layout.addWidget(import_btn)

        diag_btn = QPushButton(" Diagnostics")
        diag_btn.clicked.connect(self._open_diagnostics_dialog)
        sidebar_layout.addWidget(diag_btn)

        pref_btn = QPushButton(" Preferences")
        pref_btn.setIcon(get_icon("settings"))
        pref_btn.clicked.connect(self._open_settings_dialog)
        sidebar_layout.addWidget(pref_btn)

        main_layout.addWidget(sidebar)

        # Right Content View
        self.content_area = QWidget()
        self.content_area.setObjectName("contentArea")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(14)

        # Header Area
        header_layout = QHBoxLayout()
        self.bottle_title = QLabel("Select a Bottle")
        b_font = QFont()
        b_font.setBold(True)
        b_font.setPointSize(22)
        self.bottle_title.setFont(b_font)
        header_layout.addWidget(self.bottle_title)

        header_layout.addStretch()

        self.btn_run_exe = QPushButton(" Run Executable")
        self.btn_run_exe.setObjectName("primaryAction")
        self.btn_run_exe.setIcon(get_icon("play", color=QColor("#FFFFFF")))
        self.btn_run_exe.setEnabled(False)
        self.btn_run_exe.clicked.connect(self._run_executable)
        header_layout.addWidget(self.btn_run_exe)

        self.btn_open_drive = QPushButton(" Drive C:")
        self.btn_open_drive.setEnabled(False)
        self.btn_open_drive.clicked.connect(self._open_drive_c)
        header_layout.addWidget(self.btn_open_drive)

        self.btn_stop = QPushButton(" Stop")
        self.btn_stop.setIcon(get_icon("stop"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_bottle)
        header_layout.addWidget(self.btn_stop)

        self.content_layout.addLayout(header_layout)

        # Tabbed Bottle Details Container [NFR-01]
        self.tab_widget = QTabWidget()
        self.tab_widget.setEnabled(False)

        # ============================================================
        # TAB 1: Programs & Shortcuts
        # ============================================================
        tab_programs = QWidget()
        tab_programs_layout = QVBoxLayout(tab_programs)
        tab_programs_layout.setContentsMargins(16, 16, 16, 16)
        tab_programs_layout.setSpacing(12)

        prog_top_row = QHBoxLayout()
        prog_top_title = QLabel("Installed Programs && Game Shortcuts")
        pt_font = QFont()
        pt_font.setBold(True)
        pt_font.setPointSize(14)
        prog_top_title.setFont(pt_font)
        prog_top_row.addWidget(prog_top_title)
        prog_top_row.addStretch()

        self.btn_add_prog = QPushButton("+ Add Shortcut")
        self.btn_add_prog.clicked.connect(self._add_program_dialog)
        prog_top_row.addWidget(self.btn_add_prog)
        tab_programs_layout.addLayout(prog_top_row)

        self.programs_table = QTableWidget()
        self.programs_table.setColumnCount(3)
        self.programs_table.setHorizontalHeaderLabels(["Name", "Executable Path", "Actions"])
        self.programs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.programs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.programs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.programs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.programs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tab_programs_layout.addWidget(self.programs_table)

        self.tab_widget.addTab(tab_programs, "Programs")

        # ============================================================
        # TAB 2: Configuration & Settings [FR-05, FR-06, FR-12 to FR-16]
        # ============================================================
        tab_config = QWidget()
        tab_config_layout = QVBoxLayout(tab_config)
        tab_config_layout.setContentsMargins(16, 16, 16, 16)
        tab_config_layout.setSpacing(14)

        # Group 1: Runtime & Version
        grp_runner = QGroupBox("Environment && Runtime")
        grp_runner_layout = QFormLayout(grp_runner)
        grp_runner_layout.setContentsMargins(14, 16, 14, 14)
        grp_runner_layout.setSpacing(10)

        runner_pick_row = QHBoxLayout()
        self.runner_combo = QComboBox()
        self.runner_combo.setMinimumWidth(280)
        self.runner_combo.currentIndexChanged.connect(self._on_runner_changed)
        runner_pick_row.addWidget(self.runner_combo)
        btn_manage_r = QPushButton("Manage Runners...")
        btn_manage_r.clicked.connect(self._open_runners_dialog)
        runner_pick_row.addWidget(btn_manage_r)
        runner_pick_row.addStretch()
        grp_runner_layout.addRow("Assigned Wine/GPTK Runner:", runner_pick_row)

        self.win_ver_combo = QComboBox()
        self.win_ver_combo.setMinimumWidth(280)
        self.win_ver_combo.addItem("Windows 10 (Standard 64-bit)", WindowsVersion.WIN10)
        self.win_ver_combo.addItem("Windows 11 (Modern x64)", WindowsVersion.WIN11)
        self.win_ver_combo.addItem("Windows 7 (Legacy Compatibility)", WindowsVersion.WIN7)
        self.win_ver_combo.currentIndexChanged.connect(self._on_win_ver_changed)
        grp_runner_layout.addRow("Reported Windows Version:", self.win_ver_combo)

        tab_config_layout.addWidget(grp_runner)

        # Group 2: Graphics Translation & Performance
        grp_graphics = QGroupBox("Graphics Translation && Performance")
        grp_graphics_layout = QVBoxLayout(grp_graphics)
        grp_graphics_layout.setContentsMargins(14, 16, 14, 14)
        grp_graphics_layout.setSpacing(12)

        self.chk_msync = QCheckBox("MSync — Darwin Mach Semaphore Synchronization (Eliminates Wineserver lock contention)")
        self.chk_msync.stateChanged.connect(self._update_settings)
        grp_graphics_layout.addWidget(self.chk_msync)

        self.chk_metal_hud = QCheckBox("Apple Metal Performance HUD (Live FPS, frametimes, memory && draw calls overlay)")
        self.chk_metal_hud.stateChanged.connect(self._update_settings)
        grp_graphics_layout.addWidget(self.chk_metal_hud)

        self.chk_retina = QCheckBox("Retina High-DPI Resolution Mode (Renders at native macOS pixel density)")
        self.chk_retina.stateChanged.connect(self._update_settings)
        grp_graphics_layout.addWidget(self.chk_retina)

        self.chk_sandbox = QCheckBox("Filesystem Sandbox Isolation (Restricts drive Z: from accessing host Mac root '/')")
        self.chk_sandbox.stateChanged.connect(self._update_settings)
        grp_graphics_layout.addWidget(self.chk_sandbox)

        # Virtual Desktop row
        vd_row = QHBoxLayout()
        self.chk_virtual_desktop = QCheckBox("Emulate Virtual Desktop Container:")
        self.chk_virtual_desktop.stateChanged.connect(self._update_settings)
        vd_row.addWidget(self.chk_virtual_desktop)

        self.res_combo = QComboBox()
        self.res_combo.setMinimumWidth(140)
        self.res_combo.addItems(["1920x1080", "2560x1440", "3840x2160", "1440x900", "1280x720"])
        self.res_combo.currentIndexChanged.connect(self._update_settings)
        vd_row.addWidget(self.res_combo)
        vd_row.addStretch()
        grp_graphics_layout.addLayout(vd_row)

        # DXVK HUD row
        hud_row = QHBoxLayout()
        hud_row.addWidget(QLabel("DXVK Diagnostics Overlay HUD:"))
        self.dxvk_hud_combo = QComboBox()
        self.dxvk_hud_combo.setMinimumWidth(260)
        self.dxvk_hud_combo.addItem("Disabled", "")
        self.dxvk_hud_combo.addItem("FPS Only", "fps")
        self.dxvk_hud_combo.addItem("Standard (FPS + Dev Info)", "fps,devinfo")
        self.dxvk_hud_combo.addItem("Full Diagnostics", "fps,frametimes,memory,devinfo,drawcalls")
        self.dxvk_hud_combo.currentIndexChanged.connect(self._update_settings)
        hud_row.addWidget(self.dxvk_hud_combo)
        hud_row.addStretch()
        grp_graphics_layout.addLayout(hud_row)

        tab_config_layout.addWidget(grp_graphics)
        tab_config_layout.addStretch()

        self.tab_widget.addTab(tab_config, "Configuration")

        # ============================================================
        # TAB 3: Tools & Stores [FR-09, FR-18, FR-20, FR-26 to FR-32]
        # ============================================================
        tab_tools = QWidget()
        tab_tools_layout = QVBoxLayout(tab_tools)
        tab_tools_layout.setContentsMargins(16, 16, 16, 16)
        tab_tools_layout.setSpacing(14)

        tools_desc = QLabel("Wine utilities, store client installers, and diagnostic tools for this bottle:")
        tools_desc.setStyleSheet("color: #5C5C60; font-size: 13px;")
        tab_tools_layout.addWidget(tools_desc)

        tools_grid = QGridLayout()
        tools_grid.setSpacing(12)

        self.btn_install_store = QPushButton("  Install Game Store (Steam, Epic, GOG)")
        self.btn_install_store.setObjectName("utilityBtn")
        self.btn_install_store.clicked.connect(self._open_store_installer)
        tools_grid.addWidget(self.btn_install_store, 0, 0)

        self.btn_dependencies = QPushButton("  Dependencies (DirectX, VC++ Runtimes)")
        self.btn_dependencies.setObjectName("utilityBtn")
        self.btn_dependencies.clicked.connect(self._open_dependencies_dialog)
        tools_grid.addWidget(self.btn_dependencies, 0, 1)

        self.btn_winecfg = QPushButton("  Wine Configuration (winecfg)")
        self.btn_winecfg.setObjectName("utilityBtn")
        self.btn_winecfg.clicked.connect(self._launch_winecfg)
        tools_grid.addWidget(self.btn_winecfg, 1, 0)

        self.btn_regedit = QPushButton("  Registry Editor (regedit)")
        self.btn_regedit.setObjectName("utilityBtn")
        self.btn_regedit.clicked.connect(self._launch_regedit)
        tools_grid.addWidget(self.btn_regedit, 1, 1)

        self.btn_terminal = QPushButton("  Wine Command Prompt (cmd.exe)")
        self.btn_terminal.setObjectName("utilityBtn")
        self.btn_terminal.clicked.connect(self._launch_terminal)
        tools_grid.addWidget(self.btn_terminal, 2, 0)

        self.btn_dll_overrides = QPushButton("  DLL Overrides Configuration")
        self.btn_dll_overrides.setObjectName("utilityBtn")
        self.btn_dll_overrides.clicked.connect(self._open_dll_overrides)
        tools_grid.addWidget(self.btn_dll_overrides, 2, 1)

        self.btn_task_mgr = QPushButton("  Task Manager && Process Inspector")
        self.btn_task_mgr.setObjectName("utilityBtn")
        self.btn_task_mgr.clicked.connect(self._open_task_manager)
        tools_grid.addWidget(self.btn_task_mgr, 3, 0)

        self.btn_logs = QPushButton("  Live Diagnostic Logs Streamer")
        self.btn_logs.setObjectName("utilityBtn")
        self.btn_logs.clicked.connect(self._open_log_viewer)
        tools_grid.addWidget(self.btn_logs, 3, 1)

        self.btn_winetricks = QPushButton("  Winetricks Package Runner")
        self.btn_winetricks.setObjectName("utilityBtn")
        self.btn_winetricks.clicked.connect(self._launch_winetricks)
        tools_grid.addWidget(self.btn_winetricks, 4, 0)

        tab_tools_layout.addLayout(tools_grid)
        tab_tools_layout.addStretch()

        self.tab_widget.addTab(tab_tools, "Tools && Stores")

        # ============================================================
        # TAB 4: Maintenance & Backups [FR-03, FR-04, FR-05, FR-33 to FR-36]
        # ============================================================
        tab_maint = QWidget()
        tab_maint_layout = QVBoxLayout(tab_maint)
        tab_maint_layout.setContentsMargins(16, 16, 16, 16)
        tab_maint_layout.setSpacing(14)

        maint_desc = QLabel("Backup, duplicate, reset, or export this bottle prefix:")
        maint_desc.setStyleSheet("color: #5C5C60; font-size: 13px;")
        tab_maint_layout.addWidget(maint_desc)

        maint_grid = QGridLayout()
        maint_grid.setSpacing(12)

        self.btn_snapshots = QPushButton("  Snapshots && Rollback (Point-in-Time)")
        self.btn_snapshots.setObjectName("utilityBtn")
        self.btn_snapshots.clicked.connect(self._open_snapshots_dialog)
        maint_grid.addWidget(self.btn_snapshots, 0, 0)

        self.btn_export = QPushButton("  Export Bottle Archive (.tar.gz / .zip)")
        self.btn_export.setObjectName("utilityBtn")
        self.btn_export.clicked.connect(self._export_bottle_dialog)
        maint_grid.addWidget(self.btn_export, 0, 1)

        self.btn_clone = QPushButton("  Clone Bottle (Duplicate Prefix)")
        self.btn_clone.setObjectName("utilityBtn")
        self.btn_clone.clicked.connect(self._duplicate_bottle_dialog)
        maint_grid.addWidget(self.btn_clone, 1, 0)

        self.btn_reset = QPushButton("  Reset Prefix to Vanilla State")
        self.btn_reset.setObjectName("utilityBtn")
        self.btn_reset.setToolTip("Restores vanilla registry hives and clears temporary Wine caches")
        self.btn_reset.clicked.connect(self._reset_bottle_dialog)
        maint_grid.addWidget(self.btn_reset, 1, 1)

        self.btn_cloud_saves = QPushButton("  Cloud Saves Sync (iCloud / Drive)")
        self.btn_cloud_saves.setObjectName("utilityBtn")
        self.btn_cloud_saves.clicked.connect(self._toggle_cloud_saves_dialog)
        maint_grid.addWidget(self.btn_cloud_saves, 2, 0)

        self.btn_delete = QPushButton("  Delete Bottle Permanently")
        self.btn_delete.setObjectName("dangerAction")
        self.btn_delete.clicked.connect(self._delete_bottle_dialog)
        maint_grid.addWidget(self.btn_delete, 2, 1)

        self.btn_force_kill = QPushButton("  Force Terminate (wineserver -k)")
        self.btn_force_kill.setObjectName("dangerAction")
        self.btn_force_kill.clicked.connect(self._force_kill_bottle_dialog)
        maint_grid.addWidget(self.btn_force_kill, 3, 0)

        tab_maint_layout.addLayout(maint_grid)
        tab_maint_layout.addStretch()

        self.tab_widget.addTab(tab_maint, "Maintenance")

        self.content_layout.addWidget(self.tab_widget)
        main_layout.addWidget(self.content_area)

        # Global macOS Keybindings [SRS Section 5.1]
        QShortcut(QKeySequence.Preferences, self, self._open_settings_dialog)
        QShortcut(QKeySequence("Ctrl+N"), self, self._create_bottle_dialog)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)

    def _load_bottles(self):
        self.bottle_list.clear()
        bottles = BottleManager.list_bottles()
        for b in bottles:
            item = QListWidgetItem(b.name)
            item.setData(Qt.UserRole, b.id)
            self.bottle_list.addItem(item)

        if bottles:
            self.bottle_list.setCurrentRow(0)
        else:
            self._update_view_for_empty()

    def _update_view_for_empty(self):
        self.current_bottle = None
        self.bottle_title.setText("No Bottles Configured")
        self.btn_run_exe.setEnabled(False)
        self.btn_open_drive.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.tab_widget.setEnabled(False)
        self.programs_table.setRowCount(0)

    def _on_bottle_selected(self, current: Optional[QListWidgetItem]):
        if not current:
            self._update_view_for_empty()
            return

        bottle_id = current.data(Qt.UserRole)
        bottle = BottleManager.get_bottle(bottle_id)
        if not bottle:
            return

        self.current_bottle = bottle
        self.bottle_title.setText(bottle.name)
        self.btn_run_exe.setEnabled(True)
        self.btn_open_drive.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.tab_widget.setEnabled(True)

        # Populate available runners [FR-09]
        self.runner_combo.blockSignals(True)
        self.runner_combo.clear()
        runners = RunnerManager.get_available_runners()
        for r in runners:
            label = f"{r.name} ({'Installed' if r.is_installed else 'CDN'})"
            self.runner_combo.addItem(label, r.id)
            if r.id == bottle.runner_id:
                self.runner_combo.setCurrentIndex(self.runner_combo.count() - 1)
        self.runner_combo.blockSignals(False)

        # Reported Windows Version [FR-06]
        self.win_ver_combo.blockSignals(True)
        idx_ver = self.win_ver_combo.findData(bottle.windows_version)
        if idx_ver >= 0:
            self.win_ver_combo.setCurrentIndex(idx_ver)
        self.win_ver_combo.blockSignals(False)

        # Performance and environment toggles [FR-05, FR-13, FR-14, FR-16]
        self.chk_msync.blockSignals(True)
        self.chk_msync.setChecked(bottle.msync)
        self.chk_msync.blockSignals(False)

        self.chk_metal_hud.blockSignals(True)
        self.chk_metal_hud.setChecked(bottle.metal_hud)
        self.chk_metal_hud.blockSignals(False)

        self.chk_retina.blockSignals(True)
        self.chk_retina.setChecked(bottle.retina)
        self.chk_retina.blockSignals(False)

        self.chk_sandbox.blockSignals(True)
        self.chk_sandbox.setChecked(getattr(bottle, "sandbox_drive_z", True))
        self.chk_sandbox.blockSignals(False)

        self.chk_virtual_desktop.blockSignals(True)
        self.chk_virtual_desktop.setChecked(bottle.virtual_desktop)
        self.chk_virtual_desktop.blockSignals(False)

        self.res_combo.blockSignals(True)
        res_idx = self.res_combo.findText(bottle.virtual_desktop_res)
        if res_idx >= 0:
            self.res_combo.setCurrentIndex(res_idx)
        self.res_combo.blockSignals(False)

        self.dxvk_hud_combo.blockSignals(True)
        hud_idx = self.dxvk_hud_combo.findData(bottle.dxvk_hud)
        if hud_idx >= 0:
            self.dxvk_hud_combo.setCurrentIndex(hud_idx)
        else:
            self.dxvk_hud_combo.setCurrentIndex(0)
        self.dxvk_hud_combo.blockSignals(False)

        self._load_programs()

    def _on_win_ver_changed(self):
        if not self.current_bottle:
            return
        selected_ver = self.win_ver_combo.currentData()
        if selected_ver and selected_ver != self.current_bottle.windows_version:
            WineToolsManager.set_windows_version(self.current_bottle, selected_ver)

    def _load_programs(self):
        if not self.current_bottle:
            return
        programs = self.current_bottle.programs
        self.programs_table.setRowCount(len(programs))

        for row, p in enumerate(programs):
            self.programs_table.setItem(row, 0, QTableWidgetItem(p.name))
            self.programs_table.setItem(row, 1, QTableWidgetItem(p.exe_path))

            # Action Buttons container
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            btn_launch = QPushButton("Launch")
            btn_launch.clicked.connect(lambda _, prog=p: self._launch_program(prog))
            actions_layout.addWidget(btn_launch)

            btn_mac_app = QPushButton("Create .app")
            btn_mac_app.setToolTip("Generate standalone macOS .app bundle on Desktop")
            btn_mac_app.clicked.connect(lambda _, prog=p: self._create_app_bundle(prog))
            actions_layout.addWidget(btn_mac_app)

            btn_remove = QPushButton("Remove")
            btn_remove.clicked.connect(lambda _, prog_id=p.id: self._remove_program(prog_id))
            actions_layout.addWidget(btn_remove)

            self.programs_table.setCellWidget(row, 2, actions_widget)

    def _add_program_dialog(self):
        if not self.current_bottle:
            return
        dialog = AddProgramDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["exe_path"]:
                QMessageBox.warning(self, "Invalid Executable", "Executable path cannot be empty.")
                return

            # Auto-extract Windows PE icon [FR-23]
            icon_path = None
            try:
                extracted = IconExtractor.extract_icon(Path(data["exe_path"]))
                if extracted:
                    icon_path = str(extracted)
            except Exception:
                pass

            entry = ProgramEntry(
                id=uuid.uuid4().hex[:8],
                name=data["name"] or Path(data["exe_path"]).stem,
                exe_path=data["exe_path"],
                arguments=data["arguments"],
                icon_path=icon_path
            )
            self.current_bottle.programs.append(entry)
            BottleManager.save_bottle_config(self.current_bottle)
            self._load_programs()

    def _launch_program(self, program: ProgramEntry):
        if not self.current_bottle:
            return

        runner_dir = RunnerManager.get_runner_dir(self.current_bottle.runner_id)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        env = WineEnvironmentBuilder.build_env(self.current_bottle, runner_dir)

        if not wine_bin.exists():
            QMessageBox.information(
                self,
                "Runner Setup Required",
                f"The runner '{self.current_bottle.runner_id}' is not yet installed.\n"
                f"Please open 'Manage Runners' to install it."
            )
            return

        # [RSK-01] Pre-launch kernel anti-cheat detection & advisory
        ac_match = AntiCheatDetector.scan_path(Path(program.exe_path))
        if ac_match:
            report = AntiCheatDetector.format_report(ac_match)
            proceed = QMessageBox.warning(
                self,
                "Incompatible Kernel Anti-Cheat Detected",
                f"Notice: Anti-cheat driver signatures were found for '{program.name}':\n\n{report}\n\n"
                "Kernel anti-cheat drivers cannot execute under Wine/Darwin userspace and may fail to start or connect.\n"
                "Do you still want to attempt running this program?",
                QMessageBox.Yes | QMessageBox.No
            )
            if proceed != QMessageBox.Yes:
                return

        # [RSK-05] Rolling automated registry hive backup
        BottleManager.backup_registry(self.current_bottle.id)

        # Parse command line arguments safely with shlex [GAP-03]
        try:
            cmd_args = shlex.split(program.arguments) if program.arguments else []
        except Exception:
            cmd_args = program.arguments.split() if program.arguments else []

        full_command = WineProcessManager.build_launch_command(
            runner_path=runner_dir,
            bottle=self.current_bottle,
            exe_path=program.exe_path,
            args=cmd_args
        )

        # Log launch
        log_file = ProcessTelemetry.get_log_path(self.current_bottle.id)
        with open(log_file, "a") as f:
            f.write(f"\n--- Launching {program.name} ---\nCommand: {' '.join(full_command)}\n")

        subprocess.Popen(full_command, env=env, stdout=open(log_file, "a"), stderr=subprocess.STDOUT)

    def _create_app_bundle(self, program: ProgramEntry):
        """[FR-24] Generates a standalone macOS application on Desktop."""
        if not self.current_bottle:
            return
        desktop_dir = ShortcutManager.get_desktop_dir()
        try:
            bundle_path = ShortcutManager.create_macos_app(
                bottle=self.current_bottle,
                program=program,
                output_dir=desktop_dir
            )
            QMessageBox.information(
                self,
                "Shortcut Created",
                f"Standalone macOS App created successfully on your Desktop:\n{bundle_path.name}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate .app bundle: {e}")

    def _remove_program(self, program_id: str):
        if not self.current_bottle:
            return
        self.current_bottle.programs = [p for p in self.current_bottle.programs if p.id != program_id]
        BottleManager.save_bottle_config(self.current_bottle)
        self._load_programs()

    def _create_bottle_dialog(self):
        dialog = NewBottleDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Invalid Name", "Bottle name cannot be empty.")
                return
            try:
                config = BottleManager.create_bottle(
                    name=data["name"],
                    preset=data["preset"],
                    windows_version=data["version"]
                )
                self._load_bottles()
                for i in range(self.bottle_list.count()):
                    item = self.bottle_list.item(i)
                    if item.data(Qt.UserRole) == config.id:
                        self.bottle_list.setCurrentItem(item)
                        break
            except Exception as e:
                QMessageBox.critical(self, "Creation Error", str(e))

    def _update_settings(self):
        if not self.current_bottle:
            return
        self.current_bottle.msync = self.chk_msync.isChecked()
        self.current_bottle.metal_hud = self.chk_metal_hud.isChecked()
        self.current_bottle.retina = self.chk_retina.isChecked()

        prev_sandbox = getattr(self.current_bottle, "sandbox_drive_z", True)
        new_sandbox = self.chk_sandbox.isChecked()
        self.current_bottle.sandbox_drive_z = new_sandbox
        if prev_sandbox != new_sandbox:
            BottleManager.apply_sandbox_policy(self.current_bottle)

        self.current_bottle.virtual_desktop = self.chk_virtual_desktop.isChecked()
        self.current_bottle.virtual_desktop_res = self.res_combo.currentText()
        self.current_bottle.dxvk_hud = self.dxvk_hud_combo.currentData() or ""
        BottleManager.save_bottle_config(self.current_bottle)

    def _on_runner_changed(self):
        if not self.current_bottle:
            return
        selected_runner_id = self.runner_combo.currentData()
        if selected_runner_id and selected_runner_id != self.current_bottle.runner_id:
            self.current_bottle.runner_id = selected_runner_id
            BottleManager.save_bottle_config(self.current_bottle)

    def _open_drive_c(self):
        if not self.current_bottle:
            return
        drive_c_path = BottleManager.get_bottle_dir(self.current_bottle.id) / "drive_c"
        if drive_c_path.exists():
            subprocess.run(["open", str(drive_c_path)])

    def _run_executable(self):
        if not self.current_bottle:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Windows Executable",
            str(Path.home()),
            "Windows Binaries (*.exe *.msi *.bat)"
        )
        if not file_path:
            return

        dummy_entry = ProgramEntry(
            id="temp-run",
            name=Path(file_path).stem,
            exe_path=file_path
        )
        self._launch_program(dummy_entry)

    def _stop_bottle(self):
        """[FR-30] Sends graceful shutdown signal to bottle via wineboot -s."""
        if not self.current_bottle:
            return
        runner_dir = RunnerManager.get_runner_dir(self.current_bottle.runner_id)
        WineProcessManager.stop_bottle(self.current_bottle, runner_dir)
        QMessageBox.information(
            self,
            "Graceful Shutdown",
            f"Shutdown signal (wineboot -s) sent to prefix '{self.current_bottle.name}'."
        )

    def _force_kill_bottle_dialog(self):
        """[FR-31] Force-terminates wineserver and Wine subprocesses."""
        if not self.current_bottle:
            return
        confirm = QMessageBox.question(
            self,
            "Force Terminate Wineserver",
            f"Are you sure you want to force terminate all Wine processes for '{self.current_bottle.name}'?\n"
            "This sends a SIGKILL/wineserver -k and may cause unsaved game data loss.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            runner_dir = RunnerManager.get_runner_dir(self.current_bottle.runner_id)
            WineProcessManager.force_kill_bottle(self.current_bottle, runner_dir)
            QMessageBox.information(self, "Terminated", f"All Wine processes terminated for '{self.current_bottle.name}'.")

    def _launch_winetricks(self):
        """[FR-20] Launches Winetricks inside macOS Terminal configured with bottle environment."""
        if not self.current_bottle:
            return
        try:
            WineToolsManager.launch_winetricks_terminal(self.current_bottle)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch Winetricks: {e}")

    def _toggle_cloud_saves_dialog(self):
        """[SRS Section 9 Phase 4] Manages cloud save symlinks (iCloud Drive, Google Drive, etc.)."""
        if not self.current_bottle:
            return
        is_synced = CloudSaveManager.is_sync_enabled(self.current_bottle)
        providers = CloudSaveManager.get_cloud_providers()

        if is_synced:
            confirm = QMessageBox.question(
                self,
                "Cloud Save Sync Active",
                f"Cloud save synchronization is currently ACTIVE for '{self.current_bottle.name}'.\n\n"
                "Do you want to disable synchronization and restore local save folders to this prefix?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                try:
                    CloudSaveManager.disable_sync(self.current_bottle)
                    QMessageBox.information(self, "Sync Disabled", "Local save game directories have been restored.")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to revert cloud sync: {e}")
        else:
            if not providers:
                QMessageBox.warning(
                    self,
                    "No Cloud Storage Detected",
                    "No active iCloud Drive, Google Drive, OneDrive, or Dropbox folder was found on this Mac."
                )
                return

            provider_names = list(providers.keys())
            chosen, ok = QInputDialog.getItem(
                self,
                "Enable Cloud Saves Sync",
                "Select cloud storage provider to synchronize game saves ('Saved Games', 'Documents/My Games'):",
                provider_names,
                0,
                False
            )
            if ok and chosen:
                try:
                    cloud_path = CloudSaveManager.enable_sync(self.current_bottle, chosen)
                    QMessageBox.information(
                        self,
                        "Cloud Sync Enabled",
                        f"Game saves are now synchronized with {chosen} at:\n{cloud_path}"
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Cloud Sync Error", str(e))

    def _open_store_installer(self):
        if not self.current_bottle:
            return
        dialog = StoreInstallerDialog(self.current_bottle, self)
        dialog.exec()
        self._load_programs()

    def _open_dependencies_dialog(self):
        if not self.current_bottle:
            return
        dialog = DependenciesDialog(self.current_bottle, self)
        dialog.exec()

    def _open_runners_dialog(self):
        dialog = RunnersDialog(self)
        dialog.exec()
        if self.current_bottle and self.bottle_list.currentItem():
            self._on_bottle_selected(self.bottle_list.currentItem())

    def _open_task_manager(self):
        if not self.current_bottle:
            return
        dialog = TaskManagerDialog(self.current_bottle, self)
        dialog.exec()

    def _open_log_viewer(self):
        if not self.current_bottle:
            return
        dialog = LogViewerDialog(self.current_bottle, self)
        dialog.exec()

    def _open_snapshots_dialog(self):
        if not self.current_bottle:
            return
        dialog = SnapshotsDialog(self.current_bottle, self)
        dialog.exec()
        fresh = BottleManager.get_bottle(self.current_bottle.id)
        if fresh and self.bottle_list.currentItem():
            self._on_bottle_selected(self.bottle_list.currentItem())

    def _export_bottle_dialog(self):
        if not self.current_bottle:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Bottle Archive",
            f"{self.current_bottle.id}_export.tar.gz",
            "Compressed Archives (*.tar.gz *.zip)"
        )
        if not file_path:
            return
        fmt = "zip" if file_path.endswith(".zip") else "tar.gz"
        try:
            out_path = PortabilityManager.export_bottle(
                bottle_id=self.current_bottle.id,
                dest_path=Path(file_path),
                format=fmt
            )
            QMessageBox.information(self, "Export Complete", f"Bottle successfully exported to:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _import_bottle_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Bottle Archive to Import",
            str(Path.home()),
            "Supported Archives (*.tar.gz *.tar.xz *.zip)"
        )
        if not file_path:
            return
        name, ok = QInputDialog.getText(
            self,
            "Import Bottle Name",
            "Optional bottle name (leave empty to use archive name):"
        )
        try:
            imported = PortabilityManager.import_bottle(
                archive_path=Path(file_path),
                custom_name=name.strip() if ok and name.strip() else None
            )
            QMessageBox.information(self, "Import Complete", f"Imported bottle '{imported.name}' successfully!")
            self._load_bottles()
            for i in range(self.bottle_list.count()):
                item = self.bottle_list.item(i)
                if item.data(Qt.UserRole) == imported.id:
                    self.bottle_list.setCurrentItem(item)
                    break
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    def _duplicate_bottle_dialog(self):
        if not self.current_bottle:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Clone Bottle",
            f"Enter name for cloned copy of '{self.current_bottle.name}':",
            text=f"{self.current_bottle.name} (Copy)"
        )
        if not ok or not new_name.strip():
            return
        try:
            cloned = BottleManager.duplicate_bottle(self.current_bottle.id, new_name.strip())
            QMessageBox.information(self, "Cloned", f"Bottle cloned as '{cloned.name}'.")
            self._load_bottles()
        except Exception as e:
            QMessageBox.critical(self, "Clone Failed", str(e))

    def _delete_bottle_dialog(self):
        if not self.current_bottle:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete bottle '{self.current_bottle.name}'?\n"
            "This will delete all installed games, saves, and registry hives inside this prefix.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            BottleManager.delete_bottle(self.current_bottle.id)
            self._load_bottles()

    def _open_dll_overrides(self):
        if not self.current_bottle:
            return
        dialog = DllOverridesDialog(self.current_bottle, self)
        dialog.exec()

    def _open_diagnostics_dialog(self):
        dialog = DiagnosticsDialog(self)
        dialog.exec()

    def _launch_winecfg(self):
        if not self.current_bottle:
            return
        try:
            WineToolsManager.launch_winecfg(self.current_bottle)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch winecfg: {e}")

    def _launch_regedit(self):
        if not self.current_bottle:
            return
        try:
            WineToolsManager.launch_regedit(self.current_bottle)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch regedit: {e}")

    def _launch_terminal(self):
        if not self.current_bottle:
            return
        try:
            WineToolsManager.launch_terminal_cmd(self.current_bottle)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch Wine Terminal: {e}")

    def _open_settings_dialog(self):
        """[Section 3.2, 5.1] Opens the global preferences dialog."""
        dialog = SettingsDialog(self)
        dialog.exec()

    def _reset_bottle_dialog(self):
        """[FR-05] Confirms and resets prefix registry hives and clears temp caches."""
        if not self.current_bottle:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Bottle Reset",
            f"Are you sure you want to reset prefix '{self.current_bottle.name}'?\n"
            "This will clear temporary Wine caches and restore vanilla registry hives while strictly preserving installed games and user saves.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                BottleManager.reset_bottle(self.current_bottle.id)
                QMessageBox.information(
                    self,
                    "Reset Complete",
                    f"Bottle '{self.current_bottle.name}' was successfully reset to vanilla state."
                )
            except Exception as e:
                QMessageBox.critical(self, "Reset Error", str(e))


if __name__ == "__main__":
    from ravlator.gui.app import main
    main()

