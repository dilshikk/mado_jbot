# bot/db/database.py

import logging
import sqlite3
from datetime import datetime, timedelta

from config import BASE_DIR

logger  = logging.getLogger(__name__)
DB_PATH = str(BASE_DIR / "database.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                lang       TEXT DEFAULT 'ru',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS applications (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER,
                name             TEXT,
                birthday         TEXT,
                phone            TEXT,
                position         TEXT,
                status           TEXT DEFAULT 'pending',
                interview_time   TEXT,
                reminder_sent    INTEGER DEFAULT 0,
                view_count       INTEGER DEFAULT 0,
                notified_pending INTEGER DEFAULT 0,
                hr_score         INTEGER,
                hr_comment       TEXT,
                hr_video_msg_id  INTEGER,
                experience       TEXT,
                created_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                user_id    INTEGER PRIMARY KEY,
                blocked_at TEXT,
                unblock_at TEXT
            );

            CREATE TABLE IF NOT EXISTS vacancies (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name_ru    TEXT NOT NULL,
                name_uz    TEXT NOT NULL,
                emoji      TEXT DEFAULT '',
                is_active  INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT
            );
        """)
    _seed_vacancies()
    logger.info("БД инициализирована: %s", DB_PATH)


def _seed_vacancies() -> None:
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM vacancies").fetchone()[0]
        if count > 0:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        defaults = [
            ("Повар",         "Oshpaz",       "👨\u200d🍳", 1, 0),
            ("Официант",      "Ofitsiant",    "🤵",         1, 1),
            ("Раннер",        "Yuguruvchi",   "🏃",         1, 2),
            ("Бариста",       "Barista",      "☕️",        1, 3),
            ("Тех. персонал", "Texnik xodim", "🧹",         1, 4),
        ]
        conn.executemany(
            "INSERT INTO vacancies (name_ru, name_uz, emoji, is_active, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [(r[0], r[1], r[2], r[3], r[4], now) for r in defaults],
        )


def migrate_db() -> None:
    with _connect() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(applications)").fetchall()}
        if "experience" not in existing:
            conn.execute("ALTER TABLE applications ADD COLUMN experience TEXT")
            logger.info("Миграция: добавлена колонка experience")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vacancies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_ru TEXT NOT NULL, name_uz TEXT NOT NULL,
                emoji TEXT DEFAULT '', is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0, created_at TEXT
            )
        """)
    _seed_vacancies()


# ── Вакансии ──────────────────────────────────────────────────────────────────

def get_active_vacancies() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM vacancies WHERE is_active = 1 ORDER BY sort_order, id").fetchall()
        return [dict(r) for r in rows]


def get_all_vacancies() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM vacancies ORDER BY sort_order, id").fetchall()
        return [dict(r) for r in rows]


def add_vacancy(name_ru: str, name_uz: str, emoji: str = "") -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM vacancies").fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO vacancies (name_ru, name_uz, emoji, is_active, sort_order, created_at) VALUES (?, ?, ?, 1, ?, ?)",
            (name_ru, name_uz, emoji, max_order + 1, now),
        )
        return cursor.lastrowid


def toggle_vacancy(vacancy_id: int) -> bool:
    with _connect() as conn:
        conn.execute("UPDATE vacancies SET is_active = 1 - is_active WHERE id = ?", (vacancy_id,))
        row = conn.execute("SELECT is_active FROM vacancies WHERE id = ?", (vacancy_id,)).fetchone()
        return bool(row["is_active"]) if row else False


def delete_vacancy(vacancy_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM vacancies WHERE id = ?", (vacancy_id,))


def get_vacancy_by_id(vacancy_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)).fetchone()
        return dict(row) if row else None


# ── Пользователи ──────────────────────────────────────────────────────────────

