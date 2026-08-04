# handlers/admin_vacancies.py

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import database as db
from config import ADMIN_IDS

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── States ────────────────────────────────────────────────────────────────────

class AddVacancy(StatesGroup):
    waiting_name_ru = State()
    waiting_name_uz = State()
    waiting_emoji   = State()


# ── Клавиатура списка вакансий ────────────────────────────────────────────────

def _vacancies_keyboard(vacancies: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for v in vacancies:
        status = "✅" if v["is_active"] else "❌"
        label  = f"{v['emoji']} {v['name_ru']}".strip()
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {label}",
                callback_data=f"vac:toggle:{v['id']}",
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"vac:delete:{v['id']}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(text="➕ Добавить вакансию", callback_data="vac:add"),
    ])
    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="vac:refresh"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_delete_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"vac:delete_confirm:{vacancy_id}"),
        InlineKeyboardButton(text="❌ Отмена",       callback_data="vac:refresh"),
    ]])


# ── Команда /vacancies ────────────────────────────────────────────────────────

@router.message(Command("vacancies"))
async def cmd_vacancies(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _send_vacancy_list(message)


async def _send_vacancy_list(message: Message) -> None:
    vacancies = db.get_all_vacancies()
    active    = sum(1 for v in vacancies if v["is_active"])
    text = (
        f"💼 <b>Управление вакансиями</b>\n"
        f"{'─' * 28}\n"
        f"Всего: <b>{len(vacancies)}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ — активна (видна кандидатам)\n"
        f"❌ — отключена (скрыта)\n"
        f"🗑 — удалить вакансию"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_vacancies_keyboard(vacancies),
    )


# ── Обновить список ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "vac:refresh")
async def vac_refresh(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    vacancies = db.get_all_vacancies()
    active    = sum(1 for v in vacancies if v["is_active"])
    text = (
        f"💼 <b>Управление вакансиями</b>\n"
        f"{'─' * 28}\n"
        f"Всего: <b>{len(vacancies)}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ — активна (видна кандидатам)\n"
        f"❌ — отключена (скрыта)\n"
        f"🗑 — удалить вакансию"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_vacancies_keyboard(vacancies),
    )
    await callback.answer()


# ── Включить / Отключить вакансию ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:toggle:"))
async def vac_toggle(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    vacancy_id = int(callback.data.split(":")[2])
    is_active  = db.toggle_vacancy(vacancy_id)
    vacancy    = db.get_vacancy_by_id(vacancy_id)
    name       = f"{vacancy['emoji']} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"

    status_text = "включена ✅" if is_active else "отключена ❌"
    await callback.answer(f"Вакансия «{name}» {status_text}", show_alert=False)
    logger.info("Вакансия id=%d %s", vacancy_id, status_text)

    # Обновляем клавиатуру
    vacancies = db.get_all_vacancies()
    active    = sum(1 for v in vacancies if v["is_active"])
    text = (
        f"💼 <b>Управление вакансиями</b>\n"
        f"{'─' * 28}\n"
        f"Всего: <b>{len(vacancies)}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ — активна (видна кандидатам)\n"
        f"❌ — отключена (скрыта)\n"
        f"🗑 — удалить вакансию"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_vacancies_keyboard(vacancies),
    )


# ── Удалить вакансию (подтверждение) ─────────────────────────────────────────

@router.callback_query(F.data.startswith("vac:delete:"))
async def vac_delete_prompt(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = db.get_vacancy_by_id(vacancy_id)
    if not vacancy:
        await callback.answer("Вакансия не найдена.", show_alert=True)
        return

    name = f"{vacancy['emoji']} {vacancy['name_ru']}".strip()
    await callback.message.edit_text(
        f"🗑 <b>Удалить вакансию?</b>\n\n"
        f"«{name}»\n\n"
        f"<i>Это действие необратимо. Уже поданные анкеты не затрагиваются.</i>",
        parse_mode="HTML",
        reply_markup=_confirm_delete_keyboard(vacancy_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vac:delete_confirm:"))
async def vac_delete_confirm(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    vacancy_id = int(callback.data.split(":")[2])
    vacancy    = db.get_vacancy_by_id(vacancy_id)
    name       = f"{vacancy['emoji']} {vacancy['name_ru']}".strip() if vacancy else f"#{vacancy_id}"

    db.delete_vacancy(vacancy_id)
    logger.info("Вакансия id=%d «%s» удалена", vacancy_id, name)
    await callback.answer(f"Вакансия «{name}» удалена.", show_alert=True)

    # Возвращаем обновлённый список
    vacancies = db.get_all_vacancies()
    active    = sum(1 for v in vacancies if v["is_active"])
    text = (
        f"💼 <b>Управление вакансиями</b>\n"
        f"{'─' * 28}\n"
        f"Всего: <b>{len(vacancies)}</b>  |  Активных: <b>{active}</b>\n\n"
        f"✅ — активна (видна кандидатам)\n"
        f"❌ — отключена (скрыта)\n"
        f"🗑 — удалить вакансию"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_vacancies_keyboard(vacancies),
    )


# ── Добавить вакансию (3 шага) ────────────────────────────────────────────────

@router.callback_query(F.data == "vac:add")
async def vac_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AddVacancy.waiting_name_ru)
    await callback.message.answer(
        "➕ <b>Новая вакансия</b>\n\n"
        "<b>Шаг 1/3.</b> Введите название на <b>русском</b>:\n"
        "Например: <code>Хостес</code>",
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
    await message.answer(
        "<b>Шаг 2/3.</b> Введите название на <b>узбекском</b>:\n"
        "Например: <code>Xostes</code>",
        parse_mode="HTML",
    )


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
    await message.answer(
        "<b>Шаг 3/3.</b> Отправьте <b>эмодзи</b> для вакансии.\n"
        "Или нажмите /skip чтобы пропустить.",
        parse_mode="HTML",
    )


@router.message(AddVacancy.waiting_emoji, F.text == "/skip")
async def vac_skip_emoji(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _save_new_vacancy(message, state, emoji="")


@router.message(AddVacancy.waiting_emoji)
async def vac_got_emoji(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    emoji = (message.text or "").strip()
    await _save_new_vacancy(message, state, emoji=emoji)


async def _save_new_vacancy(message: Message, state: FSMContext, emoji: str) -> None:
    data    = await state.get_data()
    name_ru = data["name_ru"]
    name_uz = data["name_uz"]

    vacancy_id = db.add_vacancy(name_ru, name_uz, emoji)
    logger.info("Добавлена вакансия id=%d: %s / %s", vacancy_id, name_ru, name_uz)
    await state.clear()

    label = f"{emoji} {name_ru}".strip()
    await message.answer(
        f"✅ <b>Вакансия добавлена!</b>\n\n"
        f"💼 {label}\n"
        f"🇺🇿 {name_uz}\n\n"
        f"Используйте /vacancies для управления.",
        parse_mode="HTML",
    )
