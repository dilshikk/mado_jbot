# bot/utils/formatters.py

from typing import Any

from bot.lexicon import LOCALIZATION

_NONE_PLACEHOLDER = "—"


def _field(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else _NONE_PLACEHOLDER
    return str(value) if value is not None else _NONE_PLACEHOLDER


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
        f"🚇 {L.get('field_metro', 'Метро')}: {_field(data, 'metro')}\n"
        f"💪 {'Опыт работы' if lang == 'ru' else 'Ish tajribasi'}: {_field(data, 'experience')}\n"
        f"📅 {'Готовность к работе' if lang == 'ru' else 'Ishga tayyorlik'}: {_field(data, 'readiness')}\n"
        f"💰 {'Зарплатные ожидания' if lang == 'ru' else 'Ish haqi kutilmalari'}: {_field(data, 'salary')}\n"
        f"🗓 {'График' if lang == 'ru' else 'Grafik'}: {_field(data, 'schedule')}\n"
        f"🌐 {'Языки' if lang == 'ru' else 'Tillar'}: {_field(data, 'languages')}\n"
        f"📱 {L['field_phone']}: {_field(data, 'phone')}\n"
        f"🎥 {video_label}"
    )


def build_hr_resume_text(data: dict[str, Any], user_id: int, username: str) -> str:
    L = LOCALIZATION["ru"]
    return (
        f"📝 <b>{L['hr_resume_title']}</b>\n\n"
        f"🏢 <b>{L['field_branch']}:</b> {_field(data, 'branch')}\n"
        f"💼 <b>{L['field_position']}:</b> {_field(data, 'position')}\n"
        f"👤 <b>{L['field_name']}:</b> {_field(data, 'name')}\n"
        f"📅 <b>{L['field_birthday']}:</b> {_field(data, 'birthday')}\n"
        f"🚻 <b>{L['field_gender']}:</b> {_field(data, 'gender')}\n"
        f"🚇 <b>{L.get('field_metro', 'Ближайшее метро')}:</b> {_field(data, 'metro')}\n"
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
        f"🌐 <b>Языки:</b> {_field(data, 'languages')}\n"
        f"📱 <b>{L['field_phone']}:</b> <code>{_field(data, 'phone')}</code>\n\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"🔗 {L['field_username']}: @{username}"
    )
