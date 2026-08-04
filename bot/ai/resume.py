# bot/ai/resume.py
"""Генерация AI-скрининга анкеты кандидата."""

from datetime import datetime

from bot.ai.client import cf_chat
from bot.ai.models import SCREENING_MODEL
from bot.ai.parser import extract_text
from bot.ai.prompts import SCREENING_SYSTEM


def _calc_age(birthday: str | None) -> int | None:
    if not birthday:
        return None
    try:
        birth = datetime.strptime(birthday, "%d.%m.%Y")
        today = datetime.now()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except (ValueError, TypeError):
        return None


def _build_prompt(data: dict) -> str:
    age = _calc_age(data.get("birthday"))
    lines = [
        f"Вакансия: {data.get('position', '—')}",
        f"Возраст: {age if age is not None else 'неизвестен'}",
        f"Опыт работы: {data.get('experience', '—')}",
        f"Пол: {data.get('gender', '—')}",
        f"Семейное положение: {data.get('family', '—')}",
        f"Гражданство: {data.get('citizenship', '—')}",
        f"Адрес: {data.get('address', '—')}",
        f"Видео-визитка: {data.get('video_duration', 0)} сек",
    ]
    return "Анкета кандидата:\n" + "\n".join(lines)


async def screen_application(data: dict) -> str | None:
    """Возвращает текст AI-скрининга или None, если AI недоступен/ошибка.

    Никогда не бросает исключений — скрининг не должен ломать приём анкет.
    """
    result = await cf_chat(
        model=SCREENING_MODEL,
        messages=[
            {"role": "system", "content": SCREENING_SYSTEM},
            {"role": "user",   "content": _build_prompt(data)},
        ],
        max_tokens=300,
    )
    if result is None:
        return None
    return extract_text(result)
