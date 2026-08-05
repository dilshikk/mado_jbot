# migrate_sqlite_to_postgres.py
# Переносит данные из SQLite database.db → PostgreSQL
#
# Установить зависимости:
#   pip install psycopg2-binary
#
# Запуск:
#   python migrate_sqlite_to_postgres.py
#   или с параметрами:
#   python migrate_sqlite_to_postgres.py --sqlite database.db --pg "postgresql://user:pass@localhost:5432/mado"

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    raise SystemExit("❌  Установите psycopg2:  pip install psycopg2-binary")


# ─────────────────────────────────────────────────────────────────────────────
# Данные для сидирования
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_VACANCIES: list[tuple[str, str, str, int]] = [
    ("Повар",         "Oshpaz",        "👨‍🍳", 0),
    ("Официант",      "Ofitsiant",     "🤵",   1),
    ("Раннер",        "Yuguruvchi",    "🏃",   2),
    ("Бариста",       "Barista",       "☕️",  3),
    ("Тех. персонал", "Texnik xodim",  "🧹",   4),
    ("Кондитер",      "Qandolatchi",   "🍰",   5),
    ("Администратор", "Administrator", "👨‍💼", 6),
    ("Хостес",        "Xostes",        "🙋",   7),
    ("Кассир",        "Kassir",        "💵",   8),
]

# (name_ru, name_uz, line, sort_order)
METRO_STATIONS: list[tuple[str, str, str, int]] = [
    # 🔴 Чиланзарская линия
    ("Сергели",            "Sergeli",             "red",    1),
    ("Озгариш",            "O'zgarish",           "red",    2),
    ("Алмазар",            "Olmazor",             "red",    3),
    ("Чиланзар",           "Chilonzor",           "red",    4),
    ("Мирзо Улугбек",      "Mirzo Ulug'bek",      "red",    5),
    ("Новза",              "Novza",               "red",    6),
    ("Миллий Бог",         "Milliy Bog'",         "red",    7),
    ("Халклар Дустлиги",   "Xalqlar Do'stligi",   "red",    8),
    ("Пахтакор",           "Paxtakor",            "red",    9),
    ("Амир Темур Хиёбони", "Amir Temur xiyoboni", "red",   10),
    ("Хамид Олимжон",      "Hamid Olimjon",       "red",   11),
    ("Пушкин",             "Pushkin",             "red",   12),
    ("Буюк Ипак Йули",     "Buyuk Ipak Yo'li",    "red",   13),

    # 🟢 Юнусабадская линия
    ("Туркистон",          "Turkiston",           "green",  1),
    ("Юнусабад",           "Yunusobod",           "green",  2),
    ("Шахристан",          "Shahriston",          "green",  3),
    ("Бадамзар",           "Bodomzor",            "green",  4),
    ("Минор",              "Minor",               "green",  5),
    ("Абдулла Кадырий",    "Abdulla Qodiriy",     "green",  6),
    ("Юнус Раджабий",      "Yunus Rajabiy",       "green",  7),
    ("Минг Урик",          "Ming O'rik",          "green",  8),

    # 🔵 Узбекистанская линия
    ("Беруний",            "Beruniy",             "blue",   1),
    ("Тинчлик",            "Tinchlik",            "blue",   2),
    ("Чорсу",              "Chorsu",              "blue",   3),
    ("Гафур Гулям",        "G'afur G'ulom",       "blue",   4),
    ("Алишер Навои",       "Alisher Navoiy",      "blue",   5),
    ("Узбекистан",         "O'zbekiston",         "blue",   6),
    ("Космонавтов",        "Kosmonavtlar",        "blue",   7),
    ("Ойбек",              "Oybek",               "blue",   8),
    ("Ташкент",            "Toshkent",            "blue",   9),
    ("Машиностроителей",   "Mashinasozlar",       "blue",  10),
    ("Дустлик",            "Do'stlik",            "blue",  11),

    # 🟠 Линия 30-летия независимости
    ("Кипчак",             "Qipchoq",             "orange", 1),
    ("Турон",              "Turon",               "orange", 2),
    ("Курувчилар",         "Quruvchilar",         "orange", 3),
    ("Хонобод",            "Xonobod",             "orange", 4),
    ("Толарик",            "Tolariq",             "orange", 5),
    ("Кият",               "Qiyot",               "orange", 6),
    ("Матонат",            "Matonat",             "orange", 7),
    ("Куйлюк",             "Qo'yliq",             "orange", 8),
    ("Янгиобод",           "Yangiobod",           "orange", 9),
    ("Рохат",              "Rohat",               "orange",10),
    ("Олмос",              "Olmos",               "orange",11),
    ("Тузель",             "Tuzel",               "orange",12),
    ("Технопарк",          "Texnopark",           "orange",13),
]

