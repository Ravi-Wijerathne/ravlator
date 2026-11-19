"""
[Section 3.1, 5.1.1] Icon Utility for macOS PySide6 Interface.
Renders vector icons with dynamic color tinting for macOS Light & Dark Modes.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def get_icon(name: str, color: Optional[QColor] = None, size: QSize = QSize(20, 20)) -> QIcon:
    """
    Renders an SVG icon from assets/icons/lucide/, or draws a clean vector fallback.
    """
    project_root = Path(__file__).resolve().parents[3]
    svg_path = project_root / "assets" / "icons" / "lucide" / f"{name}.svg"
    if not svg_path.exists():
        svg_path = Path("assets/icons/lucide") / f"{name}.svg"
    
    if svg_path.exists():
        renderer = QSvgRenderer(str(svg_path))
        if renderer.isValid():
            pixmap = QPixmap(size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            tint = color if color and color.isValid() else QColor("#1D1D1F")
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), tint)
            painter.end()
            return QIcon(pixmap)

    # Fallback programmatic vector icon generator for standalone execution
    pixmap = QPixmap(size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    draw_color = color if color and color.isValid() else QColor("#1D1D1F")
    painter.setPen(draw_color)
    painter.setBrush(Qt.NoBrush)

    w, h = size.width(), size.height()
    if name == "play":
        painter.setBrush(draw_color)
        painter.drawPolygon([
            pixmap.rect().topLeft() + (QSize(4, 3)),
            pixmap.rect().bottomLeft() + (QSize(4, -3)),
            pixmap.rect().topRight() + (QSize(-4, h // 2))
        ])
    elif name == "plus":
        painter.drawLine(w // 2, 4, w // 2, h - 4)
        painter.drawLine(4, h // 2, w - 4, h // 2)
    elif name == "settings":
        painter.drawEllipse(3, 3, w - 6, h - 6)
        painter.drawEllipse(w // 2 - 2, h // 2 - 2, 4, 4)
    elif name in ("stop", "square"):
        painter.setBrush(draw_color)
        painter.drawRect(5, 5, w - 10, h - 10)
    elif name in ("folder", "dir"):
        painter.drawRoundedRect(3, 6, w - 6, h - 9, 2, 2)
        painter.drawLine(3, 6, 8, 6)
        painter.drawLine(8, 6, 10, 3)
        painter.drawLine(10, 3, 14, 3)
    elif name in ("cpu", "process"):
        painter.drawRoundedRect(5, 5, w - 10, h - 10, 2, 2)
        painter.drawRect(8, 8, w - 16, h - 16)
    elif name in ("terminal", "cmd"):
        painter.drawLine(5, 6, 10, h // 2)
        painter.drawLine(10, h // 2, 5, h - 6)
        painter.drawLine(11, h - 6, w - 5, h - 6)
    elif name in ("refresh", "reset"):
        painter.drawArc(4, 4, w - 8, h - 8, 45 * 16, 270 * 16)
    else:
        painter.drawRoundedRect(3, 3, w - 6, h - 6, 3, 3)

    painter.end()
    return QIcon(pixmap)
