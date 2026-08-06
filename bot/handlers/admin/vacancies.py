# bot/handlers/admin/vacancies.py

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.states import AddVacancy, EditVacancy

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Клавиатуры ────────────────────────────────────────────────────────────────

def _vacancies_keyboard(vacancies: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for v in vacancies:
        status = "✅" if v["is_active"] else "❌"
        label  = f"{v['emoji']} {v['name_ru']}".strip()
        rows.append([
            InlineKeyboardButton(text=f"{status} {label}",  callback_data=f"vac:toggle:{v['id']}"),
            InlineKeyboardButton(text="✏️",                  callback_data=f"vac:edit:{v['id']}"),
            InlineKeyboardButton(text="🗑",                  callback_data=f"vac:delete:{v['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить вакансию", callback_data="vac:add")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить",          callback_data="vac:refresh")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад",             callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_delete_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"vac:delete_confirm:{vacancy_id}"),
        InlineKeyboardButton(text="❌ Отмена",       callback_data="vac:refresh"),
    ]])


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="vac:add_cancel"),
    ]])


def _edit_field_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Название (рус)",  callback_data=f"vac:edit_field:{vacancy_id}:name_ru")],
        [InlineKeyboardButton(text="🇺🇿 Название (узб)",  callback_data=f"vac:edit_field:{vacancy_id}:name_uz")],
        [InlineKeyboardButton(text="😊 Эмодзи",           callback_data=f"vac:edit_field:{vacancy_id}:emoji")],
        [InlineKeyboardButton(text="❌ Отмена",            callback_data="vac:refresh")],
    ])


def _edit_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="vac:edit_cancel"),
    ]])


# ── Тексты ────────────────────────────────────────────────────────────────────

def _vacancy_list_text(vacancies: list[dict]) -> str:
    active = sum(1 for v in vacancies if v["is_active"])
    return (
        f"💼 <b>Управление вакансиями</b>\n{'─'*28}\n"
        f"Всего: <b>{len(vacancies)}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ — активна (видна кандидатам)\n"
        f"❌ — отключена (скрыта)\n"
        f"✏️ — редактировать\n"
        f"🗑 — удалить вакансию"
    )


# ── /vacancies ────────────────────────────────────────────────────────────────

