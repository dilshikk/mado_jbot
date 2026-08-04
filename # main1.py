# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import keyboards as kb

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- ДОБАВИЛИ НОВОЕ СОСТОЯНИЕ ДЛЯ ВАКАНСИИ ---
class HRForm(StatesGroup):
    waiting_for_language = State()
    main_menu = State()
    waiting_for_name = State()       # Шаг 1: Ожидание имени
    waiting_for_phone = State()      # Шаг 2: Ожидание телефона
    waiting_for_position = State()   # Шаг 3: Ожидание выбора вакансии


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Здравствуйте! Вас приветствует HR-бот. 👋\n"
        "Пожалуйста, выберите язык для продолжения:\n\n"
        "Xush kelibsiz! Iltimos, davom etish uchun tilni tanlang:",
        reply_markup=kb.get_language_keyboard()
    )
    await state.set_state(HRForm.waiting_for_language)


@dp.message(HRForm.waiting_for_language, F.text.in_(["🇷🇺 Русский", "🇺🇿 O'zbekcha"]))
async def process_language(message: Message, state: FSMContext):
    selected_lang = "ru" if "Русский" in message.text else "uz"
    await state.update_data(lang=selected_lang)
    
    welcome_text = (
        "Вы успешно выбрали русский язык!" 
        if selected_lang == "ru" else 
        "Siz o'zbek tilini muvaffaqiyatli tanladingiz!"
    )
    
    await state.set_state(HRForm.main_menu)
    await message.answer(welcome_text, reply_markup=kb.get_main_menu(selected_lang))


# --- ЛОГИКА АНКЕТЫ ---

@dp.message(HRForm.main_menu, F.text.in_([kb.LOCALIZATION["ru"]["btn_apply"], kb.LOCALIZATION["uz"]["btn_apply"]]))
async def start_resume(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru") 
    
    await state.set_state(HRForm.waiting_for_name)
    await message.answer(kb.LOCALIZATION[lang]["ask_name"], reply_markup=None)


@dp.message(HRForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    await state.set_state(HRForm.waiting_for_phone)
    await message.answer(kb.LOCALIZATION[lang]["ask_phone"], reply_markup=kb.get_phone_keyboard(lang))


# --- ИЗМЕНЕННЫЙ ХЭНДЛЕР ТЕЛЕФОНА (ВЕДЕТ НА ВАКАНСИИ) ---
@dp.message(HRForm.waiting_for_phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    # Переводим на шаг выбора вакансии и даем клавиатуру должностей
    await state.set_state(HRForm.waiting_for_position)
    await message.answer(kb.LOCALIZATION[lang]["ask_position"], reply_markup=kb.get_positions_keyboard(lang))


# --- НОВЫЙ ХЭНДЛЕР: ЛОВИМ ВЫБРАННУЮ ВАКАНСИЮ ---
@dp.message(HRForm.waiting_for_position)
async def process_position(message: Message, state: FSMContext):
    chosen_text = message.text
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    
    # Проверка: нажал ли человек кнопку или ввёл ерунду текстом
    valid_positions = []
    for l in ["ru", "uz"]:
        valid_positions.extend([
            kb.LOCALIZATION[l]["pos_cook"],
            kb.LOCALIZATION[l]["pos_waiter"],
            kb.LOCALIZATION[l]["pos_runner"],
            kb.LOCALIZATION[l]["pos_barista"],
            kb.LOCALIZATION[l]["pos_cleaner"]
        ])
        
    if chosen_text not in valid_positions:
        # Если текст не совпал ни с одной кнопкой, повторяем вопрос
        await message.answer(kb.LOCALIZATION[lang]["ask_position"], reply_markup=kb.get_positions_keyboard(lang))
        return

    # Сохраняем вакансию в память
    await state.update_data(position=chosen_text)
    
    # Подтягиваем обновленные данные для вывода заглушки
    updated_data = await state.get_data()
    
    debug_info = (
        f"Данные сохранены!\n\n"
        f"👤 Имя: {updated_data['name']}\n"
        f"📱 Тел: {updated_data['phone']}\n"
        f"💼 Вакансия: {updated_data['position']}"
        if lang == "ru" else
        f"Ma'lumotlar saqlandi!\n\n"
        f"👤 FIO: {updated_data['name']}\n"
        f"📱 Tel: {updated_data['phone']}\n"
        f"💼 Vakansiya: {updated_data['position']}"
    )
    
    # Возвращаем пользователя в главное меню
    await state.set_state(HRForm.main_menu)
    await message.answer(debug_info, reply_markup=kb.get_main_menu(lang))


@dp.message(HRForm.waiting_for_phone)
async def phone_incorrect(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("lang", "ru")
    await message.answer(kb.LOCALIZATION[lang]["ask_phone"], reply_markup=kb.get_phone_keyboard(lang))


# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())