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
    QVBoxLayout,
    QWidget,
)

import models as model_service


class PromptsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Промты")
        self.resize(820, 480)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по тексту или тегам...")
        self.search_input.textChanged.connect(self.reload)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Дата", "Промт", "Теги"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sectionClicked.connect(self.on_sort)

        delete_button = QPushButton("Удалить выбранный")
        delete_button.clicked.connect(self.delete_selected)

        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(delete_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self._sort_column = 1
        self._sort_desc = True
        self.reload()

    def on_sort(self, column: int) -> None:
        mapping = {0: "id", 1: "created_at", 2: "prompt", 3: "tags"}
        field = mapping.get(column, "created_at")
        if self._sort_column == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column = column
            self._sort_desc = True
        self.reload(order_by=field, order_dir="DESC" if self._sort_desc else "ASC")

    def reload(self, order_by: str = "created_at", order_dir: str = "DESC") -> None:
        search = self.search_input.text().strip() or None
        rows = model_service.load_prompts(search=search)
        if order_by == "created_at":
            rows.sort(key=lambda item: item.created_at, reverse=order_dir == "DESC")
        elif order_by == "prompt":
            rows.sort(key=lambda item: item.prompt.lower(), reverse=order_dir == "DESC")
        elif order_by == "tags":
            rows.sort(key=lambda item: (item.tags or "").lower(), reverse=order_dir == "DESC")
        elif order_by == "id":
            rows.sort(key=lambda item: item.id, reverse=order_dir == "DESC")

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for col, value in enumerate([row.id, row.created_at, row.prompt, row.tags or ""]):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row.id)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(index, col, item)
        self.table.setSortingEnabled(True)

    def delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Промты", "Выберите промт для удаления.")
            return

        item = self.table.item(row, 0)
        if not item:
            return

        prompt_id = int(item.data(Qt.ItemDataRole.UserRole))
        answer = QMessageBox.question(
            self,
            "Промты",
            "Удалить выбранный промт? Сохранённые результаты останутся в базе.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        model_service.remove_prompt(prompt_id)
        self.reload()


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
        self.timeout_input.setSuffix(" сек")
        self.timeout_input.setValue(int(float(model_service.get_setting_value("request_timeout", "30"))))

        self.db_path_input = QLineEdit(model_service.get_setting_value("db_path", "chatlist.db"))
        self.default_tags_input = QLineEdit(model_service.get_setting_value("default_tags", ""))
        self.log_checkbox = QCheckBox("Логировать запросы в chatlist.log")
        self.log_checkbox.setChecked(model_service.is_logging_enabled())

        form = QFormLayout()
        form.addRow("Таймаут запросов:", self.timeout_input)
        form.addRow("Путь к БД:", self.db_path_input)
        form.addRow("Теги по умолчанию:", self.default_tags_input)
        form.addRow("", self.log_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def save(self) -> None:
        model_service.set_setting_value("request_timeout", str(self.timeout_input.value()))
        model_service.set_setting_value("db_path", self.db_path_input.text().strip() or "chatlist.db")
        model_service.set_setting_value("default_tags", self.default_tags_input.text().strip())
        model_service.set_setting_value("log_requests", "1" if self.log_checkbox.isChecked() else "0")
        self.accept()
