# bot/states/admin_states.py

from aiogram.fsm.state import State, StatesGroup


class HRReview(StatesGroup):
    """Состояния HR при рассмотрении анкеты."""
    waiting_for_interview_details = State()


class HRScore(StatesGroup):
    """Состояния HR при выставлении оценки."""
    waiting_for_comment = State()


class Broadcast(StatesGroup):
    """Состояния мастера рассылки."""
    waiting_photo     = State()
    waiting_caption   = State()
    waiting_url       = State()
    waiting_url_title = State()
    preview           = State()
    sending           = State()


class AddVacancy(StatesGroup):
    """Состояния добавления вакансии."""
    waiting_name_ru = State()
    waiting_name_uz = State()
    waiting_emoji   = State()


class DashboardFilter(StatesGroup):
    """Состояния фильтров HR-дашборда."""
    waiting_position_filter = State()
    waiting_date_from       = State()
