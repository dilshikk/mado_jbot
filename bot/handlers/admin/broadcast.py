# bot/handlers/admin/broadcast.py

import asyncio
import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message, PhotoSize,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.states import Broadcast

router = Router()
logger = logging.getLogger(__name__)

_BROADCAST_DELAY   = 0.05
_PROGRESS_INTERVAL = 25


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Общие клавиатуры ──────────────────────────────────────────────────────────

def _admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка",            callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="👮 Список админов",      callback_data="admin:adminlist")],
        [InlineKeyboardButton(text="💼 Вакансии",            callback_data="admin:vacancies")],
        [InlineKeyboardButton(text="🚇 Станции метро",       callback_data="admin:metro")],
        [InlineKeyboardButton(text="📊 Дашборд",             callback_data="admin:dashboard")],
        [InlineKeyboardButton(text="📋 Resend (ввести ID)",  callback_data="admin:resend")],
    ])


def _back_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню администратора."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu"),
    ]])


# Кнопка отмены для каждого шага рассылки
def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить рассылку", callback_data="broadcast:cancel"),
    ]])


def _photo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Без фото",           callback_data="broadcast:skip_photo")],
        [InlineKeyboardButton(text="❌ Отменить рассылку",  callback_data="broadcast:cancel")],
    ])


def _url_skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Без ссылки",         callback_data="broadcast:skip_url")],
        [InlineKeyboardButton(text="❌ Отменить рассылку",  callback_data="broadcast:cancel")],
    ])


def _preview_keyboard(has_url: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_url:
        rows.append([InlineKeyboardButton(text="🔗 Ссылка (в сообщении)", callback_data="noop")])
    rows.append([
        InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast:send"),
        InlineKeyboardButton(text="❌ Отменить",       callback_data="broadcast:cancel"),
    ])
    rows.append([
        InlineKeyboardButton(text="✏️ Изменить фото",  callback_data="broadcast:edit:photo"),
        InlineKeyboardButton(text="✏️ Изменить текст", callback_data="broadcast:edit:caption"),
    ])
    rows.append([InlineKeyboardButton(text="✏️ Изменить ссылку", callback_data="broadcast:edit:url")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _url_keyboard(url: str | None, title: str) -> InlineKeyboardMarkup | None:
    if not url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=title or "🔗 Подробнее", url=url)
    ]])


# ── /admin — главное меню ─────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔️ У вас нет доступа к этой команде.")
        return
    await state.clear()
    await message.answer(
        f"🛠 <b>Панель администратора</b>\n{'─'*28}\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=_admin_menu_keyboard(),
    )


# ── Универсальный возврат в главное меню ──────────────────────────────────────

@router.callback_query(F.data == "admin:menu")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.answer()
    text = f"🛠 <b>Панель администратора</b>\n{'─'*28}\n\nВыберите действие:"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_admin_menu_keyboard())
    except TelegramAPIError:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_admin_menu_keyboard())


# ── Обработчики кнопок меню ───────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def menu_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await state.clear()
    await state.set_state(Broadcast.waiting_photo)
    # Редактируем сообщение главного меню — оно становится визардом рассылки
    text = (
        f"📢 <b>Создание рассылки</b>\n\n"
        f"<b>Шаг 1/4.</b> Отправьте фото для рассылки.\n"
        f"Или нажмите кнопку, чтобы пропустить.\n\n"
        f"<i>Доступ: {len(ADMIN_IDS)} администратор(ов)</i>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_photo_kb())
        await state.update_data(wizard_msg_id=callback.message.message_id)
    except TelegramAPIError:
        sent = await callback.message.answer(text, parse_mode="HTML", reply_markup=_photo_kb())
        await state.update_data(wizard_msg_id=sent.message_id)


@router.callback_query(F.data == "admin:adminlist")
async def menu_adminlist(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    lines = [f"👮 <b>Список администраторов бота</b>\n{'─'*28}"]
    for i, aid in enumerate(ADMIN_IDS, 1):
        lines.append(f"{i}. <code>{aid}</code>")
    text = "\n".join(lines)
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=_back_kb()
        )
    except TelegramAPIError:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_back_kb())


@router.callback_query(F.data == "admin:vacancies")
async def menu_vacancies(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    from bot.handlers.admin.vacancies import _vacancy_list_text, _vacancies_keyboard  # noqa: PLC0415
    vacancies = await db.get_all_vacancies(session)
    text = _vacancy_list_text(vacancies)
    kb = _vacancies_keyboard(vacancies)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except TelegramAPIError:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "admin:metro")