# ─────────────────────────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    lang        TEXT NOT NULL DEFAULT 'ru',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vacancies (
    id          SERIAL PRIMARY KEY,
    name_ru     TEXT    NOT NULL,
    name_uz     TEXT    NOT NULL,
    emoji       TEXT    NOT NULL DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS blacklist (
    user_id     BIGINT PRIMARY KEY,
    blocked_at  TEXT,
    unblock_at  TEXT
);

CREATE TABLE IF NOT EXISTS metro_stations (
    id          SERIAL PRIMARY KEY,
    name_ru     TEXT    NOT NULL,
    name_uz     TEXT    NOT NULL,
    line        TEXT    NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS applications (
    id                SERIAL PRIMARY KEY,
    user_id           BIGINT  NOT NULL,
    name              TEXT,
    birthday          TEXT,
    phone             TEXT,
    position          TEXT,
    status            TEXT    NOT NULL DEFAULT 'pending',
    interview_time    TEXT,
    reminder_sent     INTEGER NOT NULL DEFAULT 0,
    view_count        INTEGER NOT NULL DEFAULT 0,
    notified_pending  INTEGER NOT NULL DEFAULT 0,
    hr_score          INTEGER,
    hr_comment        TEXT,
    hr_video_msg_id   INTEGER,
    experience        TEXT,
    metro_station_id  INTEGER,
    created_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id                    SERIAL PRIMARY KEY,
    user_id               BIGINT  NOT NULL,
    qa_log                TEXT    NOT NULL DEFAULT '[]',
    q_count               INTEGER NOT NULL DEFAULT 0,
    status                TEXT    NOT NULL DEFAULT 'active',
    report_resume         TEXT,
    report_communication  TEXT,
    report_integrity      TEXT,
    report_job_match      TEXT,
    report_decision       TEXT,
    report_summary        TEXT,
    total_score           DOUBLE PRECISION,
    report_skills         TEXT,
    report_personality    TEXT,
    created_at            TEXT    NOT NULL,
    finished_at           TEXT
);

CREATE INDEX IF NOT EXISTS ix_interview_sessions_user_id ON interview_sessions(user_id);
"""


def fix_sequences(pg_cur: psycopg2.extensions.cursor) -> None:
    """Синхронизирует SERIAL-последовательности после ручного INSERT с id."""
    for table, col in [("vacancies", "id"), ("applications", "id"), ("metro_stations", "id")]:
        pg_cur.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', '{col}'),
                COALESCE((SELECT MAX({col}) FROM {table}), 0) + 1,
                false
            )
        """)


