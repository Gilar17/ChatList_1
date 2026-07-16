"""Диалоговые окна управления данными ChatList."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import models as model_service


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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Модели")
        self.resize(900, 480)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Название", "API ID", "Ключ (.env)", "Тип", "Активна"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)

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

    def reload(self) -> None:
        rows = model_service.load_models()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row.id,
                row.name,
                row.api_id,
                row.api_key_env_var,
                row.model_type or "",
                "Да" if row.is_active else "Нет",
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
        answer = QMessageBox.question(
            self,
            "Модели",
            "Удалить выбранную модель? Сохранённые результаты останутся в базе.",
        )
        if answer != QMessageBox.StandardButton.Yes:
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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Результаты")
        self.resize(960, 520)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по модели, промту, ответу или тегам...")
        self.search_input.textChanged.connect(self.reload)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Дата", "Модель", "Промт", "Ответ", "Теги"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)

        export_md_button = QPushButton("Экспорт Markdown")
        export_json_button = QPushButton("Экспорт JSON")
        delete_button = QPushButton("Удалить выбранный")
        close_button = QPushButton("Закрыть")

        export_md_button.clicked.connect(lambda: self.export("markdown"))
        export_json_button.clicked.connect(lambda: self.export("json"))
        delete_button.clicked.connect(self.delete_selected)
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(export_md_button)
        buttons.addWidget(export_json_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.reload()

    def _current_results(self) -> list[model_service.ResultRecord]:
        search = self.search_input.text().strip() or None
        return model_service.load_results(search=search)

    def reload(self) -> None:
        rows = self._current_results()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            prompt_preview = row.prompt_text.replace("\n", " ")
            if len(prompt_preview) > 80:
                prompt_preview = prompt_preview[:80] + "..."
            response_preview = row.response_text.replace("\n", " ")
            if len(response_preview) > 120:
                response_preview = response_preview[:120] + "..."

            values = [
                row.id,
                row.saved_at,
                row.model_name,
                prompt_preview,
                response_preview,
                row.tags or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row.id)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(index, col, item)

    def _selected_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.table.selectedItems():
            if item.column() == 0:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def export(self, fmt: str) -> None:
        selected_ids = self._selected_ids()
        results = self._current_results()
        if selected_ids:
            results = [row for row in results if row.id in selected_ids]
        if not results:
            QMessageBox.information(self, "Результаты", "Нет данных для экспорта.")
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
        QMessageBox.information(self, "Результаты", f"Файл сохранён:\n{file_path}")

    def delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Результаты", "Выберите результат.")
            return
        item = self.table.item(row, 0)
        if not item:
            return
        result_id = int(item.data(Qt.ItemDataRole.UserRole))
        answer = QMessageBox.question(self, "Результаты", "Удалить выбранный результат?")
        if answer != QMessageBox.StandardButton.Yes:
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
