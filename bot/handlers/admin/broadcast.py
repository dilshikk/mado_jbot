# bot/handlers/admin/broadcast.py
"""Главное меню /admin + FSM рассылки.

Архитектура:
  /admin → Inline главного меню (get_admin_menu_inline_kb)
  Кнопка → callback_query → переход в раздел
  Рассылка → FSM с Reply-клавиатурами для ввода
"""

import asyncio
import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.keyboards.inline import get_admin_menu_inline_kb
from bot.keyboards.reply import (
    ADMIN_BTN_CANCEL,
    get_admin_cancel_keyboard,
    get_broadcast_photo_kb,
    get_broadcast_preview_kb,
    get_broadcast_url_kb,
    remove_keyboard,
)
from bot.states import Broadcast

router = Router()
logger = logging.getLogger(__name__)

_BROADCAST_DELAY   = 0.05
_PROGRESS_INTERVAL = 25

# Тексты кнопок рассылки
_BTN_SKIP_PHOTO  = "⏭ Без фото"
_BTN_SKIP_URL    = "⏭ Без ссылки"
_BTN_SEND_ALL    = "✅ Отправить всем"
_BTN_EDIT_PHOTO  = "✏️ Изменить фото"
_BTN_EDIT_TEXT   = "✏️ Изменить текст"
_BTN_EDIT_URL    = "✏️ Изменить ссылку"


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def _show_admin_menu(message: Message, state: FSMContext) -> None:
    """Отправляет главное меню панели администратора."""
    await state.clear()
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )


# ── /admin ────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔️ У вас нет доступа к этой команде.")
        return
    await state.clear()
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nДобро пожаловать в панель управления.",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )


