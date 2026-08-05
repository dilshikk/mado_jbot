"""
AI-агенты оценки кандидатов.

Самодостаточный модуль: четыре агента анализируют анкету, резюме
и ответы кандидата на интервью и формируют структурированный отчёт.

Агенты:
- FraudDetectorAI    — выявляет противоречия в ответах кандидата;
- LanguageQualityAI  — оценивает грамотность и понятность письменных ответов;
- RedFlagAI          — отмечает потенциальные риски, опираясь только
                       на факты из анкеты и интервью;
- InterviewScoreAI   — ставит итоговые оценки по критериям (мотивация,
                       опыт, коммуникация, соответствие вакансии)
                       и формирует общий балл.

Использование:

    from bot.ai.screening import ScreeningPipeline

    pipeline = ScreeningPipeline()
    report = await pipeline.run(
        vacancy_text="описание вакансии",
        resume_text="анкета / резюме кандидата",
        interview_answers="вопросы и ответы интервью",
    )
    print(report.to_dict())

Переменные окружения:
    OPENAI_API_KEY  — ключ OpenAI (обязательно)
    OPENAI_MODEL    — модель (по умолчанию gpt-5-mini)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")


# ---------------------------------------------------------------------------
# Базовый агент
# ---------------------------------------------------------------------------


@dataclass
class AgentContext:
    """Данные, с которыми работают агенты."""

    vacancy_text: str
    resume_text: str
    interview_answers: str


class BaseAgent:
    """Общая логика вызова LLM и разбора JSON-ответа."""

    name: str = "base"
    system_prompt: str = ""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def build_user_payload(self, context: AgentContext) -> str:
        return (
            f"ВАКАНСИЯ:\n{context.vacancy_text}\n\n"
            f"АНКЕТА / РЕЗЮМЕ КАНДИДАТА:\n{context.resume_text}\n\n"
            f"ОТВЕТЫ НА ИНТЕРВЬЮ:\n{context.interview_answers}"
        )

    async def analyze(self, context: AgentContext) -> dict[str, Any]:
        """Запросить у модели структурированный JSON-отчёт."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": self.build_user_payload(context)},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("%s: модель вернула невалидный JSON", self.name)
            return {"error": "invalid_json", "agent": self.name}
        except Exception:
            logger.exception("%s: ошибка при обращении к модели", self.name)
            return {"error": "llm_request_failed", "agent": self.name}


# ---------------------------------------------------------------------------
# Агент 1. Fraud Detector AI
# ---------------------------------------------------------------------------


class FraudDetectorAI(BaseAgent):
    """Выявляет противоречия в ответах кандидата."""

    name = "fraud_detector"
    system_prompt = """Ты — Fraud Detector AI, аналитик по выявлению противоречий \
в ответах кандидата.

Твоя задача — сопоставить анкету/резюме кандидата с его ответами на интервью \
и найти противоречия, например:
- расхождения в датах, должностях, стаже и обязанностях;
- разные версии одного и того же события;
- заявленные навыки, которые кандидат не смог подтвердить на интервью;
- уклончивые или взаимоисключающие ответы.

Опирайся только на приведённые тексты. Не додумывай факты.

Ответь строго JSON-объектом:
{
  "contradictions": [
    {
      "topic": "о чём противоречие",
      "resume_says": "что указано в анкете/резюме",
      "interview_says": "что сказано на интервью",
      "severity": "low | medium | high"
    }
  ],
  "risk_level": "low | medium | high",
  "verdict": "краткий вывод в 1-2 предложениях"
}

Если противоречий нет — верни пустой список contradictions и risk_level \"low\"."""


# ---------------------------------------------------------------------------
# Агент 2. Language Quality AI
# ---------------------------------------------------------------------------


class LanguageQualityAI(BaseAgent):
    """Оценивает грамотность и понятность письменных ответов."""

    name = "language_quality"
    system_prompt = """Ты — Language Quality AI, эксперт по оценке качества \
письменной речи кандидата.

Оцени письменные ответы кандидата по критериям:
- грамотность (орфография, пунктуация, грамматика);
- понятность и структурированность изложения;
- уместность стиля для деловой коммуникации.

Оценивай только письменные ответы кандидата. Если ответы слишком короткие \
для оценки — честно укажи это в comment.

Ответь строго JSON-объектом:
{
  "grammar_score": <число 1-10>,
  "clarity_score": <число 1-10>,
  "style_score": <число 1-10>,
  "overall_score": <среднее, число 1-10>,
  "verdict": "excellent | good | acceptable | poor",
  "comment": "краткий комментарий с примерами ошибок, если они есть"
}"""


# ---------------------------------------------------------------------------
# Агент 3. Red Flag AI
# ---------------------------------------------------------------------------


