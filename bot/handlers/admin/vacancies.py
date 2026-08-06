# bot/handlers/admin/vacancies.py
"""Раздел «Вакансии» в административной панели.

Навигация (Inline Keyboard):
  Главное меню → show_vacancies_screen()
  Нажать на вакансию → экран вакансии (edit_text in-place)
    ✅/❌ Включить/Выключить → toggle
    ✏️ Изменить → выбор поля → FSM текстовый ввод
    🗑 Удалить → подтверждение → удаление
    ◀️ К вакансиям → список
  ➕ Добавить → AddVacancy FSM
  🔄 Обновить → обновить список
  ⬅️ Главное меню → /admin
"""

import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.keyboards.inline import (
    get_admin_menu_inline_kb,
    get_admin_vacancies_inline_kb,
    get_admin_vacancy_confirm_delete_inline_kb,
    get_admin_vacancy_edit_inline_kb,
    get_admin_vacancy_item_inline_kb,
)
from bot.keyboards.reply import (
    ADMIN_BTN_CANCEL,
    get_admin_cancel_keyboard,
    remove_keyboard,
)
from bot.states import AddVacancy, EditVacancy

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _vac_text(vacancies: list[dict]) -> str:
    active = sum(1 for v in vacancies if v["is_active"])
    return (
        f"💼 <b>Вакансии</b>\n{'─'*28}\n"
        f"Всего: <b>{len(vacancies)}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ активна  ❌ отключена\n"
        f"Нажмите на вакансию для управления."
    )


def _vacancy_detail_text(vacancy: dict) -> str:
    label = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip()
    return (
        f"💼 <b>{label}</b>\n{'─'*28}\n"
        f"🇺🇿 {vacancy['name_uz']}\n"
        f"Статус: {'✅ Активна' if vacancy['is_active'] else '❌ Отключена'}"
    )


# ── Публичная точка входа ─────────────────────────────────────────────────────

async def show_vacancies_screen(
    message: Message, session: AsyncSession, edit: bool = False
) -> None:
    vacancies = await db.get_all_vacancies(session)
    text = _vac_text(vacancies)
    kb   = get_admin_vacancies_inline_kb(vacancies)
    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ── /vacancies ────────────────────────────────────────────────────────────────

@router.message(Command("vacancies"))
async def cmd_vacancies(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await show_vacancies_screen(message, session)


# ── Callback: vac:list ────────────────────────────────────────────────────────

@router.callback_query(F.data == "vac:list")
async def cb_vac_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            _vac_text(vacancies), parse_mode="HTML",
            reply_markup=get_admin_vacancies_inline_kb(vacancies),
        )
    await callback.answer()


@router.callback_query(F.data == "vac:refresh")
async def cb_vac_refresh(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            _vac_text(vacancies), parse_mode="HTML",
            reply_markup=get_admin_vacancies_inline_kb(vacancies),
        )
    await callback.answer("Обновлено ✅")


@router.callback_query(F.data == "vac:home")
async def cb_vac_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
            parse_mode="HTML",
            reply_markup=get_admin_menu_inline_kb(),
        )
    await callback.answer()


# ── Callback: vac:select:{id} ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:select:"))
async def cb_vac_select(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        await callback.answer("Вакансия не найдена", show_alert=True)
        return
    await state.update_data(selected_vacancy_id=vacancy_id)
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            _vacancy_detail_text(vacancy), parse_mode="HTML",
            reply_markup=get_admin_vacancy_item_inline_kb(vacancy_id, vacancy["is_active"]),
        )
    await callback.answer()


# ── Callback: vac:toggle:{id} ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:toggle:"))
async def cb_vac_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    is_active  = await db.toggle_vacancy(session, vacancy_id)
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        await callback.answer("Вакансия не найдена", show_alert=True)
        return
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            _vacancy_detail_text(vacancy), parse_mode="HTML",
            reply_markup=get_admin_vacancy_item_inline_kb(vacancy_id, is_active),
        )
    await callback.answer("✅ Включена" if is_active else "❌ Выключена")
    logger.info("Вакансия id=%d → is_active=%s", vacancy_id, is_active)


# ── Callback: vac:edit:{id} ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:edit:"))
async def cb_vac_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        await callback.answer("Вакансия не найдена", show_alert=True)
        return
    label = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip()
    await state.update_data(selected_vacancy_id=vacancy_id)
    await state.set_state(EditVacancy.choosing_field)
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"✏️ <b>Редактировать: {label}</b>\n\nЧто изменить?",
            parse_mode="HTML",
            reply_markup=get_admin_vacancy_edit_inline_kb(vacancy_id),
        )
    await callback.answer()


# ── Callback: vac:editfield:{id}:{field} ─────────────────────────────────────

