import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Минимальная программа PyQt")
        self.setMinimumSize(360, 180)

        self.label = QLabel("Привет, PyQt!")
        self.label.setFont(QFont("Segoe UI", 11))
        self.label.setWordWrap(True)

        self.button = QPushButton("Нажми меня")
        self.button.setFont(QFont("Segoe UI", 9))
        self.button.setFixedWidth(120)
        self.button.clicked.connect(self.on_click)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(self.label)
        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.setLayout(layout)

    def on_click(self) -> None:
        self.label.setText("Минимальная программа на Python")


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Windows11" if "Windows11" in QStyleFactory.keys() else "Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
