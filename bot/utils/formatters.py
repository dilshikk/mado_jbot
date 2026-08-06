# bot/utils/formatters.py

from typing import Any

from bot.lexicon import LOCALIZATION

_NONE_PLACEHOLDER = "—"


def _field(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else _NONE_PLACEHOLDER
    return str(value) if value is not None else _NONE_PLACEHOLDER


def _metro(data: dict[str, Any], lang: str = "ru") -> str:
    """Возвращает название станции метро из FSM-данных."""
    name = data.get("metro_name") or data.get("metro")
    return str(name) if name else _NONE_PLACEHOLDER


def _languages_text(data: dict[str, Any], lang: str) -> str:
    """Возвращает читаемый список языков вместо кодов."""
    langs = data.get("languages")
    if not langs:
        return _NONE_PLACEHOLDER
    L = LOCALIZATION[lang]
    names = [L.get(f"lang_opt_{code}", code) for code in langs]
    return ", ".join(names)


def build_resume_text(data: dict[str, Any], lang: str) -> str:
    L              = LOCALIZATION[lang]
    video_duration = data.get("video_duration", 0)
    video_label = (
        f"Видео-визитка принята ({video_duration} сек)"
        if video_duration else
        "Не предоставлена"
    ) if lang == "ru" else (
        f"Video-vizitka qabul qilindi ({video_duration} sek)"
        if video_duration else
        "Taqdim etilmadi"
    )
    return (
        f"{L['confirm_title']}\n"
        f"🏢 {L['field_branch']}: {_field(data, 'branch')}\n"
        f"💼 {L['field_position']}: {_field(data, 'position')}\n"
        f"👤 {L['field_name']}: {_field(data, 'name')}\n"
        f"📅 {L['field_birthday']}: {_field(data, 'birthday')}\n"
        f"🚻 {L['field_gender']}: {_field(data, 'gender')}\n"
        f"🚇 {L.get('field_metro', 'Метро')}: {_metro(data, lang)}\n"
        f"💪 {'Опыт работы' if lang == 'ru' else 'Ish tajribasi'}: {_field(data, 'experience')}\n"
        f"📅 {'Готовность к работе' if lang == 'ru' else 'Ishga tayyorlik'}: {_field(data, 'readiness')}\n"
        f"💰 {'Зарплатные ожидания' if lang == 'ru' else 'Ish haqi kutilmalari'}: {_field(data, 'salary')}\n"
        f"🗓 {'График' if lang == 'ru' else 'Grafik'}: {_field(data, 'schedule')}\n"
        f"🌆 {'Вечерние смены' if lang == 'ru' else 'Kechki smenalar'}: {_field(data, 'evening_shifts')}\n"
        f"📆 {'Выходные и праздники' if lang == 'ru' else 'Dam olish kunlari'}: {_field(data, 'weekends')}\n"
        f"🚬 {'Курение' if lang == 'ru' else 'Chekish'}: {_field(data, 'smoking')}\n"
        f"📗 {'Медицинская книжка' if lang == 'ru' else 'Tibbiy daftar'}: {_field(data, 'med_book')}\n"
        f"🌐 {'Языки' if lang == 'ru' else 'Tillar'}: {_languages_text(data, lang)}\n"
        f"📱 {L['field_phone']}: {_field(data, 'phone')}\n"
        f"🎥 {video_label}"
    )


def build_hr_resume_text(data: dict[str, Any], lang: str, user: Any) -> str:
    """
    lang  — язык анкеты (для отображения значений).
    user  — объект aiogram User (from_user).
    HR-панель всегда на русском языке.
    """
    L = LOCALIZATION["ru"]
    user_id  = user.id
    username = user.username or ""
    return (
        f"📝 <b>{L['hr_resume_title']}</b>\n\n"
        f"🏢 <b>{L['field_branch']}:</b> {_field(data, 'branch')}\n"
        f"💼 <b>{L['field_position']}:</b> {_field(data, 'position')}\n"
        f"👤 <b>{L['field_name']}:</b> {_field(data, 'name')}\n"
        f"📅 <b>{L['field_birthday']}:</b> {_field(data, 'birthday')}\n"
        f"🚻 <b>{L['field_gender']}:</b> {_field(data, 'gender')}\n"
        f"🚇 <b>{L.get('field_metro', 'Ближайшее метро')}:</b> {_metro(data)}\n"
        f"💪 <b>Опыт работы:</b> {_field(data, 'experience')}\n"
        f"🏢 <b>Где работал:</b> {_field(data, 'exp_company')}\n"
        f"👔 <b>Должность:</b> {_field(data, 'exp_position')}\n"
        f"⏱ <b>Стаж:</b> {_field(data, 'exp_duration')}\n"
        f"📋 <b>Обязанности:</b> {_field(data, 'exp_duties')}\n"
        f"📅 <b>Готовность к работе:</b> {_field(data, 'readiness')}\n"
        f"💰 <b>Зарплатные ожидания:</b> {_field(data, 'salary')}\n"
        f"🗓 <b>График:</b> {_field(data, 'schedule')}\n"
        f"🌆 <b>Вечерние смены:</b> {_field(data, 'evening_shifts')}\n"
        f"📆 <b>Выходные и праздники:</b> {_field(data, 'weekends')}\n"
        f"🚬 <b>Курение:</b> {_field(data, 'smoking')}\n"
        f"📗 <b>Медицинская книжка:</b> {_field(data, 'med_book')}\n"
        f"🌐 <b>Языки:</b> {_languages_text(data, lang)}\n"
        f"📱 <b>{L['field_phone']}:</b> <code>{_field(data, 'phone')}</code>\n\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"🔗 {L['field_username']}: @{username}"
    )
