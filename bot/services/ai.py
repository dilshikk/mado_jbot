# bot/services/ai.py

"""AI-скрининг анкет через Cloudflare Workers AI.

Вызывается REST API — Workers-аккаунт не обязателен для хостинга бота,
достаточно Account ID и API Token из dashboard Cloudflare.
"""

import logging
from datetime import datetime

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
_TIMEOUT = aiohttp.ClientTimeout(total=25)

_SYSTEM_PROMPT = """Ты — ассистент HR-менеджера ресторана MADO (Tashkent City Mall).
Проанализируй анкету кандидата и дай короткий скрининг для HR.

Формат ответа (строго, на русском, не более 6 строк):
1. Вердикт: ✅ Подходит / ⚠️ Под вопросом / ❌ Не подходит
2-3. Главные аргументы (возраст, опыт, соответствие вакансии)
4. Риски или красные флаги (если есть)

Критерии: возраст 18–60 лет, для официанта/бариста опыт не обязателен,
для повара опыт желателен, видео-визитка длиннее 15 сек — плюс.
Будь краток, без вступлений."""


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
    if not settings.ai_available:
        return None

    url = _API_URL.format(
        account_id=settings.cloudflare_account_id,
        model=settings.ai_model,
    )
    payload = {
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(data)},
        ],
        "max_tokens": 300,
    }
    headers = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
            async with http.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Workers AI HTTP %d: %s", resp.status, body[:300])
                    return None
                result = await resp.json()
    except Exception as e:
        logger.error("Ошибка Workers AI: %s", e, exc_info=True)
        return None

    text = (result.get("result") or {}).get("response")
    if not text:
        logger.warning("Workers AI вернул пустой ответ: %s", str(result)[:300])
        return None
    return text.strip()
