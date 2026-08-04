# bot/services/ai.py
"""Обратно совместимая обёртка — делегирует в bot/ai/.

Старые импорты вида `from bot.services.ai import screen_application`
продолжают работать без изменений.
"""

from bot.ai.resume import screen_application

__all__ = ["screen_application"]
