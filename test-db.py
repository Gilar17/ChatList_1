"""Тестовая программа просмотра и редактирования SQLite-баз данных."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

PAGE_SIZE_OPTIONS = [10, 25, 50, 100]


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class ColumnInfo:
    def __init__(self, cid: int, name: str, col_type: str, notnull: bool, default: Any, pk: int) -> None:
        self.cid = cid
        self.name = name
        self.col_type = col_type or ""
        self.notnull = bool(notnull)
        self.default = default
        self.pk = pk

    @property
    def is_autoincrement_pk(self) -> bool:
        return self.pk == 1 and "INT" in self.col_type.upper() and self.name.lower() != "rowid"


class TableSchema:
    def __init__(self, table_name: str, columns: list[ColumnInfo]) -> None:
        self.table_name = table_name
        self.columns = columns

    @property
    def primary_key_columns(self) -> list[str]:
        pk_columns = sorted(
            (column for column in self.columns if column.pk > 0),
            key=lambda column: column.pk,
        )
        return [column.name for column in pk_columns]

    @property
    def uses_rowid(self) -> bool:
        return not self.primary_key_columns

    @property
    def insert_columns(self) -> list[ColumnInfo]:
        result: list[ColumnInfo] = []
        for column in self.columns:
            if column.is_autoincrement_pk and len(self.primary_key_columns) == 1:
                continue
            result.append(column)
        return result


def load_schema(connection: sqlite3.Connection, table_name: str) -> TableSchema:
    rows = connection.execute(f"PRAGMA table_info({quote_ident(table_name)})").fetchall()
    columns = [
        ColumnInfo(
            cid=int(row[0]),
            name=str(row[1]),
            col_type=str(row[2] or ""),
            notnull=bool(row[3]),
            default=row[4],
            pk=int(row[5] or 0),
        )
        for row in rows
    ]
    return TableSchema(table_name, columns)


def list_user_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND (name NOT LIKE 'sqlite_%' OR name = 'sqlite_sequence')
        ORDER BY name
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def parse_field_value(raw_value: str, column: ColumnInfo) -> Any:
    text = raw_value.strip()
    if not text:
        if column.notnull:
            raise ValueError(f"Поле «{column.name}» не может быть пустым.")
        return None
    return text


def row_to_dict(row: sqlite3.Row, column_names: list[str]) -> dict[str, Any]:
    return {name: row[name] for name in column_names}


class RecordDialog(QDialog):
    def __init__(
        self,
        schema: TableSchema,
        mode: str,
        values: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._schema = schema
        self._mode = mode
        self._inputs: dict[str, QLineEdit] = {}

        titles = {
            "create": "Создание записи",
            "edit": "Редактирование записи",
            "view": "Просмотр записи",
        }
        self.setWindowTitle(titles.get(mode, "Запись"))
        self.setMinimumWidth(460)

        if mode == "view":
            columns = schema.columns
            if schema.uses_rowid and values and "rowid" in values:
                columns = [ColumnInfo(-1, "rowid", "INTEGER", True, None, 0), *schema.columns]
        elif mode == "edit":
            columns = schema.columns
        else:
            columns = schema.insert_columns

        form = QFormLayout()
        for column in columns:
            field = QLineEdit()
            if values and column.name in values and values[column.name] is not None:
                field.setText(str(values[column.name]))
            if mode == "view":
                field.setReadOnly(True)
            if mode == "edit" and column.name in schema.primary_key_columns:
                field.setReadOnly(True)
            form.addRow(f"{column.name}:", field)
            self._inputs[column.name] = field

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        if mode == "view":
            close_button = QPushButton("Закрыть")
            close_button.clicked.connect(self.reject)
            buttons = QHBoxLayout()
            buttons.addStretch()
            buttons.addWidget(close_button)
            layout.addLayout(buttons)
        else:
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            save_button = button_box.button(QDialogButtonBox.StandardButton.Save)
            cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
            if save_button is not None:
                save_button.setText("Сохранить")
            if cancel_button is not None:
                cancel_button.setText("Отмена")
            button_box.accepted.connect(self.accept)
            button_box.rejected.connect(self.reject)
            layout.addWidget(button_box)

    def get_values(self) -> dict[str, Any]:
        if self._mode == "create":
            columns = self._schema.insert_columns
        else:
            columns = [column for column in self._schema.columns if column.name in self._inputs]

        result: dict[str, Any] = {}
        for column in columns:
            if self._mode == "edit" and column.name in self._schema.primary_key_columns:
                result[column.name] = self._inputs[column.name].text().strip()
                continue
            result[column.name] = parse_field_value(self._inputs[column.name].text(), column)
        return result


class TableBrowserWindow(QDialog):
    def __init__(self, db_path: Path, table_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._table_name = table_name
        self._current_page = 0
        self._page_size = PAGE_SIZE_OPTIONS[0]
        self._total_rows = 0
        self._column_names: list[str] = []
        self._uses_rowid = False

        self.setWindowTitle(f"Таблица: {table_name}")
        self.resize(960, 620)

        self.table = QTableWidget(0, 0)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(lambda _row, _col: self.view_record())

        self.page_label = QLabel("Страница 1 из 1")
        self.rows_info_label = QLabel("Записей: 0")

        self.page_size_combo = QComboBox()
        for size in PAGE_SIZE_OPTIONS:
            self.page_size_combo.addItem(str(size), size)

        page_size_label = QLabel("Строк на странице:")
        self.prev_button = QPushButton("Предыдущая")
        self.next_button = QPushButton("Следующая")

        self.create_button = QPushButton("Создать")
        self.view_button = QPushButton("Просмотреть")
        self.edit_button = QPushButton("Редактировать")
        self.delete_button = QPushButton("Удалить")
        self.close_button = QPushButton("Закрыть")

        self.prev_button.clicked.connect(self.show_previous_page)
        self.next_button.clicked.connect(self.show_next_page)
        self.page_size_combo.currentIndexChanged.connect(self.on_page_size_changed)
        self.create_button.clicked.connect(self.create_record)
        self.view_button.clicked.connect(self.view_record)
        self.edit_button.clicked.connect(self.edit_record)
        self.delete_button.clicked.connect(self.delete_record)
        self.close_button.clicked.connect(self.accept)

        pagination_row = QHBoxLayout()
        pagination_row.addWidget(self.prev_button)
        pagination_row.addWidget(self.page_label)
        pagination_row.addWidget(self.next_button)
        pagination_row.addStretch()
        pagination_row.addWidget(self.rows_info_label)
        pagination_row.addWidget(page_size_label)
        pagination_row.addWidget(self.page_size_combo)

        crud_row = QHBoxLayout()
        crud_row.addWidget(self.create_button)
        crud_row.addWidget(self.view_button)
        crud_row.addWidget(self.edit_button)
        crud_row.addWidget(self.delete_button)
        crud_row.addStretch()
        crud_row.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(pagination_row)
        layout.addLayout(crud_row)

        self.reload_table()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _show_error(title: str, error: Exception, parent: QWidget | None = None) -> None:
        QMessageBox.critical(parent, title, f"{title}\n\n{error}")

    @staticmethod
    def _show_warning(message: str, parent: QWidget | None = None) -> None:
        QMessageBox.information(parent, "SQLite Viewer", message)

    def _total_pages(self) -> int:
        return max((self._total_rows + self._page_size - 1) // self._page_size, 1)

    def _update_pagination_controls(self) -> None:
        total_pages = self._total_pages()
        self.page_label.setText(f"Страница {self._current_page + 1} из {total_pages}")
        self.rows_info_label.setText(f"Записей: {self._total_rows}")
        self.prev_button.setEnabled(self._current_page > 0)
        self.next_button.setEnabled(self._current_page < total_pages - 1)

    def reload_table(self) -> None:
        try:
            with self._connect() as connection:
                schema = load_schema(connection, self._table_name)
                self._uses_rowid = schema.uses_rowid
                self._column_names = (
                    ["rowid", *[column.name for column in schema.columns]]
                    if self._uses_rowid
                    else [column.name for column in schema.columns]
                )

                count_row = connection.execute(
                    f"SELECT COUNT(*) AS total FROM {quote_ident(self._table_name)}"
                ).fetchone()
                self._total_rows = int(count_row["total"]) if count_row else 0

                total_pages = self._total_pages()
                if self._current_page >= total_pages:
                    self._current_page = max(total_pages - 1, 0)

                offset = self._current_page * self._page_size
                if self._uses_rowid:
                    query = f"""
                        SELECT rowid, *
                        FROM {quote_ident(self._table_name)}
                        LIMIT ? OFFSET ?
                    """
                else:
                    query = f"""
                        SELECT *
                        FROM {quote_ident(self._table_name)}
                        LIMIT ? OFFSET ?
                    """
                rows = connection.execute(query, (self._page_size, offset)).fetchall()
        except sqlite3.Error as error:
            self._show_error("Не удалось загрузить таблицу.", error, self)
            return

        self.table.setColumnCount(len(self._column_names))
        self.table.setHorizontalHeaderLabels(self._column_names)
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            record = row_to_dict(row, self._column_names)
            for col_index, column_name in enumerate(self._column_names):
                value = record.get(column_name)
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record)
                self.table.setItem(row_index, col_index, item)

        self._update_pagination_controls()

    def on_page_size_changed(self) -> None:
        self._page_size = int(self.page_size_combo.currentData())
        self._current_page = 0
        self.reload_table()

    def show_previous_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self.reload_table()

    def show_next_page(self) -> None:
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self.reload_table()

    def _selected_record(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        record = item.data(Qt.ItemDataRole.UserRole)
        return record if isinstance(record, dict) else None

    def _build_where_clause(self, schema: TableSchema, record: dict[str, Any]) -> tuple[str, list[Any]]:
        if schema.uses_rowid:
            return "rowid = ?", [record["rowid"]]

        if not schema.primary_key_columns:
            raise ValueError("Не удалось определить первичный ключ таблицы.")

        conditions = [f"{quote_ident(name)} = ?" for name in schema.primary_key_columns]
        values = [record[name] for name in schema.primary_key_columns]
        return " AND ".join(conditions), values

    def create_record(self) -> None:
        schema = self._load_schema()
        dialog = RecordDialog(schema, "create", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            values = dialog.get_values()
            columns = [name for name in values if name != "rowid"]
            placeholders = ", ".join("?" for _ in columns)
            column_names = ", ".join(quote_ident(name) for name in columns)
            params = [values[name] for name in columns]

            with self._connect() as connection:
                connection.execute(
                    f"INSERT INTO {quote_ident(self._table_name)} ({column_names}) VALUES ({placeholders})",
                    params,
                )
                connection.commit()
        except (sqlite3.Error, ValueError) as error:
            self._show_error("Не удалось создать запись.", error, self)
            return

        self.reload_table()

    def view_record(self) -> None:
        record = self._selected_record()
        if record is None:
            self._show_warning("Выберите запись для просмотра.", self)
            return

        schema = self._load_schema()
        dialog = RecordDialog(schema, "view", record, self)
        dialog.exec()

    def edit_record(self) -> None:
        record = self._selected_record()
        if record is None:
            self._show_warning("Выберите запись для редактирования.", self)
            return

        schema = self._load_schema()
        dialog = RecordDialog(schema, "edit", record, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            values = dialog.get_values()
            where_clause, where_values = self._build_where_clause(schema, record)

            set_parts: list[str] = []
            params: list[Any] = []
            for column in schema.columns:
                if column.name in schema.primary_key_columns:
                    continue
                if column.name not in values:
                    continue
                set_parts.append(f"{quote_ident(column.name)} = ?")
                params.append(values[column.name])

            if not set_parts:
                self._show_warning("Нет полей для изменения.", self)
                return

            params.extend(where_values)
            with self._connect() as connection:
                connection.execute(
                    f"""
                    UPDATE {quote_ident(self._table_name)}
                    SET {", ".join(set_parts)}
                    WHERE {where_clause}
                    """,
                    params,
                )
                connection.commit()
        except (sqlite3.Error, ValueError) as error:
            self._show_error("Не удалось изменить запись.", error, self)
            return

        self.reload_table()

    def delete_record(self) -> None:
        record = self._selected_record()
        if record is None:
            self._show_warning("Выберите запись для удаления.", self)
            return

        message_box = QMessageBox(self)
        message_box.setWindowTitle("Подтверждение удаления")
        message_box.setText("Удалить выбранную запись?")
        yes_button = message_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        no_button = message_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        message_box.setDefaultButton(no_button)
        message_box.exec()

        if message_box.clickedButton() != yes_button:
            return

        try:
            schema = self._load_schema()
            where_clause, where_values = self._build_where_clause(schema, record)
            with self._connect() as connection:
                connection.execute(
                    f"DELETE FROM {quote_ident(self._table_name)} WHERE {where_clause}",
                    where_values,
                )
                connection.commit()
        except (sqlite3.Error, ValueError) as error:
            self._show_error("Не удалось удалить запись.", error, self)
            return

        self.reload_table()

    def _load_schema(self) -> TableSchema:
        with self._connect() as connection:
            return load_schema(connection, self._table_name)


class DatabaseSelectorWindow(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self._db_path: Path | None = None

        self.setWindowTitle("Просмотр SQLite базы данных")
        self.resize(560, 420)

        self.file_label = QLabel("Файл не выбран")
        self.file_label.setWordWrap(True)

        self.select_file_button = QPushButton("Выбрать файл БД")
        self.select_file_button.clicked.connect(self.select_database_file)

        top_row = QHBoxLayout()
        top_row.addWidget(self.file_label, stretch=1)
        top_row.addWidget(self.select_file_button)

        tables_label = QLabel("Таблицы:")
        self.tables_list = QListWidget()
        self.tables_list.currentItemChanged.connect(self.on_table_selection_changed)

        self.open_button = QPushButton("Открыть")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_selected_table)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(tables_label)
        layout.addWidget(self.tables_list, stretch=1)
        layout.addWidget(self.open_button)

    def select_database_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл базы данных",
            str(Path.cwd()),
            "SQLite (*.db);;Все файлы (*.*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        try:
            with sqlite3.connect(path) as connection:
                tables = list_user_tables(connection)
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Ошибка базы данных",
                f"Не удалось открыть файл базы данных.\n\n{error}",
            )
            return

        self._db_path = path
        self.file_label.setText(str(path))
        self.tables_list.clear()
        self.tables_list.addItems(tables)
        self.open_button.setEnabled(False)

    def on_table_selection_changed(self) -> None:
        self.open_button.setEnabled(
            self._db_path is not None and self.tables_list.currentItem() is not None
        )

    def open_selected_table(self) -> None:
        if self._db_path is None:
            QMessageBox.information(self, "SQLite Viewer", "Сначала выберите файл базы данных.")
            return

        current_item = self.tables_list.currentItem()
        if current_item is None:
            QMessageBox.information(self, "SQLite Viewer", "Выберите таблицу для открытия.")
            return

        browser = TableBrowserWindow(self._db_path, current_item.text(), self)
        browser.exec()


def main() -> int:
    app = QApplication(sys.argv)
    window = DatabaseSelectorWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
