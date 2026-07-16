"""Графический интерфейс ChatList."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import db
import models as model_service
import network
from dialogs import ModelsDialog, PromptsDialog, ResultsDialog, SettingsDialog


@dataclass
class TempResultRow:
    model_id: int | None
    model_name: str
    response_text: str
    selected: bool = False


class TempResultsStore:
    """Временная таблица результатов в памяти (не в SQLite)."""

    def __init__(self) -> None:
        self._rows: list[TempResultRow] = []

    def clear(self) -> None:
        self._rows.clear()

    def add(self, model_id: int | None, model_name: str, response_text: str) -> None:
        self._rows.append(
            TempResultRow(model_id=model_id, model_name=model_name, response_text=response_text)
        )

    def set_selected(self, index: int, selected: bool) -> None:
        if 0 <= index < len(self._rows):
            self._rows[index].selected = selected

    def get_selected(self) -> list[TempResultRow]:
        return [row for row in self._rows if row.selected]

    def all_rows(self) -> list[TempResultRow]:
        return list(self._rows)


class SendPromptWorker(QThread):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, prompt: str, active_models: list[model_service.ModelRecord]) -> None:
        super().__init__()
        self.prompt = prompt
        self.active_models = active_models

    def run(self) -> None:
        try:
            results = network.send_prompt_to_all(self.prompt, self.active_models)
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.temp_results = TempResultsStore()
        self._last_prompt = ""
        self._loading_prompt = False
        self._current_prompt_id: int | None = None
        self._send_worker: SendPromptWorker | None = None

        self.setWindowTitle("ChatList — Сравнение ответов нейросетей")
        self.setMinimumSize(700, 500)
        self.resize(950, 650)

        self._create_menu()

        body_font = QFont("Segoe UI", 10)
        button_font = QFont("Segoe UI", 9)

        prompt_caption = QLabel("Промт:")
        prompt_caption.setFont(body_font)

        self.prompt_combo = QComboBox()
        self.prompt_combo.setFont(body_font)
        self.prompt_combo.setEditable(True)
        self.prompt_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.prompt_combo.currentIndexChanged.connect(self.on_prompt_combo_changed)

        self.send_button = QPushButton("Отправить")
        self.send_button.setFont(button_font)
        self.send_button.setFixedWidth(120)
        self.send_button.clicked.connect(self.on_send)

        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(8)
        prompt_row.addWidget(prompt_caption)
        prompt_row.addWidget(self.prompt_combo, stretch=1)
        prompt_row.addWidget(self.send_button)

        self.prompt_input = QTextEdit()
        self.prompt_input.setFont(body_font)
        self.prompt_input.setPlaceholderText("Введите промт или выберите из списка...")
        self.prompt_input.setMinimumHeight(140)
        self.prompt_input.textChanged.connect(self.on_prompt_changed)

        self.results_table = QTableWidget(0, 3)
        self.results_table.setFont(body_font)
        self.results_table.setHorizontalHeaderLabels(["Выбрать", "Модель", "Ответ"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results_table.setColumnWidth(0, 70)
        self.results_table.setColumnWidth(1, 160)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setWordWrap(True)

        self.save_selected_button = QPushButton("Сохранить выбранные")
        self.save_selected_button.setFont(button_font)
        self.save_selected_button.setEnabled(False)
        self.save_selected_button.clicked.connect(self.on_save_selected)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.setFont(button_font)
        self.clear_button.clicked.connect(self.on_clear)

        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(8)
        action_buttons.addWidget(self.save_selected_button)
        action_buttons.addWidget(self.clear_button)
        action_buttons.addStretch()

        self.status_label = QLabel("Готово. Введите промт и нажмите «Отправить».")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setWordWrap(True)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        layout.addLayout(prompt_row)
        layout.addWidget(self.prompt_input)
        layout.addWidget(self.results_table, stretch=1)
        layout.addLayout(action_buttons)
        layout.addWidget(self.status_label)
        self.setCentralWidget(central)

        self.load_prompt_list()
        self._update_save_button_state()

    def _create_menu(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setFont(QFont("Segoe UI", 9))

        prompts_menu = menu_bar.addMenu("Промты")
        prompts_menu.addAction("Управление промтами", self.open_prompts_dialog)

        models_menu = menu_bar.addMenu("Модели")
        models_menu.addAction("Управление моделями", self.open_models_dialog)

        results_menu = menu_bar.addMenu("Результаты")
        results_menu.addAction("Сохранённые результаты", self.open_results_dialog)

        settings_menu = menu_bar.addMenu("Настройки")
        settings_menu.addAction("Параметры программы", self.open_settings_dialog)

    def open_prompts_dialog(self) -> None:
        dialog = PromptsDialog(self)
        dialog.exec()
        self.load_prompt_list()

    def open_models_dialog(self) -> None:
        dialog = ModelsDialog(self)
        dialog.exec()

    def open_results_dialog(self) -> None:
        dialog = ResultsDialog(self)
        dialog.exec()

    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self)
        dialog.exec()

    def load_prompt_list(self) -> None:
        self.prompt_combo.blockSignals(True)
        current_text = self.prompt_input.toPlainText().strip()
        self.prompt_combo.clear()
        self.prompt_combo.addItem("", None)

        selected_index = 0
        try:
            for index, prompt in enumerate(model_service.load_prompts(), start=1):
                preview = prompt.prompt.replace("\n", " ").strip()
                if len(preview) > 80:
                    preview = preview[:80] + "..."
                data = {"id": prompt.id, "text": prompt.prompt}
                self.prompt_combo.addItem(preview, data)
                if current_text and current_text == prompt.prompt:
                    selected_index = index
        except Exception:
            pass

        self.prompt_combo.setCurrentIndex(selected_index)
        self.prompt_combo.blockSignals(False)

    def on_prompt_combo_changed(self, index: int) -> None:
        if index <= 0:
            self._current_prompt_id = None
            return

        data = self.prompt_combo.itemData(index)
        if not isinstance(data, dict):
            return

        prompt_text = data.get("text")
        prompt_id = data.get("id")
        if not prompt_text:
            return

        self._loading_prompt = True
        self.prompt_input.setPlainText(str(prompt_text))
        self._loading_prompt = False
        self._last_prompt = str(prompt_text).strip()
        self._current_prompt_id = int(prompt_id) if prompt_id is not None else None

    def on_prompt_changed(self) -> None:
        if self._loading_prompt:
            return

        current_prompt = self.prompt_input.toPlainText().strip()
        combo_data = self.prompt_combo.currentData()
        if isinstance(combo_data, dict) and combo_data.get("text") == current_prompt:
            self._current_prompt_id = int(combo_data["id"]) if combo_data.get("id") is not None else None
        else:
            self._current_prompt_id = None

        if self._last_prompt and current_prompt != self._last_prompt and self.temp_results.all_rows():
            self.temp_results.clear()
            self.refresh_results_table()
            self.status_label.setText("Временная таблица очищена: введён новый промт.")

    def on_send(self) -> None:
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "ChatList", "Введите текст промта.")
            return

        if self._current_prompt_id is None:
            combo_data = self.prompt_combo.currentData()
            if isinstance(combo_data, dict) and combo_data.get("text") == prompt:
                self._current_prompt_id = int(combo_data["id"])
            else:
                self._current_prompt_id = model_service.save_prompt(prompt)
                self.load_prompt_list()

        self._last_prompt = prompt
        self.send_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.status_label.setText("Отправка запросов...")
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))

        active_models = model_service.load_active_models()
        self._send_worker = SendPromptWorker(prompt, active_models)
        self._send_worker.finished.connect(self.on_send_finished)
        self._send_worker.failed.connect(self.on_send_failed)
        self._send_worker.start()

    def on_send_finished(self, results: list[network.RequestResult]) -> None:
        QApplication.restoreOverrideCursor()
        self.send_button.setEnabled(True)
        self.clear_button.setEnabled(True)

        self.temp_results.clear()
        for item in results:
            self.temp_results.add(item.model_id, item.model_name, item.response_text)

        self.refresh_results_table()
        success_count = sum(1 for item in results if item.success)
        self.status_label.setText(
            f"Получено ответов: {len(results)} (успешно: {success_count}). "
            f"Запросы отправлены через OpenRouter."
        )

    def on_send_failed(self, message: str) -> None:
        QApplication.restoreOverrideCursor()
        self.send_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.status_label.setText(f"Ошибка отправки: {message}")
        QMessageBox.critical(self, "ChatList", f"Не удалось отправить запросы:\n{message}")

    def refresh_results_table(self) -> None:
        rows = self.temp_results.all_rows()
        self.results_table.setRowCount(len(rows))

        for index, row in enumerate(rows):
            checkbox = QCheckBox()
            checkbox.setChecked(row.selected)
            checkbox.stateChanged.connect(
                lambda state, row_index=index: self.on_row_selected(row_index, state)
            )

            model_item = QTableWidgetItem(row.model_name)
            model_item.setFlags(model_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            response_item = QTableWidgetItem(row.response_text)
            response_item.setFlags(response_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            response_item.setTextAlignment(
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            )

            self.results_table.setCellWidget(index, 0, checkbox)
            self.results_table.setItem(index, 1, model_item)
            self.results_table.setItem(index, 2, response_item)
            self.results_table.resizeRowToContents(index)

        self._update_save_button_state()

    def on_row_selected(self, row_index: int, state: int) -> None:
        self.temp_results.set_selected(row_index, state == int(Qt.CheckState.Checked))

    def _update_save_button_state(self) -> None:
        has_results = bool(self.temp_results.all_rows())
        self.save_selected_button.setEnabled(has_results)

    def on_save_selected(self) -> None:
        selected = self.temp_results.get_selected()
        if not selected:
            QMessageBox.information(self, "ChatList", "Отметьте хотя бы один результат для сохранения.")
            return

        prompt_text = self.prompt_input.toPlainText().strip()
        tags = model_service.get_default_tags()
        saved_count = 0

        try:
            for row in selected:
                model_service.save_result(
                    model_name=row.model_name,
                    prompt_text=prompt_text,
                    response_text=row.response_text,
                    prompt_id=self._current_prompt_id,
                    model_id=row.model_id,
                    tags=tags,
                )
                saved_count += 1
        except Exception as exc:
            QMessageBox.critical(self, "ChatList", f"Ошибка сохранения:\n{exc}")
            return

        self.temp_results.clear()
        self.refresh_results_table()
        self.status_label.setText(f"Сохранено результатов: {saved_count}.")
        QMessageBox.information(self, "ChatList", f"Сохранено результатов: {saved_count}.")

    def on_clear(self) -> None:
        self._loading_prompt = True
        self.prompt_input.clear()
        self.prompt_combo.setCurrentIndex(0)
        self._loading_prompt = False

        self._last_prompt = ""
        self._current_prompt_id = None
        self.temp_results.clear()
        self.refresh_results_table()
        self.status_label.setText("Промт и результаты очищены.")


def main() -> None:
    model_service.init_environment()
    db.init_db()
    model_service.init_default_settings()
    model_service.seed_default_models()
    network.setup_logging()

    app = QApplication(sys.argv)
    app.setStyle("Windows11" if "Windows11" in QStyleFactory.keys() else "Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
