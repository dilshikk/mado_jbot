# bot/ai/models.py
"""Выбор AI-моделей Cloudflare Workers AI."""

from enum import StrEnum


class CFModel(StrEnum):
    """Доступные модели Cloudflare Workers AI."""

    LLAMA_70B   = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    LLAMA_8B    = "@cf/meta/llama-3.1-8b-instruct"
    MISTRAL_7B  = "@cf/mistral/mistral-7b-instruct-v0.2"


# Модели по умолчанию для каждой задачи
SCREENING_MODEL = CFModel.LLAMA_70B
RESUME_MODEL    = CFModel.LLAMA_70B
INTERVIEW_MODEL = CFModel.LLAMA_8B
