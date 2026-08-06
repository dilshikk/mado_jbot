# bot/handlers/admin/metro_stations.py
"""Раздел «Метро» в административной панели.

Полностью на Inline Keyboard (CallbackQuery).
Callback data схема:
  metro:home               — главный экран (список линий)
  metro:refresh            — обновить счётчики
  metro:back               — назад в /admin меню
  metro:line:{line_id}     — список станций линии
  metro:station:{id}:{line_id} — экран станции
  metro:toggle:{id}:{line_id} — вкл/выкл станцию
  metro:delete:{id}:{line_id} — запрос удаления
  metro:confirm_delete:{id}:{line_id} — подтвердить удаление
  metro:add:{line_id}      — FSM добавления (линия известна)
  metro:add_home           — FSM добавления (выбор линии)
  metro:add_line:{line_id} — FSM: выбрали линию
  metro:cancel             — отмена FSM
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.keyboards.inline import (
    get_admin_menu_inline_kb,
    get_admin_metro_add_line_inline_kb,
    get_admin_metro_fsm_cancel_inline_kb,
    get_admin_metro_home_inline_kb,
    get_admin_metro_station_confirm_delete_inline_kb,
    get_admin_metro_station_item_inline_kb,
    get_admin_metro_stations_inline_kb,
)

router = Router()
logger = logging.getLogger(__name__)

LINES: dict[str, tuple[str, str, str]] = {
    "red":    ("🔴", "Чиланзарская",              "Chilonzor liniyasi"),
    "green":  ("🟢", "Юнусабадская",              "Yunusobod liniyasi"),
    "blue":   ("🔵", "Узбекистанская",             "O'zbekiston liniyasi"),
    "orange": ("🟠", "30 лет независимости",       "Mustaqillik 30-yilligi liniyasi"),
}


class AddStation(StatesGroup):
    waiting_line    = State()
    waiting_name_ru = State()
    waiting_name_uz = State()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _metro_home_text(total: int, active: int) -> str:
    return (
        f"🚇 <b>Станции метро</b>\n{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>\n\n"
        f"Выберите линию для просмотра и редактирования."
    )


# ── Публичная точка входа ─────────────────────────────────────────────────────

async def show_metro_home(message: Message, session: AsyncSession, edit: bool = False) -> None:
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    text   = _metro_home_text(total, active)
    kb     = get_admin_metro_home_inline_kb()
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ── /metro_stations (прямая команда) ─────────────────────────────────────────

@router.message(Command("metro_stations"))
async def cmd_metro_stations(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await show_metro_home(message, session)


# ── Callback: metro:home ─────────────────────────────────────────────────────

@router.callback_query(F.data == "metro:home")
async def cb_metro_home(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    await callback.message.edit_text(
        _metro_home_text(total, active), parse_mode="HTML",
        reply_markup=get_admin_metro_home_inline_kb(),
    )
    await callback.answer()


# ── Callback: metro:refresh ───────────────────────────────────────────────────

@router.callback_query(F.data == "metro:refresh")
async def cb_metro_refresh(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    await callback.message.edit_text(
        _metro_home_text(total, active), parse_mode="HTML",
        reply_markup=get_admin_metro_home_inline_kb(),
    )
    await callback.answer("Обновлено ✅")


# ── Callback: metro:back → Admin menu ────────────────────────────────────────

@router.callback_query(F.data == "metro:back")
async def cb_metro_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.message.edit_text(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )
    await callback.answer()


# ── Callback: metro:cancel (из FSM) ──────────────────────────────────────────

@router.callback_query(F.data == "metro:cancel")
async def cb_metro_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    total  = await db.count_metro_stations(session)
    active = await db.count_metro_stations(session, active_only=True)
    await callback.message.edit_text(
        _metro_home_text(total, active), parse_mode="HTML",
        reply_markup=get_admin_metro_home_inline_kb(),
    )
    await callback.answer()


# ── Callback: metro:line:{line_id} ────────────────────────────────────────────

@router.callback_query(F.data.startswith("metro:line:"))
async def cb_metro_line(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    line_id = callback.data.split(":")[2]
    await state.update_data(current_line=line_id)
    emoji, name_ru, name_uz = LINES.get(line_id, ("", line_id, ""))
    stations = await db.get_all_metro_stations_by_line(session, line_id)
    total  = len(stations)
    active = sum(1 for s in stations if s["active"])
    await callback.message.edit_text(
        f"{emoji} <b>{name_ru}</b> / {name_uz}\n{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>\n\n"
        f"Нажмите на станцию для управления.",
        parse_mode="HTML",
        reply_markup=get_admin_metro_stations_inline_kb(stations, line_id),
    )
    await callback.answer()


# ── Callback: metro:station:{id}:{line_id} ────────────────────────────────────

@router.callback_query(F.data.startswith("metro:station:"))
async def cb_metro_station(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    station_id = int(parts[2])
    line_id    = parts[3]
    await state.update_data(current_line=line_id, selected_station_id=station_id)
    station = await db.get_metro_station_by_id(session, station_id)
    if not station:
        await callback.answer("Станция не найдена", show_alert=True)
        return
    emoji_line, line_name, _ = LINES.get(line_id, ("", line_id, ""))
    await callback.message.edit_text(
        f"🚇 <b>{station['name_ru']}</b> / {station['name_uz']}\n"
        f"{emoji_line} {line_name}\n"
        f"Статус: {'✅ Активна' if station['active'] else '❌ Скрыта'}",
        parse_mode="HTML",
        reply_markup=get_admin_metro_station_item_inline_kb(station_id, station["active"], line_id),
    )
    await callback.answer()


# ── Callback: metro:toggle:{id}:{line_id} ────────────────────────────────────

@router.callback_query(F.data.startswith("metro:toggle:"))
async def cb_metro_toggle(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    station_id = int(parts[2])
    line_id    = parts[3]
    new_active = await db.toggle_metro_station(session, station_id)
    station    = await db.get_metro_station_by_id(session, station_id)
    if not station:
        await callback.answer("Станция не найдена", show_alert=True)
        return
    emoji_line, line_name, _ = LINES.get(line_id, ("", line_id, ""))
    await callback.message.edit_text(
        f"🚇 <b>{station['name_ru']}</b> / {station['name_uz']}\n"
        f"{emoji_line} {line_name}\n"
        f"Статус: {'✅ Активна' if new_active else '❌ Скрыта'}",
        parse_mode="HTML",
        reply_markup=get_admin_metro_station_item_inline_kb(station_id, new_active, line_id),
    )
    await callback.answer("✅ Включена" if new_active else "❌ Выключена")
    logger.info("Станция id=%d → active=%s", station_id, new_active)


# ── Callback: metro:delete:{id}:{line_id} ────────────────────────────────────

@router.callback_query(F.data.startswith("metro:delete:"))
async def cb_metro_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    station_id = int(parts[2])
    line_id    = parts[3]
    station    = await db.get_metro_station_by_id(session, station_id)
    if not station:
        await callback.answer("Станция не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"🗑 <b>Удалить станцию?</b>\n\n«{station['name_ru']}»\n\n"
        f"<i>Поданные анкеты не затрагиваются.</i>",
        parse_mode="HTML",
        reply_markup=get_admin_metro_station_confirm_delete_inline_kb(station_id, line_id),
    )
    await callback.answer()


# ── Callback: metro:confirm_delete:{id}:{line_id} ────────────────────────────

@router.callback_query(F.data.startswith("metro:confirm_delete:"))
async def cb_metro_confirm_delete(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    station_id = int(parts[2])
    line_id    = parts[3]
    station    = await db.get_metro_station_by_id(session, station_id)
    name       = station["name_ru"] if station else f"#{station_id}"
    await db.delete_metro_station(session, station_id)
    logger.info("Станция id=%d «%s» удалена", station_id, name)
    await state.update_data(selected_station_id=None)
    stations = await db.get_all_metro_stations_by_line(session, line_id)
    emoji_line, line_name, _ = LINES.get(line_id, ("", line_id, ""))
    total  = len(stations)
    active = sum(1 for s in stations if s["active"])
    await callback.message.edit_text(
        f"✅ «{name}» удалена.\n\n"
        f"{emoji_line} <b>{line_name}</b>\n{'─'*28}\n"
        f"Всего: <b>{total}</b>  |  Активных: <b>{active}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_metro_stations_inline_kb(stations, line_id),
    )
    await callback.answer("Удалено")


# ── Callback: metro:add_home → выбор линии ───────────────────────────────────

@router.callback_query(F.data == "metro:add_home")
async def cb_metro_add_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AddStation.waiting_line)
    await callback.message.edit_text(
        "➕ <b>Новая станция</b>\n\n<b>Шаг 1/3.</b> Выберите линию:",
        parse_mode="HTML",
        reply_markup=get_admin_metro_add_line_inline_kb(),
    )
    await callback.answer()


# ── Callback: metro:add:{line_id} → FSM (линия известна) ─────────────────────

@router.callback_query(F.data.startswith("metro:add:"))
async def cb_metro_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    line_id = callback.data.split(":")[2]
    emoji, name_ru, _ = LINES.get(line_id, ("", line_id, ""))
    await state.update_data(new_station_line=line_id, current_line=line_id)
    await state.set_state(AddStation.waiting_name_ru)
    await callback.message.edit_text(
        f"➕ <b>Новая станция</b> | {emoji} {name_ru}\n\n"
        f"<b>Шаг 2/3.</b> Введите название на <b>русском</b>:\n"
        f"Например: <code>Алмазар</code>",
        parse_mode="HTML",
        reply_markup=get_admin_metro_fsm_cancel_inline_kb(),
    )
    await callback.answer()


# ── Callback: metro:add_line:{line_id} ───────────────────────────────────────

@router.callback_query(AddStation.waiting_line, F.data.startswith("metro:add_line:"))
async def cb_metro_add_line(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    line_id = callback.data.split(":")[2]
    emoji, name_ru, _ = LINES.get(line_id, ("", line_id, ""))
    await state.update_data(new_station_line=line_id, current_line=line_id)
    await state.set_state(AddStation.waiting_name_ru)
    await callback.message.edit_text(
        f"➕ <b>Новая станция</b> | {emoji} {name_ru}\n\n"
        f"<b>Шаг 2/3.</b> Введите название на <b>русском</b>:\n"
        f"Например: <code>Алмазар</code>",
        parse_mode="HTML",
        reply_markup=get_admin_metro_fsm_cancel_inline_kb(),
    )
    await callback.answer()


# ── FSM: ввод названия (русский) ─────────────────────────────────────────────

@router.message(AddStation.waiting_name_ru, F.text)
async def metro_got_name_ru(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer(
            "❌ Слишком короткое. Попробуйте ещё раз:",
            reply_markup=get_admin_metro_fsm_cancel_inline_kb(),
        )
        return
    await state.update_data(new_station_name_ru=text)
    await state.set_state(AddStation.waiting_name_uz)
    await message.answer(
        f"➕ <b>Новая станция</b>\n\n✅ Русское: <b>{text}</b>\n\n"
        f"<b>Шаг 3/3.</b> Введите название на <b>узбекском</b>:\n"
        f"Например: <code>Olmazor</code>",
        parse_mode="HTML",
        reply_markup=get_admin_metro_fsm_cancel_inline_kb(),
    )


# ── FSM: ввод названия (узбекский) ───────────────────────────────────────────

@router.message(AddStation.waiting_name_uz, F.text)
async def metro_got_name_uz(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer(
            "❌ Слишком короткое. Попробуйте ещё раз:",
            reply_markup=get_admin_metro_fsm_cancel_inline_kb(),
        )
        return
    data    = await state.get_data()
    name_ru = data["new_station_name_ru"]
    line_id = data["new_station_line"]
    station_id = await db.add_metro_station(session, name_ru, text, line_id)
    logger.info("Добавлена станция id=%d: %s / %s (line=%s)", station_id, name_ru, text, line_id)
    await state.update_data(current_line=line_id)
    await state.set_state(None)
    emoji, line_name_ru, _ = LINES.get(line_id, ("", line_id, ""))
    stations = await db.get_all_metro_stations_by_line(session, line_id)
    await message.answer(
        f"✅ Добавлена: <b>{name_ru}</b> / {text}\n{emoji} {line_name_ru}",
        parse_mode="HTML",
        reply_markup=get_admin_metro_stations_inline_kb(stations, line_id),
    )