async def menu_metro(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    from bot.handlers.admin.metro_stations import show_metro_menu  # noqa: PLC0415
    await show_metro_menu(callback.message, session, edit=True)


@router.callback_query(F.data == "admin:dashboard")
async def menu_dashboard(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    # Заменяем меню заглушкой с кнопкой «Назад»
    try:
        await callback.message.edit_text(
            "📊 <b>Дашборд</b>\n\n⏳ Загрузка...",
            parse_mode="HTML",
            reply_markup=_back_kb(),
        )
    except TelegramAPIError:
        pass
    from bot.handlers.hr.dashboard import _send_dashboard  # noqa: PLC0415
    await _send_dashboard(callback.message, session)


@router.callback_query(F.data == "admin:resend")
async def menu_resend_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(Broadcast.waiting_resend_id)
    text = (
        "📋 <b>Resend карточки кандидата</b>\n\n"
        "Введите <b>Telegram ID</b> кандидата:"
    )
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:resend_cancel"),
    ]])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=cancel_kb)
        await state.update_data(wizard_msg_id=callback.message.message_id)
    except TelegramAPIError:
        sent = await callback.message.answer(text, parse_mode="HTML", reply_markup=cancel_kb)
        await state.update_data(wizard_msg_id=sent.message_id)


@router.callback_query(F.data == "admin:resend_cancel")
async def menu_resend_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    text = f"🛠 <b>Панель администратора</b>\n{'─'*28}\n\nВыберите действие:"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_admin_menu_keyboard())
    except TelegramAPIError:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_admin_menu_keyboard())


@router.message(Broadcast.waiting_resend_id)
async def menu_resend_execute(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:resend_cancel"),
    ]])
    if not text.isdigit():
        await message.answer("❌ Введите числовой Telegram ID:", reply_markup=cancel_kb)
        return
    with suppress(TelegramAPIError):
        await message.delete()
    await state.clear()
    from bot.handlers.hr.dashboard import resend_candidate_card  # noqa: PLC0415
    message.text = f"/resend {text}"
    await resend_candidate_card(message, session)


# ── /adminlist (прямая команда) ────────────────────────────────────────────────

