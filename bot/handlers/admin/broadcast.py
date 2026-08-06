# bot/handlers/admin/broadcast.py
"""Главное меню /admin + FSM рассылки.

Архитектура «стек экранов»:
  /admin  →  Reply главного меню (get_admin_menu_keyboard)
  Кнопка  →  сначала убирается старая Reply (remove_keyboard),
             затем отправляется новое сообщение с Reply раздела.
  ⬅️ Назад / ❌ Отмена  →  убирается Reply раздела,
                            восстанавливается Reply главного меню.

Никаких Inline-клавиатур внутри панели администратора.
"""

import asyncio
import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PhotoSize,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_IDS
from bot.db import requests as db
from bot.keyboards.reply import (
    ADMIN_BTN_BACK,
    ADMIN_BTN_CANCEL,
    get_admin_back_keyboard,
    get_admin_cancel_keyboard,
    get_admin_menu_keyboard,
    get_admin_skip_cancel_keyboard,
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

# Тексты кнопок главного меню
_BTN_BROADCAST   = "📢 Рассылка"
_BTN_VACANCIES   = "💼 Вакансии"
_BTN_METRO       = "🚇 Метро"
_BTN_DASHBOARD   = "📊 Дашборд"
_BTN_ADMINLIST   = "👮 Администраторы"
_BTN_RESEND      = "📋 Resend"

# Тексты кнопок в разделе «Рассылка»
_BTN_SKIP_PHOTO  = "⏭ Без фото"
_BTN_SKIP_URL    = "⏭ Без ссылки"
_BTN_SEND_ALL    = "✅ Отправить всем"
_BTN_EDIT_PHOTO  = "✏️ Изменить фото"
_BTN_EDIT_TEXT   = "✏️ Изменить текст"
_BTN_EDIT_URL    = "✏️ Изменить ссылку"

# Тексты кнопок в разделе «Resend»
_BTN_RESEND_BACK = ADMIN_BTN_BACK


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Хелпер: переход «назад» в главное меню ───────────────────────────────────

async def _go_home(message: Message, state: FSMContext) -> None:
    """Завершает FSM и восстанавливает главное меню."""
    await state.clear()
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard(),
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
        reply_markup=get_admin_menu_keyboard(),
    )


# ── Кнопки главного меню ──────────────────────────────────────────────────────

@router.message(F.text == _BTN_BROADCAST)
async def reply_broadcast(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await state.set_state(Broadcast.waiting_photo)
    # Убираем Reply главного меню, затем показываем экран рассылки
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        "📢 <b>Создание рассылки</b>\n\n"
        "<b>Шаг 1/4.</b> Отправьте фото.\n"
        "Или нажмите «⏭ Без фото».",
        parse_mode="HTML",
        reply_markup=get_broadcast_photo_kb(),
    )


