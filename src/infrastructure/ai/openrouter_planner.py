from __future__ import annotations

import json
import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from typing import List, Literal, Union

from pydantic import BaseModel, Field, ValidationError


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL_NAME = "openai/gpt-5-mini"

TEMPERATURE = 0.2
MAX_RETRIES = 3
TIMEOUT = 30

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return (raw or "").strip().lower() not in {"0", "false", "no", "off", ""}


def _truncate(text: str, limit: int = 2000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"... <truncated {len(text) - limit} chars>"


class TimeSlot(BaseModel):
    start: datetime
    end: datetime


class ScheduledResult(BaseModel):
    is_scheduled: bool
    slot: TimeSlot | None
    message: str


class CognitiveAnalysisResult(BaseModel):
    concentration_level: Literal["deep", "medium", "light"]
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_block_minutes: int = Field(ge=5, le=240)
    preferred_energy: Literal["high", "medium", "low"]
    best_time_of_day: str
    scheduling: ScheduledResult
    reason: str
    actions: List[str]


class TaskInput(BaseModel):
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    user_estimate: str | None = None
    wake_up_time: str = Field(default="08:00")
    bed_time: str = Field(default="23:00")
    free_slots: List[TimeSlot] = Field(default_factory=list)
    deadline: Union[datetime, None] = None


class QuillHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            if self.text_parts and not self.text_parts[-1].endswith("\n"):
                self.text_parts.append("\n")
        elif tag == "u":
            self.text_parts.append("__")
        elif tag == "s":
            self.text_parts.append("~~")
        elif tag in ("strong", "b"):
            self.text_parts.append("**")
        elif tag in ("em", "i"):
            self.text_parts.append("*")
        elif tag == "li":
            self.text_parts.append("\n- ")
        elif tag == "br":
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "p":
            self.text_parts.append("\n")
        elif tag == "u":
            self.text_parts.append("__")
        elif tag == "s":
            self.text_parts.append("~~")
        elif tag in ("strong", "b"):
            self.text_parts.append("**")
        elif tag in ("em", "i"):
            self.text_parts.append("*")

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self) -> str:
        return "".join(self.text_parts).strip()


def clean_quill_html(html_content: str) -> str:
    if not html_content:
        return ""
    parser = QuillHTMLParser()
    parser.feed(html_content)
    return parser.get_text()


