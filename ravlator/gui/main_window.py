"""
[Section 3.2, 5.1] Main Desktop Interface for Ravlator.
Implements the macOS navigation sidebar, bottle dashboard, and executable runner.
"""

import sys
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QCheckBox, QComboBox, QLineEdit, QDialog, QDialogButtonBox, QFormLayout
)

from ravlator.core.bottle import BottleManager
from ravlator.core.config import Config
from ravlator.core.models import BottleConfig, PresetType, WindowsVersion
from ravlator.core.runner import RunnerManager
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.gui.utils.icons import get_icon
from ravlator.gui.views.dependencies_dialog import DependenciesDialog
from ravlator.gui.views.runners_dialog import RunnersDialog


class NewBottleDialog(QDialog):
    """Dialog for creating a new Wine prefix [FR-01, FR-02]."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Bottle")
        self.setFixedWidth(380)

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


class MainWindow(QMainWindow):
    """Primary application window adhering to macOS HIG."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ravlator — Windows Gaming Manager")
        self.resize(960, 620)
        self.setMinimumSize(800, 500)

        self.current_bottle: Optional[BottleConfig] = None

        self._setup_ui()
        self._load_bottles()

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left Sidebar
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

        main_layout.addWidget(sidebar)

        # Right Content View
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(16)

        # Header Area
        header_layout = QHBoxLayout()
        self.bottle_title = QLabel("Select a Bottle")
        b_font = QFont()
        b_font.setBold(True)
        b_font.setPointSize(20)
        self.bottle_title.setFont(b_font)
        header_layout.addWidget(self.bottle_title)

        header_layout.addStretch()

        self.btn_run_exe = QPushButton(" Run Executable (.exe)")
        self.btn_run_exe.setIcon(get_icon("play"))
        self.btn_run_exe.setEnabled(False)
        self.btn_run_exe.clicked.connect(self._run_executable)
        header_layout.addWidget(self.btn_run_exe)

        self.btn_open_drive = QPushButton(" Drive C:")
        self.btn_open_drive.setEnabled(False)
        self.btn_open_drive.clicked.connect(self._open_drive_c)
        header_layout.addWidget(self.btn_open_drive)

        self.btn_dependencies = QPushButton(" Dependencies")
        self.btn_dependencies.setEnabled(False)
        self.btn_dependencies.clicked.connect(self._open_dependencies_dialog)
        header_layout.addWidget(self.btn_dependencies)

        self.btn_stop = QPushButton(" Stop")
        self.btn_stop.setIcon(get_icon("stop"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_bottle)
        header_layout.addWidget(self.btn_stop)

        self.content_layout.addLayout(header_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.content_layout.addWidget(line)

        # Configuration Quick Toggles
        self.toggles_box = QWidget()
        toggles_layout = QVBoxLayout(self.toggles_box)
        toggles_layout.setContentsMargins(0, 8, 0, 8)

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
        self.btn_stop.setEnabled(False)
        self.toggles_box.setEnabled(False)

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

    def _on_runner_changed(self):
        if not self.current_bottle:
            return
        selected_runner_id = self.runner_combo.currentData()
        if selected_runner_id and selected_runner_id != self.current_bottle.runner_id:
            self.current_bottle.runner_id = selected_runner_id
            BottleManager.save_bottle_config(self.current_bottle)

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
                # Select the newly created bottle
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

        runner_dir = RunnerManager.get_runner_dir(self.current_bottle.runner_id)
        env = WineEnvironmentBuilder.build_env(self.current_bottle, runner_dir)
        args = WineProcessManager.inject_steam_cef_workaround(file_path, [])
        
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        if not wine_bin.exists():
            # Prompt that a runner needs to be installed
            QMessageBox.information(
                self,
                "Runner Setup Required",
                f"The runner '{self.current_bottle.runner_id}' is not yet unpacked in:\n"
                f"{runner_dir}\n\n"
                "Ravlator prepared the isolated environment variables successfully."
            )
            return

        subprocess.Popen([str(wine_bin), file_path] + args, env=env)

    def _stop_bottle(self):
        if not self.current_bottle:
            return
        runner_dir = RunnerManager.get_runner_dir(self.current_bottle.runner_id)
        WineProcessManager.force_kill_bottle(self.current_bottle, runner_dir)
        QMessageBox.information(self, "Bottle Stopped", f"All active processes for '{self.current_bottle.name}' terminated.")
