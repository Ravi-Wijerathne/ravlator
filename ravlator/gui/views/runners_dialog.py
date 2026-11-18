"""
[FR-07, FR-08, FR-10, NFR-01] Runners Management Dialog for PySide6.
Enables downloading Wine-CX / GPTK 2 from GitHub CDN or importing custom local engines.
"""

from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFileDialog, QMessageBox
)

from ravlator.core.downloader import DownloadProgress
from ravlator.core.models import RunnerInfo
from ravlator.core.runner import RunnerManager


class RunnerDownloadWorker(QThread):
    progress_updated = Signal(object)
    finished = Signal(bool, str)

    def __init__(self, runner_id: str):
        super().__init__()
        self.runner_id = runner_id

    def run(self):
        try:
            RunnerManager.download_and_extract_runner(
                runner_id=self.runner_id,
                progress_callback=lambda p: self.progress_updated.emit(p)
            )
            self.finished.emit(True, "Runner installed successfully.")
        except Exception as e:
            self.finished.emit(False, str(e))


class RunnersDialog(QDialog):
    """Dialog to manage installed and available execution engines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Runner & Engine Manager")
        self.resize(720, 420)

        self.worker = None

        self._setup_ui()
        self._load_runners()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header = QLabel("Installed and Available Wine / GPTK 2 Runners")
        header_layout.addWidget(header)
        header_layout.addStretch()

        btn_import = QPushButton(" Import Local Runner...")
        btn_import.clicked.connect(self._import_local_runner)
        header_layout.addWidget(btn_import)
        layout.addLayout(header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Runner Name", "Version", "Status", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _load_runners(self):
        runners = RunnerManager.get_available_runners()
        self.table.setRowCount(len(runners))

        for row, r in enumerate(runners):
            self.table.setItem(row, 0, QTableWidgetItem(r.name))
            self.table.setItem(row, 1, QTableWidgetItem(r.version))

            status_text = "Installed" if r.is_installed else "Available (CDN)"
            self.table.setItem(row, 2, QTableWidgetItem(status_text))

            if r.is_installed:
                btn = QPushButton("Uninstall")
                btn.clicked.connect(lambda _, run_id=r.id: self._uninstall_runner(run_id))
            else:
                btn = QPushButton("Download")
                btn.clicked.connect(lambda _, run_id=r.id: self._download_runner(run_id))
            self.table.setCellWidget(row, 3, btn)

    def _download_runner(self, runner_id: str):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.table.setEnabled(False)

        self.worker = RunnerDownloadWorker(runner_id)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, progress: DownloadProgress):
        self.progress_bar.setValue(int(progress.percentage))

    def _on_finished(self, success: bool, message: str):
        self.table.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, "Success", "Runner unpacked and ready for gaming!")
            self._load_runners()
        else:
            QMessageBox.critical(self, "Download Error", message)

    def _import_local_runner(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Local Wine Distribution (Containing bin/wine64)",
            str(Path.home())
        )
        if not path:
            return

        try:
            RunnerManager.register_local_runner(Path(path))
            QMessageBox.information(self, "Import Successful", f"Registered local runner from:\n{path}")
            self._load_runners()
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    def _uninstall_runner(self, runner_id: str):
        confirm = QMessageBox.question(
            self,
            "Confirm Uninstall",
            f"Are you sure you want to remove runner '{runner_id}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            RunnerManager.uninstall_runner(runner_id)
            self._load_runners()
