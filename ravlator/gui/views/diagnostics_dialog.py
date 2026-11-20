"""
[FR-07, FR-11] System Diagnostics & Hardware Compatibility Dialog.
Displays macOS version, Rosetta 2, AVX2, and Ray Tracing translation readiness.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit
)

from ravlator.core.diagnostics import DiagnosticsManager


class DiagnosticsDialog(QDialog):
    """System compatibility and hardware evaluation panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Diagnostics & Gaming Capabilities")
        self.setFixedWidth(540)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        diag = DiagnosticsManager.get_system_diagnostics()

        title = QLabel(f"<b>Hardware & OS Environment</b>")
        title_font = QFont()
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)

        # Status Badges
        def make_row(label: str, value: str, badge_color: str = None):
            row = QHBoxLayout()
            lbl = QLabel(label)
            val = QLabel(value)
            val.setStyleSheet(f"font-weight: bold; color: {badge_color or 'palette(text)'};")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            return row

        layout.addLayout(make_row("Operating System:", f"{diag.macos_name} ({diag.macos_version})"))
        layout.addLayout(make_row("Hardware Processor:", f"{diag.cpu_brand} ({diag.chip_generation})"))
        layout.addLayout(make_row("Unified Memory:", f"{diag.memory_gb} GB Unified RAM"))

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        features_title = QLabel("<b>Windows Gaming Translation Features</b>")
        layout.addWidget(features_title)

        rosetta_status = "Installed & Active" if diag.has_rosetta2 else "Missing (Action Required)"
        rosetta_color = "#34C759" if diag.has_rosetta2 else "#FF3B30"
        layout.addLayout(make_row("Rosetta 2 Translation:", rosetta_status, rosetta_color))

        avx2_status = "Supported (macOS 15+)" if diag.has_avx2_emulation else "Requires macOS 15+ (Sequoia)"
        avx2_color = "#34C759" if diag.has_avx2_emulation else "#FF9500"
        layout.addLayout(make_row("AVX2 Instruction Set:", avx2_status, avx2_color))

        rt_status = "Supported (M3/M4 Hardware RT)" if diag.has_hardware_raytracing else "Rasterization Only"
        rt_color = "#34C759" if diag.has_hardware_raytracing else "#8E8E93"
        layout.addLayout(make_row("DirectX 12 Ray Tracing:", rt_status, rt_color))

        # Recommendation box
        rec_frame = QFrame()
        rec_frame.setStyleSheet("background-color: palette(alternate-base); border-radius: 8px; padding: 10px;")
        rec_layout = QVBoxLayout(rec_frame)
        rec_layout.setContentsMargins(10, 10, 10, 10)

        rec_label = QLabel("<b>Recommended Configuration:</b>")
        rec_layout.addWidget(rec_label)

        if diag.has_avx2_emulation:
            msg = "• Your system is fully equipped to run modern AAA Windows titles requiring AVX2 vector instructions."
        else:
            msg = "• Upgrade to macOS Sequoia (15.0+) to unlock AVX2 instruction set emulation for newer AAA titles."
        rec_text = QLabel(msg)
        rec_text.setWordWrap(True)
        rec_layout.addWidget(rec_text)

        layout.addWidget(rec_frame)

        if not diag.has_rosetta2 and diag.is_apple_silicon:
            btn_install_rosetta = QPushButton("Install Rosetta 2 (Apple Silicon)")
            btn_install_rosetta.setObjectName("primaryAction")
            btn_install_rosetta.clicked.connect(self._install_rosetta)
            layout.addWidget(btn_install_rosetta)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _install_rosetta(self):
        from PySide6.QtWidgets import QMessageBox
        success = DiagnosticsManager.install_rosetta()
        if success:
            QMessageBox.information(self, "Rosetta 2 Installed", "Rosetta 2 translation engine was installed successfully.")
            self.accept()
        else:
            QMessageBox.warning(self, "Installation", "Please execute 'softwareupdate --install-rosetta' in Terminal to authorize.")