# ── Callback: кнопки главного меню ───────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(Broadcast.waiting_photo)
    await callback.message.delete()
    await callback.message.answer(
        "📢 <b>Создание рассылки</b>\n\n"
        "<b>Шаг 1/4.</b> Отправьте фото.\n"
        "Или нажмите «⏭ Без фото».",
        parse_mode="HTML",
        reply_markup=get_broadcast_photo_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:vacancies")
async def cb_vacancies(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    from bot.handlers.admin.vacancies import show_vacancies_screen  # noqa: PLC0415
    await show_vacancies_screen(callback.message, session, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin:metro")
async def cb_metro(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    from bot.handlers.admin.metro_stations import show_metro_home  # noqa: PLC0415
    await show_metro_home(callback.message, session, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admin:dashboard")
async def cb_dashboard(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    from bot.handlers.hr.dashboard import _send_dashboard  # noqa: PLC0415
    await callback.message.delete()
    await _send_dashboard(callback.message, session)
    await callback.message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:adminlist")
async def cb_adminlist(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    lines = [f"👮 <b>Список администраторов</b>\n{'─'*28}"]
    for i, aid in enumerate(ADMIN_IDS, 1):
        lines.append(f"{i}. <code>{aid}</code>")
    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:home")]
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:resend")
async def cb_resend(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(Broadcast.waiting_resend_id)
    await callback.message.delete()
    await callback.message.answer(
        "📋 <b>Resend карточки кандидата</b>\n\nВведите <b>Telegram ID</b>:",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:home")
async def cb_admin_home(callback: CallbackQuery, state: FSMContext) -> None:
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


# ── Кнопка «Отмена» — глобальный выход из любого FSM ─────────────────────────

@router.message(F.text == ADMIN_BTN_CANCEL)
async def reply_cancel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )


# ── Resend FSM ────────────────────────────────────────────────────────────────

@router.message(Broadcast.waiting_resend_id, F.text == ADMIN_BTN_CANCEL)
async def resend_cancel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )


@router.message(Broadcast.waiting_resend_id)
async def resend_execute(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой Telegram ID:", reply_markup=get_admin_cancel_keyboard())
        return
    await state.clear()
    from bot.handlers.hr.dashboard import resend_candidate_card  # noqa: PLC0415
    message.text = f"/resend {text}"
    await resend_candidate_card(message, session)
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )


# ── /adminlist (прямая команда) ────────────────────────────────────────────────

@router.message(Command("adminlist"))
async def cmd_adminlist(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    lines = [f"👮 <b>Список администраторов</b>\n{'─'*28}"]
    for i, aid in enumerate(ADMIN_IDS, 1):
        lines.append(f"{i}. <code>{aid}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── Broadcast FSM ─────────────────────────────────────────────────────────────

@router.message(Broadcast.waiting_photo, F.photo)
async def broadcast_got_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(Broadcast.waiting_caption)
    await message.answer("<b>Шаг 2/4.</b> Введите текст сообщения (HTML).", parse_mode="HTML",
                         reply_markup=get_admin_cancel_keyboard())


@router.message(Broadcast.waiting_photo, F.text == _BTN_SKIP_PHOTO)
async def broadcast_skip_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(photo_file_id=None)
    await state.set_state(Broadcast.waiting_caption)
    await message.answer("<b>Шаг 2/4.</b> Введите текст сообщения (HTML).", parse_mode="HTML",
                         reply_markup=get_admin_cancel_keyboard())


@router.message(Broadcast.waiting_photo, F.text == ADMIN_BTN_CANCEL)
async def broadcast_cancel_at_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer("🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
                         parse_mode="HTML", reply_markup=get_admin_menu_inline_kb())


@router.message(Broadcast.waiting_caption, F.text)
async def broadcast_got_caption(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        await message.answer("⏳", reply_markup=remove_keyboard())
        await message.answer("🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
                             parse_mode="HTML", reply_markup=get_admin_menu_inline_kb())
        return
    await state.update_data(caption=message.text)
    await state.set_state(Broadcast.waiting_url)
    await message.answer("<b>Шаг 3/4.</b> Отправьте URL-ссылку или пропустите.", parse_mode="HTML",
                         reply_markup=get_broadcast_url_kb())


@router.message(Broadcast.waiting_url, F.text == _BTN_SKIP_URL)
async def broadcast_skip_url(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(url=None, url_title=None)
    await _show_preview(message, state, session)


@router.message(Broadcast.waiting_url, F.text == ADMIN_BTN_CANCEL)
async def broadcast_cancel_at_url(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer("🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
                         parse_mode="HTML", reply_markup=get_admin_menu_inline_kb())


@router.message(Broadcast.waiting_url, F.text)
async def broadcast_got_url(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    url = (message.text or "").strip()
    if not url.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с https://", reply_markup=get_broadcast_url_kb())
        return
    await state.update_data(url=url)
    await state.set_state(Broadcast.waiting_url_title)
    await message.answer(
        "<b>Шаг 4/4.</b> Введите название кнопки-ссылки.\nНапример: <code>Открыть меню</code>",
        parse_mode="HTML", reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(Broadcast.waiting_url_title, F.text)
async def broadcast_got_url_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await state.clear()
        await message.answer("⏳", reply_markup=remove_keyboard())
        await message.answer("🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
                             parse_mode="HTML", reply_markup=get_admin_menu_inline_kb())
        return
    await state.update_data(url_title=message.text.strip())
    await _show_preview(message, state, session)


async def _show_preview(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data      = await state.get_data()
    photo_id  = data.get("photo_file_id")
    caption   = data.get("caption", "")
    url       = data.get("url")
    url_title = data.get("url_title", "🔗 Подробнее")
    count     = len(await db.get_all_user_ids(session))
    await state.set_state(Broadcast.preview)
    await message.answer(
        f"👁 <b>Предпросмотр</b>\n{'─'*28}\n"
        f"👥 Получателей: <b>{count}</b>\n\n"
        f"{'📸 Фото: ✅' if photo_id else '📸 Фото: —'}\n"
        f"📝 Текст:\n<blockquote>{caption[:300]}{'...' if len(caption) > 300 else ''}</blockquote>\n"
        f"{'🔗 ' + url if url else '🔗 —'}\n"
        f"{'🔖 ' + url_title if url else ''}",
        parse_mode="HTML",
        reply_markup=get_broadcast_preview_kb(),
    )


@router.message(Broadcast.preview, F.text == ADMIN_BTN_CANCEL)
async def broadcast_cancel_preview(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer("🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
                         parse_mode="HTML", reply_markup=get_admin_menu_inline_kb())


@router.message(Broadcast.preview, F.text == "✏️ Изменить фото")
async def broadcast_edit_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_photo)
    await message.answer("Отправьте новое фото:", reply_markup=get_broadcast_photo_kb())


@router.message(Broadcast.preview, F.text == "✏️ Изменить текст")
async def broadcast_edit_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_caption)
    await message.answer("Введите новый текст:", reply_markup=get_admin_cancel_keyboard())


@router.message(Broadcast.preview, F.text == "✏️ Изменить ссылку")
async def broadcast_edit_url(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_url)
    await message.answer("Введите новую ссылку:", reply_markup=get_broadcast_url_kb())


@router.message(Broadcast.preview, F.text == "✅ Отправить всем")
async def broadcast_send(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    await state.set_state(Broadcast.sending)

    photo_id  = data.get("photo_file_id")
    caption   = data.get("caption", "")
    url       = data.get("url")
    url_title = data.get("url_title", "🔗 Подробнее")
    url_kb    = (
        InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=url_title, url=url),
        ]])
        if url else None
    )

    user_ids = await db.get_all_user_ids(session)
    total    = len(user_ids)
    sent_count = failed = blocked = 0

    progress = await message.answer(f"📤 Отправляю... 0 / {total}", reply_markup=remove_keyboard())

    for i, user_id in enumerate(user_ids, 1):
        try:
            if photo_id:
                await message.bot.send_photo(chat_id=user_id, photo=photo_id,
                                             caption=caption, parse_mode="HTML", reply_markup=url_kb)
            else:
                await message.bot.send_message(chat_id=user_id, text=caption,
                                               parse_mode="HTML", reply_markup=url_kb)
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
            logger.exception("Broadcast error user=%d: %s", user_id, e)
        if i % _PROGRESS_INTERVAL == 0 or i == total:
            with suppress(TelegramAPIError):
                await progress.edit_text(
                    f"📤 Отправляю... {i} / {total}\n✅ {sent_count}  ❌ {failed}  🚫 {blocked}"
                )
        await asyncio.sleep(_BROADCAST_DELAY)

    await state.clear()
    no_errors = failed == 0 and blocked == 0
    await message.answer(
        f"📊 <b>Рассылка завершена</b>\n{'─'*28}\n"
        f"👥 Всего: <b>{total}</b>\n"
        f"✅ Отправлено: <b>{sent_count}</b>\n"
        f"🚫 Заблокировали: <b>{blocked}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>\n\n"
        f"{'✅ Без ошибок!' if no_errors else '⚠️ Часть сообщений не доставлена.'}",
        parse_mode="HTML",
        reply_markup=get_admin_menu_inline_kb(),
    )
    logger.info("Broadcast done: sent=%d failed=%d blocked=%d total=%d", sent_count, failed, blocked, total)