SYSTEM_PROMPT_TEMPLATE = """
Ты — интеллектуальный планировщик задач с учетом биоритмов.

Твоя задача:
1. Проанализировать когнитивную сложность задачи.
2. Рассчитать пики активности пользователя на основе времени пробуждения ({wake_up_time}) и сна ({bed_time}).

   МОДЕЛЬ БИОРИТМОВ (отсчет от времени пробуждения):
   - Фаза 1 (Раскачка): 0-2 часа. Энергия растет.
   - Фаза 2 (ПЕРВЫЙ ПИК - Золотой час): 2-5 часов. Максимальная когнитивная способность. ИДЕАЛЬНО для "deep".
   - Фаза 3 (Спад/Обед): 6-8 часов. Энергия падает. Плохо для "deep".
   - Фаза 4 (ВТОРОЙ ПИК): 9-11 часов. Энергия средняя/высокая. Хорошо для "medium" или рутины.
   - Фаза 5 (Вечерний спад): 12+ часов (или за 3-4 часа до сна). Энергия низкая. ТОЛЬКО "light".

3. Если переданы свободные слоты (free_slots) и дедлайн (deadline):
   - СТРОГО выбирай слот ИСКЛЮЧИТЕЛЬНО из списка free_slots.
   - Все даты и время должны быть в формате ISO 8601 (YYYY-MM-DDTHH:MM:SS).
   - НЕ ВЫДУМЫВАЙ свои слоты и НЕ РАСШИРЯЙ переданные интервалы.

   !!! ПРОВЕРКА ДЛИТЕЛЬНОСТИ (CRITICAL) !!!
   1. Сначала определи recommended_block_minutes (например, 90 минут).
   2. Для каждого слота из free_slots вычисли его длительность: (end - start).
   3. ЕСЛИ длительность слота МЕНЬШЕ recommended_block_minutes — ЭТОТ СЛОТ СТРОГО ЗАПРЕЩЕН.
   4. ЕСЛИ длительность слота БОЛЬШЕ или РАВНА recommended_block_minutes — ЭТОТ СЛОТ ПОДХОДИТ.
   5. ВАЖНО: Если слот длиннее необходимого, ОБРЕЖЬ ЕГО.
      - Верни slot.start = начало свободного окна.
      - Верни slot.end = начало + recommended_block_minutes.
      - НЕ возвращай все окно целиком, если оно больше чем нужно.
   6. Ты НЕ ИМЕЕШЬ ПРАВА пытаться "впихнуть" задачу в слот, который КОРОЧЕ recommended_block_minutes.
   7. Если подходящего по длине слота нет — ставь is_scheduled: false.

   - Слот должен быть ДО дедлайна.
   - Слот должен соответствовать энергии (сравнивай время слота с фазами биоритмов, игнорируя дату для определения фазы).
   - ВАЖНО: Не ставь "deep" задачи на вечерний спад (за 3-4 часа до сна), если есть хоть какая-то альтернатива.
   - Если идеального слота нет — бери компромиссный (например, "deep" на спаде), но ОБЯЗАТЕЛЬНО подходящий по длительности.
   - Если ни один слот не подходит по длительности или дедлайну — ставь is_scheduled: false и объясни причину.

Правила маппинга энергии:
- "deep" (высокая концентрация) -> Только ПЕРВЫЙ ПИК (приоритет) или ВТОРОЙ ПИК (компромисс). Избегать спадов.
- "medium" -> ВТОРОЙ ПИК или ПЕРВЫЙ ПИК.
- "light" -> Любое время, можно на спадах.

ОБРАТИ ВНИМАНИЕ НА ФОРМАТИРОВАНИЕ HTML В ОПИСАНИИ:
- Текст в __двойных подчеркиваниях__ (например __важно__) является ПОДЧЕРКНУТЫМ.
- Текст в ~~тильдах~~ является ЗАЧЕРКНУТЫМ.
- Текст в **звездочках** — жирный.

JSON-схема ответа:
{{
  "concentration_level": "deep|medium|light",
  "confidence": 0.0-1.0,
  "recommended_block_minutes": int,
  "preferred_energy": "high|medium|low",
  "best_time_of_day": "строка с описанием идеального времени (абстрактно)",
  "scheduling": {{
    "is_scheduled": true/false,
    "slot": {{"start": "ISO 8601", "end": "ISO 8601"}} или null,
    "message": "Объяснение, почему выбрано это время или почему не удалось найти слот"
  }},
  "reason": "краткое объяснение",
  "actions": ["список действий"]
}}
""".strip()


def build_user_prompt(task: TaskInput) -> str:
    cleaned_description = clean_quill_html(task.description)
    tags_str = ", ".join(task.tags) if task.tags else "нет тегов"

    slots_str = "Не переданы"
    if task.free_slots:
        slots_str = ", ".join(
            f"{s.start.replace(microsecond=0).isoformat()}/{s.end.replace(microsecond=0).isoformat()}"
            for s in task.free_slots
        )

    deadline_str = task.deadline.replace(microsecond=0).isoformat() if task.deadline else "Не указан"

    return f"""
Задача:
Название: {task.title}
Описание: {cleaned_description}

Параметры пользователя:
- Подъем: {task.wake_up_time}
- Отбой: {task.bed_time}

Ограничения:
- Свободные слоты (ISO 8601): {slots_str}
- Дедлайн (ISO 8601): {deadline_str}

Дополнительный контекст:
- Теги: {tags_str}
- Оценка пользователя: {task.user_estimate or "не указана"}
""".strip()


def _extract_first_json_object(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if text.startswith("{") and text.endswith("}"):
        return text
    start_idx = text.find("{")
    if start_idx < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]
    return None


