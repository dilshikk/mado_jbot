from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    """Состояния анкеты кандидата."""
    waiting_for_lang     = State()
    waiting_branch       = State()
    waiting_position     = State()
    waiting_name         = State()
    waiting_birthday     = State()
    waiting_gender       = State()
    waiting_address      = State()
    waiting_metro        = State()
    waiting_citizenship  = State()
    waiting_languages    = State()
    waiting_phone        = State()

    # Опыт работы — сначала "Есть ли опыт?"
    waiting_experience   = State()
    # Под-шаги опыта (только если ответил "Да")
    waiting_exp_company  = State()
    waiting_exp_position = State()
    waiting_exp_duration = State()
    waiting_exp_duties   = State()

    # Условия работы
    waiting_readiness      = State()
    waiting_salary         = State()
    waiting_schedule       = State()
    waiting_evening_shifts = State()
    waiting_weekends       = State()
    waiting_smoking        = State()
    waiting_med_book       = State()

    # Контакты и медиа
    waiting_photo        = State()
    waiting_video        = State()
    waiting_confirmation = State()
