"""
[Section 3.2, 7.2] Main PySide6 Application Entry Point.
Initializes the Qt event loop, theme palette, and main window.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ravlator.gui.main_window import MainWindow


def main():
    # macOS High-DPI & Platform setup
    app = QApplication(sys.argv)
    app.setApplicationName("Ravlator")
    app.setOrganizationName("Ravlator")
    app.setApplicationDisplayName("Ravlator")

    # Set default native macOS font hierarchy
    font = QFont("-apple-system", 12)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