def call_openrouter(system_prompt: str, user_prompt: str, *, attempt: int | None = None) -> tuple[str, dict]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model_name = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL_NAME)
    debug = _bool_env("OPENROUTER_DEBUG", False)

    payload = {
        "model": model_name,
        "temperature": TEMPERATURE,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "time-shape-manager",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_URL, data=data, headers=headers, method="POST")

    ssl_verify_raw = (os.getenv("OPENROUTER_SSL_VERIFY", "1") or "1").strip().lower()
    ssl_verify = ssl_verify_raw not in {"0", "false", "no", "off"}

    if ssl_verify:
        ctx = ssl.create_default_context()
        ca_bundle = os.getenv("OPENROUTER_CA_BUNDLE")
        if ca_bundle:
            ctx.load_verify_locations(cafile=ca_bundle)
        else:
            try:
                import certifi  # type: ignore

                ctx.load_verify_locations(cafile=certifi.where())
            except Exception:
                pass
    else:
        ctx = ssl._create_unverified_context()

    if debug:
        logger.info(
            "OpenRouter request: model=%s attempt=%s timeout=%ss ssl_verify=%s ca_bundle=%s payload_bytes=%s sys_len=%s user_len=%s",
            model_name,
            attempt if attempt is not None else "-",
            TIMEOUT,
            ssl_verify,
            "set" if os.getenv("OPENROUTER_CA_BUNDLE") else "auto",
            len(data),
            len(system_prompt or ""),
            len(user_prompt or ""),
        )

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if debug:
                logger.info(
                    "OpenRouter response: status=%s elapsed_ms=%s body_len=%s",
                    getattr(response, "status", None),
                    elapsed_ms,
                    len(response_body),
                )
            raw_json = json.loads(response_body)
            content = raw_json["choices"][0]["message"]["content"]
            usage = raw_json.get("usage", {})
            if debug:
                logger.info("OpenRouter parsed: content_len=%s usage=%s", len(content or ""), usage)
                logger.debug("OpenRouter content (truncated): %s", _truncate(content or ""))
            return content, usage
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "OpenRouter HTTPError: status=%s reason=%s elapsed_ms=%s body_len=%s body(truncated)=%s",
            getattr(exc, "code", None),
            getattr(exc, "reason", None),
            elapsed_ms,
            len(body),
            _truncate(body),
        )
        raise
    except urllib.error.URLError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "OpenRouter URLError: reason=%s elapsed_ms=%s",
            getattr(exc, "reason", None),
            elapsed_ms,
        )
        raise


def analyze_task(task: TaskInput) -> CognitiveAnalysisResult:
    last_error: Exception | None = None
    debug = _bool_env("OPENROUTER_DEBUG", False)
    logger.info(
        "AI planning: start title=%s free_slots=%s has_deadline=%s model=%s",
        _truncate(task.title, 200),
        len(task.free_slots),
        bool(task.deadline),
        os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL_NAME),
    )
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        wake_up_time=task.wake_up_time,
        bed_time=task.bed_time,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_content, _usage = call_openrouter(
                system_prompt,
                build_user_prompt(task),
                attempt=attempt,
            )

            try:
                parsed_json = json.loads(raw_content)
            except json.JSONDecodeError:
                extracted = _extract_first_json_object(raw_content)
                logger.error(
                    "AI planning: JSONDecodeError attempt=%s raw_len=%s extracted=%s raw(truncated)=%s",
                    attempt,
                    len(raw_content or ""),
                    "yes" if extracted else "no",
                    _truncate(raw_content or "") if debug else "<hidden; set OPENROUTER_DEBUG=1>",
                )
                if not extracted:
                    raise
                parsed_json = json.loads(extracted)

            try:
                result = CognitiveAnalysisResult.model_validate(parsed_json)
            except ValidationError as exc:
                logger.error(
                    "AI planning: ValidationError attempt=%s errors=%s raw_len=%s raw(truncated)=%s",
                    attempt,
                    exc.errors(),
                    len(raw_content or ""),
                    _truncate(raw_content or ""),
                )
                raise

            if debug:
                logger.info(
                    "AI planning: success attempt=%s concentration=%s minutes=%s scheduled=%s",
                    attempt,
                    result.concentration_level,
                    result.recommended_block_minutes,
                    bool(result.scheduling and result.scheduling.is_scheduled),
                )
            return result
        except (json.JSONDecodeError, ValidationError, urllib.error.URLError, RuntimeError, KeyError) as exc:
            last_error = exc
            logger.error(
                "AI planning: attempt failed attempt=%s type=%s error=%s",
                attempt,
                type(exc).__name__,
                str(exc),
            )
            if isinstance(exc, RuntimeError):
                raise
            time.sleep(0.5 * attempt)

    logger.error(
        "AI planning: exhausted retries=%s last_error_type=%s last_error=%s",
        MAX_RETRIES,
        type(last_error).__name__ if last_error else None,
        str(last_error) if last_error else None,
    )
    if isinstance(last_error, RuntimeError):
        raise last_error
    raise RuntimeError("Не удалось получить валидный ответ от модели") from last_error
