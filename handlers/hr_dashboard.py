# handlers/hr_dashboard.py

import csv
import io
import logging
import keyboards as kb
from contextlib import suppress
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)
from utils.formatters import build_hr_resume_text
import database as db
from config import ADMIN_IDS

router = Router()
logger = logging.getLogger(__name__)

_STATUS_ICON: dict[str, str] = {
    "pending":  "⏳",
    "accepted": "✅",
    "rejected": "❌",
    "hold":     "⏸",
}


# ── States ────────────────────────────────────────────────────────────────────

class DashboardFilter(StatesGroup):
    waiting_position_filter = State()
    waiting_date_from       = State()


# ── Проверка прав ─────────────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Клавиатуры ────────────────────────────────────────────────────────────────

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
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="dash:refresh"),
        ],
    ])


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="dash:refresh")
    ]])


# ── Главный дашборд ───────────────────────────────────────────────────────────

async def _send_dashboard(message: Message) -> None:
    """Отправляет дашборд. Вынесено отдельно чтобы переиспользовать из refresh."""
    stats  = db.get_dashboard_stats()
    trends = db.get_weekly_trend()
    scores = db.get_score_stats()

    # Мини-график тренда
    trend_lines = []
    for day in trends:
        bar = "█" * min(day["count"], 10)
        if day["count"] > 10:
            bar += f"({day['count']})"
        trend_lines.append(f"  {day['label']}: {bar or '—'}")
    trend_text = "\n".join(trend_lines) or "  нет данных"

    # Топ должностей
    top_positions = "\n".join(
        f"  {i+1}. {p['position']} — {p['count']} чел."
        for i, p in enumerate(stats["top_positions"][:3])
    ) or "  нет данных"

    # Защита от None в avg_score
    avg_score = scores.get("avg_score") or 0.0
    score_bar = (
        "⭐️" * round(avg_score) + "☆" * (5 - round(avg_score))
        if avg_score else "—"
    )
    avg_score_str = f"{avg_score}/5" if avg_score else "нет оценок"

    text = (
        f"📊 <b>HR Dashboard — MADO</b>\n"
        f"<i>Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n"
        f"{'─' * 30}\n\n"

        f"👥 <b>Пользователи</b>\n"
        f"  Всего в базе:       <b>{stats['total_users']}</b>\n"
        f"  Новых сегодня:      <b>{stats['new_today']}</b>\n"
        f"  Новых за неделю:    <b>{stats['new_week']}</b>\n\n"

        f"📝 <b>Анкеты</b>\n"
        f"  Всего:              <b>{stats['total_apps']}</b>\n"
        f"  ⏳ На рассмотрении: <b>{stats['pending']}</b>\n"
        f"  ✅ Одобрено:        <b>{stats['accepted']}</b>\n"
        f"  ❌ Отклонено:       <b>{stats['rejected']}</b>\n"
        f"  ⏸ На паузе:        <b>{stats['hold']}</b>\n\n"

        f"📅 <b>Собеседования</b>\n"
        f"  Запланировано:      <b>{stats['interviews_planned']}</b>\n"
        f"  Сегодня:            <b>{stats['interviews_today']}</b>\n\n"

        f"⭐️ <b>Средняя оценка кандидатов</b>\n"
        f"  {score_bar}  <b>{avg_score_str}</b>  "
        f"(оценено: {scores.get('scored_count', 0)})\n\n"

        f"🏆 <b>Топ вакансий</b>\n"
        f"{top_positions}\n\n"

        f"📈 <b>Анкеты за последние 7 дней</b>\n"
        f"<code>{trend_text}</code>"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=_dashboard_keyboard())

