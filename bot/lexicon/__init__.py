from bot.lexicon.ru import TEXTS_RU
from bot.lexicon.uz import TEXTS_UZ
from bot.lexicon.form_extra import EXTRA_RU, EXTRA_UZ

# Мёрджим расширения в базовые словари (form_extra добавляет новые ключи,
# существующие ключи в TEXTS_RU/UZ имеют приоритет)
_RU = {**EXTRA_RU, **TEXTS_RU}
_UZ = {**EXTRA_UZ, **TEXTS_UZ}

LOCALIZATION: dict = {
    "ru": _RU,
    "uz": _UZ,
}
