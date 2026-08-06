# bot/handlers/admin/metro_stations.py
"""FSM для управления списком станций метро."""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db

router = Router()
logger = logging.getLogger(__name__)

# ── Линии метро ───────────────────────────────────────────────────────────────

LINES: dict[str, tuple[str, str, str]] = {
    "red":    ("🔴", "Чиланзарская",               "Chilonzor liniyasi"),
    "green":  ("🟢", "Юнусабадская",               "Yunusobod liniyasi"),
    "blue":   ("🔵", "Узбекистанская",              "O'zbekiston liniyasi"),
    "orange": ("🟠", "30-летия независимости",      "Mustaqillik 30-yilligi liniyasi"),
}


# ── FSM ───────────────────────────────────────────────────────────────────────

class AddStation(StatesGroup):
    waiting_line    = State()
    waiting_name_ru = State()
    waiting_name_uz = State()


# ── Клавиатуры ────────────────────────────────────────────────────────────────

def _lines_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, (emoji, name_ru, _) in LINES.items():
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {name_ru}",
            callback_data=f"ms:line:{key}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Добавить станцию", callback_data="ms:add")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить",         callback_data="ms:refresh")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад",            callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _stations_keyboard(stations: list[dict], line: str) -> InlineKeyboardMarkup:
    rows = []
    for s in stations:
        status = "✅" if s["active"] else "❌"
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {s['name_ru']}",
                callback_data=f"ms:toggle:{s['id']}:{line}",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"ms:delete:{s['id']}:{line}"),
        ])
    rows.append([InlineKeyboardButton(text="◀️ К линиям", callback_data="ms:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_delete_keyboard(station_id: int, line: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить",  callback_data=f"ms:delete_confirm:{station_id}:{line}"),
        InlineKeyboardButton(text="❌ Отмена",        callback_data=f"ms:line:{line}"),
    ]])


def _line_select_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, (emoji, name_ru, _) in LINES.items():
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {name_ru}",
            callback_data=f"ms:add_line:{key}",
        )])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="ms:add_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="ms:add_cancel")
    ]])


# ── Хелперы ───────────────────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _metro_menu_text(total: int, active: int) -> str:
    return (
        f"🚇 <b>Управление станциями метро</b>\n{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>\n\n"
        f"Выберите линию для просмотра и редактирования:"
    )


async def _refresh_line_view(
    message: Message,
    session: AsyncSession,
    line: str,
    edit: bool = True,
) -> None:
    stations = await db.get_all_metro_stations_by_line(session, line)
    emoji, name_ru, name_uz = LINES.get(line, ("", line, line))
    total   = len(stations)
    active  = sum(1 for s in stations if s["active"])
    text = (
        f"{emoji} <b>{name_ru}</b> / {name_uz}\n"
        f"{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ — активна  ❌ — скрыта  🗑 — удалить"
    )
    if edit:
        try:
            await message.edit_text(text, parse_mode="HTML",
                                    reply_markup=_stations_keyboard(stations, line))
        except TelegramBadRequest:
            await message.answer(text, parse_mode="HTML",
                                 reply_markup=_stations_keyboard(stations, line))
    else:
        await message.answer(text, parse_mode="HTML",
                             reply_markup=_stations_keyboard(stations, line))


# ── Точка входа ───────────────────────────────────────────────────────────────

async def show_metro_menu(message: Message, session: AsyncSession, edit: bool = False) -> None:
    """Вызывается из /admin-меню и команды /metro_stations.

    edit=True → редактирует текущее сообщение (для inline-навигации из /admin).
    edit=False → отправляет новое сообщение (для команды /metro_stations).
    """
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    text   = _metro_menu_text(total, active)
    kb     = _lines_keyboard()
    if edit:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except TelegramAPIError:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("metro_stations"))
