"""
[Section 3.2, 7.2] Main PySide6 Application Entry Point.
Initializes the Qt event loop, theme palette, and main window.
"""

import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ravlator.core.config import Config
from ravlator.gui.main_window import MainWindow
from ravlator.gui.styles import get_stylesheet


def main():
    # macOS High-DPI & Platform setup
    app = QApplication(sys.argv)
    app.setApplicationName("Ravlator")
    app.setOrganizationName("Ravlator")
    app.setApplicationDisplayName("Ravlator")
    app.setStyle("Fusion")

    # Application Dock & Window Icon
    logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    # Set default native macOS font hierarchy
    font = QFont("-apple-system", 13)
    app.setFont(font)

    # Apply unified macOS Light Theme [User preference: light theme only]
    app.setStyleSheet(get_stylesheet("light"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
