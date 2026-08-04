# bot/handlers/hr/dashboard.py

import csv
import io
import logging
from contextlib import suppress
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import ADMIN_CHAT_ID, ADMIN_IDS
from bot.db import requests as db
from bot import keyboards as kb
from bot.lexicon import LOCALIZATION
from bot.states import DashboardFilter
from bot.utils.formatters import build_hr_resume_text

router = Router()
logger = logging.getLogger(__name__)

_STATUS_ICON: dict[str, str] = {
    "pending":  "⏳",
    "accepted": "✅",
    "rejected": "❌",
    "hold":     "⏸",
}


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏳ Ожидающие",   callback_data="dash:list:pending"),
            InlineKeyboardButton(text="✅ Одобренные",  callback_data="dash:list:accepted"),
        ],
        [
            InlineKeyboardButton(text="❌ Отклонённые", callback_data="dash:list:rejected"),
            InlineKeyboardButton(text="📅 Сегодня",     callback_data="dash:list:today"),
        ],
        [
            InlineKeyboardButton(text="🏆 По должностям", callback_data="dash:positions"),
            InlineKeyboardButton(text="⭐️ Оценки",        callback_data="dash:scores"),
        ],
        [
            InlineKeyboardButton(text="🔍 Поиск по имени", callback_data="dash:search"),
            InlineKeyboardButton(text="📤 Экспорт CSV",    callback_data="dash:export"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="dash:refresh")],
    ])


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="dash:refresh")
    ]])