@router.callback_query(F.data.startswith("vac:editfield:"))
async def cb_vac_editfield(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    vacancy_id = int(parts[2])
    field      = parts[3]
    field_labels = {
        "name_ru": "название на <b>русском</b>",
        "name_uz": "название на <b>узбекском</b>",
        "emoji":   "<b>эмодзи</b>",
    }
    label = field_labels.get(field, field)
    hint  = "\nОтправьте <code>-</code> чтобы убрать эмодзи." if field == "emoji" else ""
    await state.update_data(selected_vacancy_id=vacancy_id, edit_field=field)
    await state.set_state(EditVacancy.waiting_value)
    await callback.message.answer(
        f"✏️ Введите новое {label}:{hint}",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )
    await callback.answer()


# ── Callback: vac:delete:{id} ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:delete:"))
async def cb_vac_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        await callback.answer("Вакансия не найдена", show_alert=True)
        return
    label = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip()
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"🗑 <b>Удалить вакансию?</b>\n\n«{label}»\n\n"
            f"<i>Это необратимо. Анкеты не затрагиваются.</i>",
            parse_mode="HTML",
            reply_markup=get_admin_vacancy_confirm_delete_inline_kb(vacancy_id),
        )
    await callback.answer()


# ── Callback: vac:confirm_delete:{id} ────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:confirm_delete:"))
async def cb_vac_confirm_delete(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    name       = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"
    await db.delete_vacancy(session, vacancy_id)
    logger.info("Вакансия id=%d «%s» удалена", vacancy_id, name)
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"✅ «{name}» удалена.\n\n" + _vac_text(vacancies),
            parse_mode="HTML",
            reply_markup=get_admin_vacancies_inline_kb(vacancies),
        )
    await callback.answer("Удалено")


# ── Callback: vac:add ────────────────────────────────────────────────────────

@router.callback_query(F.data == "vac:add")
async def cb_vac_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AddVacancy.waiting_name_ru)
    await callback.message.answer(
        "➕ <b>Новая вакансия</b>\n\n<b>Шаг 1/3.</b> Введите название на <b>русском</b>:",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )
    await callback.answer()


# ── AddVacancy FSM ────────────────────────────────────────────────────────────

@router.message(AddVacancy.waiting_name_ru, F.text)
async def vac_add_name_ru(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        await _send_vac_list(message, session)
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое. Попробуйте ещё раз:", reply_markup=get_admin_cancel_keyboard())
        return
    await state.update_data(name_ru=text)
    await state.set_state(AddVacancy.waiting_name_uz)
    await message.answer(
        "➕ <b>Новая вакансия</b>\n\n<b>Шаг 2/3.</b> Введите название на <b>узбекском</b>:",
        parse_mode="HTML", reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(AddVacancy.waiting_name_uz, F.text)
async def vac_add_name_uz(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        await _send_vac_list(message, session)
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое. Попробуйте ещё раз:", reply_markup=get_admin_cancel_keyboard())
        return
    await state.update_data(name_uz=text)
    await state.set_state(AddVacancy.waiting_emoji)
    await message.answer(
        "➕ <b>Новая вакансия</b>\n\n<b>Шаг 3/3.</b> Отправьте эмодзи.\nИли /skip для пропуска.",
        parse_mode="HTML", reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(AddVacancy.waiting_emoji, F.text == "/skip")
async def vac_add_skip_emoji(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _save_vacancy(message, state, session, emoji="")


@router.message(AddVacancy.waiting_emoji, F.text)
async def vac_add_emoji(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        await _send_vac_list(message, session)
        return
    await _save_vacancy(message, state, session, emoji=(message.text or "").strip())


async def _save_vacancy(message: Message, state: FSMContext, session: AsyncSession, emoji: str) -> None:
    data = await state.get_data()
    vid  = await db.add_vacancy(session, data["name_ru"], data["name_uz"], emoji)
    logger.info("Добавлена вакансия id=%d: %s / %s", vid, data["name_ru"], data["name_uz"])
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    label = f"{emoji} {data['name_ru']}".strip()
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        f"✅ <b>Вакансия добавлена!</b>\n\n💼 {label}\n\n" + _vac_text(vacancies),
        parse_mode="HTML",
        reply_markup=get_admin_vacancies_inline_kb(vacancies),
    )


# ── EditVacancy FSM ───────────────────────────────────────────────────────────

@router.message(EditVacancy.waiting_value, F.text)
async def vac_save_field(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        await _send_vac_list(message, session)
        return
    data       = await state.get_data()
    vacancy_id = data.get("selected_vacancy_id")
    field      = data.get("edit_field")
    value      = (message.text or "").strip()
    if field in ("name_ru", "name_uz") and len(value) < 2:
        await message.answer("❌ Слишком короткое название. Попробуйте ещё раз:",
                             reply_markup=get_admin_cancel_keyboard())
        return
    if field == "emoji" and value == "-":
        value = ""
    await db.update_vacancy(session, vacancy_id, **{field: value})
    logger.info("Вакансия id=%d поле=%s обновлено: %r", vacancy_id, field, value)
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        "✅ Обновлено!\n\n" + _vac_text(vacancies),
        parse_mode="HTML",
        reply_markup=get_admin_vacancies_inline_kb(vacancies),
    )


async def _send_vac_list(message: Message, session: AsyncSession) -> None:
    vacancies = await db.get_all_vacancies(session)
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        _vac_text(vacancies), parse_mode="HTML",
        reply_markup=get_admin_vacancies_inline_kb(vacancies),
    )
