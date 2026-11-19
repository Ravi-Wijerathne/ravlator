"""
[Section 3.2, 5.1, FR-22, FR-24, FR-26, FR-29, FR-32]
Main Desktop Interface for Ravlator.
Implements the macOS navigation sidebar, bottle dashboard, program launcher,
macOS .app generator, task manager, and store installer.
"""

import sys
import subprocess
from pathlib import Path
from typing import Optional
import uuid

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QCheckBox, QComboBox, QLineEdit, QDialog, QDialogButtonBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView
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
from ravlator.gui.utils.icons import get_icon
from ravlator.gui.views.dependencies_dialog import DependenciesDialog
from ravlator.gui.views.runners_dialog import RunnersDialog
from ravlator.gui.views.store_installer_dialog import StoreInstallerDialog
from ravlator.gui.views.task_manager_dialog import TaskManagerDialog
from ravlator.gui.views.log_viewer_dialog import LogViewerDialog
from ravlator.gui.views.snapshots_dialog import SnapshotsDialog


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
        self.resize(1020, 680)
        self.setMinimumSize(850, 550)

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
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: palette(window); border-right: 1px solid palette(mid);")
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
        self.bottle_list.setStyleSheet("border: none; background: transparent;")
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

        main_layout.addWidget(sidebar)

        # Right Content View
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(14)

        # Header Area
        header_layout = QHBoxLayout()
        self.bottle_title = QLabel("Select a Bottle")
        b_font = QFont()
        b_font.setBold(True)
        b_font.setPointSize(20)
        self.bottle_title.setFont(b_font)
        header_layout.addWidget(self.bottle_title)

        header_layout.addStretch()

        self.btn_run_exe = QPushButton(" Run Executable")
        self.btn_run_exe.setIcon(get_icon("play"))
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

        # Secondary Actions Toolbar
        tools_layout = QHBoxLayout()

        self.btn_install_store = QPushButton(" Install Game Store")
        self.btn_install_store.setEnabled(False)
        self.btn_install_store.clicked.connect(self._open_store_installer)
        tools_layout.addWidget(self.btn_install_store)

        self.btn_dependencies = QPushButton(" Dependencies")
        self.btn_dependencies.setEnabled(False)
        self.btn_dependencies.clicked.connect(self._open_dependencies_dialog)
        tools_layout.addWidget(self.btn_dependencies)

        self.btn_task_mgr = QPushButton(" Task Manager")
        self.btn_task_mgr.setEnabled(False)
        self.btn_task_mgr.clicked.connect(self._open_task_manager)
        tools_layout.addWidget(self.btn_task_mgr)

        self.btn_logs = QPushButton(" Live Logs")
        self.btn_logs.setEnabled(False)
        self.btn_logs.clicked.connect(self._open_log_viewer)
        tools_layout.addWidget(self.btn_logs)

        self.btn_snapshots = QPushButton(" Snapshots")
        self.btn_snapshots.setEnabled(False)
        self.btn_snapshots.clicked.connect(self._open_snapshots_dialog)
        tools_layout.addWidget(self.btn_snapshots)

        self.btn_export = QPushButton(" Export...")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_bottle_dialog)
        tools_layout.addWidget(self.btn_export)

        self.btn_clone = QPushButton(" Clone")
        self.btn_clone.setEnabled(False)
        self.btn_clone.clicked.connect(self._duplicate_bottle_dialog)
        tools_layout.addWidget(self.btn_clone)

        self.btn_delete = QPushButton(" Delete")
        self.btn_delete.setEnabled(False)
        self.btn_delete.setStyleSheet("color: #FF3B30;")
        self.btn_delete.clicked.connect(self._delete_bottle_dialog)
        tools_layout.addWidget(self.btn_delete)

        tools_layout.addStretch()
        self.content_layout.addLayout(tools_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.content_layout.addWidget(line)

        # Programs / Game Shortcuts Section [FR-22, FR-24]
        programs_header_layout = QHBoxLayout()
        programs_title = QLabel("Programs & Game Shortcuts")
        p_font = QFont()
        p_font.setBold(True)
        programs_title.setFont(p_font)
        programs_header_layout.addWidget(programs_title)

        programs_header_layout.addStretch()
        self.btn_add_prog = QPushButton("+ Add Shortcut")
        self.btn_add_prog.setEnabled(False)
        self.btn_add_prog.clicked.connect(self._add_program_dialog)
        programs_header_layout.addWidget(self.btn_add_prog)
        self.content_layout.addLayout(programs_header_layout)

        self.programs_table = QTableWidget()
        self.programs_table.setColumnCount(3)
        self.programs_table.setHorizontalHeaderLabels(["Name", "Executable Path", "Actions"])
        self.programs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.programs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.programs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.programs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.programs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.programs_table.setMaximumHeight(180)
        self.content_layout.addWidget(self.programs_table)

        # Configuration Quick Toggles
        self.toggles_box = QWidget()
        toggles_layout = QVBoxLayout(self.toggles_box)
        toggles_layout.setContentsMargins(0, 4, 0, 4)

        toggles_title = QLabel("Graphics & Engine Settings")
        t_font = QFont()
        t_font.setBold(True)
        toggles_title.setFont(t_font)
        toggles_layout.addWidget(toggles_title)

        runner_row = QHBoxLayout()
        runner_row.addWidget(QLabel("Assigned Runner:"))
        self.runner_combo = QComboBox()
        self.runner_combo.currentIndexChanged.connect(self._on_runner_changed)
        runner_row.addWidget(self.runner_combo)
        runner_row.addStretch()
        toggles_layout.addLayout(runner_row)

        self.chk_msync = QCheckBox("MSync (Darwin Mach Semaphore Synchronization)")
        self.chk_msync.stateChanged.connect(self._update_settings)
        toggles_layout.addWidget(self.chk_msync)

        self.chk_metal_hud = QCheckBox("Apple Metal Performance HUD (MTL_HUD_ENABLED)")
        self.chk_metal_hud.stateChanged.connect(self._update_settings)
        toggles_layout.addWidget(self.chk_metal_hud)

        self.chk_retina = QCheckBox("Retina High-DPI Resolution Mode")
        self.chk_retina.stateChanged.connect(self._update_settings)
        toggles_layout.addWidget(self.chk_retina)

        self.content_layout.addWidget(self.toggles_box)
        self.content_layout.addStretch()

        main_layout.addWidget(self.content_area)

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
        self.btn_dependencies.setEnabled(False)
        self.btn_install_store.setEnabled(False)
        self.btn_task_mgr.setEnabled(False)
        self.btn_logs.setEnabled(False)
        self.btn_snapshots.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_clone.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.btn_add_prog.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.toggles_box.setEnabled(False)
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
        self.btn_dependencies.setEnabled(True)
        self.btn_install_store.setEnabled(True)
        self.btn_task_mgr.setEnabled(True)
        self.btn_logs.setEnabled(True)
        self.btn_snapshots.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_clone.setEnabled(True)
        self.btn_delete.setEnabled(True)
        self.btn_add_prog.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.toggles_box.setEnabled(True)

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

        self.chk_msync.setChecked(bottle.msync)
        self.chk_metal_hud.setChecked(bottle.metal_hud)
        self.chk_retina.setChecked(bottle.retina)

        self._load_programs()

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

            entry = ProgramEntry(
                id=uuid.uuid4().hex[:8],
                name=data["name"] or Path(data["exe_path"]).stem,
                exe_path=data["exe_path"],
                arguments=data["arguments"]
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

        cmd = [str(wine_bin), program.exe_path]
        if program.arguments:
            cmd.extend(program.arguments.split())

        final_args = WineProcessManager.inject_steam_cef_workaround(program.exe_path, cmd[1:])
        full_command = [cmd[0]] + final_args

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
        if not self.current_bottle:
            return
        runner_dir = RunnerManager.get_runner_dir(self.current_bottle.runner_id)
        WineProcessManager.force_kill_bottle(self.current_bottle, runner_dir)
        QMessageBox.information(self, "Bottle Stopped", f"Processes terminated for '{self.current_bottle.name}'.")

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