async def _send_dashboard(message: Message, session: AsyncSession) -> None:
    stats  = await db.get_dashboard_stats(session)
    trends = await db.get_weekly_trend(session)
    scores = await db.get_score_stats(session)

    trend_lines = []
    for day in trends:
        bar = "█" * min(day["count"], 10)
        if day["count"] > 10:
            bar += f"({day['count']})"
        trend_lines.append(f"  {day['label']}: {bar or '—'}")
    trend_text = "\n".join(trend_lines) or "  нет данных"

    top_positions = "\n".join(
        f"  {i+1}. {p['position']} — {p['count']} чел."
        for i, p in enumerate(stats["top_positions"][:3])
    ) or "  нет данных"

    avg_score     = scores.get("avg_score") or 0.0
    score_bar     = ("⭐️" * round(avg_score) + "☆" * (5 - round(avg_score))) if avg_score else "—"
    avg_score_str = f"{avg_score}/5" if avg_score else "нет оценок"

    text = (
        f"📊 <b>HR Dashboard — MADO</b>\n<i>Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n{'─'*30}\n\n"
        f"👥 <b>Пользователи</b>\n  Всего:            <b>{stats['total_users']}</b>\n  Новых сегодня:    <b>{stats['new_today']}</b>\n  Новых за неделю:  <b>{stats['new_week']}</b>\n\n"
        f"📝 <b>Анкеты</b>\n  Всего: <b>{stats['total_apps']}</b>\n  ⏳ На рассмотрении: <b>{stats['pending']}</b>\n  ✅ Одобрено: <b>{stats['accepted']}</b>\n  ❌ Отклонено: <b>{stats['rejected']}</b>\n  ⏸ На паузе: <b>{stats['hold']}</b>\n\n"
        f"📅 <b>Собеседования</b>\n  Запланировано: <b>{stats['interviews_planned']}</b>\n  Сегодня: <b>{stats['interviews_today']}</b>\n\n"
        f"⭐️ <b>Средняя оценка</b>\n  {score_bar}  <b>{avg_score_str}</b>  (оценено: {scores.get('scored_count', 0)})\n\n"
        f"🏆 <b>Топ вакансий</b>\n{top_positions}\n\n"
        f"📈 <b>Анкеты за 7 дней</b>\n<code>{trend_text}</code>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=_dashboard_keyboard())


@router.message(Command("dashboard"))
async def cmd_dashboard(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _send_dashboard(message, session)


@router.message(F.text.startswith("/resend"))
async def resend_candidate_card(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: <code>/resend USER_ID</code>", parse_mode="HTML")
        return
    candidate_id = int(parts[1])
    bot: Bot     = message.bot
    app          = await db.get_latest_application(session, candidate_id)
    if not app:
        await message.answer(f"❌ Анкета для user_id={candidate_id} не найдена.")
        return
    try:
        tg_user      = await bot.get_chat(candidate_id)
        username_raw = tg_user.username or LOCALIZATION["ru"]["none_text"]
    except Exception:
        username_raw = LOCALIZATION["ru"]["none_text"]
    data = {
        "name": app.get("name"), "birthday": app.get("birthday"), "phone": app.get("phone"),
        "position": app.get("position"), "branch": "MADO (Tashkent City Mall)",
        "gender": "—", "family": "—", "citizenship": "—", "address": "—",
    }
    resume_text = build_hr_resume_text(data, candidate_id, username_raw)
    hr_keyboard = kb.get_hr_action_keyboard(phone=app.get("phone", ""), username=username_raw, candidate_id=candidate_id)
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=resume_text, reply_markup=hr_keyboard, parse_mode="HTML")
    await message.answer(f"✅ Карточка кандидата {candidate_id} отправлена в HR-чат.")


@router.callback_query(F.data.startswith("dash:list:"))
async def dashboard_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    filter_key = callback.data.split(":")[2]
    if filter_key == "today":
        apps  = await db.get_applications_today(session)
        title = "📅 Анкеты за сегодня"
    else:
        apps  = await db.get_applications_by_status(session, filter_key)
        title = {"pending": "⏳ На рассмотрении", "accepted": "✅ Одобренные", "rejected": "❌ Отклонённые"}.get(filter_key, "📋 Анкеты")
    if not apps:
        await callback.answer("Нет данных по этому фильтру.", show_alert=True)
        return
    lines = [f"<b>{title}</b> ({len(apps)})\n{'─'*28}"]
    for i, a in enumerate(apps[:20], 1):
        score_str = f" ⭐{a['hr_score']}" if a.get("hr_score") else ""
        date_str  = a["created_at"][:10] if a.get("created_at") else "—"
        lines.append(f"\n{i}. <b>{a['name']}</b> — {a['position']}\n   📱 {a['phone']}  📅 {date_str}{score_str}")
    if len(apps) > 20:
        lines.append(f"\n<i>...и ещё {len(apps)-20}. Используйте экспорт CSV.</i>")
    with suppress(TelegramAPIError):
        await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "dash:positions")
async def dashboard_positions(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    data = await db.get_stats_by_position(session)
    if not data:
        await callback.answer("Нет данных.", show_alert=True)
        return
    max_count = max(p["total"] for p in data) or 1
    lines     = ["<b>🏆 Статистика по вакансиям</b>\n" + "─"*28]
    for p in data:
        bar_len  = round(p["total"] / max_count * 10)
        bar      = "▓" * bar_len + "░" * (10 - bar_len)
        accepted = p.get("accepted", 0)
        pct      = round(accepted / p["total"] * 100) if p["total"] else 0
        lines.append(f"\n<b>{p['position']}</b>\n  {bar} {p['total']} заявок\n  ✅ Одобрено: {accepted} ({pct}%)")
    with suppress(TelegramAPIError):
        await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "dash:scores")
async def dashboard_scores(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    data = await db.get_detailed_score_stats(session)
    if not data["scored_count"]:
        await callback.answer("Оценок пока нет.", show_alert=True)
        return
    dist_lines = []
    for star in range(5, 0, -1):
        count   = data["distribution"].get(star, 0)
        bar_len = round(count / data["scored_count"] * 10) if data["scored_count"] else 0
        dist_lines.append(f"  {'⭐'*star}: {'▓'*bar_len}{'░'*(10-bar_len)} {count}")
    top_comments = "\n".join(
        f"  • {c['name']} ({c['hr_score']}⭐): {c['hr_comment']}"
        for c in data["top_comments"][:3]
    ) or "  нет комментариев"
    text = (
        f"⭐️ <b>Детальная статистика оценок</b>\n{'─'*28}\n\n"
        f"Оценено: <b>{data['scored_count']}</b>\nСредняя: <b>{data['avg_score']}/5</b>\n\n"
        f"<b>Распределение:</b>\n{chr(10).join(dist_lines)}\n\n"
        f"<b>Последние комментарии:</b>\n{top_comments}"
    )
    with suppress(TelegramAPIError):
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_keyboard())
    await callback.answer()


@router.callback_query(F.data == "dash:search")
async def dashboard_search_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(DashboardFilter.waiting_position_filter)
    await callback.message.answer("🔍 Введите имя или часть имени кандидата:")
    await callback.answer()


@router.message(DashboardFilter.waiting_position_filter)
async def dashboard_search_result(message: Message, state: FSMContext, session: AsyncSession) -> None:
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        await message.answer("❌ Введите имя для поиска.")
        return
    apps = await db.search_applications_by_name(session, query)
    if not apps:
        await message.answer(f"🔍 По запросу «{query}» ничего не найдено.")
        return
    lines = [f"🔍 <b>Результат: «{query}»</b> ({len(apps)})\n{'─'*28}"]
    for a in apps[:15]:
        icon = _STATUS_ICON.get(a["status"], "❓")
        lines.append(f"\n{icon} <b>{a['name']}</b>\n  💼 {a['position']}  📱 {a['phone']}\n  🆔 <code>{a['user_id']}</code>  📅 {a['created_at'][:10]}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "dash:export")
async def dashboard_export(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    apps = await db.get_all_applications(session)
    if not apps:
        await callback.answer("Нет данных для экспорта.", show_alert=True)
        return
    await callback.answer("⏳ Генерирую CSV...", show_alert=False)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "user_id", "ФИО", "Дата рождения", "Телефон", "Вакансия", "Статус", "Оценка", "Комментарий HR", "Дата подачи", "Дата собеседования"])
    for a in apps:
        writer.writerow([
            a["id"], a["user_id"], a["name"], a["birthday"], a["phone"],
            a["position"], a["status"], a.get("hr_score", ""), a.get("hr_comment", ""),
            a["created_at"], a.get("interview_time", ""),
        ])
    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename  = f"mado_applications_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await callback.message.answer_document(
        document=BufferedInputFile(csv_bytes, filename=filename),
        caption=f"📤 <b>Экспорт анкет MADO</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n📝 Записей: <b>{len(apps)}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "dash:refresh")
async def dashboard_refresh(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    with suppress(TelegramAPIError):
        await callback.message.delete()
    await _send_dashboard(callback.message, session)
    await callback.answer()
