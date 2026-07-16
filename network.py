"""Отправка HTTP-запросов к API нейросетей."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

import models as model_service

if TYPE_CHECKING:
    from models import ModelRecord

STUB_MODE = True
DEFAULT_TIMEOUT = 30.0


@dataclass
class RequestResult:
    model_name: str
    response_text: str
    success: bool = True


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


def _send_openai_compatible(model: ModelRecord, prompt: str, timeout: float) -> RequestResult:
    api_key = model_service.get_api_key(model.api_key_env_var)
    if not api_key:
        return RequestResult(
            model_name=model.name,
            response_text=f"Ошибка: не задан API-ключ ({model.api_key_env_var})",
            success=False,
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_openai_payload(model.api_id, prompt)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(model.api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            text = _parse_openai_response(data)
            return RequestResult(model_name=model.name, response_text=text, success=True)
    except httpx.TimeoutException:
        return RequestResult(
            model_name=model.name,
            response_text="Ошибка: превышен таймаут запроса",
            success=False,
        )
    except httpx.HTTPStatusError as exc:
        return RequestResult(
            model_name=model.name,
            response_text=f"Ошибка HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            success=False,
        )
    except (httpx.RequestError, ValueError, KeyError) as exc:
        return RequestResult(
            model_name=model.name,
            response_text=f"Ошибка: {exc}",
            success=False,
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
    )


def send_prompt_to_model(
    model: ModelRecord,
    prompt: str,
    timeout: float = DEFAULT_TIMEOUT,
    use_stub: bool = STUB_MODE,
) -> RequestResult:
    if use_stub:
        return _send_stub(model, prompt)

    model_type = (model.model_type or "openai").lower()
    if model_type in {"openai", "deepseek", "groq", "openrouter"}:
        return _send_openai_compatible(model, prompt, timeout)

    return RequestResult(
        model_name=model.name,
        response_text=f"Ошибка: неподдерживаемый тип API ({model.model_type})",
        success=False,
    )


def send_prompt_to_all(
    prompt: str,
    active_models: list[ModelRecord] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    use_stub: bool = STUB_MODE,
) -> list[RequestResult]:
    if active_models is None:
        active_models = model_service.load_active_models()

    if not active_models:
        return [
            RequestResult(
                model_name="—",
                response_text="Нет активных моделей. Добавьте или включите модели в базе данных.",
                success=False,
            )
        ]

    results: list[RequestResult] = []
    for model in active_models:
        results.append(send_prompt_to_model(model, prompt, timeout=timeout, use_stub=use_stub))
    return results
