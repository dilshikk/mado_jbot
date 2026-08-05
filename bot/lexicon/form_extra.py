# bot/lexicon/form_extra.py
"""Дополнительные тексты для новых шагов анкеты."""

EXTRA_RU = {
    # Кнопка пропустить (для inline-клавиатур)
    "btn_skip": "⏭ Пропустить",

    # Опыт работы — ветвление Да/Нет
    "ask_experience_yn": "💼 Есть ли у вас опыт работы?",
    "exp_no":  "❌ Нет",
    "exp_yes": "✅ Да",

    # Под-вопросы опыта
    "ask_exp_company":  "🏢 Где вы работали? (Название компании или организации)",
    "ask_exp_position": "👔 Какую должность вы занимали?",
    "ask_exp_duration": "⏱ Сколько времени вы там проработали?",
    "ask_exp_duties":   "📋 Опишите ваши основные обязанности",

    # Готовность к работе
    "ask_readiness":        "📅 Когда вы готовы приступить к работе?",
    "readiness_today":      "Сегодня",
    "readiness_tomorrow":   "Завтра",
    "readiness_week":       "В течение недели",
    "readiness_two_weeks":  "Через две недели",
    "readiness_month":      "Через месяц",

    # Зарплатные ожидания
    "ask_salary": "💰 Каковы ваши зарплатные ожидания?\n(Напишите сумму или диапазон, например: <code>3 000 000 – 5 000 000 сум</code>)",

    # График работы
    "ask_schedule":   "🗓 Какой график работы вам предпочтителен?",
    "schedule_6_1":   "6/1",
    "schedule_5_2":   "5/2",
    "schedule_3_1":   "3/1",
    "schedule_2_2":   "2/2",
    "schedule_full":  "Полный рабочий день",
    "schedule_flex":  "Гибкий график",
    "schedule_any":   "Не имеет значения",

    # Вечерние смены
    "ask_evening_shifts": "🌆 Готовы ли вы работать в вечерние смены?",
    "evening_yes":        "✅ Да",
    "evening_no":         "❌ Нет",
    "evening_agreement":  "🤝 По согласованию",

    # Выходные и праздники
    "ask_weekends":       "📆 Готовы ли вы работать в выходные и праздничные дни?",
    "weekends_yes":       "✅ Да",
    "weekends_no":        "❌ Нет",
    "weekends_sometimes": "🔄 Иногда",

    # Курение
    "ask_smoking": "🚬 Вы курите?",
    "smoking_no":  "🚭 Нет",
    "smoking_yes": "🚬 Да",

    # Медицинская книжка
    "ask_med_book":         "📗 Есть ли у вас медицинская книжка?",
    "med_book_yes":         "✅ Да",
    "med_book_no":          "❌ Нет",
    "med_book_in_progress": "⏳ В процессе оформления",

    # Языки владения
    "ask_languages":  "🌐 Какими языками вы владеете?\n(Можно выбрать несколько)",
    "lang_opt_ru":    "Русский",
    "lang_opt_uz":    "Узбекский",
    "lang_opt_en":    "Английский",
    "lang_opt_tr":    "Турецкий",
    "lang_opt_other": "Другое",
    "languages_done": "✅ Готово",

    # Фото
    "ask_photo": "📸 Отправьте ваше <b>фото</b>\n(или нажмите «⏭ Пропустить»)",
}

EXTRA_UZ = {
    # Кнопка пропустить
    "btn_skip": "⏭ O'tkazib yuborish",

    # Опыт работы — ветвление
    "ask_experience_yn": "💼 Sizda ish tajribasi bormi?",
    "exp_no":  "❌ Yo'q",
    "exp_yes": "✅ Ha",

    # Под-вопросы опыта
    "ask_exp_company":  "🏢 Qayerda ishlagansiz? (Kompaniya yoki tashkilot nomi)",
    "ask_exp_position": "👔 Qanday lavozimda ishlagansiz?",
    "ask_exp_duration": "⏱ Qancha vaqt u yerda ishladingiz?",
    "ask_exp_duties":   "📋 Asosiy vazifalaringizni tavsiflang",

    # Готовность
    "ask_readiness":       "📅 Ishga qachon tayyor bo'lasiz?",
    "readiness_today":     "Bugun",
    "readiness_tomorrow":  "Ertaga",
    "readiness_week":      "Bir hafta ichida",
    "readiness_two_weeks": "Ikki haftadan so'ng",
    "readiness_month":     "Bir oydan so'ng",

    # Зарплата
    "ask_salary": "💰 Ish haqi bo'yicha kutishlaringiz qanday?\n(Miqdor yoki oraliq yozing, masalan: <code>3 000 000 – 5 000 000 so'm</code>)",

    # График
    "ask_schedule":  "🗓 Qanday ish grafigini afzal ko'rasiz?",
    "schedule_6_1":  "6/1",
    "schedule_5_2":  "5/2",
    "schedule_3_1":  "3/1",
    "schedule_2_2":  "2/2",
    "schedule_full": "To'liq ish kuni",
    "schedule_flex": "Erkin grafik",
    "schedule_any":  "Muhim emas",

    # Вечерние смены
    "ask_evening_shifts": "🌆 Kechki smenlarda ishlashga tayyormisiz?",
    "evening_yes":        "✅ Ha",
    "evening_no":         "❌ Yo'q",
    "evening_agreement":  "🤝 Kelishuvga ko'ra",

    # Выходные
    "ask_weekends":       "📆 Dam olish kunlari va bayramlarda ishlashga tayyormisiz?",
    "weekends_yes":       "✅ Ha",
    "weekends_no":        "❌ Yo'q",
    "weekends_sometimes": "🔄 Ba'zan",

    # Курение
    "ask_smoking": "🚬 Chekasizmi?",
    "smoking_no":  "🚭 Yo'q",
    "smoking_yes": "🚬 Ha",

    # Медкнижка
    "ask_med_book":         "📗 Sizda tibbiy daftar bormi?",
    "med_book_yes":         "✅ Ha",
    "med_book_no":          "❌ Yo'q",
    "med_book_in_progress": "⏳ Rasmiylashtirilmoqda",

    # Языки
    "ask_languages":  "🌐 Qaysi tillarni bilasiz?\n(Bir nechtasini tanlash mumkin)",
    "lang_opt_ru":    "Rus",
    "lang_opt_uz":    "O'zbek",
    "lang_opt_en":    "Ingliz",
    "lang_opt_tr":    "Turk",
    "lang_opt_other": "Boshqa",
    "languages_done": "✅ Tayyor",

    # Фото
    "ask_photo": "📸 Rasmingizni yuboring\n(yoki «⏭ O'tkazib yuborish» tugmasini bosing)",
}
