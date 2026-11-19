"""
[Section 5.1] macOS Human Interface Design Stylesheet & Theme System.
Provides dark and light mode styles adhering to Apple HIG aesthetic.
"""


def get_stylesheet(theme_mode: str = "dark") -> str:
    """Returns CSS/QSS stylesheet for Ravlator matching macOS HIG."""
    if theme_mode == "light":
        return """
        QMainWindow, QDialog {
            background-color: #F2F2F7;
            color: #1D1D1F;
        }
        QWidget {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
            font-size: 13px;
            color: #1D1D1F;
        }
        QListWidget {
            background-color: #FFFFFF;
            border: 1px solid #D1D1D6;
            border-radius: 8px;
            padding: 4px;
        }
        QListWidget::item {
            padding: 8px 12px;
            border-radius: 6px;
        }
        QListWidget::item:selected {
            background-color: #007AFF;
            color: #FFFFFF;
        }
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #D1D1D6;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #E5E5EA;
        }
        QPushButton:pressed {
            background-color: #D1D1D6;
        }
        QComboBox, QLineEdit {
            background-color: #FFFFFF;
            border: 1px solid #D1D1D6;
            border-radius: 6px;
            padding: 5px 10px;
        }
        QTableWidget {
            background-color: #FFFFFF;
            border: 1px solid #D1D1D6;
            border-radius: 8px;
            gridline-color: #E5E5EA;
        }
        QHeaderView::section {
            background-color: #F2F2F7;
            padding: 6px;
            border: none;
            border-bottom: 1px solid #D1D1D6;
            font-weight: bold;
        }
        QCheckBox {
            spacing: 8px;
        }
        QFrame[frameShape="4"] {
            color: #D1D1D6;
        }
        """

    # Dark Mode (Default)
    return """
    QMainWindow, QDialog {
        background-color: #1E1E1E;
        color: #F5F5F7;
    }
    QWidget {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
        font-size: 13px;
        color: #F5F5F7;
    }
    QListWidget {
        background-color: #252526;
        border: 1px solid #383838;
        border-radius: 8px;
        padding: 4px;
    }
    QListWidget::item {
        padding: 8px 12px;
        border-radius: 6px;
    }
    QListWidget::item:selected {
        background-color: #007AFF;
        color: #FFFFFF;
    }
    QPushButton {
        background-color: #2D2D2D;
        border: 1px solid #3E3E3E;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 500;
        color: #F5F5F7;
    }
    QPushButton:hover {
        background-color: #383838;
    }
    QPushButton:pressed {
        background-color: #4A4A4A;
    }
    QComboBox, QLineEdit {
        background-color: #252526;
        border: 1px solid #3E3E3E;
        border-radius: 6px;
        padding: 5px 10px;
        color: #F5F5F7;
    }
    QTableWidget {
        background-color: #252526;
        border: 1px solid #383838;
        border-radius: 8px;
        gridline-color: #333333;
    }
    QHeaderView::section {
        background-color: #1E1E1E;
        padding: 6px;
        border: none;
        border-bottom: 1px solid #383838;
        font-weight: bold;
        color: #AEAEB2;
    }
    QCheckBox {
        spacing: 8px;
        color: #F5F5F7;
    }
    QFrame[frameShape="4"] {
        color: #383838;
    }
    """
