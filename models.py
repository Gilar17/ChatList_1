"""Логика работы с моделями нейросетей и промтами."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import db
from dotenv import load_dotenv

DEFAULT_SEED_MODELS: list[dict[str, Any]] = [
    {
        "name": "GPT-4o",
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "api_id": "openai/gpt-4o",
        "api_key_env_var": "OPENROUTER_API_KEY",
        "is_active": 1,
        "model_type": "openrouter",
    },
    {
        "name": "DeepSeek",
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "api_id": "deepseek-chat",
        "api_key_env_var": "DEEPSEEK_API_KEY",
        "is_active": 1,
        "model_type": "deepseek",
    },
    {
        "name": "Groq Llama",
        "api_url": "https://api.groq.com/openai/v1/chat/completions",
        "api_id": "llama-3.3-70b-versatile",
        "api_key_env_var": "GROQ_API_KEY",
        "is_active": 1,
        "model_type": "groq",
    },
    {
        "name": "OpenAI GPT-4o",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "api_id": "gpt-4o",
        "api_key_env_var": "OPENAI_API_KEY",
        "is_active": 0,
        "model_type": "openai",
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


def init_environment() -> None:
    load_dotenv()


def get_api_key(api_key_env_var: str) -> str | None:
    return os.getenv(api_key_env_var)


def load_models() -> list[ModelRecord]:
    return [ModelRecord.from_row(row) for row in db.list_models()]


def load_active_models() -> list[ModelRecord]:
    return [ModelRecord.from_row(row) for row in db.list_active_models()]


def get_model_by_id(model_id: int) -> ModelRecord | None:
    row = db.get_model(model_id)
    return ModelRecord.from_row(row) if row else None


def add_model(
    name: str,
    api_url: str,
    api_id: str,
    api_key_env_var: str,
    is_active: int = 1,
    model_type: str | None = None,
) -> int:
    return db.create_model(name, api_url, api_id, api_key_env_var, is_active, model_type)


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
        return
    for item in DEFAULT_SEED_MODELS:
        db.create_model(
            name=item["name"],
            api_url=item["api_url"],
            api_id=item["api_id"],
            api_key_env_var=item["api_key_env_var"],
            is_active=item["is_active"],
            model_type=item.get("model_type"),
        )


def save_prompt(prompt: str, tags: str | None = None) -> int:
    return db.create_prompt(prompt, tags)


def load_prompts(search: str | None = None) -> list[PromptRecord]:
    return [PromptRecord.from_row(row) for row in db.list_prompts(search=search)]


def get_prompt_by_id(prompt_id: int) -> PromptRecord | None:
    row = db.get_prompt(prompt_id)
    return PromptRecord.from_row(row) if row else None