async def cmd_metro_stations(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await show_metro_menu(message, session, edit=False)


# ── Просмотр станций линии ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ms:line:"))
async def ms_show_line(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    line = callback.data.split(":")[2]
    await callback.answer()
    await _refresh_line_view(callback.message, session, line, edit=True)


@router.callback_query(F.data == "ms:back")
async def ms_back(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await show_metro_menu(callback.message, session, edit=True)
    await callback.answer()


@router.callback_query(F.data == "ms:refresh")
async def ms_refresh(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await show_metro_menu(callback.message, session, edit=True)
    await callback.answer("✅ Обновлено")


# ── Toggle (вкл/выкл) ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ms:toggle:"))
async def ms_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    _, _, station_id_str, line = callback.data.split(":")
    station_id = int(station_id_str)
    new_active = await db.toggle_metro_station(session, station_id)
    status_text = "включена ✅" if new_active else "отключена ❌"
    await callback.answer(f"Станция {status_text}")
    await _refresh_line_view(callback.message, session, line, edit=True)


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ms:delete:"))
async def ms_delete_prompt(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    station_id = int(parts[2])
    line       = parts[3]
    station    = await db.get_metro_station_by_id(session, station_id)
    if not station:
        await callback.answer("Станция не найдена.", show_alert=True)
        return
    name = station["name_ru"]
    try:
        await callback.message.edit_text(
            f"🗑 <b>Удалить станцию?</b>\n\n«{name}»\n\n"
            f"<i>Это необратимо. Поданные анкеты не затрагиваются.</i>",
            parse_mode="HTML",
            reply_markup=_confirm_delete_keyboard(station_id, line),
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("ms:delete_confirm:"))
async def ms_delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    station_id = int(parts[2])
    line       = parts[3]
    station    = await db.get_metro_station_by_id(session, station_id)
    name       = station["name_ru"] if station else f"#{station_id}"
    await db.delete_metro_station(session, station_id)
    logger.info("Станция id=%d «%s» удалена", station_id, name)
    await callback.answer(f"Станция «{name}» удалена.", show_alert=True)
    await _refresh_line_view(callback.message, session, line, edit=True)


# ── Добавить станцию (FSM) ────────────────────────────────────────────────────

@router.callback_query(F.data == "ms:add")
async def ms_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AddStation.waiting_line)
    try:
        await callback.message.edit_text(
            "➕ <b>Новая станция</b>\n\n<b>Шаг 1/3.</b> Выберите линию:",
            parse_mode="HTML",
            reply_markup=_line_select_keyboard(),
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "➕ <b>Новая станция</b>\n\n<b>Шаг 1/3.</b> Выберите линию:",
            parse_mode="HTML",
            reply_markup=_line_select_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("ms:add_line:"), AddStation.waiting_line)
async def ms_add_got_line(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    line = callback.data.split(":")[2]
    await state.update_data(new_station_line=line)
    await state.set_state(AddStation.waiting_name_ru)
    emoji, name_ru, _ = LINES.get(line, ("", line, ""))
    chat_id = callback.message.chat.id
    try:
        await callback.message.edit_text(
            f"➕ <b>Новая станция</b> | {emoji} {name_ru}\n\n"
            f"<b>Шаг 2/3.</b> Введите название на <b>русском</b>:\n"
            f"Например: <code>Алмазар</code>",
            parse_mode="HTML",
            reply_markup=_cancel_keyboard(),
        )
        await state.update_data(wizard_msg_id=callback.message.message_id, wizard_chat_id=chat_id)
    except TelegramBadRequest:
        sent = await callback.message.answer(
            f"➕ <b>Новая станция</b> | {emoji} {name_ru}\n\n"
            f"<b>Шаг 2/3.</b> Введите название на <b>русском</b>:\n"
            f"Например: <code>Алмазар</code>",
            parse_mode="HTML",
            reply_markup=_cancel_keyboard(),
        )
        await state.update_data(wizard_msg_id=sent.message_id, wizard_chat_id=chat_id)
    await callback.answer()


@router.message(AddStation.waiting_name_ru)
async def ms_got_name_ru(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое название. Введите ещё раз:",
                             reply_markup=_cancel_keyboard())
        return
    await state.update_data(new_station_name_ru=text)
    await state.set_state(AddStation.waiting_name_uz)

    data    = await state.get_data()
    wid     = data.get("wizard_msg_id")
    chat_id = data.get("wizard_chat_id", message.chat.id)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    if wid:
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=wid,
                text=f"➕ <b>Новая станция</b>\n\n"
                     f"✅ Русское: <b>{text}</b>\n\n"
                     f"<b>Шаг 3/3.</b> Введите название на <b>узбекском</b>:\n"
                     f"Например: <code>Olmazor</code>",
                parse_mode="HTML",
                reply_markup=_cancel_keyboard(),
            )
        except TelegramBadRequest:
            pass


@router.message(AddStation.waiting_name_uz)
async def ms_got_name_uz(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое название. Введите ещё раз:",
                             reply_markup=_cancel_keyboard())
        return

    data    = await state.get_data()
    name_ru = data["new_station_name_ru"]
    line    = data["new_station_line"]
    wid     = data.get("wizard_msg_id")
    chat_id = data.get("wizard_chat_id", message.chat.id)

    station_id = await db.add_metro_station(session, name_ru, text, line)
    logger.info("Добавлена станция id=%d: %s / %s (line=%s)", station_id, name_ru, text, line)
    await state.clear()

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    emoji, line_name_ru, _ = LINES.get(line, ("", line, ""))
    result_text = (
        f"✅ <b>Станция добавлена!</b>\n\n"
        f"🚇 {name_ru} / {text}\n"
        f"{emoji} Линия: {line_name_ru}"
    )

    # Редактируем визард в результат с кнопкой возврата
    if wid:
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=wid,
                text=result_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ К станциям метро", callback_data="ms:refresh"),
                ]]),
            )
            return
        except TelegramBadRequest:
            pass

    # Fallback
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    await message.bot.send_message(
        chat_id=chat_id,
        text=_metro_menu_text(total, active),
        parse_mode="HTML",
        reply_markup=_lines_keyboard(),
    )


@router.callback_query(F.data == "ms:add_cancel")
async def ms_add_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.answer("Добавление отменено")
    await show_metro_menu(callback.message, session, edit=True)
