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
  gpt-5-mini — быстрые структурированные задачи (дешевле)
  gpt-5      — сложные задачи: диалог, логика, генерация текста
"""

GPT5       = "gpt-5"
GPT5_MINI  = "gpt-5-mini"

# ── Модели по агентам ─────────────────────────────────────────────────────────

# Уровень 1: Interview AI — живые вопросы, понимает контекст анкеты.
INTERVIEW_MODEL = GPT5_MINI

# Уровень 2: Resume Extractor AI — структурирует данные в JSON.
RESUME_MODEL = GPT5_MINI

# Уровень 3: Communication AI — оценивает стиль речи кандидата.
COMMUNICATION_MODEL = GPT5_MINI

# Уровень 3: Integrity AI — ищет противоречия между анкетой и ответами.
INTEGRITY_MODEL = GPT5_MINI

# Уровень 4: Job Match AI — сравнивает профиль кандидата с вакансией.
JOB_MATCH_MODEL = GPT5_MINI

# Уровень 5: Hiring Decision AI — итоговый отчёт для HR.
HIRING_DECISION_MODEL = GPT5

# ── Устаревшие алиасы (обратная совместимость) ───────────────────────────────
SCREENING_MODEL = GPT5
RESUME_MODEL_LEGACY = GPT5
SKILL_ANALYZER_MODEL = GPT5_MINI
HR_SUMMARY_MODEL = GPT5
LLAMA_70B = GPT5        # back-compat
LLAMA_8B = GPT5_MINI    # back-compat
MISTRAL_7B = GPT5_MINI  # back-compat
