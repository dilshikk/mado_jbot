# bot/ai/schemas.py
"""Pydantic-модели для ответов AI-агентов пайплайна.

Каждая модель точно соответствует JSON-схеме в prompts.py.
Все поля имеют разумные default-значения — ValidationError
никогда не прерывает пайплайн: _parse() возвращает fallback-объект
с полями-заглушками и error='validation_error'.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


# ── вспомогательные типы ──────────────────────────────────────────────────────

Severity  = Literal["low", "medium", "high"]
Verdict4  = Literal["excellent", "good", "acceptable", "poor"]
Verdict3  = Literal["recommended", "conditional", "not_recommended"]
Decision  = Literal["invite", "review", "reject", "needs_manual_review"]
Priority  = Literal["high", "medium", "low"]


# ═══════════════════════════════════════════════════════════════════════════════
# Уровень 2 — Resume Extractor
# ═══════════════════════════════════════════════════════════════════════════════

class CandidateInfo(BaseModel):
    name:             str = ""
    age:              int = 0
    gender:           str = ""
    position_applied: str = ""
    branch:           str = ""
    phone:            str = ""
    address:          str = ""
    citizenship:      str = ""


class JobEntry(BaseModel):
    company:          str        = ""
    role:             str        = ""
    duration:         str        = ""
    responsibilities: list[str]  = Field(default_factory=list)


class ExperienceInfo(BaseModel):
    total_years:         float      = 0.0
    has_restaurant_exp:  bool       = False
    jobs:                list[JobEntry] = Field(default_factory=list)


class SkillsInfo(BaseModel):
    hard: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)


class LanguageEntry(BaseModel):
    lang:  str = ""
    level: str = ""


class KeyAnswer(BaseModel):
    question: str = ""
    answer:   str = ""


class ResumeResult(BaseModel):
    candidate:          CandidateInfo = Field(default_factory=CandidateInfo)
    experience:         ExperienceInfo = Field(default_factory=ExperienceInfo)
    skills:             SkillsInfo     = Field(default_factory=SkillsInfo)
    languages:          list[LanguageEntry] = Field(default_factory=list)
    education:          str  = ""
    salary_expectation: str  = ""
    availability:       str  = ""
    key_answers:        list[KeyAnswer] = Field(default_factory=list)
    notes:              str  = ""
    confidence:         float = 0.0
    # служебные поля (добавляются пайплайном при ошибке)
    error:              str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Уровень 3а — Communication Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class ScoreWithEvidence(BaseModel):
    score:    float = 0.0
    evidence: str   = ""


class CommunicationScores(BaseModel):
    clarity:        ScoreWithEvidence = Field(default_factory=ScoreWithEvidence)
    friendliness:   ScoreWithEvidence = Field(default_factory=ScoreWithEvidence)
    confidence:     ScoreWithEvidence = Field(default_factory=ScoreWithEvidence)
    stress_response: ScoreWithEvidence = Field(default_factory=ScoreWithEvidence)
    motivation:     ScoreWithEvidence = Field(default_factory=ScoreWithEvidence)
    consistency:    ScoreWithEvidence = Field(default_factory=ScoreWithEvidence)


class CommunicationResult(BaseModel):
    scores:          CommunicationScores = Field(default_factory=CommunicationScores)
    overall_score:   float = 0.0
    guest_facing_fit: bool = False
    strengths:       list[str] = Field(default_factory=list)
    weaknesses:      list[str] = Field(default_factory=list)
    verdict:         Verdict4  = "acceptable"
    summary:         str  = ""
    confidence:      float = 0.0
    error:           str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Уровень 3б — Integrity
# ═══════════════════════════════════════════════════════════════════════════════

class Contradiction(BaseModel):
    topic:          str      = ""
    form_says:      str      = ""
    interview_says: str      = ""
    severity:       Severity = "low"
    note:           str      = ""


class RedFlag(BaseModel):
    type:           str      = ""
    evidence:       str      = ""
    severity:       Severity = "low"
    recommendation: str      = ""


class IntegrityResult(BaseModel):
    contradictions:    list[Contradiction] = Field(default_factory=list)
    red_flags:         list[RedFlag]       = Field(default_factory=list)
    unverified_skills: list[str]           = Field(default_factory=list)
    risk_level:        Severity   = "low"
    verdict:           str        = ""
    confidence:        float      = 0.0
    error:             str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Уровень 4 — Job Match
# ═══════════════════════════════════════════════════════════════════════════════

class ScoreWithComment(BaseModel):
    score:   float = 0.0
    comment: str   = ""


class JobMatchBreakdown(BaseModel):
    experience:    ScoreWithComment = Field(default_factory=ScoreWithComment)
    skills:        ScoreWithComment = Field(default_factory=ScoreWithComment)
    communication: ScoreWithComment = Field(default_factory=ScoreWithComment)
    integrity:     ScoreWithComment = Field(default_factory=ScoreWithComment)


class JobMatchResult(BaseModel):
    position:             str      = ""
    match_percent:        int      = 0
    breakdown:            JobMatchBreakdown = Field(default_factory=JobMatchBreakdown)
    meets:                list[str] = Field(default_factory=list)
    gaps:                 list[str] = Field(default_factory=list)
    conditions:           list[str] = Field(default_factory=list)
    alternative_position: str       = ""
    verdict:              Verdict3  = "conditional"
    summary:              str       = ""
    confidence:           float     = 0.0
    error:                str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Уровень 5 — Hiring Decision
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionScores(BaseModel):
    motivation:    ScoreWithComment = Field(default_factory=ScoreWithComment)
    experience:    ScoreWithComment = Field(default_factory=ScoreWithComment)
    communication: ScoreWithComment = Field(default_factory=ScoreWithComment)
    integrity:     ScoreWithComment = Field(default_factory=ScoreWithComment)


class DecisionResult(BaseModel):
    scores:           DecisionScores = Field(default_factory=DecisionScores)
    total_score:      float    = 0.0   # заполняется Python-кодом, не AI
    decision:         Decision = "review"
    priority:         Priority = "low"
    confidence:       float    = 0.0
    reasons:          list[str] = Field(default_factory=list)
    questions_for_hr: list[str] = Field(default_factory=list)
    strengths:        list[str] = Field(default_factory=list)
    concerns:         list[str] = Field(default_factory=list)
    onboarding_notes: str       = ""
    error:            str | None = None

    @model_validator(mode="after")
    def _clamp_total_score(self) -> "DecisionResult":
        """Гарантирует total_score в диапазоне [0, 10]."""
        self.total_score = max(0.0, min(10.0, self.total_score))
        return self


# ═══════════════════════════════════════════════════════════════════════════════
# Итоговый результат пайплайна
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineResult(BaseModel):
    resume:        ResumeResult
    communication: CommunicationResult
    integrity:     IntegrityResult
    job_match:     JobMatchResult
    decision:      DecisionResult
    total_score:   float | None = None
    status:        Literal["completed", "partial", "needs_manual_review"] = "completed"
    failed_agents: list[str] = Field(default_factory=list)
    summary:       str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Вспомогательная функция: безопасный парсинг
# ═══════════════════════════════════════════════════════════════════════════════

type _AgentModel = (
    ResumeResult
    | CommunicationResult
    | IntegrityResult
    | JobMatchResult
    | DecisionResult
)


def parse_agent_result(
    model_cls: type[_AgentModel],
    raw: dict[str, Any],
    agent_name: str,
) -> _AgentModel:
    """Валидирует raw-dict через Pydantic-модель.

    При ValidationError логирует предупреждение и возвращает
    экземпляр с дефолтными значениями + error='validation_error',
    чтобы пайплайн никогда не падал из-за неожиданного ответа модели.
    """
    from pydantic import ValidationError  # локальный import для скорости

    # Если вышестоящий код уже положил {"error": ...} — пробрасываем
    if "error" in raw:
        return model_cls.model_validate({"error": raw["error"]})

    try:
        return model_cls.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "parse_agent_result: %s — ValidationError (%d ошибок), "
            "используем defaults. raw_keys=%s",
            agent_name, exc.error_count(), list(raw.keys()),
        )
        return model_cls.model_validate({"error": "validation_error"})
