# bot/states/user_forms.py

from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    """Состояния анкеты кандидата."""
    waiting_for_lang     = State()
    waiting_branch       = State()
    waiting_position     = State()
    waiting_name         = State()
    waiting_birthday     = State()
    waiting_gender       = State()
    waiting_family       = State()
    waiting_citizenship  = State()
    waiting_address      = State()
    waiting_experience   = State()
    waiting_phone        = State()
    waiting_video        = State()
    waiting_confirmation = State()