class RedFlagAI(BaseAgent):
    """Отмечает потенциальные риски на основе фактов из анкеты и интервью."""

    name = "red_flag"
    system_prompt = """Ты — Red Flag AI, аналитик кадровых рисков.

Твоя задача — отметить потенциальные риски по кандидату, например:
- частая смена мест работы без объяснимых причин;
- длительные перерывы в стаже;
- явные несоответствия опыта требованиям вакансии;
- противоречивые или расплывчатые ответы на ключевые вопросы.

Правила:
- Опирайся ТОЛЬКО на факты из анкеты и ответов на интервью.
- Не делай предположений о личных качествах, возрасте, семье и т.п.
- Каждый флаг должен содержать конкретное доказательство из текста.

Ответь строго JSON-объектом:
{
  "flags": [
    {
      "type": "тип риска (например, frequent_job_changes)",
      "evidence": "цитата или факт из анкеты/интервью",
      "severity": "low | medium | high",
      "comment": "почему это риск"
    }
  ],
  "risk_level": "low | medium | high",
  "verdict": "краткий вывод в 1-2 предложениях"
}

Если рисков нет — верни пустой список flags и risk_level \"low\"."""


# ---------------------------------------------------------------------------
# Агент 4. Interview Score AI
# ---------------------------------------------------------------------------


class InterviewScoreAI(BaseAgent):
    """Формирует итоговую оценку кандидата по критериям и общий балл."""

    name = "interview_score"
    system_prompt = """Ты — Interview Score AI, система итоговой оценки кандидата.

Оцени кандидата по четырём критериям (каждый от 1 до 10):
- motivation    — мотивация и заинтересованность в вакансии;
- experience    — релевантный опыт и подтверждённые навыки;
- communication — качество коммуникации в интервью;
- vacancy_fit   — общее соответствие требованиям вакансии.

Также учитывай отчёты других агентов (противоречия, риски, качество речи), \
если они приложены.

Ответь строго JSON-объектом:
{
  "criteria": {
    "motivation":    {"score": <1-10>, "comment": "обоснование"},
    "experience":    {"score": <1-10>, "comment": "обоснование"},
    "communication": {"score": <1-10>, "comment": "обоснование"},
    "vacancy_fit":   {"score": <1-10>, "comment": "обоснование"}
  },
  "total_score": <среднее по критериям, число 1-10>,
  "recommendation": "strong_yes | yes | maybe | no",
  "summary": "итоговое резюме по кандидату в 2-3 предложениях"
}"""

    def build_user_payload(self, context: AgentContext) -> str:
        base = super().build_user_payload(context)
        if self.extra_reports:
            reports = json.dumps(self.extra_reports, ensure_ascii=False, indent=2)
            return f"{base}\n\nОТЧЁТЫ ДРУГИХ АГЕНТОВ:\n{reports}"
        return base

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        extra_reports: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(client, model)
        self.extra_reports = extra_reports


# ---------------------------------------------------------------------------
# Оркестратор
# ---------------------------------------------------------------------------


@dataclass
class ScreeningReport:
    """Сводный отчёт по кандидату от всех агентов."""

    fraud: dict[str, Any] = field(default_factory=dict)
    language: Optional[dict[str, Any]] = None
    red_flags: dict[str, Any] = field(default_factory=dict)
    score: dict[str, Any] = field(default_factory=dict)

    @property
    def total_score(self) -> Optional[float]:
        value = self.score.get("total_score")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def recommendation(self) -> Optional[str]:
        value = self.score.get("recommendation")
        return str(value) if value else None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScreeningPipeline:
    """Запускает четырёх агентов и собирает сводный отчёт.

    Fraud Detector, Language Quality и Red Flag работают параллельно,
    Interview Score — в конце, с учётом их результатов.
    """

    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        model: str = DEFAULT_MODEL,
        check_language: bool = True,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._model = model
        # Оценка грамотности нужна не для всех вакансий
        self._check_language = check_language

    async def run(
        self,
        vacancy_text: str,
        resume_text: str,
        interview_answers: str,
    ) -> ScreeningReport:
        context = AgentContext(
            vacancy_text=vacancy_text,
            resume_text=resume_text,
            interview_answers=interview_answers,
        )

        tasks = [
            FraudDetectorAI(self._client, self._model).analyze(context),
            RedFlagAI(self._client, self._model).analyze(context),
        ]
        if self._check_language:
            tasks.append(
                LanguageQualityAI(self._client, self._model).analyze(context)
            )

        results = await asyncio.gather(*tasks)
        fraud_report = results[0]
        red_flag_report = results[1]
        language_report = results[2] if self._check_language else None

        extra_reports: dict[str, Any] = {
            "fraud_detector": fraud_report,
            "red_flag": red_flag_report,
        }
        if language_report is not None:
            extra_reports["language_quality"] = language_report

        score_report = await InterviewScoreAI(
            self._client,
            self._model,
            extra_reports=extra_reports,
        ).analyze(context)

        return ScreeningReport(
            fraud=fraud_report,
            language=language_report,
            red_flags=red_flag_report,
            score=score_report,
        )
