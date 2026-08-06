# bot/handlers/admin/metro_stations.py
"""Раздел «Метро» в административной панели.

Навигация (стек экранов — только Reply Keyboard):
  Главное меню → show_metro_home()
    Нажать линию → экран станций
      Нажать станцию → экран станции (toggle / delete)
        ◀️ К станциям
      ➕ Добавить в эту линию → AddStation FSM
    ➕ Добавить станцию → выбор линии → AddStation FSM
    ⬅️ Назад → Главное меню
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.keyboards.reply import (
    ADMIN_BTN_BACK,
    ADMIN_BTN_CANCEL,
    get_admin_cancel_keyboard,
    get_admin_menu_keyboard,
    get_admin_metro_lines_kb,
    get_admin_metro_stations_kb,
    get_admin_station_confirm_delete_kb,
    get_admin_station_item_kb,
    remove_keyboard,
)

router = Router()
logger = logging.getLogger(__name__)

# ── Линии ─────────────────────────────────────────────────────────────────────

LINES: dict[str, tuple[str, str, str]] = {
    "red":    ("🔴", "Чиланзарская",              "Chilonzor liniyasi"),
    "green":  ("🟢", "Юнусабадская",              "Yunusobod liniyasi"),
    "blue":   ("🔵", "Узбекистанская",             "O'zbekiston liniyasi"),
    "orange": ("🟠", "30-летия независимости",     "Mustaqillik 30-yilligi liniyasi"),
}

# Кнопки линий (текст → ключ)
_LINE_BUTTONS: dict[str, str] = {
    "🔴 Чиланзарская":           "red",
    "🟢 Юнусабадская":           "green",
    "🔵 Узбекистанская":          "blue",
    "🟠 30-летия независимости":  "orange",
}

# Кнопки раздела
_BTN_ADD_STATION       = "➕ Добавить станцию"
_BTN_ADD_TO_LINE       = "➕ Добавить в эту линию"
_BTN_REFRESH           = "🔄 Обновить"
_BTN_TO_LINES          = "◀️ К линиям"
_BTN_TO_STATIONS       = "◀️ К станциям"
_BTN_TOGGLE_ON         = "✅ Включить"
_BTN_TOGGLE_OFF        = "❌ Выключить"
_BTN_DELETE            = "🗑 Удалить"
_BTN_CONFIRM_DELETE    = "✅ Да, удалить станцию"


class AddStation(StatesGroup):
    waiting_line    = State()  # только при добавлении без выбора линии
    waiting_name_ru = State()
    waiting_name_uz = State()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Хелперы ───────────────────────────────────────────────────────────────────

def _metro_home_text(total: int, active: int) -> str:
    return (
        f"🚇 <b>Станции метро</b>\n{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>\n\n"
        f"Выберите линию для просмотра и редактирования."
    )


def _station_label(s: dict) -> str:
    status = "✅" if s["active"] else "❌"
    return f"{status} {s['name_ru']}"


async def _get_station_by_label(label: str, line: str, session: AsyncSession) -> dict | None:
    stations = await db.get_all_metro_stations_by_line(session, line)
    for s in stations:
        if _station_label(s) == label:
            return s
    return None


# ── Публичная точка входа ─────────────────────────────────────────────────────

async def show_metro_home(message: Message, session: AsyncSession) -> None:
    """Открывает главный экран раздела «Метро»."""
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        _metro_home_text(total, active),
        parse_mode="HTML",
        reply_markup=get_admin_metro_lines_kb(),
    )


# ── /metro_stations ───────────────────────────────────────────────────────────

@router.message(Command("metro_stations"))
async def cmd_metro_stations(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await show_metro_home(message, session)


# ── Главный экран метро ───────────────────────────────────────────────────────

@router.message(F.text == _BTN_REFRESH)
async def metro_refresh(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    await message.answer(
        _metro_home_text(total, active),
        parse_mode="HTML",
        reply_markup=get_admin_metro_lines_kb(),
    )


@router.message(F.text == ADMIN_BTN_BACK)
async def metro_back(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard(),
    )


@router.message(F.text == _BTN_TO_LINES)
async def metro_to_lines(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    await message.answer(
        _metro_home_text(total, active),
        parse_mode="HTML",
        reply_markup=get_admin_metro_lines_kb(),
    )


# ── Экран линии ───────────────────────────────────────────────────────────────

@router.message(F.text.in_(_LINE_BUTTONS))
async def metro_show_line(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    line_key = _LINE_BUTTONS[message.text]
    await state.update_data(current_line=line_key)
    emoji, name_ru, name_uz = LINES[line_key]
    stations = await db.get_all_metro_stations_by_line(session, line_key)
    total  = len(stations)
    active = sum(1 for s in stations if s["active"])
    await message.answer(
        f"{emoji} <b>{name_ru}</b> / {name_uz}\n{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>\n\n"
        f"Нажмите на станцию для управления.",
        parse_mode="HTML",
        reply_markup=get_admin_metro_stations_kb(stations),
    )


# ── Кнопка «Добавить станцию» с выбором линии ─────────────────────────────────

@router.message(F.text == _BTN_ADD_STATION)
async def metro_add_start(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    # Выбор линии — через те же кнопки линий, но в состоянии waiting_line
    await state.set_state(AddStation.waiting_line)
    await message.answer(
        "➕ <b>Новая станция</b>\n\n<b>Шаг 1/3.</b> Выберите линию:",
        parse_mode="HTML",
        reply_markup=get_admin_metro_lines_kb(),
    )


@router.message(AddStation.waiting_line, F.text.in_(_LINE_BUTTONS))
async def metro_add_got_line(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    line_key = _LINE_BUTTONS[message.text]
    await state.update_data(new_station_line=line_key, current_line=line_key)
    emoji, name_ru, _ = LINES[line_key]
    await state.set_state(AddStation.waiting_name_ru)
    await message.answer(
        f"➕ <b>Новая станция</b> | {emoji} {name_ru}\n\n"
        f"<b>Шаг 2/3.</b> Введите название на <b>русском</b>:\n"
        f"Например: <code>Алмазар</code>",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


# ── Кнопка «Добавить в эту линию» ─────────────────────────────────────────────

@router.message(F.text == _BTN_ADD_TO_LINE)
async def metro_add_to_current_line(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    line_key = data.get("current_line")
    if not line_key:
        await message.answer("⚠️ Сначала выберите линию.")
        return
    emoji, name_ru, _ = LINES.get(line_key, ("", line_key, ""))
    await state.update_data(new_station_line=line_key)
    await state.set_state(AddStation.waiting_name_ru)
    await message.answer(
        f"➕ <b>Новая станция</b> | {emoji} {name_ru}\n\n"
        f"<b>Шаг 2/3.</b> Введите название на <b>русском</b>:",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


# ── AddStation FSM ─────────────────────────────────────────────────────────────

@router.message(AddStation.waiting_name_ru, F.text)
async def metro_got_name_ru(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое. Попробуйте ещё раз:",
                             reply_markup=get_admin_cancel_keyboard())
        return
    await state.update_data(new_station_name_ru=text)
    await state.set_state(AddStation.waiting_name_uz)
    await message.answer(
        f"➕ <b>Новая станция</b>\n\n"
        f"✅ Русское: <b>{text}</b>\n\n"
        f"<b>Шаг 3/3.</b> Введите название на <b>узбекском</b>:\n"
        f"Например: <code>Olmazor</code>",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(AddStation.waiting_name_uz, F.text)
async def metro_got_name_uz(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое. Попробуйте ещё раз:",
                             reply_markup=get_admin_cancel_keyboard())
        return
    data    = await state.get_data()
    name_ru = data["new_station_name_ru"]
    line    = data["new_station_line"]
    station_id = await db.add_metro_station(session, name_ru, text, line)
    logger.info("Добавлена станция id=%d: %s / %s (line=%s)", station_id, name_ru, text, line)
    await state.update_data(current_line=line)
    await state.set_state(None)
    emoji, line_name_ru, _ = LINES.get(line, ("", line, ""))
    stations = await db.get_all_metro_stations_by_line(session, line)
    await message.answer(
        f"✅ Добавлена: <b>{name_ru}</b> / {text}\n{emoji} {line_name_ru}",
        parse_mode="HTML",
        reply_markup=get_admin_metro_stations_kb(stations),
    )


# ── Экран станции ──────────────────────────────────────────────────────────────

@router.message(F.text == _BTN_TO_STATIONS)
async def metro_to_stations(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    line = data.get("current_line")
    if not line:
        await metro_to_lines(message, state, session)
        return
    stations = await db.get_all_metro_stations_by_line(session, line)
    emoji, name_ru, _ = LINES.get(line, ("", line, ""))
    total  = len(stations)
    active = sum(1 for s in stations if s["active"])
    await message.answer(
        f"{emoji} <b>{name_ru}</b>\n{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_metro_stations_kb(stations),
    )


# ── Нажатие на станцию из списка ──────────────────────────────────────────────

@router.message(F.text)
async def metro_item_select(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Перехватывает нажатие на кнопку-станцию из списка."""
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    line = data.get("current_line")
    if not line:
        return
    station = await _get_station_by_label(message.text, line, session)
    if not station:
        return
    await state.update_data(selected_station_id=station["id"])
    emoji_line, line_name, _ = LINES.get(line, ("", line, ""))
    await message.answer(
        f"🚇 <b>{station['name_ru']}</b> / {station['name_uz']}\n"
        f"{emoji_line} {line_name}\n"
        f"Статус: {'✅ Активна' if station['active'] else '❌ Скрыта'}",
        parse_mode="HTML",
        reply_markup=get_admin_station_item_kb(station["active"]),
    )


