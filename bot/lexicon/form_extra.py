# bot/lexicon/form_extra.py
"""Дополнительные тексты для новых шагов анкеты."""

EXTRA_RU = {
    # Кнопка пропустить
    "btn_skip": "⏭ Пропустить",
    "languages_done_empty": "Выберите хотя бы один язык или нажмите «⏭ Пропустить».",

    # Опыт работы — ветвление Да/Нет
    "ask_experience_yn": "💼 Есть ли у вас опыт работы?",
    "exp_no":  "❌ Нет",
    "exp_yes": "✅ Да",

    # Под-вопросы опыта
    "ask_exp_company":  "🏢 Где вы работали? (Название компании или организации)",
    "ask_exp_position": "👔 Какую должность вы занимали?\n(или нажмите «⏭ Пропустить»)",
    "ask_exp_duration": "⏱ Сколько времени вы там проработали?\n(или нажмите «⏭ Пропустить»)",
    "ask_exp_duties":   "📋 Опишите ваши основные обязанности\n(или нажмите «⏭ Пропустить»)",

    # Готовность к работе
    "ask_readiness":        "📅 Когда вы готовы приступить к работе?",
    "readiness_today":      "Сегодня",
    "readiness_tomorrow":   "Завтра",
    "readiness_week":       "В течение недели",
    "readiness_two_weeks":  "Через две недели",
    "readiness_month":      "Через месяц",

    # Зарплатные ожидания
    "ask_salary": (
        "💰 Каковы ваши зарплатные ожидания?\n"
        "(Напишите сумму или диапазон, например: <code>3 000 000 – 5 000 000 сум</code>)\n"
        "или нажмите «⏭ Пропустить»"
    ),

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

    # Фото и видео
    "ask_photo": "📸 Отправьте ваше <b>фото</b>\n(или нажмите «⏭ Пропустить»)",
    "ask_video": (
        "🎥 Отправьте <b>видео-визитку</b> (кружок или видео).\n"
        "⚠️ Минимум — <b>15 секунд</b>.\n"
        "(или нажмите «⏭ Пропустить»)"
    ),

    # ── Ошибки валидации ──────────────────────────────────────────────────
    "bad_languages": (
        "❌ Пожалуйста, выберите язык из списка\n"
        "или нажмите «⏭ Пропустить» чтобы пропустить этот шаг."
    ),
    "bad_readiness": (
        "❌ Пожалуйста, выберите один из предложенных вариантов."
    ),
    "bad_experience_yn": (
        "❌ Пожалуйста, выберите «✅ Да» или «❌ Нет»."
    ),
    "bad_schedule": (
        "❌ Пожалуйста, выберите график из предложенного списка."
    ),
    "bad_evening_shifts": (
        "❌ Пожалуйста, выберите один из предложенных вариантов."
    ),
    "bad_weekends": (
        "❌ Пожалуйста, выберите один из предложенных вариантов."
    ),
    "bad_smoking": (
        "❌ Пожалуйста, выберите один из предложенных вариантов."
    ),
    "bad_med_book": (
        "❌ Пожалуйста, выберите один из предложенных вариантов."
    ),
    "bad_photo": (
        "❌ Пожалуйста, отправьте фотографию\n"
        "или нажмите «⏭ Пропустить» чтобы пропустить этот шаг."
    ),
    "bad_video": (
        "❌ Пожалуйста, отправьте видео или видео-кружок\n"
        "или нажмите «⏭ Пропустить» чтобы пропустить этот шаг."
    ),
    "bad_video_short": (
        "❌ Видео слишком короткое ({duration} сек).\n"
        "Нужно минимум <b>{min_duration} секунд</b>. Попробуйте ещё раз."
    ),
}

