import os
import json
import threading
import time
from datetime import datetime
from flask import Flask
import telebot
from telebot import types  # Подключаем кнопки
import firebase_admin
from firebase_admin import credentials, db

# ==========================================
# 1. ИНИЦИАЛИЗАЦИЯ И БЕЗОПАСНОСТЬ
# ==========================================
app = Flask(__name__)

TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_URL = os.environ.get('FIREBASE_URL')

if not TOKEN or not DATABASE_URL:
    print("ОШИБКА: Не заданы BOT_TOKEN или FIREBASE_URL!")
    exit(1)

try:
    cred_json = os.environ.get('FIREBASE_KEY')
    if not cred_json:
        print("ОШИБКА: FIREBASE_KEY не задан!")
        exit(1)
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
    print("✅ Firebase подключен безопасно.")
except Exception as e:
    print(f"❌ ОШИБКА Firebase: {e}")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (КЛАВИАТУРЫ)
# ==========================================
def get_main_keyboard(chat_id):
    """Создает клавиатуру, проверяя, является ли пользователь оператором"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Проверяем, есть ли chat_id в базе операторов
    is_operator = False
    try:
        ops = db.reference('operators').get() or {}
        for op in ops.values():
            if str(op.get('tgChatId')) == str(chat_id):
                is_operator = True
                break
    except: pass

    if is_operator:
        btn_status = types.KeyboardButton("📊 Статус системы")
        btn_duty = types.KeyboardButton("📅 Моя смена")
        btn_app = types.KeyboardButton("📱 Открыть Пульт")
        btn_id = types.KeyboardButton("🆔 Мой ID")
        markup.add(btn_status, btn_duty)
        markup.add(btn_app, btn_id)
    else:
        # Если человек просто зашел, даем ему только кнопку получить ID
        markup.add(types.KeyboardButton("🆔 Получить chat_id"))

    return markup

# ==========================================
# 3. ОБРАБОТЧИКИ КОМАНД И КНОПОК
# ==========================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    name = message.from_user.first_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Добро пожаловать в бот системы оповещения.\n"
        f"Используй кнопки ниже для навигации."
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=get_main_keyboard(message.chat.id))

@bot.message_handler(func=lambda message: message.text in ["🆔 Получить chat_id", "🆔 Мой ID", "/mychat"])
def cmd_get_id(message):
    chat_id = message.chat.id
    text = (
        f"🆔 <b>Ваш Telegram ID:</b>\n\n"
        f"<code>{chat_id}</code>\n\n"
        f"Скопируйте это число (нажмите на него) и вставьте в приложении "
        f"«Пульт оператора» → Профиль → 🔐 Привязать Telegram (2FA)."
    )
    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=get_main_keyboard(chat_id))

@bot.message_handler(func=lambda message: message.text == "📊 Статус системы")
def cmd_status(message):
    try:
        # Считаем данные из базы
        residents = db.reference('residents').get() or {}
        regions = db.reference('regions').get() or {}
        
        total_residents = len(residents)
        active_alerts = 0
        for r in regions.values():
            sig = r.get('signal')
            if sig and 'clear' not in sig:
                active_alerts += 1

        text = (
            f"📊 <b>Статус системы</b>\n\n"
            f"👥 Жителей в базе: <b>{total_residents}</b>\n"
            f"🚨 Активных тревог: <b>{active_alerts}</b>\n"
            f"🟢 Система работает в штатном режиме."
        )
        bot.reply_to(message, text, parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при получении статуса.")

@bot.message_handler(func=lambda message: message.text == "📅 Моя смена")
def cmd_duty(message):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        duty = db.reference(f'duty_schedule/{today}').get()
        if duty and duty.get('email'):
            name = duty.get('name', 'Неизвестно')
            email = duty.get('email', '')
            # Проверяем, совпадает ли с текущим оператором (по chat_id)
            ops = db.reference('operators').get() or {}
            is_me = False
            for op in ops.values():
                if str(op.get('tgChatId')) == str(message.chat.id) and op.get('email') == email:
                    is_me = True
                    break
            
            if is_me:
                bot.reply_to(message, f"📅 <b>Ваша смена сегодня!</b>\n\nДежурный: {name}\nДата: {today}", parse_mode='HTML')
            else:
                bot.reply_to(message, f"📅 <b>Сегодня на смене:</b>\n{name}\n\nВы не дежурите сегодня.", parse_mode='HTML')
        else:
            bot.reply_to(message, "📅 На сегодня дежурный не назначен.")
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при получении данных о смене.")

@bot.message_handler(func=lambda message: message.text == "📱 Открыть Пульт")
def cmd_app(message):
    bot.reply_to(message, "📱 Откройте приложение <b>«Пульт оператора»</b> на своем телефоне для подачи сигналов и управления.", parse_mode='HTML')

# Обработка остального текста
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Пожалуйста, используйте кнопки внизу экрана для управления ботом. 👇", reply_markup=get_main_keyboard(message.chat.id))


# ==========================================
# 4. СЛУШАТЕЛИ FIREBASE (АВТО-УВЕДОМЛЕНИЯ)
# ==========================================
def on_2fa_request(event):
    if event.data is None: return
    try:
        data = event.data
        code = data.get('code')
        chat_id = data.get('tgChatId')
        if chat_id and code:
            markup = types.InlineKeyboardMarkup()
            # Добавляем кнопку "Скопировать" (просто визуальная подсказка)
            markup.add(types.InlineKeyboardButton("✅ Я ввел код", callback_data="code_entered"))
            
            bot.send_message(chat_id, 
                f"🔐 <b>Код входа в пульт:</b>\n\n"
                f"<code>{code}</code>\n\n"
                f"Действителен 5 минут. Никому не сообщайте его.", 
                parse_mode='HTML', reply_markup=markup)
        db.reference(event.path).delete()
    except Exception as e:
        print(f"Ошибка 2FA: {e}")

def on_signing_doc(event):
    if event.data is None: return
    try:
        data = event.data
        title = data.get('title', 'Без названия')
        targets = data.get('targets', [])
        created_at = data.get('createdAt', 0)
        
        if time.time() * 1000 - created_at > 60000:
            return
            
        ops = db.reference('operators').get() or {}
        for op in ops.values():
            email = op.get('email', '').lower()
            tg = op.get('tgChatId')
            if not tg: continue
            if '*' in targets or email in targets:
                # Инлайн кнопка для документа
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📄 Ознакомиться и подписать", callback_data=f"read_doc_{title}"))
                
                bot.send_message(tg, 
                    f"📋 <b>Новый документ на подпись:</b>\n\n«{title}»\n\n"
                    f"Пожалуйста, зайдите в приложение для ознакомления и подписания.", 
                    parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        print(f"Ошибка on_signing_doc: {e}")

# Обработка нажатий на инлайн-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "code_entered":
        bot.answer_callback_query(call.id, "Отлично! Введите код в приложении.")
        bot.delete_message(call.message.chat.id, call.message.message_id) # Удаляем сообщение с кодом для безопасности
    elif call.data.startswith("read_doc_"):
        bot.answer_callback_query(call.id, "Откройте приложение «Пульт оператора» → ✍️ Подписание")
        bot.send_message(call.message.chat.id, "Для просмотра документа перейдите в приложение в раздел «✍️ Подписание».")

# ==========================================
# 5. ДЕЖУРСТВА (ФОНОВАЯ ЗАДАЧА)
# ==========================================
def check_duty():
    while True:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            duty = db.reference(f'duty_schedule/{today}').get()
            if duty and duty.get('email'):
                email = duty['email'].lower()
                name = duty.get('name', 'Оператор')
                ops = db.reference('operators').get() or {}
                for op in ops.values():
                    if op.get('email', '').lower() == email and op.get('tgChatId'):
                        if 8 <= datetime.now().hour <= 9:
                            bot.send_message(op['tgChatId'], f"📅 <b>Напоминание:</b>\n{name}, сегодня ваша смена оператора!", parse_mode='HTML')
                            time.sleep(3600)
        except Exception as e:
            print(f"Ошибка duty: {e}")
        time.sleep(3600)

# ==========================================
# 6. ЗАПУСК
# ==========================================
def start_firebase_listeners():
    try:
        db.reference('2fa_requests').listen(on_2fa_request)
        print("✅ Слушатель 2FA запущен.")
    except Exception as e:
        print(f"Ошибка слушателя 2FA: {e}")
    
    try:
        db.reference('signing_docs').listen(on_signing_doc)
        print("✅ Слушатель документов запущен.")
    except Exception as e:
        print(f"Ошибка слушателя документов: {e}")

def run_bot():
    print("✅ Бот запущен и слушает сообщения...")
    bot.infinity_polling()

@app.route('/')
def health():
    return "Bot is running successfully!"

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=start_firebase_listeners, daemon=True).start()
    threading.Thread(target=check_duty, daemon=True).start()
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)