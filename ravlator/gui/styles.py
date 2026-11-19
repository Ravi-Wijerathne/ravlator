"""
[Section 5.1, NFR-01] macOS Human Interface Design Stylesheet & Theme System.
Provides a clean, unified macOS Light Theme adhering strictly to Apple HIG aesthetics.
"""


def get_stylesheet(theme_mode: str = "light") -> str:
    """Returns CSS/QSS stylesheet for Ravlator matching macOS HIG (Light Mode default)."""
    return """
    /* Global Application Canvas */
    QMainWindow, QDialog {
        background-color: #F5F5F7;
        color: #1D1D1F;
    }
    QWidget {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro", "Helvetica Neue", sans-serif;
        font-size: 13px;
        color: #1D1D1F;
    }

    /* Left Sidebar */
    QWidget#sidebar {
        background-color: #ECECEF;
        border-right: 1px solid #D1D1D6;
    }
    QWidget#sidebar QLabel {
        color: #1D1D1F;
        font-weight: bold;
    }
    QWidget#sidebar QListWidget {
        background-color: transparent;
        border: none;
        padding: 4px;
        outline: none;
    }
    QWidget#sidebar QListWidget::item {
        padding: 8px 12px;
        border-radius: 6px;
        color: #1D1D1F;
        margin-bottom: 2px;
    }
    QWidget#sidebar QListWidget::item:selected {
        background-color: #007AFF;
        color: #FFFFFF;
        font-weight: 600;
    }
    QWidget#sidebar QListWidget::item:hover:!selected {
        background-color: #DFDFE3;
    }
    QWidget#sidebar QPushButton {
        background-color: #FFFFFF;
        border: 1px solid #C7C7CC;
        border-radius: 6px;
        padding: 7px 12px;
        color: #1D1D1F;
        text-align: left;
        font-size: 12px;
        font-weight: 500;
    }
    QWidget#sidebar QPushButton:hover {
        background-color: #E2E2E8;
    }
    QWidget#sidebar QPushButton:pressed {
        background-color: #D5D5DC;
    }

    /* Content Area & Cards */
    QWidget#contentArea {
        background-color: #FFFFFF;
    }

    /* Tabs Navigation */
    QTabWidget::pane {
        border: 1px solid #E5E5EA;
        border-radius: 8px;
        background-color: #FFFFFF;
        top: -1px;
    }
    QTabBar::tab {
        background-color: #EBEBED;
        border: 1px solid #D1D1D6;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 18px;
        margin-right: 4px;
        font-size: 13px;
        font-weight: 500;
        color: #5C5C60;
    }
    QTabBar::tab:selected {
        background-color: #FFFFFF;
        color: #007AFF;
        font-weight: 600;
        border-bottom: 1px solid #FFFFFF;
    }
    QTabBar::tab:hover:!selected {
        background-color: #DFDFE4;
        color: #1D1D1F;
    }

    /* Buttons */
    QPushButton {
        background-color: #FFFFFF;
        border: 1px solid #C7C7CC;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 500;
        color: #1D1D1F;
    }
    QPushButton:hover {
        background-color: #F2F2F7;
        border-color: #AEAEB2;
    }
    QPushButton:pressed {
        background-color: #E5E5EA;
    }
    QPushButton:disabled {
        background-color: #F9F9FB;
        border-color: #E5E5EA;
        color: #AEAEB2;
    }
    QPushButton#primaryAction {
        background-color: #007AFF;
        border: 1px solid #0062CC;
        color: #FFFFFF;
        font-weight: 600;
    }
    QPushButton#primaryAction:hover {
        background-color: #0069D9;
    }
    QPushButton#primaryAction:pressed {
        background-color: #0056B3;
    }
    QPushButton#primaryAction:disabled {
        background-color: #99C8FF;
        border-color: #99C8FF;
        color: #FFFFFF;
    }
    QPushButton#dangerAction {
        background-color: #FFFFFF;
        border: 1px solid #FF3B30;
        color: #FF3B30;
        font-weight: 500;
    }
    QPushButton#dangerAction:hover {
        background-color: #FFECEB;
    }
    QPushButton#dangerAction:pressed {
        background-color: #FFD5D2;
    }

    /* Utility Grid Buttons */
    QPushButton#utilityBtn {
        background-color: #F8F8FA;
        border: 1px solid #E5E5EA;
        border-radius: 8px;
        padding: 12px 14px;
        text-align: left;
        font-size: 13px;
        font-weight: 600;
        color: #1D1D1F;
    }
    QPushButton#utilityBtn:hover {
        background-color: #EFF0F5;
        border-color: #007AFF;
    }
    QPushButton#utilityBtn:pressed {
        background-color: #E4E5ED;
    }
    QPushButton#utilityBtn:disabled {
        background-color: #FAFAFC;
        border-color: #F0F0F4;
        color: #C7C7CC;
    }

    /* Dropdowns & Text Inputs */
    QComboBox, QLineEdit {
        background-color: #FFFFFF;
        border: 1px solid #C7C7CC;
        border-radius: 6px;
        padding: 5px 10px;
        color: #1D1D1F;
        selection-background-color: #007AFF;
        selection-color: #FFFFFF;
    }
    QComboBox:focus, QLineEdit:focus {
        border: 1.5px solid #007AFF;
    }
    QComboBox:disabled, QLineEdit:disabled {
        background-color: #F2F2F7;
        color: #8E8E93;
        border-color: #E5E5EA;
    }

    /* Checkboxes */
    QCheckBox {
        spacing: 9px;
        color: #1D1D1F;
        font-size: 13px;
    }
    QCheckBox:disabled {
        color: #8E8E93;
    }
    QCheckBox::indicator {
        width: 17px;
        height: 17px;
        border: 1.5px solid #8E8E93;
        border-radius: 4px;
        background-color: #FFFFFF;
    }
    QCheckBox::indicator:hover {
        border-color: #007AFF;
    }
    QCheckBox::indicator:checked {
        background-color: #007AFF;
        border-color: #007AFF;
    }
    QCheckBox::indicator:disabled {
        border-color: #D1D1D6;
        background-color: #F2F2F7;
    }

    /* Table Widget */
    QTableWidget {
        background-color: #FFFFFF;
        border: 1px solid #E5E5EA;
        border-radius: 8px;
        gridline-color: #F2F2F7;
        color: #1D1D1F;
        selection-background-color: #EBF4FF;
        selection-color: #1D1D1F;
    }
    QHeaderView::section {
        background-color: #F7F7F9;
        padding: 7px 10px;
        border: none;
        border-bottom: 1px solid #E5E5EA;
        font-weight: 600;
        color: #5C5C60;
        font-size: 12px;
    }

    /* Group Boxes */
    QGroupBox {
        border: 1px solid #E5E5EA;
        border-radius: 8px;
        margin-top: 14px;
        padding-top: 12px;
        font-weight: 600;
        color: #1D1D1F;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 4px;
        color: #1D1D1F;
    }

    /* Dividers */
    QFrame[frameShape="4"] {
        color: #E5E5EA;
    }

    /* Scrollbars */
    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #C7C7CC;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #8E8E93;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    """