@router.message(F.text == _BTN_VACANCIES)
async def reply_vacancies(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    from bot.handlers.admin.vacancies import show_vacancies_screen  # noqa: PLC0415
    await show_vacancies_screen(message, session)


@router.message(F.text == _BTN_METRO)
async def reply_metro(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    from bot.handlers.admin.metro_stations import show_metro_home  # noqa: PLC0415
    await show_metro_home(message, session)


@router.message(F.text == _BTN_DASHBOARD)
async def reply_dashboard(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer("⏳", reply_markup=remove_keyboard())
    from bot.handlers.hr.dashboard import _send_dashboard  # noqa: PLC0415
    await _send_dashboard(message, session)
    # Восстанавливаем главное меню после дашборда
    await message.answer("Выберите раздел:", reply_markup=get_admin_menu_keyboard())


@router.message(F.text == _BTN_ADMINLIST)
async def reply_adminlist(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer("⏳", reply_markup=remove_keyboard())
    lines = [f"👮 <b>Список администраторов</b>\n{'─'*28}"]
    for i, aid in enumerate(ADMIN_IDS, 1):
        lines.append(f"{i}. <code>{aid}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=get_admin_back_keyboard())


@router.message(F.text == _BTN_RESEND)
async def reply_resend(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_resend_id)
    await message.answer("⏳", reply_markup=remove_keyboard())
    await message.answer(
        "📋 <b>Resend карточки кандидата</b>\n\nВведите <b>Telegram ID</b>:",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


# ── Кнопка «Назад» из простых разделов (Администраторы, Дашборд) ──────────────

@router.message(F.text == ADMIN_BTN_BACK)
async def reply_back(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    # Работает как общий обработчик «Назад» для разделов без собственного FSM.
    # Разделы с FSM (Вакансии, Метро, Рассылка) перехватывают эту кнопку
    # своими фильтрами по State, поэтому здесь она попадает только тогда,
    # когда FSM не активен (простые разделы).
    await _go_home(message, state)


# ── Кнопка «Отмена» — глобальный выход из любого FSM ─────────────────────────

@router.message(F.text == ADMIN_BTN_CANCEL)
async def reply_cancel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _go_home(message, state)


# ── Resend FSM ────────────────────────────────────────────────────────────────

@router.message(Broadcast.waiting_resend_id, F.text == ADMIN_BTN_CANCEL)
async def resend_cancel(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _go_home(message, state)


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
    await message.answer("Выберите раздел:", reply_markup=get_admin_menu_keyboard())


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

# Шаг 1: фото
@router.message(Broadcast.waiting_photo, F.photo)
async def broadcast_got_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(Broadcast.waiting_caption)
    await message.answer(
        "<b>Шаг 2/4.</b> Введите текст сообщения (HTML).",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(Broadcast.waiting_photo, F.text == _BTN_SKIP_PHOTO)
async def broadcast_skip_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.update_data(photo_file_id=None)
    await state.set_state(Broadcast.waiting_caption)
    await message.answer(
        "<b>Шаг 2/4.</b> Введите текст сообщения (HTML).",
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


@router.message(Broadcast.waiting_photo, F.text == ADMIN_BTN_CANCEL)
async def broadcast_cancel_at_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _go_home(message, state)


# Шаг 2: текст
@router.message(Broadcast.waiting_caption, F.text)
async def broadcast_got_caption(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await _go_home(message, state)
        return
    await state.update_data(caption=message.text)
    await state.set_state(Broadcast.waiting_url)
    await message.answer(
        "<b>Шаг 3/4.</b> Отправьте URL-ссылку или пропустите.",
        parse_mode="HTML",
        reply_markup=get_broadcast_url_kb(),
    )


# Шаг 3: ссылка
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
    await _go_home(message, state)


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
        parse_mode="HTML",
        reply_markup=get_admin_cancel_keyboard(),
    )


# Шаг 4: название кнопки
@router.message(Broadcast.waiting_url_title, F.text)
async def broadcast_got_url_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    if message.text == ADMIN_BTN_CANCEL:
        await _go_home(message, state)
        return
    await state.update_data(url_title=message.text.strip())
    await _show_preview(message, state, session)


# Предпросмотр
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


# Кнопки предпросмотра
@router.message(Broadcast.preview, F.text == ADMIN_BTN_CANCEL)
async def broadcast_cancel_preview(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _go_home(message, state)


@router.message(Broadcast.preview, F.text == _BTN_EDIT_PHOTO)
async def broadcast_edit_photo(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_photo)
    await message.answer("Отправьте новое фото:", reply_markup=get_broadcast_photo_kb())


@router.message(Broadcast.preview, F.text == _BTN_EDIT_TEXT)
async def broadcast_edit_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_caption)
    await message.answer("Введите новый текст:", reply_markup=get_admin_cancel_keyboard())


@router.message(Broadcast.preview, F.text == _BTN_EDIT_URL)
async def broadcast_edit_url(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_url)
    await message.answer("Введите новую ссылку:", reply_markup=get_broadcast_url_kb())


@router.message(Broadcast.preview, F.text == _BTN_SEND_ALL)
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
                await message.bot.send_photo(
                    chat_id=user_id, photo=photo_id,
                    caption=caption, parse_mode="HTML", reply_markup=url_kb,
                )
            else:
                await message.bot.send_message(
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
        reply_markup=get_admin_menu_keyboard(),
    )
    logger.info("Broadcast done: sent=%d failed=%d blocked=%d total=%d", sent_count, failed, blocked, total)
