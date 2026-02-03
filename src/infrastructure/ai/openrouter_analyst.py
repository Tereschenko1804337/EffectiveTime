from __future__ import annotations

import json
import logging
import os
import urllib.error
from pydantic import BaseModel, Field, ValidationError
from .openrouter_planner import call_openrouter, _extract_first_json_object, MAX_RETRIES

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — эксперт по продуктивности и управлению временем (Time Management Coach).
Твоя задача — проанализировать статистику работы пользователя за неделю и дать конструктивную обратную связь.

Входные данные (JSON):
- Общее количество задач.
- Распределение времени по статусам (сколько времени задачи находились в "В работе", "Новый", "Блокировано" и т.д.).
- Среднее время выполнения задачи (Cycle Time).
- Список категорий задач.

Твоя цель:
1. Выявить "узкие места" (bottlenecks). Например, если задачи слишком долго висят в "Блокировано" или "Ревью".
2. Оценить эффективность. Соответствует ли время "В работе" количеству закрытых задач?
3. Дать 3-4 конкретных совета по улучшению процесса.
4. Тон общения: профессиональный, поддерживающий, но честный.

Формат ответа JSON:
{
  "score": int, // Оценка продуктивности от 1 до 100
  "summary": "Краткое резюме (1-2 предложения)",
  "analysis": "Подробный анализ в формате Markdown. Используй заголовки, списки, жирный шрифт.",
  "recommendations": ["Совет 1", "Совет 2", "Совет 3"]
}
"""

class AnalysisInput(BaseModel):
    total_tasks: int
    completed_tasks: int
    avg_completion_time_hours: float
    status_distribution: dict[str, str]  # "Status Name": "HH:MM" or "XX hours"
    category_distribution: dict[str, int]

class AnalysisResult(BaseModel):
    score: int = Field(ge=0, le=100)
    summary: str
    analysis: str
    recommendations: list[str]

def analyze_productivity(data: AnalysisInput) -> AnalysisResult:
    user_prompt = f"""
Проанализируй следующую статистику за неделю:

Всего задач: {data.total_tasks}
Завершено: {data.completed_tasks}
Среднее время выполнения (Cycle Time): {data.avg_completion_time_hours:.1f} ч.

Время в статусах (общее):
{json.dumps(data.status_distribution, ensure_ascii=False, indent=2)}

Категории задач:
{json.dumps(data.category_distribution, ensure_ascii=False, indent=2)}
    """.strip()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_content, _ = call_openrouter(SYSTEM_PROMPT, user_prompt, attempt=attempt)
            
            parsed_json = None
            try:
                parsed_json = json.loads(raw_content)
            except json.JSONDecodeError:
                extracted = _extract_first_json_object(raw_content)
                if extracted:
                    parsed_json = json.loads(extracted)
            
            if not parsed_json:
                raise ValueError("Could not parse JSON from response")

            return AnalysisResult.model_validate(parsed_json)

        except (Exception) as exc:
            logger.error(f"AI analysis failed attempt={attempt}: {exc}")
            if attempt == MAX_RETRIES:
                # Return fallback instead of crashing
                return AnalysisResult(
                    score=0,
                    summary="Не удалось провести анализ.",
                    analysis="К сожалению, сервис анализа временно недоступен. Попробуйте позже.",
                    recommendations=[]
                )
