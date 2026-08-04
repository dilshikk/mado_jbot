# bot/handlers/user/common.py

import asyncio
import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db import database as db
from bot import keyboards as kb
from config import ADMIN_IDS
from bot.filters.common import IsPrivateChat
from bot.messages import LOCALIZATION
from bot.states import Form

router = Router()
router.message.filter(IsPrivateChat())

logger = logging.getLogger(__name__)
_BROADCAST_DELAY = 0.05


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, lang: str) -> None:
    if lang in ("ru", "uz"):
        db.register_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            lang=lang,
        )
        await message.answer(LOCALIZATION[lang]["welcome"], reply_markup=kb.get_main_menu(lang), parse_mode="HTML")
    else:
        await message.answer("Пожалуйста, выберите язык / Iltimos, tilni tanlang:", reply_markup=kb.get_language_keyboard())
        await state.set_state(Form.waiting_for_lang)


@router.message(Form.waiting_for_lang, F.text.in_(["🇷🇺 Русский", "🇺🇿 O'zbekcha"]))
async def set_language(message: Message, state: FSMContext) -> None:
    lang = "ru" if "Русский" in message.text else "uz"
    await state.update_data(lang=lang)
    db.register_user(user_id=message.from_user.id, username=message.from_user.username, first_name=message.from_user.first_name, lang=lang)
    await message.answer(LOCALIZATION[lang]["welcome"], reply_markup=kb.get_main_menu(lang), parse_mode="HTML")
    await state.clear()


@router.message(F.text.in_(["🌐 Сменить язык", "🌐 Tilni o'zgartirish"]))
async def change_lang(message: Message, state: FSMContext) -> None:
    await message.answer("Пожалуйста, выберите язык / Iltimos, tilni tanlang:", reply_markup=kb.get_language_keyboard())
    await state.set_state(Form.waiting_for_lang)


@router.message(F.text.in_(["🏢 О ресторане", "🏢 Restoran haqida"]))
async def about_restaurant(message: Message, lang: str) -> None:
    await message.answer(LOCALIZATION[lang]["about_text"], parse_mode="HTML")


@router.message(F.text.in_(["📋 Мой статус", "📋 Mening statusim"]))
async def my_status(message: Message, lang: str) -> None:
    try:
        status = db.get_application_status(message.from_user.id)
    except Exception as e:
        logger.error("my_status db error user=%d: %s", message.from_user.id, e, exc_info=True)
        await message.answer(LOCALIZATION[lang]["status_error"])
        return
    key = status if status in LOCALIZATION[lang]["statuses"] else "none"
    await message.answer(LOCALIZATION[lang]["statuses"][key])


@router.message(Command("stats"))
async def cmd_stats(message: Message, lang: str) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    total_users, total_apps = db.get_stats()
    await message.answer(LOCALIZATION[lang]["hr_stats_text"].format(total_users=total_users, total_apps=total_apps), parse_mode="HTML")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, lang: str) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        await message.answer(LOCALIZATION[lang]["broadcast_no_reply"])
        return
    users = db.get_all_user_ids()
    total = len(users)
    sent = failed = 0
    progress = await message.answer(LOCALIZATION[lang]["broadcast_progress"].format(current=0, total=total))
    for i, user_id in enumerate(users, 1):
        try:
            await message.reply_to_message.copy_to(user_id)
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning("broadcast copy_to user=%d: %s", user_id, e)
        if i % 25 == 0 or i == total:
            with suppress(Exception):
                await progress.edit_text(LOCALIZATION[lang]["broadcast_progress"].format(current=i, total=total) + f"\n✅ {sent}  ❌ {failed}")
        await asyncio.sleep(_BROADCAST_DELAY)
    await progress.edit_text(LOCALIZATION[lang]["broadcast_done"].format(sent=sent, failed=failed), parse_mode="HTML")
