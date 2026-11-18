"""
[FR-17, FR-18, NFR-01] Dependencies Dialog for PySide6.
Provides 1-click installation of Windows runtimes with non-blocking QThread execution.
"""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QMessageBox
)

from ravlator.core.bottle import BottleManager
from ravlator.core.dependencies import DependencyManager
from ravlator.core.downloader import DownloadProgress
from ravlator.core.models import BottleConfig, DependencyRecipe


class DependencyWorker(QThread):
    progress_updated = Signal(object)
    finished = Signal(bool, str)

    def __init__(self, bottle_id: str, recipe_id: str):
        super().__init__()
        self.bottle_id = bottle_id
        self.recipe_id = recipe_id

    def run(self):
        try:
            DependencyManager.install_dependency(
                bottle_id=self.bottle_id,
                recipe_id=self.recipe_id,
                progress_callback=lambda p: self.progress_updated.emit(p)
            )
            self.finished.emit(True, "Installation complete.")
        except Exception as e:
            self.finished.emit(False, str(e))


class DependenciesDialog(QDialog):
    """Catalog dialog to view and install runtime packages inside the active bottle."""

    def __init__(self, bottle: BottleConfig, parent=None):
        super().__init__(parent)
        self.bottle = bottle
        self.setWindowTitle(f"Dependencies — {bottle.name}")
        self.resize(680, 420)

        self.worker = None

        self._setup_ui()
        self._load_dependencies()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(f"Manage Runtime Dependencies for <b>{self.bottle.name}</b>")
        layout.addWidget(header)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Category", "Status", "Action"])
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

    def _load_dependencies(self):
        recipes = DependencyManager.get_available_recipes()
        self.table.setRowCount(len(recipes))

        # Re-fetch latest bottle state
        fresh_bottle = BottleManager.get_bottle(self.bottle.id)
        if fresh_bottle:
            self.bottle = fresh_bottle

        for row, r in enumerate(recipes):
            self.table.setItem(row, 0, QTableWidgetItem(r.name))
            self.table.setItem(row, 1, QTableWidgetItem(r.category))

            is_installed = r.id in self.bottle.installed_dependencies
            status_text = "Installed" if is_installed else "Available"
            self.table.setItem(row, 2, QTableWidgetItem(status_text))

            btn = QPushButton("Install")
            btn.setEnabled(not is_installed)
            if not is_installed:
                btn.clicked.connect(lambda _, rec=r: self._install_dep(rec))
            self.table.setCellWidget(row, 3, btn)

    def _install_dep(self, recipe: DependencyRecipe):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.table.setEnabled(False)

        self.worker = DependencyWorker(self.bottle.id, recipe.id)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, progress: DownloadProgress):
        self.progress_bar.setValue(int(progress.percentage))

    def _on_finished(self, success: bool, message: str):
        self.table.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, "Success", "Dependency installed successfully!")
            self._load_dependencies()
        else:
            QMessageBox.critical(self, "Installation Failed", message)
