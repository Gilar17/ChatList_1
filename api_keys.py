"""Безопасное хранение и получение API-ключей OpenRouter."""

from __future__ import annotations

import logging
import os
import sys

import keyring
from keyring.errors import KeyringError

logger = logging.getLogger("chatlist.api_keys")

KEYRING_SERVICE = "ChatList"
KEYRING_USERNAME = "OPENROUTER_API_KEY"
OPENROUTER_ENV_VAR = "OPENROUTER_API_KEY"

MISSING_OPENROUTER_KEY_MESSAGE = (
    "API-ключ OpenRouter не настроен. Откройте Настройки → OpenRouter API "
    "и добавьте собственный ключ."
)


def is_development_mode() -> bool:
    return not getattr(sys, "frozen", False)


def mask_api_key(key: str) -> str:
    cleaned = key.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "••••••••"
    return f"{cleaned[:4]}...{cleaned[-4:]}"


def _get_from_keyring() -> str | None:
    try:
        value = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except KeyringError:
        logger.warning("Не удалось прочитать ключ из хранилища учётных данных Windows")
        return None
    if value and value.strip():
        return value.strip()
    return None


def get_openrouter_api_key() -> str | None:
    key = _get_from_keyring()
    if key:
        return key

    env_key = os.getenv(OPENROUTER_ENV_VAR)
    if env_key and env_key.strip():
        return env_key.strip()
    return None


def has_openrouter_api_key() -> bool:
    return get_openrouter_api_key() is not None


def save_openrouter_api_key(api_key: str) -> None:
    cleaned = api_key.strip()
    if not cleaned:
        raise ValueError("API-ключ не может быть пустым.")
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, cleaned)
    except KeyringError as exc:
        raise RuntimeError("Не удалось сохранить ключ в хранилище Windows.") from exc
    os.environ.pop(OPENROUTER_ENV_VAR, None)


def delete_openrouter_api_key() -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except KeyringError:
        pass


def get_missing_api_key_message(api_key_env_var: str = OPENROUTER_ENV_VAR) -> str:
    if api_key_env_var == OPENROUTER_ENV_VAR:
        return MISSING_OPENROUTER_KEY_MESSAGE
    return f"Ошибка: не задан API-ключ ({api_key_env_var})"
