"""
[FR-33, FR-34] Snapshot Manager Dialog for PySide6.
Provides point-in-time state capture and instant rollback of bottle registry and configurations.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QInputDialog, QLineEdit
)

from ravlator.core.models import BottleConfig
from ravlator.core.snapshots import SnapshotManager


class SnapshotsDialog(QDialog):
    """Dialog allowing users to take and restore point-in-time snapshots."""

    def __init__(self, bottle: BottleConfig, parent=None):
        super().__init__(parent)
        self.bottle = bottle
        self.setWindowTitle(f"Snapshots — {bottle.name}")
        self.resize(720, 380)

        self._setup_ui()
        self._load_snapshots()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header = QLabel(f"Point-in-Time Snapshots for <b>{self.bottle.name}</b>")
        header_layout.addWidget(header)
        header_layout.addStretch()

        btn_take = QPushButton("+ Take Snapshot")
        btn_take.clicked.connect(self._create_snapshot)
        header_layout.addWidget(btn_take)
        layout.addLayout(header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Created Date", "Description", "Snapshot ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Bottom Actions
        actions_layout = QHBoxLayout()

        btn_restore = QPushButton("Restore to Selected Snapshot")
        btn_restore.clicked.connect(self._restore_selected)
        actions_layout.addWidget(btn_restore)

        actions_layout.addStretch()

        btn_delete = QPushButton("Delete Snapshot")
        btn_delete.clicked.connect(self._delete_selected)
        actions_layout.addWidget(btn_delete)

        layout.addLayout(actions_layout)

    def _load_snapshots(self):
        snapshots = SnapshotManager.list_snapshots(self.bottle.id)
        self.table.setRowCount(len(snapshots))

        for row, s in enumerate(snapshots):
            name_item = QTableWidgetItem(s.name)
            name_item.setData(Qt.UserRole, s.id)
            self.table.setItem(row, 0, name_item)

            # Format ISO date
            date_display = s.created_at[:19].replace("T", " ")
            self.table.setItem(row, 1, QTableWidgetItem(date_display))
            self.table.setItem(row, 2, QTableWidgetItem(s.description or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(s.id))

    def _create_snapshot(self):
        name, ok = QInputDialog.getText(
            self,
            "New Snapshot",
            "Enter a name for this snapshot (e.g. 'Before Modding'):"
        )
        if not ok or not name.strip():
            return

        desc, ok = QInputDialog.getText(
            self,
            "Snapshot Description",
            "Optional description:"
        )
        try:
            SnapshotManager.create_snapshot(
                bottle_id=self.bottle.id,
                name=name.strip(),
                description=desc.strip() if ok else ""
            )
            QMessageBox.information(self, "Snapshot Created", f"Snapshot '{name}' captured successfully!")
            self._load_snapshots()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to take snapshot: {e}")

    def _restore_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a snapshot row to restore.")
            return

        row = selected_rows[0].row()
        snap_id = self.table.item(row, 0).data(Qt.UserRole)
        snap_name = self.table.item(row, 0).text()

        confirm = QMessageBox.question(
            self,
            "Confirm Rollback",
            f"Are you sure you want to rollback to snapshot '{snap_name}'?\n"
            "This will revert the bottle registry and configuration to this point in time.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                SnapshotManager.rollback_snapshot(self.bottle.id, snap_id)
                QMessageBox.information(self, "Success", f"Bottle successfully restored to '{snap_name}'.")
            except Exception as e:
                QMessageBox.critical(self, "Rollback Failed", str(e))

    def _delete_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        snap_id = self.table.item(row, 0).data(Qt.UserRole)
        SnapshotManager.delete_snapshot(self.bottle.id, snap_id)
        self._load_snapshots()
