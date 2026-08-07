# bot/ai/models.py
"""Выбор AI-моделей OpenAI.

5-уровневый пайплайн оценки кандидата:
  Уровень 1 — Interview AI            (bot/ai/interview.py)
  Уровень 2 — Resume Extractor AI     (1 запрос, JSON-структура)
  Уровень 3 — Communication AI        (параллельно с Integrity AI)
              Integrity AI             (параллельно с Communication AI)
  Уровень 4 — Job Match AI            (видит уровни 2+3)
  Уровень 5 — Hiring Decision AI      (видит всё)

Выбор модели:
  gpt-4o-mini — быстрые структурированные задачи (дешевле)
  gpt-4o      — сложные задачи: диалог, логика, генерация текста
"""

GPT4O       = "gpt-4o"
GPT4O_MINI  = "gpt-4o-mini"

# ── Модели по агентам ─────────────────────────────────────────────────────────

# Уровень 1: Interview AI — живые вопросы, понимает контекст анкеты.
INTERVIEW_MODEL = GPT4O_MINI

# Уровень 2: Resume Extractor AI — структурирует данные в JSON.
RESUME_MODEL = GPT4O_MINI

# Уровень 3: Communication AI — оценивает стиль речи кандидата.
COMMUNICATION_MODEL = GPT4O_MINI

# Уровень 3: Integrity AI — ищет противоречия между анкетой и ответами.
INTEGRITY_MODEL = GPT4O_MINI

# Уровень 4: Job Match AI — сравнивает профиль кандидата с вакансией.
JOB_MATCH_MODEL = GPT4O_MINI

# Уровень 5: Hiring Decision AI — итоговый отчёт для HR.
HIRING_DECISION_MODEL = GPT4O

# ── Устаревшие алиасы (обратная совместимость) ───────────────────────────────
SCREENING_MODEL = GPT4O
RESUME_MODEL_LEGACY = GPT4O
SKILL_ANALYZER_MODEL = GPT4O_MINI
HR_SUMMARY_MODEL = GPT4O
LLAMA_70B = GPT4O        # back-compat если где-то импортируется напрямую
LLAMA_8B = GPT4O_MINI    # back-compat
MISTRAL_7B = GPT4O_MINI  # back-compat
