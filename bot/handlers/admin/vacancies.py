# bot/handlers/admin/vacancies.py

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.states import AddVacancy

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _vacancies_keyboard(vacancies: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for v in vacancies:
        status = "✅" if v["is_active"] else "❌"
        label  = f"{v['emoji']} {v['name_ru']}".strip()
        rows.append([
            InlineKeyboardButton(text=f"{status} {label}", callback_data=f"vac:toggle:{v['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"vac:delete:{v['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить вакансию", callback_data="vac:add")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="vac:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_delete_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"vac:delete_confirm:{vacancy_id}"),
        InlineKeyboardButton(text="❌ Отмена",       callback_data="vac:refresh"),
    ]])


def _vacancy_list_text(vacancies: list[dict]) -> str:
    active = sum(1 for v in vacancies if v["is_active"])
    return (
        f"💼 <b>Управление вакансиями</b>\n{'─'*28}\n"
        f"Всего: <b>{len(vacancies)}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ — активна (видна кандидатам)\n"
        f"❌ — отключена (скрыта)\n"
        f"🗑 — удалить вакансию"
    )


@router.message(Command("vacancies"))
async def cmd_vacancies(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    vacancies = await db.get_all_vacancies(session)
    await message.answer(_vacancy_list_text(vacancies), parse_mode="HTML", reply_markup=_vacancies_keyboard(vacancies))


@router.callback_query(F.data == "vac:refresh")
async def vac_refresh(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    try:
        await callback.message.edit_text(_vacancy_list_text(vacancies), parse_mode="HTML", reply_markup=_vacancies_keyboard(vacancies))
    except TelegramBadRequest:
        pass  # Сообщение не изменилось — игнорируем
    await callback.answer("✅ Обновлено")


@router.callback_query(F.data.startswith("vac:toggle:"))
async def vac_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    vacancy_id = int(callback.data.split(":")[2])
    is_active  = await db.toggle_vacancy(session, vacancy_id)
    vacancy    = await db.get_vacancy_by_id(session, vacancy_id)
    name       = f"{vacancy['emoji']} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"
    status_text = "включена ✅" if is_active else "отключена ❌"
    await callback.answer(f"Вакансия «{name}» {status_text}")
    logger.info("Вакансия id=%d %s", vacancy_id, status_text)
    vacancies = await db.get_all_vacancies(session)
    try:
        await callback.message.edit_text(_vacancy_list_text(vacancies), parse_mode="HTML", reply_markup=_vacancies_keyboard(vacancies))
    except TelegramBadRequest:
        pass  # Сообщение не изменилось — игнорируем


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
        f"🗑 <b>Удалить вакансию?</b>\n\n«{name}»\n\n<i>Это необратимо. Уже поданные анкеты не затрагиваются.</i>",
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
        await callback.message.edit_text(_vacancy_list_text(vacancies), parse_mode="HTML", reply_markup=_vacancies_keyboard(vacancies))
    except TelegramBadRequest:
        pass  # Сообщение не изменилось — игнорируем


@router.callback_query(F.data == "vac:add")
async def vac_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AddVacancy.waiting_name_ru)
    await callback.message.answer(
        "➕ <b>Новая вакансия</b>\n\n<b>Шаг 1/3.</b> Введите название на <b>русском</b>:\nНапример: <code>Хостес</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddVacancy.waiting_name_ru)
async def vac_got_name_ru(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое название. Введите ещё раз:")
        return
    await state.update_data(name_ru=text)
    await state.set_state(AddVacancy.waiting_name_uz)
    await message.answer("<b>Шаг 2/3.</b> Введите название на <b>узбекском</b>:\nНапример: <code>Xostes</code>", parse_mode="HTML")


@router.message(AddVacancy.waiting_name_uz)
async def vac_got_name_uz(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("❌ Слишком короткое название. Введите ещё раз:")
        return
    await state.update_data(name_uz=text)
    await state.set_state(AddVacancy.waiting_emoji)
    await message.answer("<b>Шаг 3/3.</b> Отправьте <b>эмодзи</b>.\nИли /skip чтобы пропустить.", parse_mode="HTML")


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
    data       = await state.get_data()
    name_ru    = data["name_ru"]
    name_uz    = data["name_uz"]
    vacancy_id = await db.add_vacancy(session, name_ru, name_uz, emoji)
    logger.info("Добавлена вакансия id=%d: %s / %s", vacancy_id, name_ru, name_uz)
    await state.clear()
    label = f"{emoji} {name_ru}".strip()
    await message.answer(
        f"✅ <b>Вакансия добавлена!</b>\n\n💼 {label}\n🇺🇿 {name_uz}\n\nИспользуйте /vacancies для управления.",
        parse_mode="HTML",
    )
