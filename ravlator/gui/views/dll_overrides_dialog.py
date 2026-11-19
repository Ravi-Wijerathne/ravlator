"""
[FR-09] DLL Overrides Configuration Dialog for PySide6.
Allows fine-grained management of native vs builtin Windows dynamic-link libraries.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QMessageBox
)

from ravlator.core.bottle import BottleManager
from ravlator.core.models import BottleConfig

COMMON_DLLS = [
    "d3d11", "d3d12", "dxgi", "d3d9", "d3d10", "d3dx9_43",
    "xinput1_3", "xinput1_4", "dinput8", "dsound", "openal32",
    "vcruntime140", "msvcp140"
]

OVERRIDE_MODES = [
    "native,builtin",
    "builtin,native",
    "native",
    "builtin",
    "disabled"
]


class DllOverridesDialog(QDialog):
    """Dialog allowing users to customize Wine DLL overrides."""

    def __init__(self, bottle: BottleConfig, parent=None):
        super().__init__(parent)
        self.bottle = bottle
        self.setWindowTitle(f"DLL Overrides — {bottle.name}")
        self.resize(640, 420)

        self._setup_ui()
        self._load_overrides()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(f"Configure Dynamic Link Library (DLL) Overrides for <b>{self.bottle.name}</b>")
        layout.addWidget(header)

        # Add Override Bar
        add_layout = QHBoxLayout()
        self.dll_combo = QComboBox()
        self.dll_combo.setEditable(True)
        self.dll_combo.setPlaceholderText("Select or enter DLL name (e.g. d3d11)")
        for dll in COMMON_DLLS:
            self.dll_combo.addItem(dll)
        add_layout.addWidget(self.dll_combo, 2)

        self.mode_combo = QComboBox()
        for mode in OVERRIDE_MODES:
            self.mode_combo.addItem(mode)
        add_layout.addWidget(self.mode_combo, 1)

        btn_add = QPushButton("Add Override")
        btn_add.clicked.connect(self._add_override)
        add_layout.addWidget(btn_add)

        layout.addLayout(add_layout)

        # Table of active overrides
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Library Name", "Override Mode", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def _load_overrides(self):
        overrides = self.bottle.dll_overrides
        self.table.setRowCount(len(overrides))

        for row, (dll, mode) in enumerate(overrides.items()):
            self.table.setItem(row, 0, QTableWidgetItem(dll))

            # Mode selector
            mode_box = QComboBox()
            for m in OVERRIDE_MODES:
                mode_box.addItem(m)
            mode_box.setCurrentText(mode)
            mode_box.currentTextChanged.connect(lambda new_m, lib=dll: self._change_mode(lib, new_m))
            self.table.setCellWidget(row, 1, mode_box)

            # Delete button
            btn_delete = QPushButton("Remove")
            btn_delete.clicked.connect(lambda _, lib=dll: self._remove_override(lib))
            self.table.setCellWidget(row, 2, btn_delete)

    def _add_override(self):
        dll_name = self.dll_combo.currentText().strip().lower()
        if not dll_name:
            return
        if dll_name.endswith(".dll"):
            dll_name = dll_name[:-4]

        mode = self.mode_combo.currentText()
        self.bottle.dll_overrides[dll_name] = mode
        BottleManager.save_bottle_config(self.bottle)
        self._load_overrides()

    def _change_mode(self, dll: str, new_mode: str):
        self.bottle.dll_overrides[dll] = new_mode
        BottleManager.save_bottle_config(self.bottle)

    def _remove_override(self, dll: str):
        if dll in self.bottle.dll_overrides:
            del self.bottle.dll_overrides[dll]
            BottleManager.save_bottle_config(self.bottle)
            self._load_overrides()