def register_user(user_id: int, username: str | None, first_name: str | None, lang: str = "ru") -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, lang, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, lang=excluded.lang
            """,
            (user_id, username, first_name, lang, now),
        )


def get_user_lang(user_id: int) -> str:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return row["lang"] if row else "ru"
    except sqlite3.Error as e:
        logger.error("get_user_lang error user=%d: %s", user_id, e, exc_info=True)
        return "ru"


def get_all_user_ids() -> list[int]:
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT user_id FROM users").fetchall()
            return [r["user_id"] for r in rows]
    except sqlite3.Error as e:
        logger.error("get_all_user_ids error: %s", e, exc_info=True)
        return []


# ── Чёрный список ─────────────────────────────────────────────────────────────

def block_user(user_id: int, days: int = 30) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    unblock_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO blacklist (user_id, blocked_at, unblock_at) VALUES (?, ?, ?)", (user_id, now, unblock_at))


def is_user_blocked(user_id: int) -> bool:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM blacklist WHERE user_id = ? AND unblock_at > ?",
                (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ).fetchone()
            return row is not None
    except sqlite3.Error as e:
        logger.error("is_user_blocked error user=%d: %s", user_id, e, exc_info=True)
        return False


def get_users_to_unblock() -> list[int]:
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT user_id FROM blacklist WHERE unblock_at <= ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()
            return [r["user_id"] for r in rows]
    except sqlite3.Error as e:
        logger.error("get_users_to_unblock error: %s", e, exc_info=True)
        return []


def unblock_user(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))


# ── Анкеты ────────────────────────────────────────────────────────────────────

def save_application(user_id: int, name: str, birthday: str, phone: str, position: str, experience: str = "—") -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO applications (user_id, name, birthday, phone, position, experience, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (user_id, name, birthday, phone, position, experience, now),
        )
        return cursor.lastrowid


def get_application_status(user_id: int) -> str | None:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT status FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
            return row["status"] if row else None
    except sqlite3.Error as e:
        logger.error("get_application_status error user=%d: %s", user_id, e, exc_info=True)
        return None


def update_application_status(user_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE applications SET status = ? WHERE id = (SELECT id FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1)",
            (status, user_id),
        )


def get_applications_by_status(status: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM applications WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        return [dict(r) for r in rows]


def get_applications_today() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM applications WHERE created_at LIKE ? ORDER BY created_at DESC", (f"{today}%",)).fetchall()
        return [dict(r) for r in rows]


def get_all_applications() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM applications ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def search_applications_by_name(query: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM applications WHERE name LIKE ? ORDER BY created_at DESC LIMIT 20", (f"%{query}%",)).fetchall()
        return [dict(r) for r in rows]


def set_interview_time(user_id: int, interview_iso: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE applications SET interview_time = ?, reminder_sent = 0 WHERE id = (SELECT id FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1)",
            (interview_iso, user_id),
        )


def get_pending_reminders() -> list[dict]:
    now        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    in_2_hours = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT a.id, a.user_id, a.interview_time, u.lang
                FROM applications a JOIN users u ON u.user_id = a.user_id
                WHERE a.status = 'accepted' AND a.interview_time IS NOT NULL
                  AND a.reminder_sent = 0 AND a.interview_time <= ? AND a.interview_time > ?
                """,
                (in_2_hours, now),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("get_pending_reminders error: %s", e, exc_info=True)
        return []


