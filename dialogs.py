"""Диалоговые окна управления данными ChatList."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from markdown_viewer import format_received_at, show_response_markdown


class PromptEditDialog(QDialog):
    def __init__(self, prompt: model_service.PromptRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prompt_id = prompt.id
        self.setWindowTitle("Редактирование промта")
        self.setMinimumSize(520, 360)

        self.prompt_input = QTextEdit()
        self.prompt_input.setFont(QFont("Segoe UI", 10))
        self.prompt_input.setMinimumHeight(180)
        self.prompt_input.setPlainText(prompt.prompt)

        self.tags_input = QLineEdit()
        self.tags_input.setFont(QFont("Segoe UI", 10))
        self.tags_input.setText(prompt.tags or "")

        form = QFormLayout()
        form.addRow("Промт:", self.prompt_input)
        form.addRow("Теги:", self.tags_input)

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

    def save(self) -> None:
        prompt_text = self.prompt_input.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "Редактирование промта", "Введите текст промта.")
            return

        tags = self.tags_input.text().strip() or None
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
        self.table.itemSelectionChanged.connect(self._update_edit_button_state)
        self.table.cellDoubleClicked.connect(self.on_edit_selected)

        self.edit_button = QPushButton("Редактировать")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.on_edit_selected)

        self.delete_button = QPushButton("Удалить")
        self.delete_button.clicked.connect(self.delete_selected)

        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.reload()

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
        self._update_edit_button_state()

    def _selected_prompt_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _update_edit_button_state(self) -> None:
        self.edit_button.setEnabled(self._selected_prompt_id() is not None)

    def _sync_main_prompt_list(self) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "load_prompt_list"):
            parent.load_prompt_list()

    def on_edit_selected(self, *_args: object) -> None:
        prompt_id = self._selected_prompt_id()
        if prompt_id is None:
            QMessageBox.information(self, "Управление промтами", "Выберите промт для редактирования.")
            return

        prompt = model_service.get_prompt_by_id(prompt_id)
        if prompt is None:
            return

        dialog = PromptEditDialog(prompt, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.reload(selected_id=prompt_id)
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


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(420)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 300)
        self.timeout_input.setValue(int(float(model_service.get_setting_value("request_timeout", "90"))))

        self.db_path_input = QLineEdit(model_service.get_setting_value("db_path", "chatlist.db"))
        self.default_tags_input = QLineEdit(model_service.get_setting_value("default_tags", ""))
        self.log_checkbox = QCheckBox("Записывать историю запросов в файл chatlist.log")
        self.log_checkbox.setChecked(model_service.is_logging_enabled())

        form = QFormLayout()
        form.addRow("Время ожидания ответа, сек.:", self.timeout_input)
        form.addRow("Файл базы данных:", self.db_path_input)
        form.addRow("Теги по умолчанию:", self.default_tags_input)
        form.addRow("", self.log_checkbox)

        buttons = QDialogButtonBox()
        save_button = buttons.addButton("Сохранить", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = buttons.addButton("Отменить", QDialogButtonBox.ButtonRole.RejectRole)
        save_button.clicked.connect(self.save)
        cancel_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def save(self) -> None:
        model_service.set_setting_value("request_timeout", str(self.timeout_input.value()))
        model_service.set_setting_value("db_path", self.db_path_input.text().strip() or "chatlist.db")
        model_service.set_setting_value("default_tags", self.default_tags_input.text().strip())
        model_service.set_setting_value("log_requests", "1" if self.log_checkbox.isChecked() else "0")
        self.accept()
