"""
[FR-32] Real-Time Wine Diagnostic Log Viewer Dialog.
Displays stdout/stderr logs with search filter, auto-refresh, and export capabilities.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QLineEdit, QFileDialog, QMessageBox, QCheckBox
)

from ravlator.core.models import BottleConfig
from ravlator.core.telemetry import ProcessTelemetry


class LogViewerDialog(QDialog):
    """Real-time log streamer and diagnostic inspection window."""

    def __init__(self, bottle: BottleConfig, parent=None):
        super().__init__(parent)
        self.bottle = bottle
        self.setWindowTitle(f"Wine Logs — {bottle.name}")
        self.resize(760, 480)

        self._setup_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_refresh)
        self.timer.start(1500)

        self._refresh_log()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header with Search and Auto-refresh
        header_layout = QHBoxLayout()
        header = QLabel(f"Wine Diagnostic Stream: <b>{self.bottle.name}</b>")
        header_layout.addWidget(header)
        header_layout.addStretch()

        self.chk_auto = QCheckBox("Auto-Refresh")
        self.chk_auto.setChecked(True)
        header_layout.addWidget(self.chk_auto)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_log)
        header_layout.addWidget(btn_refresh)

        layout.addLayout(header_layout)

        # Log Text Area
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        mono_font = QFont("Menlo", 11)
        mono_font.setStyleHint(QFont.Monospace)
        self.log_edit.setFont(mono_font)
        layout.addWidget(self.log_edit)

        # Filter bar and actions
        bottom_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter text...")
        self.search_input.textChanged.connect(self._filter_text)
        bottom_layout.addWidget(self.search_input)

        btn_copy = QPushButton("Copy All")
        btn_copy.clicked.connect(self._copy_all)
        bottom_layout.addWidget(btn_copy)

        btn_export = QPushButton("Export Log...")
        btn_export.clicked.connect(self._export_log)
        bottom_layout.addWidget(btn_export)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear_log)
        bottom_layout.addWidget(btn_clear)

        layout.addLayout(bottom_layout)

    def _refresh_log(self):
        content = ProcessTelemetry.read_recent_logs(self.bottle.id, max_lines=200)
        self.raw_content = content
        self._filter_text(self.search_input.text())
        # Scroll to bottom
        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _auto_refresh(self):
        if self.chk_auto.isChecked():
            self._refresh_log()

    def _filter_text(self, query: str):
        if not hasattr(self, "raw_content"):
            return
        if not query:
            self.log_edit.setPlainText(self.raw_content)
        else:
            filtered = [
                line for line in self.raw_content.splitlines()
                if query.lower() in line.lower()
            ]
            self.log_edit.setPlainText("\n".join(filtered))

    def _copy_all(self):
        self.log_edit.selectAll()
        self.log_edit.copy()
        QMessageBox.information(self, "Copied", "Log contents copied to clipboard.")

    def _export_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostic Log",
            f"{self.bottle.name}_log.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.log_edit.toPlainText())
            QMessageBox.information(self, "Exported", f"Saved log to:\n{file_path}")

    def _clear_log(self):
        log_path = ProcessTelemetry.get_log_path(self.bottle.id)
        if log_path.exists():
            log_path.write_text("")
        self._refresh_log()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)
