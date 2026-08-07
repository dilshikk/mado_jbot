# bot/ai/schemas.py
"""JSON Schema definitions for OpenAI Structured Outputs (Responses API).

Agents with well-defined static output use json_schema + strict=True.
Resume and Integrity agents use json_object (dynamic keys / nested arrays).
Interview agent uses json_object (competency_status has dynamic keys).
"""

from __future__ import annotations

# ── helpers ───────────────────────────────────────────────────────────────────


def _schema_format(name: str, schema: dict) -> dict:
    """Builds a Responses-API text.format dict for a named JSON schema."""
    return {
        "type": "json_schema",
        "name": name,
        "strict": True,
        "schema": schema,
    }


# Re-usable for agents that don't have a strict schema
JSON_OBJECT_FORMAT: dict = {"type": "json_object"}

# ── sub-schema building blocks ────────────────────────────────────────────────


def _scored_criterion() -> dict:
    return {
        "type": "object",
        "properties": {
            "score":    {"type": "integer"},
            "evidence": {"type": "string"},
        },
        "required": ["score", "evidence"],
        "additionalProperties": False,
    }


def _breakdown_item() -> dict:
    return {
        "type": "object",
        "properties": {
            "score":   {"type": "integer"},
            "comment": {"type": "string"},
        },
        "required": ["score", "comment"],
        "additionalProperties": False,
    }


# ── Communication AI ──────────────────────────────────────────────────────────

_COMMUNICATION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": {
                "clarity":         _scored_criterion(),
                "friendliness":    _scored_criterion(),
                "confidence":      _scored_criterion(),
                "stress_response": _scored_criterion(),
                "motivation":      _scored_criterion(),
                "consistency":     _scored_criterion(),
            },
            "required": ["clarity", "friendliness", "confidence",
                         "stress_response", "motivation", "consistency"],
            "additionalProperties": False,
        },
        "overall_score":    {"type": "number"},
        "guest_facing_fit": {"type": "boolean"},
        "strengths":        {"type": "array", "items": {"type": "string"}},
        "weaknesses":       {"type": "array", "items": {"type": "string"}},
        "verdict":          {"type": "string",
                             "enum": ["excellent", "good", "acceptable", "poor"]},
        "summary":          {"type": "string"},
        "confidence":       {"type": "number"},
    },
    "required": ["scores", "overall_score", "guest_facing_fit",
                 "strengths", "weaknesses", "verdict", "summary", "confidence"],
    "additionalProperties": False,
}

COMMUNICATION_FORMAT = _schema_format("communication_result", _COMMUNICATION_SCHEMA)

# ── Job Match AI ──────────────────────────────────────────────────────────────

_JOB_MATCH_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "position":            {"type": "string"},
        "match_percent":       {"type": "integer"},
        "breakdown": {
            "type": "object",
            "properties": {
                "experience":    _breakdown_item(),
                "skills":        _breakdown_item(),
                "communication": _breakdown_item(),
                "integrity":     _breakdown_item(),
            },
            "required": ["experience", "skills", "communication", "integrity"],
            "additionalProperties": False,
        },
        "meets":               {"type": "array", "items": {"type": "string"}},
        "gaps":                {"type": "array", "items": {"type": "string"}},
        "conditions":          {"type": "array", "items": {"type": "string"}},
        "alternative_position": {"type": "string"},
        "verdict":             {"type": "string",
                                "enum": ["recommended", "conditional", "not_recommended"]},
        "summary":             {"type": "string"},
        "confidence":          {"type": "number"},
    },
    "required": ["position", "match_percent", "breakdown", "meets", "gaps",
                 "conditions", "alternative_position", "verdict", "summary", "confidence"],
    "additionalProperties": False,
}

JOB_MATCH_FORMAT = _schema_format("job_match_result", _JOB_MATCH_SCHEMA)

# ── Hiring Decision AI ────────────────────────────────────────────────────────

_HIRING_DECISION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": {
                "motivation":    _breakdown_item(),
                "experience":    _breakdown_item(),
                "communication": _breakdown_item(),
                "integrity":     _breakdown_item(),
            },
            "required": ["motivation", "experience", "communication", "integrity"],
            "additionalProperties": False,
        },
        "total_score":      {"type": "number"},
        "decision":         {"type": "string",
                             "enum": ["invite", "review", "reject"]},
        "priority":         {"type": "string",
                             "enum": ["high", "medium", "low"]},
        "confidence":       {"type": "number"},
        "reasons":          {"type": "array", "items": {"type": "string"}},
        "questions_for_hr": {"type": "array", "items": {"type": "string"}},
        "strengths":        {"type": "array", "items": {"type": "string"}},
        "concerns":         {"type": "array", "items": {"type": "string"}},
        "onboarding_notes": {"type": "string"},
    },
    "required": ["scores", "total_score", "decision", "priority", "confidence",
                 "reasons", "questions_for_hr", "strengths", "concerns", "onboarding_notes"],
    "additionalProperties": False,
}

HIRING_DECISION_FORMAT = _schema_format("hiring_decision_result", _HIRING_DECISION_SCHEMA)
