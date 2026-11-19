"""
[FR-26, FR-27, FR-28] Game Store One-Click Installer Dialog for PySide6.
Provides 1-click deployment for Steam, Epic Games Launcher, and GOG Galaxy.
"""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QMessageBox
)

from ravlator.core.bottle import BottleManager
from ravlator.core.downloader import DownloadProgress
from ravlator.core.models import BottleConfig
from ravlator.core.stores import StoreManager, StoreDefinition


class StoreInstallerWorker(QThread):
    progress_updated = Signal(object)
    finished = Signal(bool, str)

    def __init__(self, bottle_id: str, store_id: str):
        super().__init__()
        self.bottle_id = bottle_id
        self.store_id = store_id

    def run(self):
        try:
            StoreManager.install_store(
                bottle_id=self.bottle_id,
                store_id=self.store_id,
                progress_callback=lambda p: self.progress_updated.emit(p)
            )
            self.finished.emit(True, "Installation complete.")
        except Exception as e:
            self.finished.emit(False, str(e))


class StoreInstallerDialog(QDialog):
    """Dialog allowing users to install gaming store launchers with automated stability fixes."""

    def __init__(self, bottle: BottleConfig, parent=None):
        super().__init__(parent)
        self.bottle = bottle
        self.setWindowTitle(f"Install Store Launchers — {bottle.name}")
        self.resize(700, 360)

        self.worker = None

        self._setup_ui()
        self._load_stores()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(f"Deploy Game Store Clients into <b>{self.bottle.name}</b>")
        layout.addWidget(header)

        notice = QLabel(
            "Note: Steam installations automatically include the Chromium Embedded Framework (CEF) "
            "stability arguments to prevent black screen issues."
        )
        notice.setStyleSheet("color: palette(placeholder-text);")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Store Name", "Status", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _load_stores(self):
        stores = StoreManager.list_supported_stores()
        self.table.setRowCount(len(stores))

        fresh_bottle = BottleManager.get_bottle(self.bottle.id)
        if fresh_bottle:
            self.bottle = fresh_bottle

        for row, s in enumerate(stores):
            self.table.setItem(row, 0, QTableWidgetItem(s.name))

            is_installed = StoreManager.is_store_installed(self.bottle, s.id)
            status_text = "Installed" if is_installed else "Available"
            self.table.setItem(row, 1, QTableWidgetItem(status_text))

            btn = QPushButton("Install")
            btn.setEnabled(not is_installed)
            if not is_installed:
                btn.clicked.connect(lambda _, store_def=s: self._install_store(store_def))
            self.table.setCellWidget(row, 2, btn)

    def _install_store(self, store: StoreDefinition):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.table.setEnabled(False)

        self.worker = StoreInstallerWorker(self.bottle.id, store.id)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, progress: DownloadProgress):
        self.progress_bar.setValue(int(progress.percentage))

    def _on_finished(self, success: bool, message: str):
        self.table.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, "Success", "Game store installed and added to bottle shortcuts!")
            self._load_stores()
        else:
            QMessageBox.critical(self, "Installation Failed", message)
