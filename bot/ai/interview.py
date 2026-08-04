# bot/ai/interview.py
"""Логика AI-интервью: генерация уточняющих вопросов для кандидата."""

from bot.ai.client import cf_chat
from bot.ai.models import INTERVIEW_MODEL
from bot.ai.parser import extract_text
from bot.ai.prompts import INTERVIEW_SYSTEM


async def generate_interview_question(data: dict, lang: str = "ru") -> str | None:
    """Генерирует один уточняющий вопрос для кандидата на основе его анкеты.

    Args:
        data: словарь с данными анкеты (position, experience, и т.д.)
        lang: язык кандидата — "ru" или "uz"

    Returns:
        Строка с вопросом или None, если AI недоступен/ошибка.
    """
    lang_hint = "Отвечай на русском языке." if lang == "ru" else "Javob o'zbek tilida bo'lsin."
    user_prompt = (
        f"Вакансия: {data.get('position', '—')}\n"
        f"Опыт: {data.get('experience', '—')}\n"
        f"Гражданство: {data.get('citizenship', '—')}\n"
        f"{lang_hint}"
    )

    result = await cf_chat(
        model=INTERVIEW_MODEL,
        messages=[
            {"role": "system", "content": INTERVIEW_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=150,
    )
    if result is None:
        return None
    return extract_text(result)
