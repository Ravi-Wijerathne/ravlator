"""
[FR-26, FR-27, FR-28] Game Store Integration & Setup Guide Dialog.
Allows users to launch official store installers (.exe / .msi), automatically configures
CEF stability flags for Steam, and synchronizes native macOS Steam login credentials.
"""

from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QFrame
)

from ravlator.core.bottle import BottleManager
from ravlator.core.models import BottleConfig
from ravlator.core.stores import StoreManager, StoreDefinition
from ravlator.gui.utils.icons import get_icon


class StoreInstallerDialog(QDialog):
    """Dialog providing guided setup for official gaming store launchers."""

    def __init__(self, bottle: BottleConfig, parent=None):
        super().__init__(parent)
        self.bottle = bottle
        self.setWindowTitle(f"Game Stores & Launchers — {bottle.name}")
        self.resize(760, 460)

        self._setup_ui()
        self._load_stores()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header Card
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "QFrame { background-color: #F8F9FA; border: 1px solid #E5E5EA; border-radius: 8px; padding: 12px; }"
        )
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(6)

        header_title = QLabel(f"Deploy Game Store Clients into <b>{self.bottle.name}</b>")
        header_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F;")
        header_layout.addWidget(header_title)

        instructions = QLabel(
            "To install a game store, download the official Windows installer (.exe or .msi) from the provider's website. "
            "Then click <b>Run Installer...</b> to launch the interactive setup wizard inside this bottle. "
            "Ravlator automatically configures the necessary stability arguments (including Steam CEF flags)."
        )
        instructions.setStyleSheet("color: #5C5C60; font-size: 12px; line-height: 1.4;")
        instructions.setWordWrap(True)
        header_layout.addWidget(instructions)

        layout.addWidget(header_frame)

        # Stores Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Store Client", "Status", "Official Source", "Execution"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Bottom Utilities Bar
        bottom_box = QHBoxLayout()
        bottom_box.setSpacing(10)

        btn_detect = QPushButton(" Auto-Detect Installed Stores")
        btn_detect.setIcon(get_icon("refresh-cw"))
        btn_detect.setToolTip("Scans Drive C: for installed stores and registers them with stability flags")
        btn_detect.clicked.connect(self._auto_detect_stores)
        bottom_box.addWidget(btn_detect)

        btn_sync = QPushButton(" Sync macOS Steam Login Cache")
        btn_sync.setToolTip("Copies native Mac Steam login session tokens to bypass CEF login errors")
        btn_sync.clicked.connect(self._sync_steam_login)
        bottom_box.addWidget(btn_sync)

        bottom_box.addStretch()

        btn_close = QPushButton("Done")
        btn_close.clicked.connect(self.accept)
        bottom_box.addWidget(btn_close)

        layout.addLayout(bottom_box)

    def _load_stores(self):
        fresh_bottle = BottleManager.get_bottle(self.bottle.id)
        if fresh_bottle:
            self.bottle = fresh_bottle

        stores = StoreManager.list_supported_stores()
        self.table.setRowCount(len(stores))

        for row, s in enumerate(stores):
            # Column 0: Name
            self.table.setItem(row, 0, QTableWidgetItem(s.name))

            # Column 1: Status
            is_installed = StoreManager.is_store_installed(self.bottle, s.id)
            status_item = QTableWidgetItem(" Installed" if is_installed else " Not Installed")
            if is_installed:
                status_item.setForeground(QColor("#34C759"))
            else:
                status_item.setForeground(QColor("#8E8E93"))
            self.table.setItem(row, 1, status_item)

            # Column 2: Official Website
            btn_web = QPushButton("Visit Website ↗")
            btn_web.setStyleSheet("padding: 4px 8px; font-size: 11px;")
            web_url = s.website_url or s.download_url
            btn_web.clicked.connect(lambda _, url=web_url: QDesktopServices.openUrl(QUrl(url)))
            self.table.setCellWidget(row, 2, btn_web)

            # Column 3: Run / Register
            if is_installed:
                btn_action = QPushButton("Add Shortcut")
                btn_action.setStyleSheet("padding: 4px 8px; font-size: 11px;")
                btn_action.clicked.connect(lambda _, store_def=s: self._register_shortcut(store_def))
            else:
                btn_action = QPushButton("Run Installer (.exe)...")
                btn_action.setStyleSheet("padding: 4px 8px; font-size: 11px; font-weight: 600;")
                btn_action.clicked.connect(lambda _, store_def=s: self._run_custom_installer(store_def))
            self.table.setCellWidget(row, 3, btn_action)

    def _run_custom_installer(self, store: StoreDefinition):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {store.name} Installer",
            str(Path.home() / "Downloads"),
            f"Windows Binaries (*.exe *.msi *.bat)"
        )
        if not file_path:
            return

        try:
            StoreManager.launch_store_installer(self.bottle, Path(file_path))
            QMessageBox.information(
                self,
                "Installer Started",
                f"The setup wizard for {store.name} has been launched inside Wine.\n\n"
                "Complete the installation wizard on screen. Once finished, click "
                "'Auto-Detect Installed Stores' to verify and add shortcuts."
            )
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", str(e))

    def _register_shortcut(self, store: StoreDefinition):
        try:
            entry = StoreManager.register_store_program(self.bottle, store.id)
            QMessageBox.information(
                self,
                "Shortcut Registered",
                f"'{entry.name}' has been added to your bottle shortcuts with stability arguments:\n\n"
                f"{entry.arguments or 'Standard configuration'}"
            )
            self._load_stores()
        except Exception as e:
            QMessageBox.critical(self, "Registration Error", str(e))

    def _auto_detect_stores(self):
        detected = StoreManager.detect_installed_stores(self.bottle)
        self._load_stores()
        if detected:
            names = ", ".join(d.name for d in detected)
            QMessageBox.information(
                self,
                "Stores Detected",
                f"Successfully detected and registered the following store launchers:\n\n{names}\n\n"
                "Recommended stability flags have been configured automatically."
            )
        else:
            QMessageBox.information(
                self,
                "Scan Complete",
                "No new unmapped store executables were found in Drive C:."
            )

    def _sync_steam_login(self):
        try:
            copied = StoreManager.sync_native_steam_login(self.bottle)
            if copied:
                QMessageBox.information(
                    self,
                    "Steam Login Cache Synced",
                    "Successfully transferred native macOS Steam credentials and session tokens!\n\n"
                    "• config.vdf & loginusers.vdf (Account session tokens)\n"
                    "• registry.vdf (Valve AutoLoginUser registry hive)\n"
                    "• userdata/ (Cloud save cache & credentials)\n\n"
                    "Steam will now log in automatically inside this bottle without CEF web login errors."
                )
                self._load_stores()
            else:
                QMessageBox.warning(self, "Sync Notice", "No active native Steam credentials found to copy.")
        except Exception as e:
            QMessageBox.critical(self, "Sync Failed", str(e))