@router.message(Command("vacancies"))
async def cmd_vacancies(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    vacancies = await db.get_all_vacancies(session)
    await message.answer(
        _vacancy_list_text(vacancies),
        parse_mode="HTML",
        reply_markup=_vacancies_keyboard(vacancies),
    )


# ── Обновить список ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "vac:refresh")
async def vac_refresh(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    try:
        await callback.message.edit_text(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )
    except TelegramBadRequest:
        await callback.message.answer(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )
    await callback.answer("✅ Обновлено")


# ── Вкл / выкл ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:toggle:"))
async def vac_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id  = int(callback.data.split(":")[2])
    is_active   = await db.toggle_vacancy(session, vacancy_id)
    vacancy     = await db.get_vacancy_by_id(session, vacancy_id)
    name        = f"{vacancy['emoji']} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"
    status_text = "включена ✅" if is_active else "отключена ❌"
    await callback.answer(f"Вакансия «{name}» {status_text}")
    logger.info("Вакансия id=%d %s", vacancy_id, status_text)
    vacancies = await db.get_all_vacancies(session)
    try:
        await callback.message.edit_text(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )
    except TelegramBadRequest:
        pass


# ── Удаление ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:delete:"))
async def vac_delete_prompt(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        await callback.answer("Вакансия не найдена.", show_alert=True)
        return
    name = f"{vacancy['emoji']} {vacancy['name_ru']}".strip()
    await callback.message.edit_text(
        f"🗑 <b>Удалить вакансию?</b>\n\n«{name}»\n\n"
        f"<i>Это необратимо. Уже поданные анкеты не затрагиваются.</i>",
        parse_mode="HTML",
        reply_markup=_confirm_delete_keyboard(vacancy_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vac:delete_confirm:"))
async def vac_delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    name       = f"{vacancy['emoji']} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"
    await db.delete_vacancy(session, vacancy_id)
    logger.info("Вакансия id=%d «%s» удалена", vacancy_id, name)
    await callback.answer(f"Вакансия «{name}» удалена.", show_alert=True)
    vacancies = await db.get_all_vacancies(session)
    try:
        await callback.message.edit_text(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )
    except TelegramBadRequest:
        pass


# ── Добавить вакансию ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "vac:add")
async def vac_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AddVacancy.waiting_name_ru)
    try:
        await callback.message.edit_text(
            "➕ <b>Новая вакансия</b>\n\n<b>Шаг 1/3.</b> Введите название на <b>русском</b>:\n"
            "Например: <code>Хостес</code>",
            parse_mode="HTML",
            reply_markup=_cancel_keyboard(),
        )
        await state.update_data(wizard_message_id=callback.message.message_id)
    except TelegramAPIError:
        sent = await callback.message.answer(
            "➕ <b>Новая вакансия</b>\n\n<b>Шаг 1/3.</b> Введите название на <b>русском</b>:\n"
            "Например: <code>Хостес</code>",
            parse_mode="HTML",
            reply_markup=_cancel_keyboard(),
        )
        await state.update_data(wizard_message_id=sent.message_id)
    await callback.answer()


@router.callback_query(F.data == "vac:add_cancel")
async def vac_add_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.answer("Добавление отменено")
    vacancies = await db.get_all_vacancies(session)
    try:
        await callback.message.edit_text(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )
    except TelegramBadRequest:
        await callback.message.answer(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )


@router.message(AddVacancy.waiting_name_ru)
async def vac_got_name_ru(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое название. Введите ещё раз:", reply_markup=_cancel_keyboard())
        return
    await state.update_data(name_ru=text)
    await state.set_state(AddVacancy.waiting_name_uz)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    if wizard_id := data.get("wizard_message_id"):
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=wizard_id,
                text="➕ <b>Новая вакансия</b>\n\n<b>Шаг 2/3.</b> Введите название на <b>узбекском</b>:\n"
                     "Например: <code>Xostes</code>",
                parse_mode="HTML",
                reply_markup=_cancel_keyboard(),
            )
        except TelegramBadRequest:
            pass


@router.message(AddVacancy.waiting_name_uz)
async def vac_got_name_uz(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое название. Введите ещё раз:", reply_markup=_cancel_keyboard())
        return
    await state.update_data(name_uz=text)
    await state.set_state(AddVacancy.waiting_emoji)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    data = await state.get_data()
    if wizard_id := data.get("wizard_message_id"):
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=wizard_id,
                text="➕ <b>Новая вакансия</b>\n\n<b>Шаг 3/3.</b> Отправьте <b>эмодзи</b>.\n"
                     "Или /skip чтобы пропустить.",
                parse_mode="HTML",
                reply_markup=_cancel_keyboard(),
            )
        except TelegramBadRequest:
            pass


@router.message(AddVacancy.waiting_emoji, F.text == "/skip")
async def vac_skip_emoji(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _save_new_vacancy(message, state, session, emoji="")


@router.message(AddVacancy.waiting_emoji)
async def vac_got_emoji(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _save_new_vacancy(message, state, session, emoji=(message.text or "").strip())


async def _save_new_vacancy(message: Message, state: FSMContext, session: AsyncSession, emoji: str) -> None:
    data      = await state.get_data()
    name_ru   = data["name_ru"]
    name_uz   = data["name_uz"]
    wizard_id = data.get("wizard_message_id")
    vacancy_id = await db.add_vacancy(session, name_ru, name_uz, emoji)
    logger.info("Добавлена вакансия id=%d: %s / %s", vacancy_id, name_ru, name_uz)
    await state.clear()
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    label = f"{emoji} {name_ru}".strip()
    # Редактируем визард в результат с кнопкой «Назад»
    if wizard_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=wizard_id,
                text=f"✅ <b>Вакансия добавлена!</b>\n\n💼 {label}\n🇺🇿 {name_uz}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ К вакансиям", callback_data="vac:refresh"),
                ]]),
            )
            return
        except TelegramBadRequest:
            pass
    # Fallback
    vacancies = await db.get_all_vacancies(session)
    await message.answer(
        _vacancy_list_text(vacancies),
        parse_mode="HTML",
        reply_markup=_vacancies_keyboard(vacancies),
    )


# ── Редактировать вакансию ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:edit:"))
async def vac_edit_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        await callback.answer("Вакансия не найдена.", show_alert=True)
        return

    name    = f"{vacancy['emoji']} {vacancy['name_ru']}".strip()
    name_uz = vacancy["name_uz"]
    emoji   = vacancy["emoji"] or "—"

    await state.set_state(EditVacancy.choosing_field)
    await state.update_data(edit_vacancy_id=vacancy_id)

    try:
        await callback.message.edit_text(
            f"✏️ <b>Редактировать вакансию</b>\n{'─'*28}\n\n"
            f"💼 {name}\n🇺🇿 {name_uz}\n😊 {emoji}\n\n"
            f"Что хотите изменить?",
            parse_mode="HTML",
            reply_markup=_edit_field_keyboard(vacancy_id),
        )
    except TelegramAPIError:
        await callback.message.answer(
            f"✏️ <b>Редактировать вакансию</b>\n{'─'*28}\n\n"
            f"💼 {name}\n🇺🇿 {name_uz}\n😊 {emoji}\n\n"
            f"Что хотите изменить?",
            parse_mode="HTML",
            reply_markup=_edit_field_keyboard(vacancy_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("vac:edit_field:"))
async def vac_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts      = callback.data.split(":")
    vacancy_id = int(parts[2])
    field      = parts[3]

    field_labels = {
        "name_ru": "название на русском",
        "name_uz": "название на узбекском",
        "emoji":   "эмодзи",
    }
    label = field_labels.get(field, field)
    hint  = "\nОтправьте один эмодзи, или <code>-</code> чтобы убрать." if field == "emoji" else ""

    await state.set_state(EditVacancy.waiting_value)
    await state.update_data(edit_vacancy_id=vacancy_id, edit_field=field)

    try:
        await callback.message.edit_text(
            f"✏️ Введите новое <b>{label}</b>:{hint}",
            parse_mode="HTML",
            reply_markup=_edit_cancel_keyboard(),
        )
    except TelegramAPIError:
        await callback.message.answer(
            f"✏️ Введите новое <b>{label}</b>:{hint}",
            parse_mode="HTML",
            reply_markup=_edit_cancel_keyboard(),
        )
    await callback.answer()


@router.message(EditVacancy.waiting_value)
async def vac_edit_value(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data       = await state.get_data()
    vacancy_id = data.get("edit_vacancy_id")
    field      = data.get("edit_field")
    value      = (message.text or "").strip()

    if not vacancy_id or not field:
        await state.clear()
        return

    if field in ("name_ru", "name_uz") and len(value) < 2:
        await message.answer("❌ Слишком короткое название. Попробуйте ещё раз:", reply_markup=_edit_cancel_keyboard())
        return

    if field == "emoji" and value == "-":
        value = ""

    kwargs: dict[str, str] = {field: value}
    await db.update_vacancy(session, vacancy_id, **kwargs)

    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    name    = f"{vacancy['emoji']} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"
    logger.info("Вакансия id=%d поле %s обновлено: %r", vacancy_id, field, value)
    await state.clear()

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    vacancies = await db.get_all_vacancies(session)
    await message.answer(
        _vacancy_list_text(vacancies),
        parse_mode="HTML",
        reply_markup=_vacancies_keyboard(vacancies),
    )


@router.callback_query(F.data == "vac:edit_cancel")
async def vac_edit_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.answer("Редактирование отменено")
    vacancies = await db.get_all_vacancies(session)
    try:
        await callback.message.edit_text(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )
    except TelegramAPIError:
        await callback.message.answer(
            _vacancy_list_text(vacancies),
            parse_mode="HTML",
            reply_markup=_vacancies_keyboard(vacancies),
        )
