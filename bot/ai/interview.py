# bot/ai/interview.py
"""Recruiter AI — диалоговое интервью с кандидатом.

Вопросы адаптируются под вакансию кандидата.
"""

import ast
import json
import logging
import re

from bot.ai.client import cf_chat
from bot.ai.models import INTERVIEW_MODEL
from bot.ai.prompts import INTERVIEW_SYSTEM

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 10
MIN_QUESTIONS = 5

# ─── Темы и примеры вопросов по вакансиям ────────────────────────────────────
# Ключи — фрагменты названия вакансии (lowercase).
# При совпадении — вставляем в системный промпт контекст вакансии.

_VACANCY_INTERVIEW_CONTEXT: list[tuple[list[str], str]] = [
    (
        ["официант", "ofitsiant", "waiter"],
        (
            "Темы интервью: работа с гостями, клиентоориентированность, продажи, "
            "командная работа, стрессоустойчивость, работа в часы пик.\n"
            "Примеры вопросов:\n"
            "- Почему вы выбрали профессию официанта?\n"
            "- Что для вас означает хороший сервис?\n"
            "- Как поступите, если гость недоволен?\n"
            "- Как будете работать при полной посадке ресторана?\n"
            "- Как предложите гостю дополнительные блюда или напитки?\n"
        ),
    ),
    (
        ["повар", "oshpaz", "cook"],
        (
            "Темы интервью: опыт приготовления, санитарные нормы, технологические карты, "
            "скорость приготовления, работа в команде, организация рабочего места.\n"
            "Примеры вопросов:\n"
            "- Какие блюда вы готовите лучше всего?\n"
            "- Работали ли вы по технологическим картам?\n"
            "- Как организуете рабочее место?\n"
            "- Что будете делать при большом количестве заказов?\n"
            "- Как контролируете качество блюд?\n"
        ),
    ),
    (
        ["бариста", "barista"],
        (
            "Темы интервью: приготовление кофе, работа с кофемашиной, продажа напитков, "
            "общение с гостями, скорость обслуживания.\n"
            "Примеры вопросов:\n"
            "- Есть ли опыт приготовления кофейных напитков?\n"
            "- Какие напитки умеете готовить?\n"
            "- Что сделаете, если гость попросит напиток, которого нет в меню?\n"
            "- Как обслуживаете очередь в часы пик?\n"
            "- Что для вас хороший сервис?\n"
        ),
    ),
    (
        ["кондитер", "confectioner", "pastry"],
        (
            "Темы интервью: выпечка, десерты, украшение изделий, соблюдение рецептуры, "
            "организация рабочего места.\n"
            "Примеры вопросов:\n"
            "- Какие десерты готовите лучше всего?\n"
            "- Работали ли по технологическим картам?\n"
            "- Как контролируете качество изделий?\n"
            "- Какие виды теста умеете готовить?\n"
            "- Как организуете своё рабочее место?\n"
        ),
    ),
    (
        ["администратор", "administrator", "manager", "менеджер"],
        (
            "Темы интервью: управление сменой, работа с персоналом, конфликтные ситуации, "
            "работа с гостями, ответственность, лидерские качества.\n"
            "Примеры вопросов:\n"
            "- Был ли опыт управления коллективом?\n"
            "- Как решаете конфликтные ситуации?\n"
            "- Как мотивируете сотрудников?\n"
            "- Что будете делать при жалобе гостя?\n"
            "- Что для вас означает хороший руководитель?\n"
        ),
    ),
    (
        ["уборщик", "уборщица", "тех. персонал", "texnik xodim", "cleaner"],
        (
            "Темы интервью: аккуратность, ответственность, санитарные требования, "
            "скорость работы.\n"
            "Примеры вопросов:\n"
            "- Есть ли опыт уборки помещений?\n"
            "- Как поддерживаете чистоту в течение дня?\n"
            "- Что будете делать при обнаружении загрязнения в зале?\n"
            "- Как относитесь к санитарным требованиям?\n"
        ),
    ),
    (
        ["раннер", "yuguruvchi", "runner"],
        (
            "Темы интервью: скорость работы, работа в команде, внимательность, "
            "ответственность.\n"
            "Примеры вопросов:\n"
            "- Работали ли в ресторане?\n"
            "- Как будете действовать при большом количестве заказов?\n"
            "- Что важнее: скорость или внимательность?\n"
            "- Как взаимодействуете с официантами и кухней?\n"
        ),
    ),
    (
        ["хостес", "hostess", "хостесс"],
        (
            "Темы интервью: встреча гостей, коммуникабельность, работа с бронированиями, "
            "стрессоустойчивость, внешний вид, грамотная речь.\n"
            "Примеры вопросов:\n"
            "- Есть ли опыт встречи гостей?\n"
            "- Что будете делать, если свободных столиков нет?\n"
            "- Как встретите VIP-гостя?\n"
            "- Что для вас означает высокий уровень сервиса?\n"
        ),
    ),
    (
        ["кассир", "kassir", "cashier"],
        (
            "Темы интервью: работа с кассой, внимательность, ответственность, "
            "денежная дисциплина, работа с гостями.\n"
            "Примеры вопросов:\n"
            "- Работали ли с кассовым оборудованием?\n"
            "- Что будете делать при обнаружении ошибки в расчётах?\n"
            "- Как поступите, если гость не согласен с чеком?\n"
            "- Как проверяете правильность расчётов?\n"
        ),
    ),
]

