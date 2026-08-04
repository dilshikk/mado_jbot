# bot/services/scheduler.py

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.db import database as db

logger = logging.getLogger(__name__)
_NOTIFY_DELAY = 0.05


async def send_interview_reminders(bot: Bot) -> None:
    pending = db.get_pending_reminders()
    if not pending:
        return
    logger.info("send_interview_reminders: найдено %d напоминаний", len(pending))
    for row in pending:
        lang           = row.get("lang") or "ru"
        interview_time = row["interview_time"]
        try:
            dt       = datetime.strptime(interview_time, "%Y-%m-%d %H:%M")
            time_str = dt.strftime("%d.%m.%Y в %H:%M")
        except ValueError:
            time_str = interview_time
        text = (
            f"⏰ <b>Напоминание!</b>\n\nСегодня <b>{time_str}</b> вас ждут на собеседовании в <b>MADO</b>.\n\nПожалуйста, не опаздывайте! 🙌"
            if lang == "ru" else
            f"⏰ <b>Eslatma!</b>\n\nBugun soat <b>{time_str}</b> da <b>MADO</b> suhbat.\n\nIltimos, kech qolmang! 🙌"
        )
        try:
            await bot.send_message(chat_id=row["user_id"], text=text, parse_mode="HTML")
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning("Напоминание не доставлено user_id=%d: %s", row["user_id"], e)
        except Exception as e:
            logger.error("Ошибка напоминания user_id=%d: %s", row["user_id"], e, exc_info=True)
        finally:
            db.mark_reminder_sent(row["id"])
        await asyncio.sleep(_NOTIFY_DELAY)


async def notify_stale_applications(bot: Bot) -> None:
    stale = db.get_stale_pending_applications(days=3)
    if not stale:
        return
    logger.info("notify_stale_applications: найдено %d анкет", len(stale))
    for row in stale:
        lang = row.get("lang") or "ru"
        text = (
            "⏳ <b>Ваша анкета всё ещё на рассмотрении.</b>\n\nМы ценим ваше терпение!"
            if lang == "ru" else
            "⏳ <b>Anketangiz hali ko'rib chiqilmoqda.</b>\n\nSabringiz uchun rahmat!"
        )
        try:
            await bot.send_message(chat_id=row["user_id"], text=text, parse_mode="HTML")
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning("Stale notify не доставлено user_id=%d: %s", row["user_id"], e)
        except Exception as e:
            logger.error("Ошибка stale notify user_id=%d: %s", row["user_id"], e, exc_info=True)
        finally:
            db.mark_pending_notified(row["id"])
        await asyncio.sleep(_NOTIFY_DELAY)


async def auto_unblock_users(bot: Bot) -> None:
    user_ids = db.get_users_to_unblock()
    if not user_ids:
        return
    logger.info("auto_unblock_users: разблокировать %d пользователей", len(user_ids))
    for user_id in user_ids:
        try:
            db.unblock_user(user_id)
        except Exception as e:
            logger.error("Ошибка разблокировки user_id=%d: %s", user_id, e, exc_info=True)
            continue
        lang = db.get_user_lang(user_id) or "ru"
        text = (
            "🔓 <b>Хорошие новости!</b>\n\nВаша временная блокировка снята. Вы снова можете подать анкету в MADO!"
            if lang == "ru" else
            "🔓 <b>Yaxshi xabar!</b>\n\nVaqtinchalik blokirovkangiz olib tashlandi. MADO'ga qayta anketa topshirishingiz mumkin!"
        )
        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning("Уведомление о разблокировке не доставлено user_id=%d: %s", user_id, e)
        except Exception as e:
            logger.error("Ошибка уведомления user_id=%d: %s", user_id, e, exc_info=True)
        await asyncio.sleep(_NOTIFY_DELAY)