def migrate(sqlite_path: str, pg_dsn: str) -> None:
    if not Path(sqlite_path).exists():
        raise SystemExit(f"❌  SQLite файл не найден: {sqlite_path}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Подключения ───────────────────────────────────────────────────────────
    sq = sqlite3.connect(sqlite_path)
    sq.row_factory = sqlite3.Row
    sc = sq.cursor()

    pg = psycopg2.connect(pg_dsn)
    pc = pg.cursor()

    print(f"✅  Подключено: SQLite={sqlite_path}  PostgreSQL=OK\n")

    # ── Схема ─────────────────────────────────────────────────────────────────
    pc.execute(DDL)
    print("✅  Схема PostgreSQL создана / уже существует")

    # ── users ─────────────────────────────────────────────────────────────────
    sc.execute("SELECT user_id, username, first_name, lang, created_at FROM users")
    rows = sc.fetchall()
    if rows:
        psycopg2.extras.execute_values(
            pc,
            """INSERT INTO users (user_id, username, first_name, lang, created_at)
               VALUES %s ON CONFLICT (user_id) DO NOTHING""",
            [(r["user_id"], r["username"], r["first_name"],
              r["lang"] or "ru", r["created_at"] or now)
             for r in rows],
        )
    print(f"✅  users          — {len(rows)} строк")

    # ── vacancies ─────────────────────────────────────────────────────────────
    sc.execute("SELECT id, name_ru, name_uz, emoji, is_active, sort_order, created_at FROM vacancies")
    rows = sc.fetchall()
    if rows:
        psycopg2.extras.execute_values(
            pc,
            """INSERT INTO vacancies (id, name_ru, name_uz, emoji, is_active, sort_order, created_at)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            [(r["id"], r["name_ru"], r["name_uz"], r["emoji"] or "",
              r["is_active"], r["sort_order"], r["created_at"])
             for r in rows],
        )
    existing_names = {r["name_ru"] for r in rows}
    # Кортеж: (name_ru, name_uz, emoji, sort_order, is_active, created_at)
    seed = [(n_ru, n_uz, em, order, 1, now)
            for n_ru, n_uz, em, order in DEFAULT_VACANCIES
            if n_ru not in existing_names]
    if seed:
        psycopg2.extras.execute_values(
            pc,
            "INSERT INTO vacancies (name_ru, name_uz, emoji, sort_order, is_active, created_at) VALUES %s",
            seed,
        )
        print(f"✅  vacancies      — {len(rows)} строк + досеяно {len(seed)}")
    else:
        print(f"✅  vacancies      — {len(rows)} строк")

    # ── blacklist ─────────────────────────────────────────────────────────────
    sc.execute("SELECT user_id, blocked_at, unblock_at FROM blacklist")
    rows = sc.fetchall()
    if rows:
        psycopg2.extras.execute_values(
            pc,
            """INSERT INTO blacklist (user_id, blocked_at, unblock_at)
               VALUES %s ON CONFLICT (user_id) DO NOTHING""",
            [(r["user_id"], r["blocked_at"], r["unblock_at"]) for r in rows],
        )
    print(f"✅  blacklist      — {len(rows)} строк")

    # ── metro_stations (seed, если таблица пустая) ────────────────────────────
    pc.execute("SELECT COUNT(*) FROM metro_stations")
    metro_count = pc.fetchone()[0]
    if metro_count == 0:
        psycopg2.extras.execute_values(
            pc,
            "INSERT INTO metro_stations (name_ru, name_uz, line, sort_order) VALUES %s",
            METRO_STATIONS,
        )
        print(f"✅  metro_stations — добавлено {len(METRO_STATIONS)} станций")
    else:
        print(f"⏭   metro_stations — уже есть {metro_count} записей, пропускаем")

    # ── applications ──────────────────────────────────────────────────────────
    sc.execute("""
        SELECT id, user_id, name, birthday, phone, position,
               status, interview_time, reminder_sent, view_count,
               notified_pending, hr_score, hr_comment, hr_video_msg_id,
               experience, created_at
        FROM applications
    """)
    rows = sc.fetchall()
    if rows:
        psycopg2.extras.execute_values(
            pc,
            """INSERT INTO applications
               (id, user_id, name, birthday, phone, position,
                status, interview_time, reminder_sent, view_count,
                notified_pending, hr_score, hr_comment, hr_video_msg_id,
                experience, metro_station_id, created_at)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            [(r["id"], r["user_id"], r["name"], r["birthday"], r["phone"],
              r["position"], r["status"] or "pending", r["interview_time"],
              r["reminder_sent"] or 0, r["view_count"] or 0,
              r["notified_pending"] or 0, r["hr_score"], r["hr_comment"],
              r["hr_video_msg_id"], r["experience"], None,
              r["created_at"] or now)
             for r in rows],
        )
    print(f"✅  applications   — {len(rows)} строк (metro_station_id=NULL)")

    # ── Синхронизируем SERIAL-sequences ──────────────────────────────────────
    fix_sequences(pc)
    print("✅  SERIAL sequences синхронизированы")

    pg.commit()
    sq.close()
    pg.close()

    print("\n🎉  Миграция завершена успешно!")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument(
        "--sqlite", default="database.db",
        help="Путь к SQLite файлу (default: database.db)",
    )
    parser.add_argument(
        "--pg",
        default="postgresql://postgres:password@localhost:5432/mado",
        help="DSN строка PostgreSQL",
    )
    args = parser.parse_args()
    migrate(args.sqlite, args.pg)
