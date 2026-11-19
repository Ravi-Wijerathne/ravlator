"""
[Section 3.2, 5.1] Global Application Settings & Preferences Dialog.
Configures global defaults for runners, presets, themes, and Wine debugging.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFormLayout, QDialogButtonBox, QMessageBox,
    QApplication
)

from ravlator.core.config import Config
from ravlator.core.models import PresetType
from ravlator.core.runner import RunnerManager


class SettingsDialog(QDialog):
    """Global configuration dialog accessible via Cmd+, or toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setFixedWidth(460)

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()

        # Default Preset
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Gaming (D3DMetal 2, MSync, High-DPI)", PresetType.GAMING)
        self.preset_combo.addItem("Productivity (WineD3D, Standard Sync)", PresetType.PRODUCTIVITY)
        self.preset_combo.addItem("Custom Environment", PresetType.CUSTOM)
        form.addRow("Default Bottle Preset:", self.preset_combo)

        # Default Runner
        self.runner_combo = QComboBox()
        runners = RunnerManager.get_available_runners()
        for r in runners:
            self.runner_combo.addItem(r.name, r.id)
        form.addRow("Default Runner:", self.runner_combo)

        # Theme Mode
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Follow macOS System Theme", "system")
        self.theme_combo.addItem("Dark Mode", "dark")
        self.theme_combo.addItem("Light Mode", "light")
        form.addRow("UI Appearance:", self.theme_combo)

        # Wine Debug Output Verbosity
        self.debug_input = QLineEdit()
        self.debug_input.setPlaceholderText("fixme-all")
        form.addRow("Default WINEDEBUG:", self.debug_input)

        # Auto Updates
        self.chk_updates = QCheckBox("Automatically check for runner and catalog updates")
        form.addRow("", self.chk_updates)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_settings(self):
        settings = Config.load_global_settings()

        # Preset
        p_val = settings.get("default_preset", "gaming")
        idx = self.preset_combo.findData(PresetType(p_val) if p_val in [e.value for e in PresetType] else PresetType.GAMING)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)

        # Runner
        r_val = settings.get("default_runner", "gptk-2.0")
        idx_r = self.runner_combo.findData(r_val)
        if idx_r >= 0:
            self.runner_combo.setCurrentIndex(idx_r)

        # Theme
        t_val = settings.get("theme_mode", "system")
        idx_t = self.theme_combo.findData(t_val)
        if idx_t >= 0:
            self.theme_combo.setCurrentIndex(idx_t)

        # Debug
        self.debug_input.setText(settings.get("default_wine_debug", "fixme-all"))

        # Updates
        self.chk_updates.setChecked(settings.get("check_updates", True))

    def _save_and_close(self):
        settings = {
            "default_preset": self.preset_combo.currentData().value,
            "default_runner": self.runner_combo.currentData(),
            "theme_mode": self.theme_combo.currentData(),
            "default_wine_debug": self.debug_input.text().strip() or "fixme-all",
            "check_updates": self.chk_updates.isChecked()
        }
        Config.save_global_settings(settings)
        app = QApplication.instance()
        if app:
            from ravlator.gui.styles import get_stylesheet
            app.setStyleSheet(get_stylesheet(settings["theme_mode"]))
        self.accept()
