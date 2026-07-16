"""Отправка HTTP-запросов к API нейросетей через OpenRouter."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

import models as model_service

if TYPE_CHECKING:
    from models import ModelRecord

STUB_MODE = False
LOG_FILE = "chatlist.log"

logger = logging.getLogger("chatlist.network")


def setup_logging() -> None:
    if logger.handlers:
        return
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@dataclass
class RequestResult:
    model_name: str
    response_text: str
    success: bool = True
    model_id: int | None = None


def _build_openai_payload(api_id: str, prompt: str) -> dict:
    return {
        "model": api_id,
        "messages": [{"role": "user", "content": prompt}],
    }


def _parse_openai_response(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Пустой ответ API: нет поля choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise ValueError("Пустой ответ API: нет текста в message.content")
    return str(content).strip()


def _log_request(model_name: str, prompt: str, success: bool, details: str) -> None:
    if not model_service.is_logging_enabled():
        return
    setup_logging()
    status = "OK" if success else "ERROR"
    preview = prompt.replace("\n", " ")[:120]
    logger.info("%s | %s | %s | %s", status, model_name, preview, details)


def _send_openrouter(model: ModelRecord, prompt: str, timeout: float) -> RequestResult:
    api_key = model_service.get_api_key(model.api_key_env_var)
    if not api_key:
        message = f"Ошибка: не задан API-ключ ({model.api_key_env_var})"
        _log_request(model.name, prompt, False, message)
        return RequestResult(
            model_name=model.name,
            response_text=message,
            success=False,
            model_id=model.id,
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ChatList",
        "X-Title": "ChatList",
    }
    payload = _build_openai_payload(model.api_id, prompt)
    endpoint = model_service.get_api_endpoint(model)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            text = _parse_openai_response(data)
            _log_request(model.name, prompt, True, f"{len(text)} символов")
            return RequestResult(
                model_name=model.name,
                response_text=text,
                success=True,
                model_id=model.id,
            )
    except httpx.TimeoutException:
        message = "Ошибка: превышен таймаут запроса"
        _log_request(model.name, prompt, False, message)
        return RequestResult(
            model_name=model.name,
            response_text=message,
            success=False,
            model_id=model.id,
        )
    except httpx.HTTPStatusError as exc:
        message = f"Ошибка HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        _log_request(model.name, prompt, False, message)
        return RequestResult(
            model_name=model.name,
            response_text=message,
            success=False,
            model_id=model.id,
        )
    except (httpx.RequestError, ValueError, KeyError) as exc:
        message = f"Ошибка: {exc}"
        _log_request(model.name, prompt, False, message)
        return RequestResult(
            model_name=model.name,
            response_text=message,
            success=False,
            model_id=model.id,
        )


def _send_stub(model: ModelRecord, prompt: str) -> RequestResult:
    preview = prompt.strip().replace("\n", " ")
    if len(preview) > 60:
        preview = preview[:60] + "..."
    return RequestResult(
        model_name=model.name,
        response_text=(
            f"[Заглушка] Ответ от «{model.name}» ({model.api_id}) "
            f"на промт: «{preview}»"
        ),
        success=True,
        model_id=model.id,
    )


def send_prompt_to_model(
    model: ModelRecord,
    prompt: str,
    timeout: float | None = None,
    use_stub: bool = STUB_MODE,
) -> RequestResult:
    if timeout is None:
        timeout = model_service.get_request_timeout()

    if use_stub:
        return _send_stub(model, prompt)

    model_type = (model.model_type or "openrouter").lower()
    if model_type in {"openai", "deepseek", "groq", "openrouter"}:
        return _send_openrouter(model, prompt, timeout)

    message = f"Ошибка: неподдерживаемый тип API ({model.model_type})"
    _log_request(model.name, prompt, False, message)
    return RequestResult(
        model_name=model.name,
        response_text=message,
        success=False,
        model_id=model.id,
    )


def send_prompt_to_all(
    prompt: str,
    active_models: list[ModelRecord] | None = None,
    timeout: float | None = None,
    use_stub: bool = STUB_MODE,
) -> list[RequestResult]:
    if timeout is None:
        timeout = model_service.get_request_timeout()

    if active_models is None:
        active_models = model_service.load_active_models()

    if not active_models:
        return [
            RequestResult(
                model_name="—",
                response_text="Нет активных моделей. Добавьте или включите модели в меню «Модели».",
                success=False,
            )
        ]

    if len(active_models) == 1:
        return [send_prompt_to_model(active_models[0], prompt, timeout=timeout, use_stub=use_stub)]

    results: list[RequestResult] = []
    with ThreadPoolExecutor(max_workers=min(len(active_models), 4)) as executor:
        futures = {
            executor.submit(send_prompt_to_model, model, prompt, timeout, use_stub): model
            for model in active_models
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item.model_name.lower())
    return results
