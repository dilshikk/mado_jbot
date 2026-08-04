# scheduler.py

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db

logger = logging.getLogger(__name__)

# Задержка между сообщениями в рассылках планировщика
_NOTIFY_DELAY = 0.05


# ── Напоминания о собеседовании ───────────────────────────────────────────────

async def send_interview_reminders(bot: Bot) -> None:
    """Отправляет напоминания за 2 часа до собеседования."""
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
            f"⏰ <b>Напоминание!</b>\n\n"
            f"Сегодня <b>{time_str}</b> вас ждут на собеседовании в ресторане <b>MADO</b>.\n\n"
            f"Пожалуйста, не опаздывайте! 🙌"
            if lang == "ru" else
            f"⏰ <b>Eslatma!</b>\n\n"
            f"Bugun soat <b>{time_str}</b> da <b>MADO</b> restoranida suhbat kutilmoqda.\n\n"
            f"Iltimos, kech qolmang! 🙌"
        )

        try:
            await bot.send_message(chat_id=row["user_id"], text=text, parse_mode="HTML")
            logger.info("Напоминание отправлено user_id=%d", row["user_id"])
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            # Помечаем отправленным даже при ошибке — чтобы не спамить
            logger.warning("Напоминание не доставлено user_id=%d: %s", row["user_id"], e)
        except Exception as e:
            logger.error("Неожиданная ошибка напоминания user_id=%d: %s", row["user_id"], e, exc_info=True)
        finally:
            # Всегда помечаем — не спамим независимо от причины сбоя
            db.mark_reminder_sent(row["id"])

        await asyncio.sleep(_NOTIFY_DELAY)


# ── Уведомление о зависших анкетах ───────────────────────────────────────────

async def notify_stale_applications(bot: Bot) -> None:
    """Уведомляет кандидатов, у которых анкета висит > 3 дней."""
    stale = db.get_stale_pending_applications(days=3)
    if not stale:
        return

    logger.info("notify_stale_applications: найдено %d анкет", len(stale))

    for row in stale:
        lang = row.get("lang") or "ru"
        text = (
            "⏳ <b>Ваша анкета всё ещё на рассмотрении.</b>\n\n"
            "Мы ценим ваше терпение! HR-менеджер свяжется с вами в ближайшее время."
            if lang == "ru" else
            "⏳ <b>Anketangiz hali ko'rib chiqilmoqda.</b>\n\n"
            "Sabringiz uchun rahmat! HR menejer tez orada siz bilan bog'lanadi."
        )

        try:
            await bot.send_message(chat_id=row["user_id"], text=text, parse_mode="HTML")
            logger.info("Stale-уведомление отправлено user_id=%d", row["user_id"])
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning("Stale notify не доставлено user_id=%d: %s", row["user_id"], e)
        except Exception as e:
            logger.error("Неожиданная ошибка stale notify user_id=%d: %s", row["user_id"], e, exc_info=True)
        finally:
            db.mark_pending_notified(row["id"])

        await asyncio.sleep(_NOTIFY_DELAY)


# ── Авторазблокировка пользователей ──────────────────────────────────────────

async def auto_unblock_users(bot: Bot) -> None:
    """Снимает блокировку у пользователей, у которых истёк срок."""
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
            "🔓 <b>Хорошие новости!</b>\n\n"
            "Ваша временная блокировка снята. "
            "Вы снова можете подать анкету в MADO!\n\n"
            "Нажмите «📝 Заполнить анкету» в меню."
            if lang == "ru" else
            "🔓 <b>Yaxshi xabar!</b>\n\n"
            "Vaqtinchalik blokirovkangiz olib tashlandi. "
            "Endi MADO'ga qayta anketa topshirishingiz mumkin!\n\n"
            "Menyudagi «📝 Anketani to'ldirish» tugmasini bosing."
        )

        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
            logger.info("Разблокирован и уведомлён user_id=%d", user_id)
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning("Уведомление о разблокировке не доставлено user_id=%d: %s", user_id, e)
        except Exception as e:
            logger.error("Неожиданная ошибка уведомления user_id=%d: %s", user_id, e, exc_info=True)

        await asyncio.sleep(_NOTIFY_DELAY)
