"""Диалоговые окна управления данными ChatList."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import models as model_service
import network
import appearance
from version import __version__
from markdown_viewer import format_received_at, show_response_markdown


def _apply_dialog_appearance(dialog: QWidget) -> None:
    appearance.apply_fonts_to_widget(dialog)


class PromptEditDialog(QDialog):
    MODE_CREATE = "create"
    MODE_EDIT = "edit"
    MODE_VIEW = "view"

    def __init__(
        self,
        prompt: model_service.PromptRecord | None = None,
        parent: QWidget | None = None,
        mode: str | None = None,
    ) -> None:
        super().__init__(parent)
        if mode is None:
            mode = self.MODE_EDIT if prompt is not None else self.MODE_CREATE

        self._mode = mode
        self._prompt_id = prompt.id if prompt is not None else None

        titles = {
            self.MODE_CREATE: "Новый промт",
            self.MODE_EDIT: "Редактирование промта",
            self.MODE_VIEW: "Просмотр промта",
        }
        self.setWindowTitle(titles.get(mode, "Промт"))
        self.setMinimumSize(520, 360)

        self.prompt_input = QTextEdit()
        self.prompt_input.setFont(QFont("Segoe UI", 10))
        self.prompt_input.setMinimumHeight(180)
        if prompt is not None:
            self.prompt_input.setPlainText(prompt.prompt)

        self.tags_input = QLineEdit()
        self.tags_input.setFont(QFont("Segoe UI", 10))
        if prompt is not None:
            self.tags_input.setText(prompt.tags or "")

        form = QFormLayout()
        if prompt is not None and mode == self.MODE_VIEW:
            id_label = QLabel(str(prompt.id))
            date_label = QLabel(prompt.created_at)
            form.addRow("ID:", id_label)
            form.addRow("Дата:", date_label)
        form.addRow("Промт:", self.prompt_input)
        form.addRow("Теги:", self.tags_input)

        if mode == self.MODE_VIEW:
            self.prompt_input.setReadOnly(True)
            self.tags_input.setReadOnly(True)
            close_button = QPushButton("Закрыть")
            close_button.clicked.connect(self.reject)
            buttons = QHBoxLayout()
            buttons.addStretch()
            buttons.addWidget(close_button)
        else:
            save_button = QPushButton("Сохранить")
            cancel_button = QPushButton("Отменить")
            save_button.clicked.connect(self.save)
            cancel_button.clicked.connect(self.reject)
            buttons = QHBoxLayout()
            buttons.addStretch()
            buttons.addWidget(save_button)
            buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addLayout(form)
        layout.addLayout(buttons)
        _apply_dialog_appearance(self)

    def save(self) -> None:
        prompt_text = self.prompt_input.toPlainText().strip()
        if not prompt_text:
            title = "Новый промт" if self._mode == self.MODE_CREATE else "Редактирование промта"
            QMessageBox.warning(self, title, "Введите текст промта.")
            return

        tags = self.tags_input.text().strip() or None
        if self._mode == self.MODE_CREATE:
            model_service.save_prompt(prompt_text, tags)
        else:
            model_service.update_prompt_record(self._prompt_id, prompt_text, tags)
        self.accept()


class PromptsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Управление промтами")
        self.resize(900, 520)

        self._sort_column = 1
        self._sort_desc = True
        self._order_by = "created_at"
        self._order_dir = "DESC"

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по тексту или тегам...")
        self.search_input.textChanged.connect(self.reload)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Дата", "Промт", "Теги"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(3, 140)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().sectionClicked.connect(self.on_sort)
        self.table.cellDoubleClicked.connect(self.on_edit_selected)

        self.create_button = QPushButton("Создать")
        self.open_button = QPushButton("Открыть")
        self.edit_button = QPushButton("Редактировать")
        self.delete_button = QPushButton("Удалить")
        self.refresh_button = QPushButton("Обновить")
        self.close_button = QPushButton("Закрыть")

        self.create_button.clicked.connect(self.create_prompt)
        self.open_button.clicked.connect(self.open_selected)
        self.edit_button.clicked.connect(self.on_edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        self.refresh_button.clicked.connect(self.refresh_table)
        self.close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.reload()
        _apply_dialog_appearance(self)

    def _sort_field(self) -> tuple[str, str]:
        mapping = {0: "id", 1: "created_at", 2: "prompt", 3: "tags"}
        field = mapping.get(self._sort_column, "created_at")
        return field, "DESC" if self._sort_desc else "ASC"

    def on_sort(self, column: int) -> None:
        if self._sort_column == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column = column
            self._sort_desc = column != 2
        self._order_by, self._order_dir = self._sort_field()
        self.reload()

    def reload(self, selected_id: int | None = None) -> None:
        search = self.search_input.text().strip() or None
        rows = model_service.load_prompts(search=search)

        if self._order_by == "created_at":
            rows.sort(key=lambda item: item.created_at, reverse=self._order_dir == "DESC")
        elif self._order_by == "prompt":
            rows.sort(key=lambda item: item.prompt.lower(), reverse=self._order_dir == "DESC")
        elif self._order_by == "tags":
            rows.sort(key=lambda item: (item.tags or "").lower(), reverse=self._order_dir == "DESC")
        elif self._order_by == "id":
            rows.sort(key=lambda item: item.id, reverse=self._order_dir == "DESC")

        self.table.setRowCount(len(rows))
        selected_row = -1
        for index, row in enumerate(rows):
            if selected_id is not None and row.id == selected_id:
                selected_row = index
            for col, value in enumerate([row.id, row.created_at, row.prompt, row.tags or ""]):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row.id)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 2:
                    item.setToolTip(row.prompt)
                self.table.setItem(index, col, item)

        if selected_row >= 0:
            self.table.selectRow(selected_row)

    def _selected_prompt_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _require_selected_prompt(self, action: str) -> model_service.PromptRecord | None:
        prompt_id = self._selected_prompt_id()
        if prompt_id is None:
            QMessageBox.information(
                self,
                "Управление промтами",
                f"Выберите промт для {action}.",
            )
            return None

        prompt = model_service.get_prompt_by_id(prompt_id)
        if prompt is None:
            QMessageBox.information(self, "Управление промтами", "Выбранный промт не найден.")
            return None
        return prompt

    def _sync_main_prompt_list(self) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "load_prompt_list"):
            parent.load_prompt_list()

    def create_prompt(self) -> None:
        dialog = PromptEditDialog(parent=self, mode=PromptEditDialog.MODE_CREATE)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.reload()
        self._sync_main_prompt_list()

    def open_selected(self, *_args: object) -> None:
        prompt = self._require_selected_prompt("просмотра")
        if prompt is None:
            return

        dialog = PromptEditDialog(prompt, self, mode=PromptEditDialog.MODE_VIEW)
        dialog.exec()

    def refresh_table(self) -> None:
        self.reload(selected_id=self._selected_prompt_id())

    def on_edit_selected(self, *_args: object) -> None:
        prompt = self._require_selected_prompt("редактирования")
        if prompt is None:
            return

        dialog = PromptEditDialog(prompt, self, mode=PromptEditDialog.MODE_EDIT)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.reload(selected_id=prompt.id)
        self._sync_main_prompt_list()

    def delete_selected(self) -> None:
        prompt_id = self._selected_prompt_id()
        if prompt_id is None:
            QMessageBox.information(self, "Управление промтами", "Выберите промт для удаления.")
            return

        message_box = QMessageBox(self)
        message_box.setWindowTitle("Управление промтами")
        message_box.setText("Удалить выбранный промт?")
        yes_button = message_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        no_button = message_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        message_box.setDefaultButton(no_button)
        message_box.exec()

        if message_box.clickedButton() != yes_button:
            return

        model_service.remove_prompt(prompt_id)
        self.reload()
        self._sync_main_prompt_list()


class ModelEditDialog(QDialog):
    def __init__(self, model: model_service.ModelRecord | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self.setWindowTitle("Редактирование модели" if model else "Новая модель")
        self.setMinimumWidth(420)

        self.name_input = QLineEdit(model.name if model else "")
        self.api_id_input = QLineEdit(model.api_id if model else "")
        self.api_url_input = QLineEdit(
            model.api_url if model else model_service.get_openrouter_endpoint()
        )
        self.api_key_env_input = QLineEdit(
            model.api_key_env_var if model else "OPENROUTER_API_KEY"
        )
        self.model_type_input = QLineEdit(model.model_type if model else "openrouter")
        self.active_checkbox = QCheckBox("Активна")
        self.active_checkbox.setChecked(bool(model.is_active) if model else True)

        form = QFormLayout()
        form.addRow("Название:", self.name_input)
        form.addRow("API ID:", self.api_id_input)
        form.addRow("URL API:", self.api_url_input)
        form.addRow("Переменная ключа:", self.api_key_env_input)
        form.addRow("Тип API:", self.model_type_input)
        form.addRow("", self.active_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText("Сохранить")
        if cancel_button is not None:
            cancel_button.setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        _apply_dialog_appearance(self)

    def get_data(self) -> dict[str, object]:
        return {
            "name": self.name_input.text().strip(),
            "api_id": self.api_id_input.text().strip(),
            "api_url": self.api_url_input.text().strip(),
            "api_key_env_var": self.api_key_env_input.text().strip(),
            "model_type": self.model_type_input.text().strip() or "openrouter",
            "is_active": 1 if self.active_checkbox.isChecked() else 0,
        }


class ModelsDialog(QDialog):
    COLUMN_WIDTHS = [50, 150, 180, 280, 140, 100, 70, 160]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Управление моделями")
        self.resize(1100, 480)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Название", "API ID", "URL API", "Ключ (.env)", "Тип", "Активна", "Дата создания"]
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, self.COLUMN_WIDTHS[column])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        add_button = QPushButton("Добавить")
        edit_button = QPushButton("Изменить")
        delete_button = QPushButton("Удалить")
        toggle_button = QPushButton("Вкл/Выкл")
        close_button = QPushButton("Закрыть")

        add_button.clicked.connect(self.add_model)
        edit_button.clicked.connect(self.edit_model)
        delete_button.clicked.connect(self.delete_model)
        toggle_button.clicked.connect(self.toggle_active)
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(edit_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(toggle_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.reload()
        _apply_dialog_appearance(self)

    @staticmethod
    def _format_created_at(created_at: str | None) -> str:
        if not created_at:
            return "—"
        try:
            parsed = datetime.fromisoformat(created_at)
            return parsed.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            return "—"

    def reload(self) -> None:
        rows = model_service.load_models()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row.id,
                row.name,
                row.api_id,
                row.api_url,
                row.api_key_env_var,
                row.model_type or "",
                "Да" if row.is_active else "Нет",
                self._format_created_at(row.created_at),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row.id)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(index, col, item)

    def _selected_model_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def add_model(self) -> None:
        dialog = ModelEditDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not data["name"] or not data["api_id"]:
            QMessageBox.warning(self, "Модели", "Заполните название и API ID.")
            return
        model_service.add_model(
            name=str(data["name"]),
            api_id=str(data["api_id"]),
            is_active=int(data["is_active"]),
            api_url=str(data["api_url"]),
            api_key_env_var=str(data["api_key_env_var"]),
            model_type=str(data["model_type"]),
        )
        self.reload()

    def edit_model(self) -> None:
        model_id = self._selected_model_id()
        if model_id is None:
            QMessageBox.information(self, "Модели", "Выберите модель.")
            return
        model = model_service.get_model_by_id(model_id)
        if not model:
            return

        dialog = ModelEditDialog(model, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        model.name = str(data["name"])
        model.api_id = str(data["api_id"])
        model.api_url = str(data["api_url"])
        model.api_key_env_var = str(data["api_key_env_var"])
        model.model_type = str(data["model_type"])
        model.is_active = int(data["is_active"])
        model_service.edit_model(model)
        self.reload()

    def delete_model(self) -> None:
        model_id = self._selected_model_id()
        if model_id is None:
            QMessageBox.information(self, "Модели", "Выберите модель.")
            return
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Модели")
        message_box.setText("Удалить выбранную модель? Сохранённые результаты останутся в базе.")
        yes_button = message_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        no_button = message_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        message_box.setDefaultButton(no_button)
        message_box.exec()

        if message_box.clickedButton() != yes_button:
            return
        model_service.remove_model(model_id)
        self.reload()

    def toggle_active(self) -> None:
        model_id = self._selected_model_id()
        if model_id is None:
            QMessageBox.information(self, "Модели", "Выберите модель.")
            return
        model = model_service.get_model_by_id(model_id)
        if not model:
            return
        model_service.set_model_active(model_id, not bool(model.is_active))
        self.reload()


class ResultsDialog(QDialog):
    SORT_OPTIONS = {
        "Дата создания": ("saved_at", "DESC"),
        "Промт": ("prompt_text", "ASC"),
        "Модель": ("model_name", "ASC"),
    }

    ROW_HEIGHT = 140
    COL_ID_WIDTH = 60
    COL_DATE_WIDTH = 160
    COL_PROMPT_RATIO = 0.30
    COL_MODEL_RATIO = 0.20
    COL_ANSWER_RATIO = 0.50

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Сохранённые результаты")
        self.resize(950, 650)

        search_label = QLabel("Поиск:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по промту, модели, ответу или тегам...")
        self.search_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.search_input.textChanged.connect(self.reload)

        sort_label = QLabel("Сортировать по:")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(list(self.SORT_OPTIONS.keys()))
        self.sort_combo.currentTextChanged.connect(self.reload)

        top_row = QHBoxLayout()
        top_row.addWidget(search_label)
        top_row.addWidget(self.search_input, stretch=1)
        top_row.addWidget(sort_label)
        top_row.addWidget(self.sort_combo)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Промт", "Модель", "Ответ", "Дата"])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, self.COL_ID_WIDTH)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, self.COL_DATE_WIDTH)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self.table.verticalHeader().setVisible(False)

        self.export_md_button = QPushButton("Экспорт в Markdown")
        self.export_json_button = QPushButton("Экспорт в JSON")
        self.open_button = QPushButton("Открыть")
        self.delete_button = QPushButton("Удалить")
        self.close_button = QPushButton("Закрыть")

        self.export_md_button.clicked.connect(lambda: self.export("markdown"))
        self.export_json_button.clicked.connect(lambda: self.export("json"))
        self.open_button.clicked.connect(self.open_selected_result)
        self.delete_button.clicked.connect(self.delete_selected)
        self.close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.export_md_button)
        buttons.addWidget(self.export_json_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(buttons)
        self.reload()
        self.update_column_widths()
        _apply_dialog_appearance(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.update_column_widths()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_column_widths()

    def update_column_widths(self) -> None:
        self.table.setColumnCount(5)

        viewport_width = self.table.viewport().width()
        if viewport_width <= 0:
            return

        fixed_width = self.COL_ID_WIDTH + self.COL_DATE_WIDTH
        free_width = max(viewport_width - fixed_width, 120)

        prompt_width = int(free_width * self.COL_PROMPT_RATIO)
        model_width = int(free_width * self.COL_MODEL_RATIO)
        answer_width = free_width - prompt_width - model_width

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, self.COL_ID_WIDTH)
        self.table.setColumnWidth(1, prompt_width)
        self.table.setColumnWidth(2, model_width)
        self.table.setColumnWidth(3, answer_width)
        self.table.setColumnWidth(4, self.COL_DATE_WIDTH)

    def _create_scrollable_text_widget(self, text: str, row_index: int) -> QTextEdit:
        widget = QTextEdit()
        widget.setReadOnly(True)
        widget.setPlainText(text)
        widget.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        widget.setFont(self.table.font())
        self._install_row_selection(widget, row_index)
        return widget

    def _install_row_selection(self, widget: QWidget, row_index: int) -> None:
        widget.setProperty("result_row_index", row_index)
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        row_index = watched.property("result_row_index")
        if row_index is not None:
            if event.type() == QEvent.Type.MouseButtonPress:
                self.table.selectRow(int(row_index))
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                self.open_selected_result(int(row_index))
        return super().eventFilter(watched, event)

    def _format_date(self, saved_at: str) -> str:
        try:
            parsed = datetime.fromisoformat(saved_at)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return saved_at

    def _sort_params(self) -> tuple[str, str]:
        return self.SORT_OPTIONS.get(self.sort_combo.currentText(), ("saved_at", "DESC"))

    def _current_results(self) -> list[model_service.ResultRecord]:
        search = self.search_input.text().strip() or None
        order_by, order_dir = self._sort_params()
        rows = model_service.load_results(search=search)

        if order_by == "saved_at":
            rows.sort(key=lambda item: item.saved_at, reverse=order_dir == "DESC")
        elif order_by == "prompt_text":
            rows.sort(key=lambda item: item.prompt_text.lower(), reverse=order_dir == "DESC")
        elif order_by == "model_name":
            rows.sort(key=lambda item: item.model_name.lower(), reverse=order_dir == "DESC")

        return rows

    def reload(self) -> None:
        rows = self._current_results()
        self.table.setRowCount(len(rows))

        for index, row in enumerate(rows):
            result_id = row.id
            prompt_text = row.prompt_text or ""
            model_name = row.model_name or "Неизвестная модель"
            response_text = row.response_text or ""
            saved_at = self._format_date(row.saved_at or "")

            id_item = QTableWidgetItem(str(result_id))
            id_item.setData(Qt.ItemDataRole.UserRole, result_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            id_item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))

            model_item = QTableWidgetItem(model_name)
            model_item.setData(Qt.ItemDataRole.UserRole, result_id)
            model_item.setFlags(model_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            model_item.setTextAlignment(
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            )

            date_item = QTableWidgetItem(saved_at)
            date_item.setData(Qt.ItemDataRole.UserRole, result_id)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            date_item.setTextAlignment(
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            )

            prompt_widget = self._create_scrollable_text_widget(prompt_text, index)
            answer_widget = self._create_scrollable_text_widget(response_text, index)

            self.table.setItem(index, 0, id_item)
            self.table.setCellWidget(index, 1, prompt_widget)
            self.table.setItem(index, 2, model_item)
            self.table.setCellWidget(index, 3, answer_widget)
            self.table.setItem(index, 4, date_item)
            self.table.setRowHeight(index, self.ROW_HEIGHT)

        self.update_column_widths()

    def _get_result_by_id(self, result_id: int) -> model_service.ResultRecord | None:
        for result in self._current_results():
            if result.id == result_id:
                return result
        for result in model_service.load_results():
            if result.id == result_id:
                return result
        return None

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        self.open_selected_result(row)

    def open_selected_result(self, row: int | None = None) -> None:
        if row is None:
            row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Сохранённые результаты",
                "Выберите результат для просмотра.",
            )
            return

        item = self.table.item(row, 0)
        if not item:
            QMessageBox.information(
                self,
                "Сохранённые результаты",
                "Выберите результат для просмотра.",
            )
            return

        result_id = int(item.data(Qt.ItemDataRole.UserRole))
        result = self._get_result_by_id(result_id)
        if result is None:
            QMessageBox.information(
                self,
                "Сохранённые результаты",
                "Выберите результат для просмотра.",
            )
            return

        show_response_markdown(
            parent=self,
            model_name=result.model_name,
            prompt_text=result.prompt_text,
            response_text=result.response_text,
            received_at=format_received_at(result.saved_at),
        )

    def _selected_result_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def export(self, fmt: str) -> None:
        result_id = self._selected_result_id()
        if result_id is None:
            QMessageBox.information(self, "Сохранённые результаты", "Выберите результат для экспорта.")
            return

        results = [row for row in self._current_results() if row.id == result_id]
        if not results:
            QMessageBox.information(self, "Сохранённые результаты", "Выберите результат для экспорта.")
            return

        if fmt == "markdown":
            content = model_service.export_results_to_markdown(results)
            suffix = "Markdown (*.md)"
            default_name = "chatlist_results.md"
        else:
            content = model_service.export_results_to_json(results)
            suffix = "JSON (*.json)"
            default_name = "chatlist_results.json"

        file_path, _ = QFileDialog.getSaveFileName(self, "Экспорт", default_name, suffix)
        if not file_path:
            return
        Path(file_path).write_text(content, encoding="utf-8")
        QMessageBox.information(self, "Сохранённые результаты", f"Файл сохранён:\n{file_path}")

    def delete_selected(self) -> None:
        result_id = self._selected_result_id()
        if result_id is None:
            QMessageBox.information(self, "Сохранённые результаты", "Выберите результат для удаления.")
            return

        message_box = QMessageBox(self)
        message_box.setWindowTitle("Сохранённые результаты")
        message_box.setText("Удалить выбранный результат?")
        yes_button = message_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        no_button = message_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        message_box.setDefaultButton(no_button)
        message_box.exec()

        if message_box.clickedButton() != yes_button:
            return

        model_service.remove_result(result_id)
        self.reload()


class ImprovePromptWorker(QThread):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        original_prompt: str,
        model: model_service.ModelRecord,
        options: model_service.ImprovePromptOptions,
    ) -> None:
        super().__init__()
        self.original_prompt = original_prompt
        self.model = model
        self.options = options

    def run(self) -> None:
        result: network.RequestResult | None = None
        try:
            result = network.improve_prompt(
                self.original_prompt,
                self.model,
                options=self.options,
            )
            if not result.success:
                self.failed.emit(result.response_text)
                return
            parsed = model_service.parse_prompt_assistant_response(
                result.response_text,
                expect_alternatives=self.options.generate_alternatives,
                expect_adapted=self.options.adapt_to_type,
            )
            self.finished.emit(parsed)
        except ValueError as exc:
            raw_text = result.response_text if result is not None else ""
            message = str(exc)
            if raw_text:
                message = f"{message}\n\nОтвет модели:\n{raw_text}"
            self.failed.emit(message)
        except Exception as exc:
            self.failed.emit(str(exc))


class PromptImprovementDialog(QDialog):
    ADAPTATION_TYPES = [
        ("code", "Код"),
        ("analysis", "Анализ"),
        ("creative", "Творческий текст"),
    ]
    COMBO_MIN_HEIGHT = 30
    OPTIONS_MIN_HEIGHT = 130
    OPTIONS_MARGIN_H = 12
    OPTIONS_MARGIN_V = 12
    OPTIONS_ROW_SPACING = 10
    OPTIONS_TO_MODEL_GAP = 6

    def __init__(self, original_prompt: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._original_prompt = original_prompt.strip()
        self._applied_text: str | None = None
        self._worker: ImprovePromptWorker | None = None

        self.setWindowTitle("Улучшение промта")
        self.setMinimumSize(780, 850)
        self.resize(820, 900)

        body_font = QFont("Segoe UI", 10)
        button_font = QFont("Segoe UI", 9)
        combo_min_height = self.COMBO_MIN_HEIGHT

        self.original_input = QTextEdit()
        self.original_input.setFont(body_font)
        self.original_input.setReadOnly(True)
        self.original_input.setPlainText(self._original_prompt)
        self.original_input.setMinimumHeight(100)
        self.original_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.original_input.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.model_combo = QComboBox()
        self.model_combo.setFont(body_font)
        self.model_combo.setMinimumHeight(combo_min_height)
        self.model_combo.setFixedHeight(combo_min_height)
        self.model_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.status_label = QLabel("Выберите модель и нажмите «Улучшить».")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setWordWrap(True)

        self._populate_models()

        self.improve_button = QPushButton("Улучшить")
        self.improve_button.setFont(button_font)
        self.improve_button.setMinimumHeight(combo_min_height)
        self.improve_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.improve_button.clicked.connect(self.on_improve)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        model_row.addWidget(QLabel("Модель для улучшения:"))
        model_row.addWidget(self.model_combo, stretch=1)
        model_row.addWidget(self.improve_button)

        model_row_container = QWidget()
        model_row_layout = QVBoxLayout(model_row_container)
        model_row_layout.setContentsMargins(0, self.OPTIONS_TO_MODEL_GAP, 0, 0)
        model_row_layout.setSpacing(0)
        model_row_layout.addLayout(model_row)

        self.alternatives_checkbox = QCheckBox(
            "Генерировать варианты переформулировки (2–3 шт.)"
        )
        self.alternatives_checkbox.setFont(body_font)
        self.alternatives_checkbox.setMinimumHeight(26)
        self.alternatives_checkbox.setChecked(True)
        self.alternatives_checkbox.toggled.connect(self._update_options_visibility)

        self.adaptation_checkbox = QCheckBox("Адаптировать под тип модели")
        self.adaptation_checkbox.setFont(body_font)
        self.adaptation_checkbox.setMinimumHeight(26)
        self.adaptation_checkbox.setChecked(False)
        self.adaptation_checkbox.toggled.connect(self._on_adaptation_toggled)

        self.adaptation_type_combo = QComboBox()
        self.adaptation_type_combo.setFont(body_font)
        self.adaptation_type_combo.setMinimumHeight(combo_min_height)
        self.adaptation_type_combo.setFixedHeight(combo_min_height)
        self.adaptation_type_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        for type_key, type_label in self.ADAPTATION_TYPES:
            self.adaptation_type_combo.addItem(type_label, type_key)
        self.adaptation_type_combo.setEnabled(False)

        self.adaptation_type_label = QLabel("Тип адаптации:")
        self.adaptation_type_label.setFont(body_font)
        self.adaptation_type_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        adaptation_type_row = QHBoxLayout()
        adaptation_type_row.setSpacing(8)
        adaptation_type_row.setContentsMargins(0, 0, 0, 0)
        adaptation_type_row.addWidget(
            self.adaptation_type_label,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        adaptation_type_row.addWidget(
            self.adaptation_type_combo,
            stretch=1,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        adaptation_type_row_widget = QWidget()
        adaptation_type_row_widget.setFixedHeight(combo_min_height)
        adaptation_type_row_widget.setLayout(adaptation_type_row)

        options_group = QGroupBox("Опции")
        options_group.setFont(body_font)
        options_group.setFixedHeight(self.OPTIONS_MIN_HEIGHT)
        options_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        options_layout = QVBoxLayout(options_group)
        options_layout.setContentsMargins(
            self.OPTIONS_MARGIN_H,
            self.OPTIONS_MARGIN_V,
            self.OPTIONS_MARGIN_H,
            self.OPTIONS_MARGIN_V,
        )
        options_layout.setSpacing(self.OPTIONS_ROW_SPACING)
        options_layout.addWidget(self.alternatives_checkbox)
        options_layout.addWidget(self.adaptation_checkbox)
        options_layout.addWidget(adaptation_type_row_widget)

        self.improved_input = QTextEdit()
        self.improved_input.setFont(body_font)
        self.improved_input.setReadOnly(True)
        self.improved_input.setPlaceholderText("Здесь появится улучшенный промт...")
        self.improved_input.setMinimumHeight(120)
        self.improved_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.improved_input.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.alternatives_label = QLabel("Альтернативные варианты:")
        self.alternatives_label.setFont(body_font)

        self.alternatives_list = QListWidget()
        self.alternatives_list.setFont(body_font)
        self.alternatives_list.setMinimumHeight(120)
        self.alternatives_list.currentItemChanged.connect(self._update_alternative_button)

        self.adapted_label = QLabel("Адаптированный промпт:")
        self.adapted_label.setFont(body_font)
        self.adapted_label.setVisible(False)

        self.adapted_input = QTextEdit()
        self.adapted_input.setFont(body_font)
        self.adapted_input.setReadOnly(True)
        self.adapted_input.setPlaceholderText("Здесь появится адаптированный промпт...")
        self.adapted_input.setMinimumHeight(100)
        self.adapted_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.adapted_input.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.adapted_input.setVisible(False)

        self.use_improved_button = QPushButton("Использовать улучшенный")
        self.use_improved_button.setFont(button_font)
        self.use_improved_button.setEnabled(False)
        self.use_improved_button.clicked.connect(self.on_use_improved)

        self.use_alternative_button = QPushButton("Использовать альтернативу")
        self.use_alternative_button.setFont(button_font)
        self.use_alternative_button.setEnabled(False)
        self.use_alternative_button.clicked.connect(self.on_use_alternative)

        self.use_adapted_button = QPushButton("Использовать адаптированный")
        self.use_adapted_button.setFont(button_font)
        self.use_adapted_button.setEnabled(False)
        self.use_adapted_button.setVisible(False)
        self.use_adapted_button.clicked.connect(self.on_use_adapted)

        self.close_button = QPushButton("Закрыть")
        self.close_button.setFont(button_font)
        self.close_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.use_improved_button)
        buttons.addWidget(self.use_alternative_button)
        buttons.addWidget(self.use_adapted_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Исходный промт:"))
        layout.addWidget(self.original_input)
        layout.addWidget(options_group)
        layout.addWidget(model_row_container)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Улучшенный промт:"))
        layout.addWidget(self.improved_input)
        layout.addWidget(self.alternatives_label)
        layout.addWidget(self.alternatives_list)
        layout.addWidget(self.adapted_label)
        layout.addWidget(self.adapted_input)
        layout.addLayout(buttons)

        self._update_options_visibility()
        _apply_dialog_appearance(self)

    def applied_text(self) -> str | None:
        return self._applied_text

    def _populate_models(self) -> None:
        self.model_combo.clear()
        active_models = model_service.load_active_models()
        if not active_models:
            self.model_combo.addItem("Нет активных моделей", None)
            self.model_combo.setEnabled(False)
            self.improve_button.setEnabled(False)
            self.status_label.setText(
                "Нет активных моделей. Добавьте или включите модели в меню «Модели»."
            )
            return

        selected_index = 0
        preferred_id = model_service.get_prompt_assistant_model_id()
        for index, model in enumerate(active_models):
            self.model_combo.addItem(model.name, model.id)
            if preferred_id is not None and model.id == preferred_id:
                selected_index = index
        self.model_combo.setCurrentIndex(selected_index)

    def _selected_model(self) -> model_service.ModelRecord | None:
        model_id = self.model_combo.currentData()
        if model_id is None:
            return None
        return model_service.get_model_by_id(int(model_id))

    def _save_selected_model(self) -> None:
        model_id = self.model_combo.currentData()
        if model_id is not None:
            model_service.set_prompt_assistant_model_id(int(model_id))

    def _build_options(self) -> model_service.ImprovePromptOptions:
        adaptation_type = self.adaptation_type_combo.currentData()
        return model_service.ImprovePromptOptions(
            generate_alternatives=self.alternatives_checkbox.isChecked(),
            adapt_to_type=self.adaptation_checkbox.isChecked(),
            adaptation_type=str(adaptation_type or "code"),
        )

    def _update_options_visibility(self) -> None:
        show_alternatives = self.alternatives_checkbox.isChecked()
        self.alternatives_label.setVisible(show_alternatives)
        self.alternatives_list.setVisible(show_alternatives)
        if not show_alternatives:
            self.alternatives_list.clear()
            self.use_alternative_button.setEnabled(False)

    def _on_adaptation_toggled(self, checked: bool) -> None:
        self.adaptation_type_combo.setEnabled(checked)
        self.adapted_label.setVisible(checked)
        self.adapted_input.setVisible(checked)
        self.use_adapted_button.setVisible(checked)
        if not checked:
            self.adapted_input.clear()
            self.use_adapted_button.setEnabled(False)

    def _update_alternative_button(self) -> None:
        has_selection = (
            self.alternatives_checkbox.isChecked()
            and self.alternatives_list.currentItem() is not None
        )
        self.use_alternative_button.setEnabled(has_selection)

    def _set_busy(self, busy: bool) -> None:
        self.improve_button.setEnabled(not busy and self.model_combo.isEnabled())
        self.model_combo.setEnabled(not busy and self.model_combo.count() > 0)
        self.alternatives_checkbox.setEnabled(not busy)
        self.adaptation_checkbox.setEnabled(not busy)
        self.adaptation_type_combo.setEnabled(
            not busy and self.adaptation_checkbox.isChecked()
        )
        self.use_improved_button.setEnabled(
            not busy and bool(self.improved_input.toPlainText().strip())
        )
        self.use_alternative_button.setEnabled(
            not busy
            and self.alternatives_checkbox.isChecked()
            and self.alternatives_list.currentItem() is not None
        )
        self.use_adapted_button.setEnabled(
            not busy
            and self.adaptation_checkbox.isChecked()
            and bool(self.adapted_input.toPlainText().strip())
        )
        self.close_button.setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

    def on_improve(self) -> None:
        if not self._original_prompt:
            QMessageBox.warning(self, "Улучшение промта", "Исходный промт пустой.")
            return

        model = self._selected_model()
        if model is None:
            QMessageBox.warning(
                self,
                "Улучшение промта",
                "Выберите активную модель для улучшения промта.",
            )
            return

        if not model_service.get_api_key(model.api_key_env_var):
            QMessageBox.warning(
                self,
                "Улучшение промта",
                model_service.get_missing_api_key_message(model.api_key_env_var),
            )
            return

        self._set_busy(True)
        self.status_label.setText(f"Отправка запроса в модель «{model.name}»...")
        self.improved_input.clear()
        self.alternatives_list.clear()
        self.adapted_input.clear()

        options = self._build_options()
        self._worker = ImprovePromptWorker(self._original_prompt, model, options)
        self._worker.finished.connect(self.on_improve_finished)
        self._worker.failed.connect(self.on_improve_failed)
        self._worker.start()

    def on_improve_finished(self, result: object) -> None:
        self._set_busy(False)
        if not isinstance(result, model_service.PromptAssistantResult):
            self.status_label.setText("Получен некорректный ответ ассистента.")
            return

        self.improved_input.setPlainText(result.improved)

        self.alternatives_list.clear()
        if self.alternatives_checkbox.isChecked():
            for alternative in result.alternatives:
                self.alternatives_list.addItem(alternative)

        if self.adaptation_checkbox.isChecked():
            self.adapted_input.setPlainText(result.adapted)
        else:
            self.adapted_input.clear()

        self.use_improved_button.setEnabled(True)
        self._update_alternative_button()
        if self.alternatives_list.count() > 0:
            self.alternatives_list.setCurrentRow(0)

        self.use_adapted_button.setEnabled(
            self.adaptation_checkbox.isChecked() and bool(result.adapted.strip())
        )

        self._save_selected_model()

        status_parts = ["Готово.", "Получен улучшенный промт"]
        if self.alternatives_checkbox.isChecked() and result.alternatives:
            status_parts.append(f"и {len(result.alternatives)} альтернатив")
        if self.adaptation_checkbox.isChecked() and result.adapted.strip():
            type_label = self.adaptation_type_combo.currentText()
            status_parts.append(f"и адаптация «{type_label}»")
        self.status_label.setText(" ".join(status_parts) + ".")

    def on_improve_failed(self, message: str) -> None:
        self._set_busy(False)
        self.status_label.setText("Не удалось улучшить промт.")
        QMessageBox.critical(
            self,
            "Улучшение промта",
            f"Не удалось получить улучшенный промт.\n\n{message}",
        )

    def on_use_improved(self) -> None:
        text = self.improved_input.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Улучшение промта", "Улучшенный промт пока не получен.")
            return
        self._applied_text = text
        self._save_selected_model()
        self.accept()

    def on_use_alternative(self) -> None:
        item = self.alternatives_list.currentItem()
        if item is None:
            QMessageBox.information(
                self,
                "Улучшение промта",
                "Выберите альтернативный вариант в списке.",
            )
            return

        text = item.text().strip()
        if not text:
            QMessageBox.information(
                self,
                "Улучшение промта",
                "Выберите альтернативный вариант в списке.",
            )
            return

        self._applied_text = text
        self._save_selected_model()
        self.accept()

    def on_use_adapted(self) -> None:
        text = self.adapted_input.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self,
                "Улучшение промта",
                "Адаптированный промпт пока не получен.",
            )
            return
        self._applied_text = text
        self._save_selected_model()
        self.accept()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)


class TestOpenRouterWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key

    def run(self) -> None:
        success, message = network.test_openrouter_connection(self.api_key)
        self.finished.emit(success, message)


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(480)
        self._applied_theme = model_service.get_theme()
        self._applied_font_size = model_service.get_font_size()
        self._test_worker: TestOpenRouterWorker | None = None

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.addItem("Тёмная", "dark")
        current_theme_index = self.theme_combo.findData(self._applied_theme)
        self.theme_combo.setCurrentIndex(current_theme_index if current_theme_index >= 0 else 0)

        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(8, 24)
        self.font_size_input.setSingleStep(1)
        self.font_size_input.setValue(self._applied_font_size)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 300)
        self.timeout_input.setValue(int(float(model_service.get_setting_value("request_timeout", "90"))))

        self.db_path_input = QLineEdit(model_service.get_setting_value("db_path", "chatlist.db"))
        self.default_tags_input = QLineEdit(model_service.get_setting_value("default_tags", ""))
        self.log_checkbox = QCheckBox("Записывать историю запросов в файл chatlist.log")
        self.log_checkbox.setChecked(model_service.is_logging_enabled())

        self.assistant_model_combo = QComboBox()
        self._populate_assistant_models()

        form = QFormLayout()
        form.addRow("Тема оформления:", self.theme_combo)
        form.addRow("Размер шрифта:", self.font_size_input)
        form.addRow("Время ожидания ответа, сек.:", self.timeout_input)
        form.addRow("Файл базы данных:", self.db_path_input)
        form.addRow("Теги по умолчанию:", self.default_tags_input)
        form.addRow("Модель для улучшения промта:", self.assistant_model_combo)
        form.addRow("", self.log_checkbox)

        openrouter_group = QGroupBox("OpenRouter API")
        openrouter_layout = QVBoxLayout(openrouter_group)

        key_row = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Введите новый API-ключ")
        self.show_key_button = QPushButton("Показать")
        self.show_key_button.setCheckable(True)
        self.show_key_button.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.api_key_input)
        key_row.addWidget(self.show_key_button)

        self.api_key_status_label = QLabel()
        self.api_key_message_label = QLabel()
        self.api_key_message_label.setWordWrap(True)

        api_buttons_row = QHBoxLayout()
        self.save_key_button = QPushButton("Сохранить ключ")
        self.delete_key_button = QPushButton("Удалить ключ")
        self.test_connection_button = QPushButton("Проверить подключение")
        api_buttons_row.addWidget(self.save_key_button)
        api_buttons_row.addWidget(self.delete_key_button)
        api_buttons_row.addWidget(self.test_connection_button)

        openrouter_layout.addWidget(QLabel("API-ключ OpenRouter:"))
        openrouter_layout.addLayout(key_row)
        openrouter_layout.addWidget(self.api_key_status_label)
        openrouter_layout.addLayout(api_buttons_row)
        openrouter_layout.addWidget(self.api_key_message_label)

        self.save_key_button.clicked.connect(self._save_api_key)
        self.delete_key_button.clicked.connect(self._delete_api_key)
        self.test_connection_button.clicked.connect(self._test_connection)
        self._refresh_api_key_status()

        buttons = QDialogButtonBox()
        save_button = buttons.addButton("Сохранить", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = buttons.addButton("Отмена", QDialogButtonBox.ButtonRole.RejectRole)
        save_button.clicked.connect(self.save)
        cancel_button.clicked.connect(self.cancel)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(openrouter_group)
        layout.addWidget(buttons)
        _apply_dialog_appearance(self)

    def _toggle_key_visibility(self, visible: bool) -> None:
        self.api_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.show_key_button.setText("Скрыть" if visible else "Показать")

    def _refresh_api_key_status(self) -> None:
        if model_service.has_openrouter_api_key():
            key = model_service.get_api_key("OPENROUTER_API_KEY") or ""
            self.api_key_status_label.setText(
                f"Сохранён ключ: {model_service.mask_api_key(key)}"
            )
            self.delete_key_button.setEnabled(True)
        else:
            self.api_key_status_label.setText("Ключ не сохранён")
            self.delete_key_button.setEnabled(False)

    def _set_api_key_busy(self, busy: bool) -> None:
        self.save_key_button.setEnabled(not busy)
        self.delete_key_button.setEnabled(not busy and model_service.has_openrouter_api_key())
        self.test_connection_button.setEnabled(not busy)

    def _save_api_key(self) -> None:
        key = self.api_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "OpenRouter API", "Введите API-ключ для сохранения.")
            return
        try:
            model_service.save_openrouter_api_key(key)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "OpenRouter API", str(exc))
            return

        self.api_key_input.clear()
        self.show_key_button.setChecked(False)
        self._toggle_key_visibility(False)
        self._refresh_api_key_status()
        self.api_key_message_label.setStyleSheet("color: #2e7d32;")
        self.api_key_message_label.setText("Ключ сохранён в Windows Credential Manager.")

    def _delete_api_key(self) -> None:
        answer = QMessageBox.question(
            self,
            "OpenRouter API",
            "Удалить сохранённый API-ключ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        model_service.delete_openrouter_api_key()
        self.api_key_input.clear()
        self._refresh_api_key_status()
        self.api_key_message_label.setStyleSheet("")
        self.api_key_message_label.setText("Ключ удалён.")

    def _test_connection(self) -> None:
        entered_key = self.api_key_input.text().strip()
        api_key = entered_key or None
        self._set_api_key_busy(True)
        self.api_key_message_label.setStyleSheet("")
        self.api_key_message_label.setText("Проверка подключения...")
        self._test_worker = TestOpenRouterWorker(api_key)
        self._test_worker.finished.connect(self._on_test_connection_finished)
        self._test_worker.start()

    def _on_test_connection_finished(self, success: bool, message: str) -> None:
        self._set_api_key_busy(False)
        self.api_key_message_label.setText(message)
        self.api_key_message_label.setStyleSheet("color: #2e7d32;" if success else "color: #c62828;")

    def closeEvent(self, event) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)

    def _populate_assistant_models(self) -> None:
        self.assistant_model_combo.clear()
        self.assistant_model_combo.addItem("Первая активная модель", None)

        selected_index = 0
        preferred_id = model_service.get_prompt_assistant_model_id()
        for index, model in enumerate(model_service.load_active_models(), start=1):
            self.assistant_model_combo.addItem(model.name, model.id)
            if preferred_id is not None and model.id == preferred_id:
                selected_index = index
        self.assistant_model_combo.setCurrentIndex(selected_index)

    def cancel(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            appearance.apply_app_appearance(app)
            parent = self.parent()
            if parent is not None and hasattr(parent, "refresh_appearance"):
                parent.refresh_appearance()
        self.reject()

    def save(self) -> None:
        theme = self.theme_combo.currentData()
        model_service.set_setting_value("theme", str(theme or "light"))
        model_service.set_setting_value("font_size", str(self.font_size_input.value()))
        model_service.set_setting_value("request_timeout", str(self.timeout_input.value()))
        model_service.set_setting_value("db_path", self.db_path_input.text().strip() or "chatlist.db")
        model_service.set_setting_value("default_tags", self.default_tags_input.text().strip())
        model_service.set_setting_value("log_requests", "1" if self.log_checkbox.isChecked() else "0")

        model_id = self.assistant_model_combo.currentData()
        model_service.set_prompt_assistant_model_id(int(model_id) if model_id is not None else None)

        app = QApplication.instance()
        if isinstance(app, QApplication):
            appearance.apply_app_appearance(app)
            parent = self.parent()
            if parent is not None and hasattr(parent, "refresh_appearance"):
                parent.refresh_appearance()
        self.accept()


class AboutDialog(QDialog):
    FEATURES_TEXT = (
        "• отправка промпта нескольким моделям одновременно\n"
        "• сравнение и сохранение результатов\n"
        "• управление промптами и моделями\n"
        "• AI-ассистент для улучшения промптов\n"
        "• создание альтернативных и адаптированных вариантов промпта\n"
        "• экспорт результатов в Markdown и JSON\n"
        "• настройка темы оформления и размера шрифта"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setMinimumSize(560, 720)
        self.resize(560, 720)

        app_icon = appearance.load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        selectable = Qt.TextInteractionFlag.TextSelectableByMouse

        self.title_label = QLabel("ChatList")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self.title_label.setTextInteractionFlags(selectable)

        self.version_label = QLabel(f"Версия {__version__}")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.version_label.setTextInteractionFlags(selectable)

        self.description_label = QLabel(
            "ChatList — это Python-приложение для отправки одного промпта нескольким "
            "нейросетям и сравнения полученных ответов."
        )
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.description_label.setTextInteractionFlags(selectable)

        self.features_title_label = QLabel("Возможности:")
        self.features_title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.features_title_label.setTextInteractionFlags(selectable)

        self.features_list_label = QLabel(self.FEATURES_TEXT)
        self.features_list_label.setWordWrap(True)
        self.features_list_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.features_list_label.setTextInteractionFlags(selectable)

        self.tech_label = QLabel(
            "Разработано с использованием Python, PyQt6, SQLite и OpenRouter API."
        )
        self.tech_label.setWordWrap(True)
        self.tech_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.tech_label.setTextInteractionFlags(selectable)

        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)
        layout.addWidget(self.title_label)
        layout.addSpacing(6)
        layout.addWidget(self.version_label)
        layout.addSpacing(18)
        layout.addWidget(self.description_label)
        layout.addSpacing(14)
        layout.addWidget(self.features_title_label)
        layout.addSpacing(6)
        layout.addWidget(self.features_list_label)
        layout.addSpacing(14)
        layout.addWidget(self.tech_label)
        layout.addStretch()
        layout.addLayout(buttons)
        _apply_dialog_appearance(self)
        self._apply_about_fonts()

    def _apply_about_fonts(self) -> None:
        base_size = appearance.get_font_size()
        title_font = QFont(appearance.FONT_FAMILY, base_size + 3)
        title_font.setWeight(QFont.Weight.Bold)
        version_font = QFont(appearance.FONT_FAMILY, max(8, base_size))
        body_font = appearance.body_font(base_size)

        self.title_label.setFont(title_font)
        self.version_label.setFont(version_font)
        for label in (
            self.description_label,
            self.features_title_label,
            self.features_list_label,
            self.tech_label,
        ):
            label.setFont(body_font)
