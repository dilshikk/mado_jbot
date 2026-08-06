# bot/handlers/admin/vacancies.py
"""Раздел «Вакансии» в административной панели.

Навигация (стек экранов — только Reply Keyboard):
  Главное меню → show_vacancies_screen()
    Нажать на вакансию → экран вакансии
      Изменить / Удалить / Включить/Выключить
        ◀️ К вакансиям → show_vacancies_screen()
    ➕ Добавить → AddVacancy FSM
    ⬅️ Назад → Главное меню
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.keyboards.reply import (
    ADMIN_BTN_BACK,
    ADMIN_BTN_CANCEL,
    get_admin_back_keyboard,
    get_admin_cancel_keyboard,
    get_admin_menu_keyboard,
    get_admin_vacancies_kb,
    get_admin_vacancy_confirm_delete_kb,
    get_admin_vacancy_edit_kb,
    get_admin_vacancy_item_kb,
    remove_keyboard,
)
from bot.states import AddVacancy, EditVacancy

router = Router()
logger = logging.getLogger(__name__)

# Тексты кнопок внутри раздела
_BTN_ADD      = "➕ Добавить вакансию"
_BTN_REFRESH  = "🔄 Обновить"
_BTN_TO_LIST  = "◀️ К вакансиям"
_BTN_TOGGLE_ON  = "✅ Включить"
_BTN_TOGGLE_OFF = "❌ Выключить"
_BTN_EDIT     = "✏️ Изменить"
_BTN_DELETE   = "🗑 Удалить"
_BTN_CONFIRM_DELETE = "✅ Да, удалить"
_BTN_EDIT_NAME_RU = "🇷🇺 Название (рус)"
_BTN_EDIT_NAME_UZ = "🇺🇿 Название (узб)"
_BTN_EDIT_EMOJI   = "😊 Эмодзи"


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


def _vacancy_label(v: dict) -> str:
    status = "✅" if v["is_active"] else "❌"
    parts  = [status]
    if v.get("emoji"):
        parts.append(v["emoji"])
    parts.append(v["name_ru"])
    return " ".join(parts)


# ── Публичная точка входа ─────────────────────────────────────────────────────

async def show_vacancies_screen(message: Message, session: AsyncSession) -> None:
    """Открывает экран вакансий. Вызывается из broadcast.py."""
    vacancies = await db.get_all_vacancies(session)
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(_vac_text(vacancies), parse_mode="HTML",
                         reply_markup=get_admin_vacancies_kb(vacancies))


# ── /vacancies ────────────────────────────────────────────────────────────────

@router.message(Command("vacancies"))
async def cmd_vacancies(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await show_vacancies_screen(message, session)


# ── Список вакансий ───────────────────────────────────────────────────────────

@router.message(F.text == _BTN_REFRESH)
async def vac_refresh(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    await message.answer(_vac_text(vacancies), parse_mode="HTML",
                         reply_markup=get_admin_vacancies_kb(vacancies))


@router.message(F.text == ADMIN_BTN_BACK)
async def vac_back(message: Message, state: FSMContext) -> None:
    """⬅️ Назад → главное меню."""
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard(),
    )


@router.message(F.text == _BTN_TO_LIST)
async def vac_to_list(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """◀️ К вакансиям — из экрана отдельной вакансии."""
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    await message.answer(_vac_text(vacancies), parse_mode="HTML",
                         reply_markup=get_admin_vacancies_kb(vacancies))


# ── Выбор вакансии из списка ──────────────────────────────────────────────────

async def _find_vacancy_by_label(label: str, session: AsyncSession) -> dict | None:
    """Находит вакансию по тексту её кнопки (статус + эмодзи + название)."""
    all_v = await db.get_all_vacancies(session)
    for v in all_v:
        if _vacancy_label(v) == label:
            return v
    return None


@router.message(F.text)
async def vac_item_or_add(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Перехватывает нажатие на вакансию из списка или кнопку «Добавить»."""
    if not _is_admin(message.from_user.id):
        return

    text = message.text or ""

    # Добавить вакансию
    if text == _BTN_ADD:
        await state.set_state(AddVacancy.waiting_name_ru)
        await message.answer(
            "➕ <b>Новая вакансия</b>\n\n<b>Шаг 1/3.</b> Введите название на <b>русском</b>:",
            parse_mode="HTML",
            reply_markup=get_admin_cancel_keyboard(),
        )
        return

    # Нажата одна из кнопок-вакансий
    vacancy = await _find_vacancy_by_label(text, session)
    if not vacancy:
        return  # не наш обработчик
    await state.update_data(selected_vacancy_id=vacancy["id"])
    label = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip()
    await message.answer(
        f"💼 <b>{label}</b>\n{'─'*28}\n"
        f"🇺🇿 {vacancy['name_uz']}\n"
        f"Статус: {'✅ Активна' if vacancy['is_active'] else '❌ Отключена'}",
        parse_mode="HTML",
        reply_markup=get_admin_vacancy_item_kb(vacancy["is_active"]),
    )


# ── Действия с вакансией ──────────────────────────────────────────────────────

