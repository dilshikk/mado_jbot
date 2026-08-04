# bot/lexicon/uz.py

TEXTS_UZ = {
    # ── Общее ─────────────────────────────────────────────────────────────
    "welcome":          "👋 <b>MADO</b>-ga xush kelibsiz!\n\nBu yerda restoranimizda ishlash uchun ariza topshirishingiz mumkin.",
    "about_text":       "🏢 <b>MADO</b> — eng yaxshi oshxona an'analarini birlashtirgan xalqaro restoranlar tarmog'i.\n\nBiz doim iqtidorli xodimlarga xursandmiz!",
    "anketa_cancelled": "❌ Anketa to'ldirish bekor qilindi. Asosiy menyuga qaytdingiz.",
    "none_text":        "mavjud emas",

    # ── Блокировка ────────────────────────────────────────────────────────
    "user_blocked_text": (
        "⚠️ <b>Kirish cheklangan.</b>\n\n"
        "Sizning anketangiz avval rad etilgan. "
        "Qayta topshirish vaqtincha mumkin emas.\n"
        "Agar bu xato deb o'ylasangiz — biz bilan bog'laning."
    ),

    # ── Подписка на канал ─────────────────────────────────────────────────
    "subscription_not_subscribed": (
        "🔒 <b>Kirish cheklangan</b>\n\n"
        "Botdan foydalanish uchun kanalimizga obuna bo'ling.\n\n"
        "Obuna bo'lgandan so'ng <b>«✅ Obuna bo'ldim»</b> tugmasini bosing."
    ),
    "subscription_confirmed":       "✅ <b>Ajoyib! Obuna tasdiqlandi.</b>\n\nEndi botdan foydalanishingiz mumkin. Boshlash uchun /start yuboring.",
    "subscription_confirmed_alert": "✅ Obuna tasdiqlandi!",
    "subscription_not_done":        "❌ Siz hali obuna bo'lmadingiz. Obuna bo'lib, qayta urinib ko'ring.",
    "btn_subscribe_channel":        "📢 Kanalga obuna bo'lish",
    "btn_check_subscription":       "✅ Obuna bo'ldim",

    # ── Шаги анкеты ───────────────────────────────────────────────────────
    "ask_branch":      "📍 Ishlamoqchi bo'lgan <b>filialni</b> tanlang:",
    "ask_position":    "💼 <b>Bo'sh ish o'rnini</b> tanlang:",
    "ask_name":        "👤 <b>F.I.Sh.</b> ni to'liq kiriting:",
    "ask_birthday":    "📅 <b>Tug'ilgan sanangizni</b> DD.MM.YYYY formatida kiriting\nMasalan: <code>25.06.1995</code>",
    "ask_gender":      "🚻 <b>Jinsingizni</b> ko'rsating:",
    "ask_family":      "💍 <b>Oilaviy ahvolingizni</b> ko'rsating:",
    "ask_citizenship": "🔹 <b>Fuqaroligingizni</b> ko'rsating:",
    "ask_address":     "🏡 <b>Yashash manzilingizni</b> kiriting\n(shahar, tuman, ko'cha / kvartal):",
    "ask_phone":       "📱 <b>Telefon raqamingizni</b> yuboring:",

    # ── Ошибки валидации ──────────────────────────────────────────────────
    "bad_birthday": (
        "❌ Sana formati noto'g'ri.\n"
        "<b>DD.MM.YYYY</b> formatida kiriting, masalan: <code>25.06.1995</code>"
    ),
    "bad_name": (
        "❌ Iltimos, to'g'ri F.I.Sh. kiriting.\n"
        "Kamida 3 ta harf, faqat harflar."
    ),

    # ── Пол / Семья / Гражданство ─────────────────────────────────────────
    "gender_male":   "🚹 Erkak",
    "gender_female": "🚺 Ayol",
    "family_single":  "💍 Bo'ydoq / Turmushga chiqmagan",
    "family_married": "👨‍👩‍👦 Oila qurgan",
    "citizenship_uzb": "🇺🇿 O'zbekiston",

    # ── Вакансии ──────────────────────────────────────────────────────────
    "pos_cook":    "Oshpaz 👨‍🍳",
    "pos_waiter":  "Ofitsiant 🤵",
    "pos_runner":  "Yuguruvchi 🏃‍♂️",
    "pos_barista": "Barista ☕️",
    "pos_cleaner": "Texnik xodim 🧹",

    # ── Кнопки интерфейса ─────────────────────────────────────────────────
    "btn_apply":       "📝 Anketani to'ldirish",
    "btn_about":       "🏢 Restoran haqida",
    "btn_change_lang": "🌐 Tilni o'zgartirish",
    "btn_cancel":      "❌ Bekor qilish",
    "btn_share_phone": "📱 Kontaktni yuborish",

    # ── Подтверждение ─────────────────────────────────────────────────────
    "confirm_title":     "📋 <b>Yuborishdan oldin ma'lumotlaringizni tekshiring:</b>",
    "confirm_btn_yes":   "✅ Hammasi to'g'ri — yuborish",
    "confirm_btn_no":    "🔄 Qaytadan to'ldirish",
    "field_branch":      "Filial",
    "field_position":    "Bo'sh ish o'rni",
    "field_name":        "F.I.Sh.",
    "field_birthday":    "Tug'ilgan sana",
    "field_gender":      "Jinsi",
    "field_family":      "Oilaviy ahvoli",
    "field_citizenship": "Fuqaroligi",
    "field_address":     "Manzil",
    "field_phone":       "Telefon",
    "field_username":    "Username",

    # ── Финал анкеты ──────────────────────────────────────────────────────
    "anketa_done": (
        "🎉 <b>Anketa muvaffaqiyatli yuborildi!</b>\n\n"
        "HR menejerimiz arizangizni ko'rib chiqadi va siz bilan bog'lanadi.\n"
        "O'rtacha javob vaqti — <b>1–2 ish kuni</b>."
    ),

    # ── Защита от дублей ──────────────────────────────────────────────────
    "anketa_block_pending":  "⏳ <b>Arizangiz allaqachon ko'rib chiqilmoqda.</b>\n\nHR menejer javobini kuting — qayta topshirish hozircha mumkin emas.",
    "anketa_block_accepted": "✅ <b>Siz allaqachon suhbatga taklif etilgansiz!</b>\n\nSizni belgilangan vaqtda kutamiz.",
    "anketa_block_hired":    "🏆 <b>Siz allaqachon MADO xodimisiz!</b>",
    "anketa_block_hold":     "⏸ <b>Anketangiz zaxiraga qoldirildi.</b>\n\nHR menejer keyinroq unga qaytadi. Qayta topshirish hozircha mumkin emas.",
    "anketa_already_exists": "⏳ <b>Sizda allaqachon faol ariza bor.</b>\n\nQayta yuborish mumkin emas.",

    # ── Статус заявки ─────────────────────────────────────────────────────
    "status_none":     "📋 Sizning faol arizangiz yo'q.",
    "status_pending":  "⏳ Arizangiz ko'rib chiqilmoqda. Javobni kuting.",
    "status_accepted": "✅ Tabriklaymiz! Siz suhbatga taklif etildingiz.",
    "status_rejected": "❌ Afsuski, arizangiz rad etildi.",
    "status_error":    "Holatni olib bo'lmadi. Keyinroq urinib ko'ring.",
    "statuses": {
        "none":     "📋 Sizning faol arizangiz yo'q.",
        "pending":  "⏳ Arizangiz ko'rib chiqilmoqda.",
        "accepted": "✅ Siz suhbatga taklif etildingiz!",
        "rejected": "❌ Arizangiz rad etildi.",
        "hold":     "⏸ Arizangiz vaqtincha qoldirildi.",
    },

    # ── Рассылка ──────────────────────────────────────────────────────────
    "broadcast_no_reply": "↩️ Tarqatmoqchi bo'lgan xabarga javob bering.",
    "broadcast_progress": "📤 Yuborilmoqda... {current} / {total}",
    "broadcast_done": (
        "📬 <b>Tarqatish yakunlandi</b>\n"
        "✅ Yuborildi: <b>{sent}</b>\n"
        "❌ Xato:      <b>{failed}</b>"
    ),

    # ── Защита групп ──────────────────────────────────────────────────────
    "group_protection_text": (
        "⚠️ <b>Anketa faqat bot bilan shaxsiy xabarlarda to'ldiriladi!</b>\n"
        "Shaxsiy chatga o'tish uchun quyidagi tugmani bosing 👇"
    ),
    "btn_redirect_pm": "🚀 Shaxsiy xabarda ochish",

    # ── HR-панель (уведомления кандидатам на узбекском) ───────────────────
    "default_anketa_title":  "📝 MADO nomzod anketi",
    "hr_resume_title":       "MADO yangi nomzod anketi",
    "hr_ask_interview":      "",
    "candidate_accepted_notice": (
        "🎉 <b>Anketangiz tasdiqlandi!</b>\n\n"
        "Sizni MADO restoraniga shaxsiy suhbatga taklif qilamiz.\n"
        "🗓 <b>Sana va vaqt:</b> <code>{interview_text}</code>\n\n"
        "Iltimos, vaqtida keling. Sizni kutamiz!"
    ),
    "candidate_rejected_notice": (
        "😔 <b>Afsuski, hozirda sizni suhbatga taklif eta olmaymiz.</b>\n\n"
        "Anketangiz zaxiramizda saqlanib qoladi. Keyinroq qayta urinib ko'rishingiz mumkin.\n"
        "MADO brendiga qiziqish bildirganingiz uchun rahmat!"
    ),
    "candidate_hired_notice": (
        "🏆 <b>Tabriklaymiz! Siz MADO'ga ishga qabul qilindingiz!</b>\n\n"
        "Jamoamizga xush kelibsiz! 🎉\n\n"
        "HR menejer tez orada siz bilan bog'lanadi."
    ),
    "candidate_hold_notice": (
        "⏸ <b>Anketangiz zaxiraga qoldirildi.</b>\n\n"
        "HR menejer keyinroq arizangizga qaytadi.\n"
        "Sabringiz uchun rahmat!"
    ),
    "hr_status_accepted":  "🟢 <b>STATUS:</b> Tasdiqlandi. Suhbat: <code>{interview_text}</code>",
    "hr_status_rejected":  "🔴 <b>STATUS:</b> Rad etildi. Foydalanuvchi bloklandi.",
    "hr_status_hold":      "⏸ <b>STATUS:</b> Kutish rejimida.",
    "hr_success_sent":     "✅ Xabarnoma nomzodga muvaffaqiyatli yuborildi.",
    "hr_alert_rejected":   "Nomzod rad etildi va bloklandi.",
    "hr_action_cancelled": "🔄 Amal bekor qilindi.",
    "hr_stats_text": (
        "📊 <b>MADO HR-bot statistikasi</b>\n\n"
        "👥 Bazadagi foydalanuvchilar: <b>{total_users}</b>\n"
        "📝 Yuborilgan anketalar: <b>{total_apps}</b>"
    ),
}
