"""
[FR-29, FR-30, FR-31] Task Manager & Active Process Inspector Dialog.
Monitors running Windows/Wine processes with live auto-refresh and termination controls.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

from ravlator.core.bottle import BottleManager
from ravlator.core.models import BottleConfig
from ravlator.core.process import WineProcessManager
from ravlator.core.runner import RunnerManager
from ravlator.core.telemetry import ProcessTelemetry


class TaskManagerDialog(QDialog):
    """Live process monitor for the active Wine bottle."""

    def __init__(self, bottle: BottleConfig, parent=None):
        super().__init__(parent)
        self.bottle = bottle
        self.setWindowTitle(f"Task Manager — {bottle.name}")
        self.resize(760, 440)

        self._setup_ui()

        # Auto-refresh timer every 2 seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_processes)
        self.timer.start(2000)

        self._refresh_processes()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header = QLabel(f"Active Processes in <b>{self.bottle.name}</b>")
        header_layout.addWidget(header)
        header_layout.addStretch()

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_processes)
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Mem %", "Command Line"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Bottom Actions
        actions_layout = QHBoxLayout()

        btn_kill_selected = QPushButton("End Selected Process")
        btn_kill_selected.clicked.connect(self._kill_selected)
        actions_layout.addWidget(btn_kill_selected)

        actions_layout.addStretch()

        btn_stop = QPushButton("Stop Bottle (wineboot -s)")
        btn_stop.clicked.connect(self._stop_bottle)
        actions_layout.addWidget(btn_stop)

        btn_kill_all = QPushButton("Force Kill All (wineserver -k)")
        btn_kill_all.setStyleSheet("color: #FF3B30;")
        btn_kill_all.clicked.connect(self._force_kill_all)
        actions_layout.addWidget(btn_kill_all)

        layout.addLayout(actions_layout)

    def _refresh_processes(self):
        procs = ProcessTelemetry.list_bottle_processes(self.bottle.id)
        self.table.setRowCount(len(procs))

        for row, p in enumerate(procs):
            pid_item = QTableWidgetItem(str(p.pid))
            pid_item.setData(Qt.UserRole, p.pid)
            self.table.setItem(row, 0, pid_item)
            self.table.setItem(row, 1, QTableWidgetItem(p.name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{p.cpu_percent:.1f}%"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{p.mem_percent:.1f}%"))
            self.table.setItem(row, 4, QTableWidgetItem(p.command))

    def _kill_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a process row to terminate.")
            return

        row = selected_rows[0].row()
        pid_item = self.table.item(row, 0)
        pid = int(pid_item.data(Qt.UserRole))

        success = ProcessTelemetry.terminate_process(pid, force=True)
        if success:
            self._refresh_processes()
        else:
            QMessageBox.critical(self, "Error", f"Could not terminate PID {pid}.")

    def _stop_bottle(self):
        runner_dir = RunnerManager.get_runner_dir(self.bottle.runner_id)
        WineProcessManager.stop_bottle(self.bottle, runner_dir)
        self._refresh_processes()

    def _force_kill_all(self):
        runner_dir = RunnerManager.get_runner_dir(self.bottle.runner_id)
        WineProcessManager.force_kill_bottle(self.bottle, runner_dir)
        self._refresh_processes()
        QMessageBox.information(self, "Terminated", "All wine processes have been terminated.")

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)
