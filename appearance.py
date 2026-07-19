"""Тема оформления и размер шрифта интерфейса ChatList."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QMenuBar,
    QPushButton,
    QStyleFactory,
    QWidget,
)

import models as model_service

FONT_FAMILY = "Segoe UI"
APP_ICON_PATH = Path(__file__).resolve().parent / "app.ico"

DARK_STYLESHEET = """
QWidget {
    color: #f0f0f0;
    background-color: #2d2d30;
}
QMainWindow, QDialog {
    background-color: #2d2d30;
}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QSpinBox, QListWidget, QTableWidget {
    background-color: #1e1e1e;
    color: #f0f0f0;
    border: 1px solid #5a5a5a;
    selection-background-color: #264f78;
    selection-color: #ffffff;
}
QComboBox {
    background-color: #1e1e1e;
    color: #f0f0f0;
    border: 1px solid #5a5a5a;
    padding: 2px 8px 2px 8px;
}
QComboBox:disabled {
    color: #c8c8c8;
    background-color: #252526;
}
QComboBox::drop-down {
    border-left: 1px solid #5a5a5a;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #252526;
    color: #f0f0f0;
    border: 1px solid #5a5a5a;
    selection-background-color: #264f78;
}
QGroupBox {
    border: 1px solid #5a5a5a;
    margin-top: 8px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #f0f0f0;
}
QPushButton {
    background-color: #3e3e42;
    color: #f0f0f0;
    border: 1px solid #5a5a5a;
    padding: 4px 12px;
}
QPushButton:hover {
    background-color: #4e4e52;
}
QPushButton:disabled {
    color: #888888;
    background-color: #333337;
}
QHeaderView::section {
    background-color: #3e3e42;
    color: #f0f0f0;
    border: 1px solid #5a5a5a;
    padding: 4px;
}
QTableWidget {
    gridline-color: #5a5a5a;
    alternate-background-color: #252526;
}
QMenuBar {
    background-color: #2d2d30;
    color: #f0f0f0;
}
QMenuBar::item:selected {
    background-color: #3e3e42;
}
QMenu {
    background-color: #2d2d30;
    color: #f0f0f0;
    border: 1px solid #5a5a5a;
}
QMenu::item:selected {
    background-color: #264f78;
}
QCheckBox {
    spacing: 6px;
}
QScrollBar:vertical {
    background: #2d2d30;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #5a5a5a;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar:horizontal {
    background: #2d2d30;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #5a5a5a;
    min-width: 24px;
    border-radius: 4px;
}
"""


def load_app_icon() -> QIcon:
    if APP_ICON_PATH.is_file():
        icon = QIcon(str(APP_ICON_PATH))
        if not icon.isNull():
            return icon
    return QIcon()


def get_font_size() -> int:
    return model_service.get_font_size()


def get_theme() -> str:
    return model_service.get_theme()


def body_font(font_size: int | None = None) -> QFont:
    size = font_size if font_size is not None else get_font_size()
    return QFont(FONT_FAMILY, size)


def button_font(font_size: int | None = None) -> QFont:
    size = font_size if font_size is not None else get_font_size()
    return QFont(FONT_FAMILY, max(8, size - 1))


def caption_font(font_size: int | None = None) -> QFont:
    size = font_size if font_size is not None else get_font_size()
    return QFont(FONT_FAMILY, max(8, size - 1))


def apply_theme(app: QApplication, theme: str | None = None) -> None:
    selected_theme = theme or get_theme()

    if selected_theme == "dark":
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 48))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 48))
        palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Button, QColor(62, 62, 66))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(38, 79, 120))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Link, QColor(100, 180, 255))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 150, 150))
        palette.setColor(QPalette.ColorRole.Light, QColor(90, 90, 90))
        palette.setColor(QPalette.ColorRole.Mid, QColor(70, 70, 70))
        palette.setColor(QPalette.ColorRole.Dark, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(20, 20, 20))
        app.setPalette(palette)
        app.setStyleSheet(DARK_STYLESHEET)
        return

    style_name = "Windows11" if "Windows11" in QStyleFactory.keys() else "Fusion"
    app.setStyle(style_name)
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet("")


def apply_font_size(app: QApplication, font_size: int | None = None) -> None:
    app.setFont(body_font(font_size))


def apply_fonts_to_widget(root: QWidget, font_size: int | None = None) -> None:
    body = body_font(font_size)
    button = button_font(font_size)
    caption = caption_font(font_size)

    root.setFont(body)
    for widget in root.findChildren(QWidget):
        if isinstance(widget, (QPushButton, QDialogButtonBox)):
            widget.setFont(button)
        elif isinstance(widget, QMenuBar):
            widget.setFont(caption)
        else:
            widget.setFont(body)


def apply_app_appearance(app: QApplication) -> None:
    apply_theme(app)
    apply_font_size(app)