@router.message(Command("adminlist"))
async def cmd_adminlist(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    lines = [f"👮 <b>Список администраторов бота</b>\n{'─'*28}"]
    for i, aid in enumerate(ADMIN_IDS, 1):
        lines.append(f"{i}. <code>{aid}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── Broadcast FSM ─────────────────────────────────────────────────────────────

async def _edit_wizard(message: Message, state: FSMContext, text: str, kb: InlineKeyboardMarkup) -> None:
    """Редактирует сообщение-визард рассылки на месте."""
    data = await state.get_data()
    wid = data.get("wizard_msg_id")
    if wid:
        with suppress(TelegramAPIError):
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=wid,
                text=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            return
    # Fallback: отправить новое сообщение и запомнить его id
    sent = await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.update_data(wizard_msg_id=sent.message_id)


# Шаг 1: фото
@router.message(Broadcast.waiting_photo, F.photo)
async def broadcast_got_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    best: PhotoSize = message.photo[-1]
    await state.update_data(photo_file_id=best.file_id)
    with suppress(TelegramAPIError):
        await message.delete()
    await state.set_state(Broadcast.waiting_caption)
    await _edit_wizard(
        message, state,
        "<b>Шаг 2/4.</b> Введите текст сообщения (поддерживается HTML).\n\n"
        "Например: <code>🔥 Новое меню уже доступно!</code>",
        _cancel_kb(),
    )


@router.callback_query(F.data == "broadcast:skip_photo", Broadcast.waiting_photo)
async def broadcast_skip_photo(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.update_data(photo_file_id=None)
    await callback.answer()
    await state.set_state(Broadcast.waiting_caption)
    try:
        await callback.message.edit_text(
            "<b>Шаг 2/4.</b> Введите текст сообщения (поддерживается HTML).\n\n"
            "Например: <code>🔥 Новое меню уже доступно!</code>",
            parse_mode="HTML",
            reply_markup=_cancel_kb(),
        )
    except TelegramAPIError:
        pass


# Шаг 2: текст
@router.message(Broadcast.waiting_caption, F.text)
async def broadcast_got_caption(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(caption=message.text)
    with suppress(TelegramAPIError):
        await message.delete()
    await state.set_state(Broadcast.waiting_url)
    await _edit_wizard(
        message, state,
        "<b>Шаг 3/4.</b> Отправьте URL-ссылку.\nИли пропустите.",
        _url_skip_kb(),
    )


# Шаг 3: ссылка
@router.message(Broadcast.waiting_url, F.text)
async def broadcast_got_url(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    url = (message.text or "").strip()
    if not url.startswith("http"):
        await _edit_wizard(
            message, state,
            "❌ Ссылка должна начинаться с <code>https://</code>",
            _url_skip_kb(),
        )
        with suppress(TelegramAPIError):
            await message.delete()
        return
    await state.update_data(url=url)
    with suppress(TelegramAPIError):
        await message.delete()
    await state.set_state(Broadcast.waiting_url_title)
    await _edit_wizard(
        message, state,
        "<b>Шаг 4/4.</b> Введите название кнопки-ссылки.\nНапример: <code>Открыть меню</code>",
        _cancel_kb(),
    )


@router.callback_query(F.data == "broadcast:skip_url", Broadcast.waiting_url)
async def broadcast_skip_url(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.update_data(url=None, url_title=None)
    await callback.answer()
    await _show_preview(callback.message, state, session)


# Шаг 4: название кнопки
@router.message(Broadcast.waiting_url_title, F.text)
async def broadcast_got_url_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(url_title=message.text.strip())
    with suppress(TelegramAPIError):
        await message.delete()
    await _show_preview(message, state, session)


# Предпросмотр (текстовый, в рамках того же сообщения-визарда)
async def _show_preview(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data      = await state.get_data()
    photo_id  = data.get("photo_file_id")
    caption   = data.get("caption", "")
    url       = data.get("url")
    url_title = data.get("url_title", "🔗 Подробнее")
    count     = len(await db.get_all_user_ids(session))
    await state.set_state(Broadcast.preview)

    preview_text = (
        f"👁 <b>Предпросмотр рассылки</b>\n{'─'*28}\n"
        f"👥 Получателей: <b>{count}</b>\n\n"
        f"{'📸 Фото: прикреплено ✅' if photo_id else '📸 Фото: —'}\n"
        f"📝 Текст:\n<blockquote>{caption[:300]}{'...' if len(caption) > 300 else ''}</blockquote>\n"
        f"{'🔗 Ссылка: ' + url if url else '🔗 Ссылка: —'}\n"
        f"{'🔖 Кнопка: ' + url_title if url else ''}"
    )
    await _edit_wizard(message, state, preview_text, _preview_keyboard(has_url=bool(url)))


# Редактирование из предпросмотра
@router.callback_query(F.data.startswith("broadcast:edit:"), Broadcast.preview)
async def broadcast_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    field = callback.data.split(":")[2]
    state_map: dict[str, tuple] = {
        "photo":   (Broadcast.waiting_photo,   "Отправьте новое фото:", _photo_kb()),
        "caption": (Broadcast.waiting_caption, "Введите новый текст:",  _cancel_kb()),
        "url":     (Broadcast.waiting_url,     "Введите новую ссылку:", _url_skip_kb()),
    }
    entry = state_map.get(field)
    if not entry:
        await callback.answer()
        return
    new_state, prompt, kb = entry
    await state.set_state(new_state)
    try:
        await callback.message.edit_text(prompt, parse_mode="HTML", reply_markup=kb)
    except TelegramAPIError:
        pass
    await callback.answer()


# Отмена — возврат в главное меню
@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.answer("Рассылка отменена")
    text = f"🛠 <b>Панель администратора</b>\n{'─'*28}\n\nВыберите действие:"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_admin_menu_keyboard())
    except TelegramAPIError:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_admin_menu_keyboard())


# Отправка
@router.callback_query(F.data == "broadcast:send", Broadcast.preview)
async def broadcast_send(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа.", show_alert=True)
        return
    data = await state.get_data()
    await state.set_state(Broadcast.sending)
    await callback.answer("🚀 Запускаю рассылку...")

    photo_id  = data.get("photo_file_id")
    caption   = data.get("caption", "")
    url       = data.get("url")
    url_title = data.get("url_title", "🔗 Подробнее")
    url_kb    = _url_keyboard(url, url_title)

    user_ids = await db.get_all_user_ids(session)
    total    = len(user_ids)
    sent_count = failed = blocked = 0

    # Редактируем визард в прогресс-сообщение
    try:
        await callback.message.edit_text(f"📤 Отправляю... 0 / {total}", reply_markup=None)
    except TelegramAPIError:
        pass
    progress_msg = callback.message

    for i, user_id in enumerate(user_ids, 1):
        try:
            if photo_id:
                await callback.bot.send_photo(
                    chat_id=user_id, photo=photo_id,
                    caption=caption, parse_mode="HTML", reply_markup=url_kb,
                )
            else:
                await callback.bot.send_message(
                    chat_id=user_id, text=caption,
                    parse_mode="HTML", reply_markup=url_kb,
                )
            sent_count += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramBadRequest as e:
            failed += 1
            logger.warning("Broadcast BadRequest user=%d: %s", user_id, e)
        except TelegramAPIError as e:
            failed += 1
            logger.error("Broadcast APIError user=%d: %s", user_id, e)
        except Exception as e:
            failed += 1
            logger.exception("Broadcast unexpected error user=%d: %s", user_id, e)
        if i % _PROGRESS_INTERVAL == 0 or i == total:
            with suppress(TelegramAPIError):
                await progress_msg.edit_text(
                    f"📤 Отправляю... {i} / {total}\n✅ {sent_count}  ❌ {failed}  🚫 {blocked}"
                )
        await asyncio.sleep(_BROADCAST_DELAY)

    no_errors = failed == 0 and blocked == 0
    with suppress(TelegramAPIError):
        await progress_msg.edit_text(
            f"📊 <b>Рассылка завершена</b>\n{'─'*28}\n"
            f"👥 Всего: <b>{total}</b>\n✅ Отправлено: <b>{sent_count}</b>\n"
            f"🚫 Заблокировали: <b>{blocked}</b>\n❌ Ошибок: <b>{failed}</b>\n\n"
            f"{'✅ Без ошибок!' if no_errors else '⚠️ Часть сообщений не доставлена.'}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ В панель управления", callback_data="admin:menu"),
            ]]),
        )
    await state.clear()
    logger.info("Broadcast finished: sent=%d failed=%d blocked=%d total=%d", sent_count, failed, blocked, total)