EXTRA_UZ = {
    # Кнопка пропустить
    "btn_skip": "⏭ O'tkazib yuborish",
    "languages_done_empty": "Kamida bitta tilni tanlang yoki «⏭ O'tkazib yuborish» tugmasini bosing.",

    # Опыт работы — ветвление
    "ask_experience_yn": "💼 Sizda ish tajribasi bormi?",
    "exp_no":  "❌ Yo'q",
    "exp_yes": "✅ Ha",

    # Под-вопросы опыта
    "ask_exp_company":  "🏢 Qayerda ishlagansiz? (Kompaniya yoki tashkilot nomi)",
    "ask_exp_position": "👔 Qanday lavozimda ishlagansiz?\n(yoki «⏭ O'tkazib yuborish» tugmasini bosing)",
    "ask_exp_duration": "⏱ Qancha vaqt u yerda ishladingiz?\n(yoki «⏭ O'tkazib yuborish» tugmasini bosing)",
    "ask_exp_duties":   "📋 Asosiy vazifalaringizni tavsiflang\n(yoki «⏭ O'tkazib yuborish» tugmasini bosing)",

    # Готовность
    "ask_readiness":       "📅 Ishga qachon tayyor bo'lasiz?",
    "readiness_today":     "Bugun",
    "readiness_tomorrow":  "Ertaga",
    "readiness_week":      "Bir hafta ichida",
    "readiness_two_weeks": "Ikki haftadan so'ng",
    "readiness_month":     "Bir oydan so'ng",

    # Зарплата
    "ask_salary": (
        "💰 Ish haqi bo'yicha kutishlaringiz qanday?\n"
        "(Miqdor yoki oraliq yozing, masalan: <code>3 000 000 – 5 000 000 so'm</code>)\n"
        "yoki «⏭ O'tkazib yuborish» tugmasini bosing"
    ),

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

    # Фото и видео
    "ask_photo": "📸 Rasmingizni yuboring\n(yoki «⏭ O'tkazib yuborish» tugmasini bosing)",
    "ask_video": (
        "🎥 <b>Video-vizitka</b> yuboring (dumaloq yoki video).\n"
        "⚠️ Minimal — <b>15 soniya</b>.\n"
        "(yoki «⏭ O'tkazib yuborish» tugmasini bosing)"
    ),

    # ── Ошибки валидации ──────────────────────────────────────────────────
    "bad_languages": (
        "❌ Iltimos, ro'yxatdan tilni tanlang\n"
        "yoki «⏭ O'tkazib yuborish» tugmasini bosib bu bosqichni o'tkazib yuboring."
    ),
    "bad_readiness": (
        "❌ Iltimos, taklif etilgan variantlardan birini tanlang."
    ),
    "bad_experience_yn": (
        "❌ Iltimos, «✅ Ha» yoki «❌ Yo'q» ni tanlang."
    ),
    "bad_schedule": (
        "❌ Iltimos, taklif etilgan ro'yxatdan grafikni tanlang."
    ),
    "bad_evening_shifts": (
        "❌ Iltimos, taklif etilgan variantlardan birini tanlang."
    ),
    "bad_weekends": (
        "❌ Iltimos, taklif etilgan variantlardan birini tanlang."
    ),
    "bad_smoking": (
        "❌ Iltimos, taklif etilgan variantlardan birini tanlang."
    ),
    "bad_med_book": (
        "❌ Iltimos, taklif etilgan variantlardan birini tanlang."
    ),
    "bad_photo": (
        "❌ Iltimos, rasm yuboring\n"
        "yoki «⏭ O'tkazib yuborish» tugmasini bosib bu bosqichni o'tkazib yuboring."
    ),
    "bad_video": (
        "❌ Iltimos, video yoki video-doira yuboring\n"
        "yoki «⏭ O'tkazib yuborish» tugmasini bosib bu bosqichni o'tkazib yuboring."
    ),
    "bad_video_short": (
        "❌ Video juda qisqa ({duration} s).\n"
        "Minimal <b>{min_duration} soniya</b> kerak. Qayta urinib ko'ring."
    ),
}
