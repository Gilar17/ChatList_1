"""Модуль доступа к SQLite. Единственная точка работы с базой данных."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB_PATH = Path("chatlist.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL,
    prompt     TEXT    NOT NULL,
    tags       TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    api_url         TEXT    NOT NULL,
    api_id          TEXT    NOT NULL,
    api_key_env_var TEXT    NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    model_type      TEXT
);

CREATE TABLE IF NOT EXISTS results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id     INTEGER,
    model_id      INTEGER,
    model_name    TEXT    NOT NULL,
    prompt_text   TEXT    NOT NULL,
    response_text TEXT    NOT NULL,
    tags          TEXT,
    saved_at      TEXT    NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE SET NULL,
    FOREIGN KEY (model_id)  REFERENCES models(id)  ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_prompts_created_at ON prompts(created_at);
CREATE INDEX IF NOT EXISTS idx_models_is_active  ON models(is_active);
CREATE INDEX IF NOT EXISTS idx_results_saved_at  ON results(saved_at);
CREATE INDEX IF NOT EXISTS idx_results_prompt_id ON results(prompt_id);
CREATE INDEX IF NOT EXISTS idx_results_model_id  ON results(model_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


@contextmanager
def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


# --- prompts ---


def create_prompt(prompt: str, tags: str | None = None, db_path: Path | str = DEFAULT_DB_PATH) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO prompts (created_at, prompt, tags) VALUES (?, ?, ?)",
            (_now_iso(), prompt, tags),
        )
        return int(cursor.lastrowid)


def get_prompt(prompt_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
        return _row_to_dict(row) if row else None


def list_prompts(
    search: str | None = None,
    order_by: str = "created_at",
    order_dir: str = "DESC",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    allowed_columns = {"created_at", "prompt", "tags", "id"}
    allowed_dirs = {"ASC", "DESC"}
    if order_by not in allowed_columns:
        order_by = "created_at"
    if order_dir not in allowed_dirs:
        order_dir = "DESC"

    query = "SELECT * FROM prompts"
    params: tuple[Any, ...] = ()
    if search:
        query += " WHERE LOWER(prompt) LIKE LOWER(?) OR LOWER(IFNULL(tags, '')) LIKE LOWER(?)"
        pattern = f"%{search}%"
        params = (pattern, pattern)
    query += f" ORDER BY {order_by} {order_dir}"
    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]


def update_prompt(
    prompt_id: int,
    prompt: str,
    tags: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE prompts SET prompt = ?, tags = ? WHERE id = ?",
            (prompt, tags, prompt_id),
        )


def delete_prompt(prompt_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))


# --- models ---


def create_model(
    name: str,
    api_url: str,
    api_id: str,
    api_key_env_var: str,
    is_active: int = 1,
    model_type: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO models (name, api_url, api_id, api_key_env_var, is_active, model_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, api_url, api_id, api_key_env_var, is_active, model_type),
        )
        return int(cursor.lastrowid)


def get_model(model_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
        return _row_to_dict(row) if row else None


def list_models(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM models ORDER BY name").fetchall()
        return [_row_to_dict(row) for row in rows]


def list_active_models(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM models WHERE is_active = 1 ORDER BY name"
        ).fetchall()
        return [_row_to_dict(row) for row in rows]


def update_model(
    model_id: int,
    name: str,
    api_url: str,
    api_id: str,
    api_key_env_var: str,
    is_active: int,
    model_type: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE models
            SET name = ?, api_url = ?, api_id = ?, api_key_env_var = ?,
                is_active = ?, model_type = ?
            WHERE id = ?
            """,
            (name, api_url, api_id, api_key_env_var, is_active, model_type, model_id),
        )


def set_model_active(
    model_id: int,
    is_active: int,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE models SET is_active = ? WHERE id = ?", (is_active, model_id))


def delete_model(model_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM models WHERE id = ?", (model_id,))


def count_models(db_path: Path | str = DEFAULT_DB_PATH) -> int:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM models").fetchone()
        return int(row["cnt"]) if row else 0


# --- results ---


def create_result(
    model_name: str,
    prompt_text: str,
    response_text: str,
    prompt_id: int | None = None,
    model_id: int | None = None,
    tags: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO results
                (prompt_id, model_id, model_name, prompt_text, response_text, tags, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (prompt_id, model_id, model_name, prompt_text, response_text, tags, _now_iso()),
        )
        return int(cursor.lastrowid)


def list_results(
    search: str | None = None,
    order_by: str = "saved_at",
    order_dir: str = "DESC",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    allowed_columns = {"saved_at", "model_name", "prompt_text", "response_text", "tags", "id"}
    allowed_dirs = {"ASC", "DESC"}
    if order_by not in allowed_columns:
        order_by = "saved_at"
    if order_dir not in allowed_dirs:
        order_dir = "DESC"

    query = "SELECT * FROM results"
    params: tuple[Any, ...] = ()
    if search:
        query += (
            " WHERE LOWER(model_name) LIKE LOWER(?) OR LOWER(prompt_text) LIKE LOWER(?) "
            "OR LOWER(response_text) LIKE LOWER(?) OR LOWER(IFNULL(tags, '')) LIKE LOWER(?)"
        )
        pattern = f"%{search}%"
        params = (pattern, pattern, pattern, pattern)
    query += f" ORDER BY {order_by} {order_dir}"
    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]


def delete_result(result_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM results WHERE id = ?", (result_id,))


# --- settings ---


def get_setting(key: str, db_path: Path | str = DEFAULT_DB_PATH) -> str | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, _now_iso()),
        )


def list_settings(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM settings ORDER BY key").fetchall()
        return [_row_to_dict(row) for row in rows]


def _self_test() -> None:
    test_db = Path("chatlist_test.db")
    if test_db.exists():
        test_db.unlink()

    init_db(test_db)

    prompt_id = create_prompt("Тестовый промт", "тест", test_db)
    assert get_prompt(prompt_id, test_db) is not None
    assert len(list_prompts(search="Тестовый", db_path=test_db)) == 1

    model_id = create_model(
        name="Test Model",
        api_url="https://example.com/v1/chat/completions",
        api_id="test-model",
        api_key_env_var="TEST_API_KEY",
        model_type="openai",
        db_path=test_db,
    )
    assert len(list_active_models(test_db)) == 1
    update_model(
        model_id, "Test Model", "https://example.com/v1", "test-model", "TEST_API_KEY", 0, "openai", test_db
    )
    assert len(list_active_models(test_db)) == 0

    result_id = create_result(
        model_name="Test Model",
        prompt_text="Тестовый промт",
        response_text="Тестовый ответ",
        prompt_id=prompt_id,
        model_id=model_id,
        db_path=test_db,
    )
    assert len(list_results(db_path=test_db)) == 1

    delete_prompt(prompt_id, test_db)
    rows = list_results(db_path=test_db)
    assert len(rows) == 1
    assert rows[0]["prompt_id"] is None
    assert rows[0]["prompt_text"] == "Тестовый промт"

    set_setting("request_timeout", "30", test_db)
    assert get_setting("request_timeout", test_db) == "30"

    test_db.unlink()
    print("db.py: все проверки пройдены")


if __name__ == "__main__":
    _self_test()