# ── Действия со станцией ───────────────────────────────────────────────────────

@router.message(F.text.in_({_BTN_TOGGLE_ON, _BTN_TOGGLE_OFF}))
async def metro_toggle(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    station_id = data.get("selected_station_id")
    line       = data.get("current_line")
    if not station_id:
        return
    new_active = await db.toggle_metro_station(session, station_id)
    station    = await db.get_metro_station_by_id(session, station_id)
    if not station:
        return
    emoji_line, line_name, _ = LINES.get(line, ("", line or "", ""))
    await message.answer(
        f"🚇 <b>{station['name_ru']}</b> / {station['name_uz']}\n"
        f"{emoji_line} {line_name}\n"
        f"Статус: {'✅ Активна' if new_active else '❌ Скрыта'}",
        parse_mode="HTML",
        reply_markup=get_admin_station_item_kb(new_active),
    )
    logger.info("Станция id=%d → active=%s", station_id, new_active)


@router.message(F.text == _BTN_DELETE)
async def metro_delete_prompt(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    station_id = data.get("selected_station_id")
    if not station_id:
        return
    station = await db.get_metro_station_by_id(session, station_id)
    if not station:
        return
    await message.answer(
        f"🗑 <b>Удалить станцию?</b>\n\n«{station['name_ru']}»\n\n"
        f"<i>Поданные анкеты не затрагиваются.</i>",
        parse_mode="HTML",
        reply_markup=get_admin_station_confirm_delete_kb(),
    )


@router.message(F.text == _BTN_CONFIRM_DELETE)
async def metro_delete_confirm(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    station_id = data.get("selected_station_id")
    line       = data.get("current_line")
    if not station_id:
        return
    station = await db.get_metro_station_by_id(session, station_id)
    name    = station["name_ru"] if station else f"#{station_id}"
    await db.delete_metro_station(session, station_id)
    logger.info("Станция id=%d «%s» удалена", station_id, name)
    await state.update_data(selected_station_id=None)
    stations = await db.get_all_metro_stations_by_line(session, line)
    await message.answer(
        f"✅ «{name}» удалена.",
        parse_mode="HTML",
        reply_markup=get_admin_metro_stations_kb(stations),
    )