# Универсальный контекст — когда вакансия не совпала ни с одним шаблоном
_DEFAULT_VACANCY_CONTEXT = (
    "Темы интервью: мотивация работать в MADO, опыт работы, работа с гостями, "
    "командная работа, стрессовые ситуации, карьерные цели.\n"
)


def _get_vacancy_context(position: str) -> str:
    """Возвращает контекст интервью для конкретной вакансии."""
    pos_lower = position.lower()
    for keywords, context in _VACANCY_INTERVIEW_CONTEXT:
        if any(kw in pos_lower for kw in keywords):
            return context
    return _DEFAULT_VACANCY_CONTEXT


def _extract_text(result: dict) -> str:
    """Извлекает текст ответа из структуры CF API."""
    inner = (result.get("result") or {}).get("response") or ""
    if isinstance(inner, dict):
        inner = inner.get("content") or inner.get("text") or str(inner)
    return str(inner).strip()


def _parse_step(raw: str) -> dict | None:
    """Пробует распарсить JSON или Python-dict из строки ответа модели."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    candidate = match.group()
    try:
        parsed = json.loads(candidate)
        if "done" in parsed:
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        parsed = ast.literal_eval(candidate)
        if isinstance(parsed, dict) and "done" in parsed:
            return parsed
    except (ValueError, SyntaxError):
        pass
    return None


def _build_messages(form_data: dict, qa_log: list[dict], lang: str) -> list[dict]:
    lang_hint       = "Общайся на русском языке." if lang == "ru" else "O'zbek tilida gaplash."
    position        = form_data.get("position", "—")
    vacancy_context = _get_vacancy_context(str(position))

    # Поля анкеты, которые уже известны — AI не должен их спрашивать повторно
    known_fields = []
    field_map = [
        ("name",          "ФИО"),
        ("birthday",      "Дата рождения"),
        ("gender",        "Пол"),
        ("phone",         "Телефон"),
        ("metro",         "Метро"),
        ("languages",     "Языки"),
        ("readiness",     "Готовность к работе"),
        ("experience",    "Опыт"),
        ("exp_company",   "Место работы"),
        ("exp_position",  "Должность в прошлом"),
        ("exp_duration",  "Стаж"),
        ("salary",        "Зарплатные ожидания"),
        ("schedule",      "График"),
        ("evening_shifts","Вечерние смены"),
        ("weekends",      "Выходные"),
        ("smoking",       "Курение"),
        ("med_book",      "Медкнижка"),
    ]
    for key, label in field_map:
        val = form_data.get(key)
        if val and val != "—":
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            known_fields.append(f"  {label}: {val}")

    known_section = "\n".join(known_fields) if known_fields else "  (нет данных)"

    context = (
        f"Язык кандидата: {lang_hint}\n"
        f"Вакансия: {position}\n"
        f"\n--- ДАННЫЕ ИЗ АНКЕТЫ (не задавай эти вопросы повторно) ---\n"
        f"{known_section}\n"
        f"---\n"
        f"\n--- ТЕМЫ И ВОПРОСЫ ДЛЯ ДАННОЙ ВАКАНСИИ ---\n"
        f"{vacancy_context}"
        f"---\n"
        f"\nВопросов задано: {len(qa_log)}. Минимум: {MIN_QUESTIONS}, максимум: {MAX_QUESTIONS}\n"
        f"Не задавай повторных вопросов. Анализируй каждый ответ и задавай уточняющие вопросы при необходимости.\n"
    )
    messages: list[dict] = [
        {"role": "system", "content": f"{INTERVIEW_SYSTEM}\n\n{context}"},
    ]
    for entry in qa_log:
        messages.append({"role": "assistant", "content": entry["q"]})
        messages.append({"role": "user",      "content": entry["a"]})
    return messages


async def get_next_step(
    form_data: dict,
    qa_log: list[dict],
    lang: str,
) -> dict:
    """Возвращает следующий шаг интервью."""
    if len(qa_log) >= MAX_QUESTIONS:
        return {"done": True, "reason": f"Достигнут лимит {MAX_QUESTIONS} вопросов"}

    messages = _build_messages(form_data, qa_log, lang)
    result = await cf_chat(model=INTERVIEW_MODEL, messages=messages, max_tokens=300)

    if result is None:
        logger.warning("cf_chat вернул None — интервью завершается")
        return {"done": True, "reason": "AI недоступен"}

    raw = _extract_text(result)
    logger.debug("CF raw ответ (интервью): %r", raw[:300] if raw else "<пусто>")

    if not raw:
        return {"done": True, "reason": "Пустой ответ AI"}

    parsed = _parse_step(raw)
    if parsed is not None:
        done = parsed.get("done", False)
        if done:
            return {"done": True, "reason": parsed.get("reason", "AI завершил интервью")}
        question = parsed.get("question", "").strip()
        if question:
            return {"done": False, "question": question}

    return {"done": False, "question": raw}
