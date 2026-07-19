"""Логика работы с моделями нейросетей, промтами, результатами и настройками."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import db
from dotenv import load_dotenv

DEFAULT_SETTINGS: dict[str, str] = {
    "request_timeout": "90",
    "db_path": "chatlist.db",
    "default_tags": "",
    "log_requests": "1",
    "prompt_assistant_model_id": "",
    "theme": "light",
    "font_size": "10",
}

DEFAULT_SEED_MODELS: list[dict[str, Any]] = [
    {
        "name": "GPT-4o",
        "api_id": "openai/gpt-4o",
        "is_active": 1,
    },
    {
        "name": "DeepSeek",
        "api_id": "deepseek/deepseek-chat",
        "is_active": 1,
    },
    {
        "name": "Llama 3.3",
        "api_id": "meta-llama/llama-3.3-70b-instruct",
        "is_active": 1,
    },
    {
        "name": "Claude 3.5",
        "api_id": "anthropic/claude-3.5-sonnet",
        "is_active": 0,
    },
]


@dataclass
class ModelRecord:
    id: int
    name: str
    api_url: str
    api_id: str
    api_key_env_var: str
    is_active: int
    model_type: str | None = None
    created_at: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ModelRecord:
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            api_url=str(row["api_url"]),
            api_id=str(row["api_id"]),
            api_key_env_var=str(row["api_key_env_var"]),
            is_active=int(row["is_active"]),
            model_type=row.get("model_type"),
            created_at=row.get("created_at"),
        )


@dataclass
class PromptRecord:
    id: int
    created_at: str
    prompt: str
    tags: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> PromptRecord:
        return cls(
            id=int(row["id"]),
            created_at=str(row["created_at"]),
            prompt=str(row["prompt"]),
            tags=row.get("tags"),
        )


@dataclass
class ResultRecord:
    id: int
    prompt_id: int | None
    model_id: int | None
    model_name: str
    prompt_text: str
    response_text: str
    tags: str | None
    saved_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ResultRecord:
        return cls(
            id=int(row["id"]),
            prompt_id=row.get("prompt_id"),
            model_id=row.get("model_id"),
            model_name=str(row["model_name"]),
            prompt_text=str(row["prompt_text"]),
            response_text=str(row["response_text"]),
            tags=row.get("tags"),
            saved_at=str(row["saved_at"]),
        )


def init_environment() -> None:
    load_dotenv()


def get_openrouter_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")


def get_openrouter_endpoint() -> str:
    return f"{get_openrouter_base_url()}/chat/completions"


def get_api_key(api_key_env_var: str = "OPENROUTER_API_KEY") -> str | None:
    return os.getenv(api_key_env_var)


def get_api_endpoint(model: ModelRecord) -> str:
    if model.api_url.startswith("http"):
        return model.api_url
    return get_openrouter_endpoint()


def init_default_settings() -> None:
    for key, value in DEFAULT_SETTINGS.items():
        if db.get_setting(key) is None:
            db.set_setting(key, value)


def get_setting_value(key: str, default: str = "") -> str:
    return db.get_setting(key) or default


def set_setting_value(key: str, value: str) -> None:
    db.set_setting(key, value)


def get_request_timeout() -> float:
    try:
        return float(get_setting_value("request_timeout", "90"))
    except ValueError:
        return 90.0


def get_default_tags() -> str | None:
    tags = get_setting_value("default_tags", "").strip()
    return tags or None


def is_logging_enabled() -> bool:
    return get_setting_value("log_requests", "1") == "1"


def get_theme() -> str:
    theme = get_setting_value("theme", "light").strip().lower()
    return theme if theme in {"light", "dark"} else "light"


def get_font_size() -> int:
    try:
        size = int(get_setting_value("font_size", "10"))
    except ValueError:
        size = 10
    return max(8, min(24, size))


@dataclass
class ImprovePromptOptions:
    generate_alternatives: bool = True
    adapt_to_type: bool = False
    adaptation_type: str = "code"


@dataclass
class PromptAssistantResult:
    improved: str
    alternatives: list[str]
    adapted: str = ""
    raw_response: str | None = None


def get_prompt_assistant_model_id() -> int | None:
    value = get_setting_value("prompt_assistant_model_id", "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def set_prompt_assistant_model_id(model_id: int | None) -> None:
    set_setting_value("prompt_assistant_model_id", "" if model_id is None else str(model_id))


def get_prompt_assistant_model() -> ModelRecord | None:
    model_id = get_prompt_assistant_model_id()
    if model_id is not None:
        model = get_model_by_id(model_id)
        if model is not None and model.is_active:
            return model

    active_models = load_active_models()
    return active_models[0] if active_models else None


def parse_prompt_assistant_response(
    text: str,
    *,
    expect_alternatives: bool = True,
    expect_adapted: bool = False,
) -> PromptAssistantResult:
    def normalize(data: dict[str, Any]) -> PromptAssistantResult:
        improved = str(data.get("improved", "")).strip()
        if not improved:
            raise ValueError("В ответе отсутствует поле improved")

        alternatives: list[str] = []
        if expect_alternatives:
            alternatives_raw = data.get("alternatives") or []
            if not isinstance(alternatives_raw, list):
                raise ValueError("Поле alternatives должно быть массивом")

            alternatives = [str(item).strip() for item in alternatives_raw if str(item).strip()]
            if len(alternatives) < 2:
                raise ValueError("Ожидается минимум 2 альтернативных варианта")
            alternatives = alternatives[:3]

        adapted = ""
        if expect_adapted:
            adapted = str(data.get("adapted", "")).strip()
            if not adapted:
                raise ValueError("В ответе отсутствует поле adapted")

        return PromptAssistantResult(
            improved=improved,
            alternatives=alternatives,
            adapted=adapted,
            raw_response=text,
        )

    cleaned = text.strip()
    candidates: list[str] = [cleaned]

    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if code_block:
        candidates.insert(0, code_block.group(1).strip())

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidates.append(cleaned[start : end + 1])

    last_error: ValueError | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = ValueError(f"Не удалось разобрать JSON: {exc}")
            continue
        if not isinstance(data, dict):
            last_error = ValueError("Ответ ассистента должен быть JSON-объектом")
            continue
        try:
            return normalize(data)
        except ValueError as exc:
            last_error = exc

    raise last_error or ValueError("Не удалось разобрать ответ ассистента")


def load_models() -> list[ModelRecord]:
    return [ModelRecord.from_row(row) for row in db.list_models()]


def load_active_models() -> list[ModelRecord]:
    return [ModelRecord.from_row(row) for row in db.list_active_models()]


def get_model_by_id(model_id: int) -> ModelRecord | None:
    row = db.get_model(model_id)
    return ModelRecord.from_row(row) if row else None


def get_model_by_name(name: str) -> ModelRecord | None:
    for model in load_models():
        if model.name == name:
            return model
    return None


def add_model(
    name: str,
    api_id: str,
    is_active: int = 1,
    api_url: str | None = None,
    api_key_env_var: str = "OPENROUTER_API_KEY",
    model_type: str = "openrouter",
) -> int:
    return db.create_model(
        name=name,
        api_url=api_url or get_openrouter_endpoint(),
        api_id=api_id,
        api_key_env_var=api_key_env_var,
        is_active=is_active,
        model_type=model_type,
    )


def edit_model(model: ModelRecord) -> None:
    db.update_model(
        model.id,
        model.name,
        model.api_url,
        model.api_id,
        model.api_key_env_var,
        model.is_active,
        model.model_type,
    )


def remove_model(model_id: int) -> None:
    db.delete_model(model_id)


def set_model_active(model_id: int, is_active: bool) -> None:
    db.set_model_active(model_id, 1 if is_active else 0)


def seed_default_models() -> None:
    if db.count_models() > 0:
        sync_models_to_openrouter()
        return

    endpoint = get_openrouter_endpoint()
    for item in DEFAULT_SEED_MODELS:
        db.create_model(
            name=item["name"],
            api_url=endpoint,
            api_id=item["api_id"],
            api_key_env_var="OPENROUTER_API_KEY",
            is_active=item["is_active"],
            model_type="openrouter",
        )


def sync_models_to_openrouter() -> None:
    endpoint = get_openrouter_endpoint()
    seed_by_name = {item["name"]: item for item in DEFAULT_SEED_MODELS}

    for model in load_models():
        seed = seed_by_name.get(model.name)
        api_id = seed["api_id"] if seed else model.api_id
        updated = ModelRecord(
            id=model.id,
            name=model.name,
            api_url=endpoint,
            api_id=api_id,
            api_key_env_var="OPENROUTER_API_KEY",
            is_active=model.is_active,
            model_type="openrouter",
            created_at=model.created_at,
        )
        edit_model(updated)


def save_prompt(prompt: str, tags: str | None = None) -> int:
    return db.create_prompt(prompt, tags or get_default_tags())


def load_prompts(search: str | None = None) -> list[PromptRecord]:
    return [PromptRecord.from_row(row) for row in db.list_prompts(search=search)]


def get_prompt_by_id(prompt_id: int) -> PromptRecord | None:
    row = db.get_prompt(prompt_id)
    return PromptRecord.from_row(row) if row else None


def update_prompt_record(prompt_id: int, prompt: str, tags: str | None = None) -> None:
    db.update_prompt(prompt_id, prompt, tags)


def remove_prompt(prompt_id: int) -> None:
    db.delete_prompt(prompt_id)


def save_result(
    model_name: str,
    prompt_text: str,
    response_text: str,
    prompt_id: int | None = None,
    model_id: int | None = None,
    tags: str | None = None,
) -> int:
    return db.create_result(
        model_name=model_name,
        prompt_text=prompt_text,
        response_text=response_text,
        prompt_id=prompt_id,
        model_id=model_id,
        tags=tags,
    )


def load_results(search: str | None = None) -> list[ResultRecord]:
    return [ResultRecord.from_row(row) for row in db.list_results(search=search)]


def remove_result(result_id: int) -> None:
    db.delete_result(result_id)


def export_results_to_markdown(results: list[ResultRecord]) -> str:
    lines = ["# Экспорт результатов ChatList", ""]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"## {index}. {result.model_name}",
                "",
                f"**Дата:** {result.saved_at}  ",
                f"**Теги:** {result.tags or '—'}  ",
                "",
                "### Промт",
                "",
                result.prompt_text,
                "",
                "### Ответ",
                "",
                result.response_text,
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def export_results_to_json(results: list[ResultRecord]) -> str:
    payload = [
        {
            "id": result.id,
            "saved_at": result.saved_at,
            "model_name": result.model_name,
            "prompt_text": result.prompt_text,
            "response_text": result.response_text,
            "tags": result.tags,
            "prompt_id": result.prompt_id,
            "model_id": result.model_id,
        }
        for result in results
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)
