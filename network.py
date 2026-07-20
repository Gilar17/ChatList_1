"""Отправка HTTP-запросов к API нейросетей через OpenRouter."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

import models as model_service

from version import __version__

if TYPE_CHECKING:
    from models import ModelRecord

STUB_MODE = False
LOG_FILE = "chatlist.log"
OPENROUTER_DIAGNOSTICS = True

logger = logging.getLogger("chatlist.network")

_SENSITIVE_PATTERNS = [
    (re.compile(r"Authorization\s*:\s*Bearer\s+\S+", re.IGNORECASE), "Authorization: Bearer [СКРЫТО]"),
    (re.compile(r"Bearer\s+sk[-_a-zA-Z0-9]+", re.IGNORECASE), "Bearer [СКРЫТО]"),
    (re.compile(r"sk-or-v1-[a-zA-Z0-9]+"), "[СКРЫТО]"),
    (re.compile(r"sk-[a-zA-Z0-9]+"), "[СКРЫТО]"),
    (re.compile(r"gsk_[a-zA-Z0-9]+"), "[СКРЫТО]"),
    (re.compile(r"(OPENROUTER_API_KEY|OPENAI_API_KEY|DEEPSEEK_API_KEY|GROQ_API_KEY)\s*=\s*\S+"), r"\1=[СКРЫТО]"),
]


def _sanitize_log_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def setup_logging() -> None:
    if logger.handlers:
        return
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info("ChatList %s — журнал запросов запущен", __version__)


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
    preview = _sanitize_log_text(prompt.replace("\n", " ")[:120])
    safe_details = _sanitize_log_text(details)
    logger.info("%s | %s | %s | %s", status, model_name, preview, safe_details)


def _print_openrouter_diagnostics(
    endpoint: str,
    model: ModelRecord,
    api_key: str | None,
    *,
    http_status: int | None = None,
    response_text: str | None = None,
) -> None:
    if not OPENROUTER_DIAGNOSTICS:
        return

    print("[OpenRouter] URL:", endpoint)
    print("[OpenRouter] API ID:", model.api_id)
    print("[OpenRouter] ключ задан:", "да" if api_key else "нет")
    print("[OpenRouter] длина ключа:", len(api_key) if api_key else 0)
    if http_status is not None:
        print("[OpenRouter] HTTP-код:", http_status)
    if response_text is not None:
        print("[OpenRouter] ответ сервера:", response_text)


def _send_openrouter(model: ModelRecord, prompt: str, timeout: float) -> RequestResult:
    api_key = model_service.get_api_key(model.api_key_env_var)
    if not api_key:
        message = model_service.get_missing_api_key_message(model.api_key_env_var)
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
        with httpx.Client(timeout=timeout, trust_env=True) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            if response.status_code >= 400:
                _print_openrouter_diagnostics(
                    endpoint,
                    model,
                    api_key,
                    http_status=response.status_code,
                    response_text=response.text,
                )
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
        response_body = exc.response.text
        message = f"Ошибка HTTP {exc.response.status_code}: {_sanitize_log_text(response_body)}"
        _print_openrouter_diagnostics(
            endpoint,
            model,
            api_key,
            http_status=exc.response.status_code,
            response_text=response_body,
        )
        _log_request(model.name, prompt, False, message)
        return RequestResult(
            model_name=model.name,
            response_text=message,
            success=False,
            model_id=model.id,
        )
    except (httpx.RequestError, ValueError, KeyError) as exc:
        message = f"Ошибка: {_sanitize_log_text(str(exc))}"
        _log_request(model.name, prompt, False, message)
        return RequestResult(
            model_name=model.name,
            response_text=message,
            success=False,
            model_id=model.id,
        )


def test_openrouter_connection(api_key: str | None = None) -> tuple[bool, str]:
    key = (api_key or model_service.get_api_key("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return False, model_service.get_missing_api_key_message()

    endpoint = f"{model_service.get_openrouter_base_url()}/models"
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://github.com/ChatList",
        "X-Title": "ChatList",
    }

    try:
        with httpx.Client(timeout=30.0, trust_env=True) as client:
            response = client.get(endpoint, headers=headers)
            if response.status_code == 200:
                return True, "Подключение успешно"
            if response.status_code == 401:
                return False, "Ошибка авторизации: ключ недействителен или отозван."
            if response.status_code == 403:
                return False, "Доступ запрещён: проверьте права API-ключа."
            body = _sanitize_log_text(response.text[:500])
            return False, f"Ошибка HTTP {response.status_code}: {body}"
    except httpx.TimeoutException:
        return False, "Превышено время ожидания ответа сервера OpenRouter."
    except httpx.RequestError as exc:
        return False, f"Ошибка сети: {_sanitize_log_text(str(exc))}"


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


ADAPTATION_TYPE_LABELS = {
    "code": "Код",
    "analysis": "Анализ",
    "creative": "Творческий текст",
}

ADAPTATION_TYPE_HINTS = {
    "code": "написание, объяснение или исправление программного кода",
    "analysis": "подробный разбор, сравнение, причины и выводы",
    "creative": "создание идей или творческого текста",
}


def _build_assistant_system_prompt(options: model_service.ImprovePromptOptions) -> str:
    format_lines = ['  "improved": "улучшенная версия промта"']
    if options.generate_alternatives:
        format_lines.append(
            '  "alternatives": ["вариант 1", "вариант 2", "вариант 3"]'
        )
    if options.adapt_to_type:
        hint = ADAPTATION_TYPE_HINTS.get(options.adaptation_type, "выбранный тип задачи")
        format_lines.append(f'  "adapted": "одна адаптированная версия промта ({hint})"')

    format_example = "{\n" + ",\n".join(format_lines) + "\n}"

    requirements = [
        "Верни только JSON без пояснений и markdown вне JSON-объекта.",
        "Не добавляй лишний текст до или после JSON.",
    ]
    if options.generate_alternatives:
        requirements.append("alternatives: ровно 2 или 3 переформулировки исходного промта.")
    if options.adapt_to_type:
        type_label = ADAPTATION_TYPE_LABELS.get(options.adaptation_type, options.adaptation_type)
        requirements.append(
            f"adapted: одна версия промта, адаптированная под тип «{type_label}»."
        )

    return "\n".join(
        [
            "Ты — ассистент по улучшению промтов для ChatList.",
            "Сохраняй язык и смысл исходного промта.",
            "",
            "Задача для поля improved — сделать промт более конкретным и полезным:",
            "- сохрани первоначальный смысл;",
            "- добавь цель запроса;",
            "- добавь необходимые подробности;",
            "- укажи желаемый формат результата;",
            "- не придумывай лишние сведения о пользователе.",
            "",
            "Пример: исходный «Как лучше планировать свой день?» → improved:",
            "«Составь простой пошаговый план эффективной организации дня. "
            "Объясни, как определить приоритетные задачи, распределить время на работу "
            "и отдых, избежать перегрузки и вечером оценить результат. "
            "Приведи пример дневного расписания.»",
            "",
            "Формат ответа:",
            format_example,
            "",
            "Требования:",
            *[f"- {item}" for item in requirements],
        ]
    )


def _build_improvement_user_message(
    original_prompt: str,
    options: model_service.ImprovePromptOptions,
) -> str:
    lines = ["Улучши следующий промт."]
    if options.generate_alternatives:
        lines.append("Предложи 2–3 альтернативные переформулировки.")
    if options.adapt_to_type:
        type_label = ADAPTATION_TYPE_LABELS.get(
            options.adaptation_type,
            options.adaptation_type,
        )
        lines.append(f"Создай одну адаптированную версию для типа «{type_label}».")
    lines.extend(["", f"Исходный промт:\n{original_prompt.strip()}"])
    return "\n".join(lines)


def _build_stub_improvement_response(
    original_prompt: str,
    options: model_service.ImprovePromptOptions,
) -> str:
    preview = original_prompt.strip().replace("\n", " ")
    if len(preview) > 80:
        preview = preview[:80] + "..."

    if "планировать" in original_prompt.lower() and "день" in original_prompt.lower():
        improved = (
            "Составь простой пошаговый план эффективной организации дня. "
            "Объясни, как определить приоритетные задачи, распределить время на работу "
            "и отдых, избежать перегрузки и вечером оценить результат. "
            "Приведи пример дневного расписания."
        )
    else:
        improved = (
            f"Подробно и структурированно ответь на запрос. "
            f"Укажи цель, необходимые детали и желаемый формат результата. "
            f"Тема: {preview}"
        )

    payload: dict[str, object] = {"improved": improved}

    if options.generate_alternatives:
        payload["alternatives"] = [
            f"Дай развёрнутый ответ на тему: {preview}",
            f"Объясни по шагам: {preview}",
            f"Сформулируй практические рекомендации по теме: {preview}",
        ]

    if options.adapt_to_type:
        adaptation_templates = {
            "code": (
                f"Напиши программный код и поясни решение для задачи: {preview}. "
                "Покажи пример реализации и объясни ключевые части."
            ),
            "analysis": (
                f"Проведи подробный анализ темы: {preview}. "
                "Сравни подходы, объясни причины и сформулируй выводы."
            ),
            "creative": (
                f"Предложи творческие идеи и образный текст по теме: {preview}. "
                "Сгенерируй несколько нестандартных вариантов."
            ),
        }
        payload["adapted"] = adaptation_templates.get(
            options.adaptation_type,
            f"Адаптируй запрос под тип «{options.adaptation_type}»: {preview}",
        )

    return json.dumps(payload, ensure_ascii=False, indent=2)


def improve_prompt(
    original_prompt: str,
    model: ModelRecord,
    options: model_service.ImprovePromptOptions | None = None,
    timeout: float | None = None,
    use_stub: bool = STUB_MODE,
) -> RequestResult:
    original_prompt = original_prompt.strip()
    if not original_prompt:
        return RequestResult(
            model_name=model.name,
            response_text="Ошибка: промт пустой",
            success=False,
            model_id=model.id,
        )

    if options is None:
        options = model_service.ImprovePromptOptions()

    if timeout is None:
        timeout = model_service.get_request_timeout()

    if use_stub:
        return RequestResult(
            model_name=model.name,
            response_text=_build_stub_improvement_response(original_prompt, options),
            success=True,
            model_id=model.id,
        )

    system_prompt = _build_assistant_system_prompt(options)
    user_message = _build_improvement_user_message(original_prompt, options)
    combined_prompt = f"{system_prompt}\n\n{user_message}"
    return send_prompt_to_model(model, combined_prompt, timeout=timeout, use_stub=use_stub)
