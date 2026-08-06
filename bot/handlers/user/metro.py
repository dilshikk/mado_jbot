# bot/handlers/user/metro.py
"""Inline-хендлер выбора станции метро."""

import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards as kb
from bot.db import requests as db
from bot.filters.common import IsPrivateChat
from bot.lexicon import LOCALIZATION
from bot.states import Form

router = Router()
router.callback_query.filter(IsPrivateChat())

logger = logging.getLogger(__name__)

_PROMPT = {
    "ru": "🚇 Выберите ближайшую станцию метро:",
    "uz": "🚇 Eng yaqin metro bekatini tanlang:",
}

_RECAP_LABEL = {
    "ru": "🚇 Ближайшее метро",
    "uz": "🚇 Eng yaqin metro",
}


async def ask_metro(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Form.waiting_metro)
    with suppress(TelegramAPIError):
        stub = await message.answer("🚇", reply_markup=kb.remove_keyboard())
    with suppress(TelegramAPIError):
        await stub.delete()
    await message.answer(
        _PROMPT.get(lang, _PROMPT["ru"]),
        reply_markup=kb.get_metro_lines_keyboard(lang),
    )


async def _go_to_languages(message: Message, state: FSMContext, session: AsyncSession, lang: str) -> None:
    """Переходим к следующему шагу — выбор языков."""
    from bot.handlers.user.form_extra import ask_languages  # noqa: PLC0415
    await ask_languages(message, state, lang)


# ─── Callback: выбор линии ───────────────────────────────────────

@router.callback_query(Form.waiting_metro, F.data.startswith("metro_line:"))
async def on_metro_line(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    lang = data.get("lang", "ru")
    line = callback.data.split(":", 1)[1]

    if line == "skip":
        await state.update_data(metro_station_id=None, metro_name=None)
        logger.info("on_metro_line: user_id=%d skipped", callback.from_user.id)
        with suppress(TelegramAPIError):
            await callback.answer()
        # Сначала следующий шаг, потом удаляем — иначе message недоступен
        await _go_to_languages(callback.message, state, session, lang)
        with suppress(TelegramAPIError):
            await callback.message.delete()
        return

    stations = await db.get_metro_stations_by_line(session, line)
    if not stations:
        logger.warning("on_metro_line: no stations for line=%s", line)
        with suppress(TelegramAPIError):
            await callback.answer("Станции не найдены", show_alert=True)
        return

    from bot.keyboards.inline import METRO_LINES  # noqa: PLC0415
    line_info = METRO_LINES.get(line, ("", "", ""))
    line_name = line_info[2] if lang == "uz" else line_info[1]
    line_emoji = line_info[0]

    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            f"{line_emoji} {line_name} \n\n{_PROMPT.get(lang, _PROMPT['ru'])}",
            reply_markup=kb.get_metro_stations_keyboard(stations, line, lang),
            parse_mode="HTML",
        )
    await state.update_data(_metro_current_line=line)
    with suppress(TelegramAPIError):
        await callback.answer()


# ─── Callback: выбор станции ────────────────────────────────────

@router.callback_query(Form.waiting_metro, F.data.startswith("metro_station:"))
async def on_metro_station(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    lang = data.get("lang", "ru")
    station_id = int(callback.data.split(":", 1)[1])

    station = await db.get_metro_station_by_id(session, station_id)
    if not station:
        with suppress(TelegramAPIError):
            await callback.answer("Станция не найдена", show_alert=True)
        return

    name_key = "name_uz" if lang == "uz" else "name_ru"
    station_name = station.get(name_key, "—")

    await state.update_data(metro_station_id=station_id, metro_name=station_name)
    logger.info(
        "on_metro_station: user_id=%d station_id=%d name=%r",
        callback.from_user.id, station_id, station_name,
    )

    with suppress(TelegramAPIError):
        await callback.answer(f"✅ {station_name}")

    # Recap-сообщение — показываем выбранную станцию
    recap_label = _RECAP_LABEL.get(lang, _RECAP_LABEL["ru"])
    await callback.message.answer(
        f"{recap_label}: <b>{station_name}</b>",
        parse_mode="HTML",
    )

    # Переходим к следующему шагу ПЕРЕД удалением сообщения с кнопками
    await _go_to_languages(callback.message, state, session, lang)

    with suppress(TelegramAPIError):
        await callback.message.delete()


# ─── Callback: назад к линиям ────────────────────────────────────

@router.callback_query(Form.waiting_metro, F.data == "metro_back")
async def on_metro_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "ru")
    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            _PROMPT.get(lang, _PROMPT["ru"]),
            reply_markup=kb.get_metro_lines_keyboard(lang),
        )
    with suppress(TelegramAPIError):
        await callback.answer()


# ─── Callback: отмена заполнения анкеты ──────────────────────────────

@router.callback_query(F.data == "metro_cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.clear()
    await state.update_data(lang=lang)
    logger.info("on_cancel: user_id=%d cancelled form", callback.from_user.id)

    with suppress(TelegramAPIError):
        await callback.answer()
    await callback.message.answer(
        LOCALIZATION[lang]["anketa_cancelled"],
        reply_markup=kb.get_main_menu(lang),
        parse_mode="HTML",
    )
    with suppress(TelegramAPIError):
        await callback.message.delete()
