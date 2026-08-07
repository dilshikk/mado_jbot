# bot/ai/resume.py
"""AI-скрининг анкеты + отправка HR-карточки в чат.

Порядок отправки:
  1. AI-скрининг запускается сразу.
  2. HR-карточка + AI-результат отправляются одним сообщением.
  3. Видео-визитка (если есть) идёт следующим сообщением.
"""

import logging
from contextlib import suppress
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.client import cf_chat
from bot.ai.models import SCREENING_MODEL
from bot.ai.parser import extract_text
from bot.ai.prompts import SCREENING_SYSTEM
from bot.core.config import ADMIN_CHAT_ID, settings
from bot.db import requests as db
from bot import keyboards as kb
from bot.utils.formatters import build_hr_resume_text

logger = logging.getLogger(__name__)

# Reasoning-модели (GPT-5, GPT-5-mini) тратят токены на рассуждения ДО генерации ответа.
# 2000 = ~1500 reasoning + ~500 content.
_SCREENING_MAX_TOKENS = 2000


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


async def _run_ai_screening(data: dict) -> str | None:
    """Запускает AI-скрининг и возвращает текст или None."""
    result = await cf_chat(
        model=SCREENING_MODEL,
        messages=[
            {"role": "system", "content": SCREENING_SYSTEM},
            {"role": "user",   "content": _build_prompt(data)},
        ],
        max_tokens=_SCREENING_MAX_TOKENS,
    )
    if result is None:
        return None
    return extract_text(result)


async def screen_application(
    bot: Bot,
    session: AsyncSession,
    app_id: int,
    data: dict,
    user,
) -> None:
    """Отправляет HR-карточку + AI-скрининг одним сообщением, видео отдельно.

    Никогда не бросает исключений — не должна ломать приём анкеты.
    """
    lang = await db.get_user_lang(session, user.id) or "ru"
    username_raw = user.username or "отсутствует"

    resume_text = build_hr_resume_text(data, lang, user)
    hr_keyboard = kb.get_hr_action_keyboard(
        phone=data.get("phone", ""),
        username=username_raw,
        candidate_id=user.id,
    )

    # Сначала запрашиваем AI (best-effort)
    ai_text: str | None = None
    if settings.ai_available:
        try:
            ai_text = await _run_ai_screening(data)
        except Exception as exc:
            logger.error(
                "screen_application: AI-скрининг упал user=%d: %s",
                user.id, exc,
            )

    # Собираем одно сообщение: карточка + AI-скрининг
    if ai_text:
        full_text = (
            f"{resume_text}\n\n"
            f"{'─' * 30}\n"
            f"🤖 <b>AI-скрининг:</b>\n{ai_text}"
        )
    else:
        full_text = resume_text

    # Сообщение Telegram ограничено 4096 символами
    if len(full_text) > 4096:
        full_text = full_text[:4090] + "\n…"

    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=full_text,
            reply_markup=hr_keyboard,
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error(
            "screen_application: ошибка отправки HR-карточки user=%d: %s",
            user.id, exc,
        )

    # Видео-визитка отдельным сообщением
    video_file_id = data.get("video_file_id")
    is_video_note = data.get("is_video_note", False)
    if video_file_id:
        try:
            if is_video_note:
                msg = await bot.send_video_note(
                    chat_id=ADMIN_CHAT_ID,
                    video_note=video_file_id,
                )
            else:
                msg = await bot.send_video(
                    chat_id=ADMIN_CHAT_ID,
                    video=video_file_id,
                    caption=f"🎥 Видео-визитка | user_id={user.id}",
                )
            with suppress(Exception):
                await db.save_hr_video_msg_id(session, user.id, msg.message_id)
        except Exception as exc:
            logger.error(
                "screen_application: ошибка отправки видео user=%d: %s",
                user.id, exc,
            )