@router.message(F.text.startswith("/resend"))
async def resend_candidate_card(message: Message) -> None:
    from config import ADMIN_IDS, ADMIN_CHAT_ID
    
    # Только для администраторов
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(
            "Использование: <code>/resend USER_ID</code>\n"
            "Пример: <code>/resend 8182421826</code>",
            parse_mode="HTML",
        )
        return

    candidate_id = int(parts[1])
    bot: Bot = message.bot

    app = db.get_latest_application(candidate_id)
    if not app:
        await message.answer(f"❌ Анкета для user_id={candidate_id} не найдена.")
        return

    # Получаем данные пользователя
    try:
        tg_user = await bot.get_chat(candidate_id)
        username_raw = tg_user.username or LOCALIZATION["ru"]["none_text"]
    except Exception:
        username_raw = LOCALIZATION["ru"]["none_text"]

    # Собираем данные как будто из FSM
    data = {
        "name":        app.get("name"),
        "birthday":    app.get("birthday"),
        "phone":       app.get("phone"),
        "position":    app.get("position"),
        "branch":      "MADO (Tashkent City Mall)",
        "gender":      "—",
        "family":      "—",
        "citizenship": "—",
        "address":     "—",
    }

    resume_text = build_hr_resume_text(data, candidate_id, username_raw)
    hr_keyboard = kb.get_hr_action_keyboard(
        phone=app.get("phone", ""),
        username=username_raw,
        candidate_id=candidate_id,
    )

    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=resume_text,
        reply_markup=hr_keyboard,
        parse_mode="HTML",
    )
    await message.answer(f"✅ Карточка кандидата {candidate_id} отправлена в HR-чат.")

