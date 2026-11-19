"""
[Section 3.2, 7.2] Main PySide6 Application Entry Point.
Initializes the Qt event loop, theme palette, and main window.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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

    # Set default native macOS font hierarchy
    font = QFont("-apple-system", 12)
    app.setFont(font)

    # Load and apply theme palette [SRS Section 5.1]
    settings = Config.load_global_settings()
    theme_mode = settings.get("theme_mode", "dark")
    app.setStyleSheet(get_stylesheet(theme_mode))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
