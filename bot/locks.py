# bot/locks.py
"""Реестры asyncio.Lock для защиты от TOCTOU-гонок.

aiogram запускается в одном event-loop, поэтому process-local asyncio.Lock
достаточно для сериализации критических секций внутри одного процесса
(Telegram никогда не доставляет update-ы из одного чата параллельно).

Использование::

    async with submission_lock(user_id):
        # проверка статуса + INSERT -- атомарно

    async with interview_lock(session_id):
        # проверка report_decision + run_all_agents -- атомарно
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

# Для подачи анкеты: ключ — user_id
_submission_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# Для финиша интервью: ключ — interview_session_id
_interview_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def submission_lock(user_id: int) -> asyncio.Lock:
    """Возвращает лок для данного user_id.

    Обеспечивает атомарность проверки-статуса + сохранения анкеты.
    """
    return _submission_locks[user_id]


def interview_lock(session_id: int) -> asyncio.Lock:
    """Возвращает лок для данной interview_session_id.

    Обеспечивает атомарность проверки-report_decision + run_all_agents.
    """
    return _interview_locks[session_id]
