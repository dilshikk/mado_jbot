# bot/lexicon/uz.py

TEXTS_UZ = {
    # ── Общее ─────────────────────────────────────────────────
    "welcome": "👋 MADO -ga xush kelibsiz!\n\nBu yerda restoranimizda ishlash uchun ariza topshirishingiz mumkin.",
    "about_text": "🏢 MADO — eng yaxshi oshxona an'analarini birlashtirgan xalqaro restoranlar tarmog'i.\n\nBiz doim iqtidorli xodimlarga xursandmiz!",
    "anketa_cancelled": "❌ Anketa to'ldirish bekor qilindi. Asosiy menyuga qaytdingiz.",
    "none_text": "mavjud emas",

    # ── Блокировка ───────────────────────────────────────────
    "user_blocked_text": (
        "⚠️ Kirish cheklangan. \n\n"
        "Sizning anketangiz avval rad etilgan. "
        "Qayta topshirish vaqtincha mumkin emas.\n"
        "Agar bu xato deb o'ylasangiz — biz bilan bog'laning."
    ),

    # ── Подписка на канал ────────────────────────────────────
    "subscription_not_subscribed": (
        "🔒 Kirish cheklangan \n\n"
        "Botdan foydalanish uchun kanalimizga obuna bo'ling.\n\n"
        "Obuna bo'lgandan so'ng «✅ Obuna bo'ldim» tugmasini bosing."
    ),
    "subscription_confirmed": "✅ Ajoyib! Obuna tasdiqlandi. \n\nEndi botdan foydalanishingiz mumkin. Boshlash uchun /start yuboring.",
    "subscription_confirmed_alert": "✅ Obuna tasdiqlandi!",
    "subscription_not_done": "❌ Siz hali obuna bo'lmadingiz. Obuna bo'lib, qayta urinib ko'ring.",
    "btn_subscribe_channel": "📢 Kanalga obuna bo'lish",
    "btn_check_subscription": "✅ Obuna bo'ldim",

    # ── Шаги анкеты ──────────────────────────────────────────
    "ask_branch": "📍 Ishlamoqchi bo'lgan filialni tanlang:",
    "ask_position": "💼 Bo'sh ish o'rnini tanlang:",
    "ask_name": "👤 F.I.Sh. ni to'liq kiriting:",
    "ask_birthday": "📅 Tug'ilgan sanangizni DD.MM.YYYY formatida kiriting\nMasalan: 25.06.1995 ",
    "ask_gender": "🚺 Jinsingizni ko'rsating:",
    "ask_citizenship": "🔹 Fuqaroligingizni ko'rsating yoki «⏭ O'tkazib yuborish» tugmasini bosing:",
    "ask_address": "🏡 Yashash manzilingizni kiriting\n(shahar, tuman, ko'cha / kvartal):",
    "ask_metro": "🚇 Eng yaqin metro ni tanlang yoki «⏭ O'tkazib yuborish» tugmasini bosing:",
    "ask_phone": "📱 Telefon raqamingizni yuboring:",

    # ── Ошибки валидации ─────────────────────────────────────
    "bad_name": (
        "❌ Iltimos, to'g'ri F.I.Sh. kiriting.\n"
        "Kamida 3 ta harf, faqat harflar."
    ),
    "bad_birthday": (
        "❌ Sana formati noto'g'ri.\n"
        " DD.MM.YYYY formatida kiriting, masalan: 25.06.1995 "
    ),
    "bad_age": (
        "❌ Yosh 18 dan 60 yoshgacha bo'lishi kerak.\n"
        "Iltimos, to'g'ri tug'ilgan sanani kiriting."
    ),
    "bad_gender": (
        "❌ Iltimos, taklif etilgan variantlardan jinsni tanlang."
    ),
    "bad_phone": (
        "❌ Telefon raqami noto'g'ri.\n"
        "«📱 Kontaktni yuborish» tugmasini bosing yoki qo'lda kiriting.\n"
        "Masalan: +998901234567 "
    ),
    "bad_metro": (
        "❌ Iltimos, ro'yxatdan metro bekatini tanlang yoki «⏭ O'tkazib yuborish» tugmasini bosing."
    ),
    "bad_position": (
        "❌ Iltimos, taklif etilgan ro'yxatdan vakansiyani tanlang."
    ),

    # ── Пол / Семья / Гражданство ───────────────────────────────
    "gender_male": "🚹 Erkak",
    "gender_female": "🚺 Ayol",
    "citizenship_uzb": "🇺🇿 O'zbekiston",
    "metro_skip": "⏭ O'tkazib yuborish",
    "citizenship_skip":"⏭ O'tkazib yuborish",
    "field_metro": "Eng yaqin metro",

    # ── Вакансии ───────────────────────────────────────────
    "pos_cook": "Oshpaz 👨‍🍳",
    "pos_waiter": "Ofitsiant 🤵",
    "pos_runner": "Yuguruvchi 🏃‍♂️",
    "pos_barista": "Barista ☕️",
    "pos_cleaner": "Texnik xodim 🧹",
    "pos_pastry": "Qandolatchi 🍰",
    "pos_admin": "Administrator 👨‍💼",
    "pos_hostess": "Xostes 🙋",
    "pos_cashier": "Kassir 💵",

    # ── Кнопки интерфейса ───────────────────────────────────
    "btn_apply": "📝 Anketani to'ldirish",
    "btn_about": "🏢 Restoran haqida",
    "btn_change_lang": "🌐 Tilni o'zgartirish",
    "btn_cancel": "❌ Bekor qilish",
    "btn_share_phone": "📱 Kontaktni yuborish",

    # ── Подтверждение ─────────────────────────────────────
    "confirm_title": "📋 Yuborishdan oldin ma'lumotlaringizni tekshiring: ",
    "confirm_btn_yes": "✅ Hammasi to'g'ri — yuborish",
    "confirm_btn_no": "🔄 Qaytadan to'ldirish",
    "field_branch": "Filial",
    "field_position": "Bo'sh ish o'rni",
    "field_name": "F.I.Sh.",
    "field_birthday": "Tug'ilgan sana",
    "field_gender": "Jinsi",
    "field_family": "Oilaviy ahvoli",
    "field_citizenship": "Fuqaroligi",
    "field_address": "Manzil",
    "field_phone": "Telefon",
    "field_username": "Username",

    # ── Финал анкеты ───────────────────────────────────────
    "anketa_done": (
        "🎉 Anketa muvaffaqiyatli yuborildi! \n\n"
        "HR menejerimiz arizangizni ko'rib chiqadi va siz bilan bog'lanadi.\n"
        "O'rtacha javob vaqti — 1–2 ish kuni."
    ),
    "anketa_confirmed": (
        "✅ Anketa qabul qilindi!\n\n"
        "HR menejerimiz arizangizni ko'rib chiqadi va siz bilan bog'lanadi.\n"
        "O'rtacha javob vaqti — 1–2 ish kuni."
    ),

    # ── Защита от дублей ─────────────────────────────────────
    "anketa_block_pending": "⏳ Arizangiz allaqachon ko'rib chiqilmoqda. \n\nHR menejer javobini kuting — qayta topshirish hozircha mumkin emas.",
    "anketa_block_accepted": "✅ Siz allaqachon suhbatga taklif etilgansiz! \n\nSizni belgilangan vaqtda kutamiz.",
    "anketa_block_hired": "🏆 Siz allaqachon MADO xodimisiz! ",
    "anketa_block_hold": "⏸ Anketangiz zaxiraga qoldirildi. \n\nHR menejer keyinroq unga qaytadi. Qayta topshirish hozircha mumkin emas.",
    "anketa_already_exists": "⏳ Sizda allaqachon faol ariza bor. \n\nQayta yuborish mumkin emas.",

    # ── Статус заявки ───────────────────────────────────────
    "status_none": "📋 Sizning faol arizangiz yo'q.",
    "status_pending": "⏳ Arizangiz ko'rib chiqilmoqda. Javobni kuting.",
    "status_accepted": "✅ Tabriklaymiz! Siz suhbatga taklif etildingiz.",
    "status_rejected": "❌ Afsuski, arizangiz rad etildi.",
    "status_error": "Holatni olib bo'lmadi. Keyinroq urinib ko'ring.",
    "statuses": {
        "none": "📋 Sizning faol arizangiz yo'q.",
        "pending": "⏳ Arizangiz ko'rib chiqilmoqda.",
        "accepted": "✅ Siz suhbatga taklif etildingiz!",
        "rejected": "❌ Arizangiz rad etildi.",
        "hold": "⏸ Arizangiz vaqtincha qoldirildi.",
    },

    # ── Рассылка ───────────────────────────────────────────
    "broadcast_no_reply": "↩️ Tarqatmoqchi bo'lgan xabarga javob bering.",
    "broadcast_progress": "📤 Yuborilmoqda... {current} / {total}",
    "broadcast_done": (
        "📬 Tarqatish yakunlandi \n"
        "✅ Yuborildi: {sent} \n"
        "❌ Xato: {failed} "
    ),

    # ── Защита групп ────────────────────────────────────────
    "group_protection_text": (
        "⚠️ Anketa faqat bot bilan shaxsiy xabarlarda to'ldiriladi! \n"
        "Shaxsiy chatga o'tish uchun quyidagi tugmani bosing 👇"
    ),
    "btn_redirect_pm": "🚀 Shaxsiy xabarda ochish",

    # ── HR-панель (уведомления кандидатам на узбекском) ───────────────
    "default_anketa_title": "📝 MADO nomzod anketi",
    "hr_resume_title": "MADO yangi nomzod anketi",
    "hr_ask_interview": "",
    "candidate_accepted_notice": (
        "🎉 Anketangiz tasdiqlandi! \n\n"
        "Sizni MADO restoraniga shaxsiy suhbatga taklif qilamiz.\n"
        "🗓 Sana va vaqt: {interview_text} \n\n"
        "Iltimos, vaqtida keling. Sizni kutamiz!"
    ),
    "candidate_rejected_notice": (
        "😔 Afsuski, hozirda sizni suhbatga taklif eta olmaymiz. \n\n"
        "Anketangiz zaxiramizda saqlanib qoladi. Keyinroq qayta urinib ko'rishingiz mumkin.\n"
        "MADO brendiga qiziqish bildirganingiz uchun rahmat!"
    ),
    "candidate_hired_notice": (
        "🏆 Tabriklaymiz! Siz MADO'ga ishga qabul qilindingiz! \n\n"
        "Jamoamizga xush kelibsiz! 🎉\n\n"
        "HR menejer tez orada siz bilan bog'lanadi."
    ),
    "candidate_hold_notice": (
        "⏸ Anketangiz zaxiraga qoldirildi. \n\n"
        "HR menejer keyinroq arizangizga qaytadi.\n"
        "Sabringiz uchun rahmat!"
    ),
    "hr_status_accepted": "🟢 STATUS: Tasdiqlandi. Suhbat: {interview_text} ",
    "hr_status_rejected": "🔴 STATUS: Rad etildi. Foydalanuvchi bloklandi.",
    "hr_status_hold": "⏸ STATUS: Kutish rejimida.",
    "hr_success_sent": "✅ Xabarnoma nomzodga muvaffaqiyatli yuborildi.",
    "hr_alert_rejected": "Nomzod rad etildi va bloklandi.",
    "hr_action_cancelled": "🔄 Amal bekor qilindi.",
    "hr_stats_text": (
        "📊 MADO HR-bot statistikasi \n\n"
        "👥 Bazadagi foydalanuvchilar: {total_users} \n"
        "📝 Yuborilgan anketalar: {total_apps} "
    ),
}
