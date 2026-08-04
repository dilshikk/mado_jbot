# bot/ai/models.py
"""Выбор AI-моделей Cloudflare Workers AI."""

# Python 3.10 не имеет StrEnum (появился в 3.11).
# Используем простые строковые константы.

LLAMA_70B  = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
LLAMA_8B   = "@cf/meta/llama-3.1-8b-instruct"
MISTRAL_7B = "@cf/mistral/mistral-7b-instruct-v0.2"

# Модели по умолчанию для каждой задачи
SCREENING_MODEL = LLAMA_70B
RESUME_MODEL    = LLAMA_70B
INTERVIEW_MODEL = LLAMA_8B
