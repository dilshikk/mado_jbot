# bot/utils/formatters.py

from typing import Any

from bot.lexicon import LOCALIZATION

_NONE_PLACEHOLDER = "—"


def _field(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return str(value) if value is not None else _NONE_PLACEHOLDER


def build_resume_text(data: dict[str, Any], lang: str) -> str:
    L              = LOCALIZATION[lang]
    video_duration = data.get("video_duration", 0)
    video_label    = f"Видео-визитка принята ({video_duration} сек)" if lang == "ru" else f"Video-vizitka qabul qilindi ({video_duration} sek)"
    return (
        f"{L['confirm_title']}\n"
        f"🏢 {L['field_branch']}: {_field(data, 'branch')}\n"
        f"💼 {L['field_position']}: {_field(data, 'position')}\n"
        f"👤 {L['field_name']}: {_field(data, 'name')}\n"
        f"📅 {L['field_birthday']}: {_field(data, 'birthday')}\n"
        f"🚻 {L['field_gender']}: {_field(data, 'gender')}\n"
        f"💍 {L['field_family']}: {_field(data, 'family')}\n"
        f"🔹 {L['field_citizenship']}: {_field(data, 'citizenship')}\n"
        f"🏡 {L['field_address']}: {_field(data, 'address')}\n"
        f"💪 {'Опыт работы' if lang == 'ru' else 'Ish tajribasi'}: {_field(data, 'experience')}\n"
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
        f"💍 <b>{L['field_family']}:</b> {_field(data, 'family')}\n"
        f"🔹 <b>{L['field_citizenship']}:</b> {_field(data, 'citizenship')}\n"
        f"🏡 <b>{L['field_address']}:</b> {_field(data, 'address')}\n"
        f"💪 <b>Опыт работы:</b> {_field(data, 'experience')}\n"
        f"📱 <b>{L['field_phone']}:</b> <code>{_field(data, 'phone')}</code>\n\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"🔗 {L['field_username']}: @{username}"
    )
