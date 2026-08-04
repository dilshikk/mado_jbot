# bot/states/interview.py

from aiogram.fsm.state import State, StatesGroup


class Interview(StatesGroup):
    """Состояния AI-интервью кандидата."""
    answering = State()   # ждём ответ на текущий вопрос