@router.message(Command("dashboard"))
async def cmd_dashboard(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await _send_dashboard(message)


# ── Список анкет по статусу ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("dash:list:"))
async def dashboard_list(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    filter_key = callback.data.split(":")[2]

    if filter_key == "today":
        apps  = db.get_applications_today()
        title = "📅 Анкеты за сегодня"
    else:
        apps = db.get_applications_by_status(filter_key)
        titles = {
            "pending":  "⏳ Анкеты на рассмотрении",
            "accepted": "✅ Одобренные кандидаты",
            "rejected": "❌ Отклонённые кандидаты",
        }
        title = titles.get(filter_key, "📋 Анкеты")

    if not apps:
        await callback.answer("Нет данных по этому фильтру.", show_alert=True)
        return

    lines = [f"<b>{title}</b> ({len(apps)})\n{'─'*28}"]
    for i, a in enumerate(apps[:20], 1):
        score_str = f" ⭐{a['hr_score']}" if a.get("hr_score") else ""
        date_str  = a["created_at"][:10] if a.get("created_at") else "—"
        lines.append(
            f"\n{i}. <b>{a['name']}</b> — {a['position']}\n"
            f"   📱 {a['phone']}  📅 {date_str}{score_str}"
        )

    if len(apps) > 20:
        lines.append(
            f"\n<i>...и ещё {len(apps) - 20}. "
            f"Используйте экспорт CSV для полного списка.</i>"
        )

    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=_back_keyboard()
        )
    await callback.answer()


# ── Статистика по должностям ──────────────────────────────────────────────────

@router.callback_query(F.data == "dash:positions")
async def dashboard_positions(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    data = db.get_stats_by_position()
    if not data:
        await callback.answer("Нет данных.", show_alert=True)
        return

    max_count = max(p["total"] for p in data) or 1
    lines     = ["<b>🏆 Статистика по вакансиям</b>\n" + "─" * 28]

    for p in data:
        bar_len  = round(p["total"] / max_count * 10)
        bar      = "▓" * bar_len + "░" * (10 - bar_len)
        accepted = p.get("accepted", 0)
        pct      = round(accepted / p["total"] * 100) if p["total"] else 0
        lines.append(
            f"\n<b>{p['position']}</b>\n"
            f"  {bar} {p['total']} заявок\n"
            f"  ✅ Одобрено: {accepted} ({pct}%)"
        )

    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=_back_keyboard()
        )
    await callback.answer()


# ── Детальная статистика оценок ───────────────────────────────────────────────

@router.callback_query(F.data == "dash:scores")
async def dashboard_scores(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    data = db.get_detailed_score_stats()
    if not data["scored_count"]:
        await callback.answer("Оценок пока нет.", show_alert=True)
        return

    dist_lines = []
    for star in range(5, 0, -1):
        count   = data["distribution"].get(star, 0)
        bar_len = round(count / data["scored_count"] * 10) if data["scored_count"] else 0
        bar     = "▓" * bar_len + "░" * (10 - bar_len)
        dist_lines.append(f"  {'⭐' * star}: {bar} {count}")

    top_comments = "\n".join(
        f"  • {c['name']} ({c['hr_score']}⭐): {c['hr_comment']}"
        for c in data["top_comments"][:3]
    ) or "  нет комментариев"

    text = (
        f"⭐️ <b>Детальная статистика оценок</b>\n"
        f"{'─' * 28}\n\n"
        f"Оценено кандидатов: <b>{data['scored_count']}</b>\n"
        f"Средняя оценка:     <b>{data['avg_score']}/5</b>\n\n"
        f"<b>Распределение:</b>\n"
        f"{chr(10).join(dist_lines)}\n\n"
        f"<b>Последние комментарии HR:</b>\n"
        f"{top_comments}"
    )

    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=_back_keyboard()
        )
    await callback.answer()


# ── Поиск по имени ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "dash:search")
async def dashboard_search_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(DashboardFilter.waiting_position_filter)
    await callback.message.answer(
        "🔍 Введите имя или часть имени кандидата для поиска:"
    )
    await callback.answer()


@router.message(DashboardFilter.waiting_position_filter)
async def dashboard_search_result(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    await state.clear()

    # Защита от пустого запроса
    if not query:
        await message.answer("❌ Введите имя для поиска.")
        return

    apps = db.search_applications_by_name(query)

    if not apps:
        await message.answer(f"🔍 По запросу «{query}» ничего не найдено.")
        return

    lines = [f"🔍 <b>Результат поиска: «{query}»</b> ({len(apps)})\n{'─'*28}"]
    for a in apps[:15]:
        icon = _STATUS_ICON.get(a["status"], "❓")
        lines.append(
            f"\n{icon} <b>{a['name']}</b>\n"
            f"  💼 {a['position']}  📱 {a['phone']}\n"
            f"  🆔 <code>{a['user_id']}</code>  📅 {a['created_at'][:10]}"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


# ── Экспорт CSV ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "dash:export")
async def dashboard_export(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return

    apps = db.get_all_applications()
    if not apps:
        await callback.answer("Нет данных для экспорта.", show_alert=True)
        return

    await callback.answer("⏳ Генерирую CSV...", show_alert=False)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "user_id", "ФИО", "Дата рождения", "Телефон",
        "Вакансия", "Статус", "Оценка", "Комментарий HR",
        "Дата подачи", "Дата собеседования",
    ])
    for a in apps:
        writer.writerow([
            a["id"],          a["user_id"],            a["name"],
            a["birthday"],    a["phone"],               a["position"],
            a["status"],      a.get("hr_score", ""),    a.get("hr_comment", ""),
            a["created_at"],  a.get("interview_time", ""),
        ])

    # utf-8-sig — корректное отображение кириллицы в Excel
    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename  = f"mado_applications_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    await callback.message.answer_document(
        document=BufferedInputFile(csv_bytes, filename=filename),
        caption=(
            f"📤 <b>Экспорт анкет MADO</b>\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"📝 Всего записей: <b>{len(apps)}</b>"
        ),
        parse_mode="HTML",
    )


# ── Обновить дашборд ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "dash:refresh")
async def dashboard_refresh(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    with suppress(TelegramAPIError):
        await callback.message.delete()
    # Используем вспомогательную функцию — не вызываем cmd_dashboard напрямую
    await _send_dashboard(callback.message)
    await callback.answer()