@router.message(F.text.in_({_BTN_TOGGLE_ON, _BTN_TOGGLE_OFF}))
async def vac_toggle(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    vacancy_id = data.get("selected_vacancy_id")
    if not vacancy_id:
        return
    is_active = await db.toggle_vacancy(session, vacancy_id)
    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        return
    label = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip()
    await message.answer(
        f"💼 <b>{label}</b>\n{'─'*28}\n"
        f"🇺🇿 {vacancy['name_uz']}\n"
        f"Статус: {'✅ Активна' if is_active else '❌ Отключена'}",
        parse_mode="HTML",
        reply_markup=get_admin_vacancy_item_kb(is_active),
    )
    logger.info("Вакансия id=%d → is_active=%s", vacancy_id, is_active)


@router.message(F.text == _BTN_EDIT)
async def vac_edit_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    vacancy_id = data.get("selected_vacancy_id")
    if not vacancy_id:
        return
    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        return
    label = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip()
    await state.set_state(EditVacancy.choosing_field)
    await message.answer(
        f"✏️ <b>Редактировать: {label}</b>\n\nЧто изменить?",
        parse_mode="HTML",
        reply_markup=get_admin_vacancy_edit_kb(),
    )


@router.message(F.text == _BTN_DELETE)
async def vac_delete_prompt(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    vacancy_id = data.get("selected_vacancy_id")
    if not vacancy_id:
        return
    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    if not vacancy:
        return
    label = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip()
    await message.answer(
        f"🗑 <b>Удалить вакансию?</b>\n\n«{label}»\n\n"
        f"<i>Это необратимо. Анкеты не затрагиваются.</i>",
        parse_mode="HTML",
        reply_markup=get_admin_vacancy_confirm_delete_kb(),
    )


@router.message(F.text == _BTN_CONFIRM_DELETE)
async def vac_delete_confirm(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    vacancy_id = data.get("selected_vacancy_id")
    if not vacancy_id:
        return
    vacancy = await db.get_vacancy_by_id(session, vacancy_id)
    name = f"{vacancy.get('emoji', '')} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"
    await db.delete_vacancy(session, vacancy_id)
    logger.info("Вакансия id=%d «%s» удалена", vacancy_id, name)
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    await message.answer(
        f"✅ «{name}» удалена.\n\n" + _vac_text(vacancies),
        parse_mode="HTML",
        reply_markup=get_admin_vacancies_kb(vacancies),
    )


# ── EditVacancy FSM ───────────────────────────────────────────────────────────

@router.message(EditVacancy.choosing_field, F.text.in_({_BTN_EDIT_NAME_RU, _BTN_EDIT_NAME_UZ, _BTN_EDIT_EMOJI}))
async def vac_choose_field(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    field_map = {
        _BTN_EDIT_NAME_RU: ("name_ru", "название на <b>русском</b>"),
        _BTN_EDIT_NAME_UZ: ("name_uz", "название на <b>узбекском</b>"),
        _BTN_EDIT_EMOJI:   ("emoji",   "<b>эмодзи</b>"),
    }
    field, label = field_map[message.text]
    await state.update_data(edit_field=field)
    await state.set_state(EditVacancy.waiting_value)
    hint = "\nОтправьте <code>-</code> чтобы убрать эмодзи." if field == "emoji" else ""
    await message.answer(
        f"✏️ Введите новое {label}:{hint}",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(EditVacancy.choosing_field, F.text == _BTN_TO_LIST)
async def vac_edit_cancel_to_list(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    await message.answer(_vac_text(vacancies), parse_mode="HTML",
                         reply_markup=get_admin_vacancies_kb(vacancies))


@router.message(EditVacancy.waiting_value, F.text)
async def vac_save_field(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        vacancies = await db.get_all_vacancies(session)
        await message.answer(_vac_text(vacancies), parse_mode="HTML",
                             reply_markup=get_admin_vacancies_kb(vacancies))
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
    await message.answer(
        f"✅ Обновлено!\n\n" + _vac_text(vacancies),
        parse_mode="HTML",
        reply_markup=get_admin_vacancies_kb(vacancies),
    )


# ── AddVacancy FSM ────────────────────────────────────────────────────────────

@router.message(AddVacancy.waiting_name_ru, F.text)
async def vac_add_name_ru(message: Message, state: FSMContext) -> None:
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
    await state.update_data(name_ru=text)
    await state.set_state(AddVacancy.waiting_name_uz)
    await message.answer(
        "➕ <b>Новая вакансия</b>\n\n<b>Шаг 2/3.</b> Введите название на <b>узбекском</b>:",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(AddVacancy.waiting_name_uz, F.text)
async def vac_add_name_uz(message: Message, state: FSMContext) -> None:
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
    await state.update_data(name_uz=text)
    await state.set_state(AddVacancy.waiting_emoji)
    await message.answer(
        "➕ <b>Новая вакансия</b>\n\n<b>Шаг 3/3.</b> Отправьте эмодзи.\nИли /skip для пропуска.",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
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
        return
    await _save_vacancy(message, state, session, emoji=(message.text or "").strip())


async def _save_vacancy(message: Message, state: FSMContext, session: AsyncSession, emoji: str) -> None:
    data = await state.get_data()
    vid = await db.add_vacancy(session, data["name_ru"], data["name_uz"], emoji)
    logger.info("Добавлена вакансия id=%d: %s / %s", vid, data["name_ru"], data["name_uz"])
    await state.clear()
    vacancies = await db.get_all_vacancies(session)
    label = f"{emoji} {data['name_ru']}".strip()
    await message.answer(
        f"✅ <b>Вакансия добавлена!</b>\n\n💼 {label}\n\n" + _vac_text(vacancies),
        parse_mode="HTML",
        reply_markup=get_admin_vacancies_kb(vacancies),
    )
