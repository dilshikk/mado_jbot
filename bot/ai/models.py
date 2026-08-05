# bot/ai/models.py
"""Выбор AI-моделей Cloudflare Workers AI.

5-уровневый пайплайн оценки кандидата:
  Уровень 1 — Interview AI            (bot/ai/interview.py)
  Уровень 2 — Resume Extractor AI     (1 запрос, JSON-структура)
  Уровень 3 — Communication AI        (параллельно с Integrity AI)
              Integrity AI             (параллельно с Communication AI)
  Уровень 4 — Job Match AI            (видит уровни 2+3)
  Уровень 5 — Hiring Decision AI      (видит всё)

Выбор размера модели:
  70B — задачи, требующие глубокого понимания, логики или генерации текста
  8B  — структурированный анализ по готовым данным (быстрее, дешевле)
"""

# Python 3.10 не имеет StrEnum (появился в 3.11).
# Используем простые строковые константы.

LLAMA_70B  = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
LLAMA_8B   = "@cf/meta/llama-3.1-8b-instruct"
MISTRAL_7B = "@cf/mistral/mistral-7b-instruct-v0.2"

# ── Модели по агентам ─────────────────────────────────────────────────────────

# Уровень 1: Interview AI — генерирует живые вопросы, понимает контекст анкеты.
# Требует мощной модели для естественного диалога.
INTERVIEW_MODEL = LLAMA_70B

# Уровень 2: Resume Extractor AI — структурирует данные анкеты и интервью.
# Требует качественной генерации структурированного JSON.
RESUME_MODEL = LLAMA_70B

# Уровень 3: Communication AI — оценивает стиль речи и коммуникации кандидата.
# Анализ по готовым данным, 8B достаточно.
COMMUNICATION_MODEL = LLAMA_8B

# Уровень 3: Integrity AI — ищет противоречия между анкетой и ответами.
# Требует сильной логики → 70B.
INTEGRITY_MODEL = LLAMA_70B

# Уровень 4: Job Match AI — сравнивает профиль кандидата с вакансией.
# Структурированное сравнение, 8B достаточно.
JOB_MATCH_MODEL = LLAMA_8B

# Уровень 5: Hiring Decision AI — формирует итоговый отчёт для HR.
# Должен быть качественным и убедительным → 70B.
HIRING_DECISION_MODEL = LLAMA_70B

# ── Устаревшие алиасы (обратная совместимость) ───────────────────────────────
SCREENING_MODEL = LLAMA_70B
RESUME_MODEL_LEGACY = LLAMA_70B  # был RESUME_MODEL в bot/ai/resume.py
SKILL_ANALYZER_MODEL = LLAMA_8B
HR_SUMMARY_MODEL = LLAMA_70B