def mark_reminder_sent(application_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE applications SET reminder_sent = 1 WHERE id = ?", (application_id,))


def increment_view_count(user_id: int) -> int:
    with _connect() as conn:
        conn.execute(
            "UPDATE applications SET view_count = view_count + 1 WHERE id = (SELECT id FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1)",
            (user_id,),
        )
        row = conn.execute("SELECT view_count FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
        return row["view_count"] if row else 0


def get_stale_pending_applications(days: int = 3) -> list[dict]:
    threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT a.id, a.user_id, u.lang FROM applications a JOIN users u ON u.user_id = a.user_id WHERE a.status = 'pending' AND a.notified_pending = 0 AND a.created_at <= ?",
                (threshold,),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("get_stale_pending_applications error: %s", e, exc_info=True)
        return []


def mark_pending_notified(application_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE applications SET notified_pending = 1 WHERE id = ?", (application_id,))


def save_hr_score(user_id: int, score: int, comment: str = "") -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE applications SET hr_score = ?, hr_comment = ? WHERE id = (SELECT id FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1)",
            (score, comment, user_id),
        )


def get_score_stats() -> dict:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT AVG(hr_score) as avg_score, COUNT(hr_score) as scored_count FROM applications WHERE hr_score IS NOT NULL").fetchone()
            return {"avg_score": round(row["avg_score"] or 0, 1), "scored_count": row["scored_count"] or 0}
    except sqlite3.Error as e:
        logger.error("get_score_stats error: %s", e, exc_info=True)
        return {"avg_score": 0, "scored_count": 0}


def get_detailed_score_stats() -> dict:
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT hr_score, COUNT(*) as cnt FROM applications WHERE hr_score IS NOT NULL GROUP BY hr_score").fetchall()
            distribution = {r["hr_score"]: r["cnt"] for r in rows}
            scored_count = sum(distribution.values())
            avg_row      = conn.execute("SELECT AVG(hr_score) FROM applications WHERE hr_score IS NOT NULL").fetchone()
            comments     = conn.execute("SELECT name, hr_score, hr_comment FROM applications WHERE hr_comment IS NOT NULL AND hr_comment != '' ORDER BY created_at DESC LIMIT 5").fetchall()
            return {"distribution": distribution, "scored_count": scored_count, "avg_score": round(avg_row[0] or 0, 1), "top_comments": [dict(r) for r in comments]}
    except sqlite3.Error as e:
        logger.error("get_detailed_score_stats error: %s", e, exc_info=True)
        return {"distribution": {}, "scored_count": 0, "avg_score": 0, "top_comments": []}


def get_stats() -> tuple[int, int]:
    try:
        with _connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    except sqlite3.Error as e:
        logger.error("get_stats error: %s", e, exc_info=True)
        return 0, 0


def get_dashboard_stats() -> dict:
    today    = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    with _connect() as conn:
        def count(sql: str, params: tuple = ()) -> int:
            return conn.execute(sql, params).fetchone()[0]
        statuses = {s: count("SELECT COUNT(*) FROM applications WHERE status = ?", (s,)) for s in ("pending", "accepted", "rejected", "hold", "hired")}
        top_pos  = conn.execute("SELECT position, COUNT(*) as count FROM applications GROUP BY position ORDER BY count DESC LIMIT 5").fetchall()
        return {
            "total_users":        count("SELECT COUNT(*) FROM users"),
            "new_today":          count("SELECT COUNT(*) FROM users WHERE created_at LIKE ?", (f"{today}%",)),
            "new_week":           count("SELECT COUNT(*) FROM users WHERE created_at >= ?", (week_ago,)),
            "total_apps":         count("SELECT COUNT(*) FROM applications"),
            "interviews_planned": count("SELECT COUNT(*) FROM applications WHERE interview_time IS NOT NULL AND status = 'accepted'"),
            "interviews_today":   count("SELECT COUNT(*) FROM applications WHERE interview_time LIKE ? AND status = 'accepted'", (f"{today}%",)),
            "top_positions":      [dict(r) for r in top_pos],
            **statuses,
        }


def get_weekly_trend() -> list[dict]:
    week_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT substr(created_at, 1, 10) as day, COUNT(*) as count FROM applications WHERE created_at >= ? GROUP BY day ORDER BY day",
            (week_ago,),
        ).fetchall()
    counts_by_day = {r["day"]: r["count"] for r in rows}
    result = []
    for i in range(6, -1, -1):
        dt = datetime.now() - timedelta(days=i)
        result.append({"label": dt.strftime("%d.%m"), "count": counts_by_day.get(dt.strftime("%Y-%m-%d"), 0)})
    return result


def get_stats_by_position() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT position, COUNT(*) as total, SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) as accepted FROM applications GROUP BY position ORDER BY total DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def save_hr_video_msg_id(user_id: int, msg_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE applications SET hr_video_msg_id = ? WHERE id = (SELECT id FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1)",
            (msg_id, user_id),
        )


def get_latest_application(user_id: int) -> dict | None:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("get_latest_application error user=%d: %s", user_id, e, exc_info=True)
        return None
