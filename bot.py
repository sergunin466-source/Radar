import os
import json
import threading
import time
from datetime import datetime
from flask import Flask
import telebot
from telebot import types
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_URL = os.environ.get('FIREBASE_URL')

if not TOKEN or not DATABASE_URL:
    exit(1)

try:
    cred_dict = json.loads(os.environ.get('FIREBASE_KEY'))
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
    print("✅ Firebase OK")
except Exception as e:
    print(f"❌ Firebase Error: {e}")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# ТВОЙ ID, ЧТОБЫ КНОПКИ РАБОТАЛИ ВСЕГДА
MY_CHAT_ID = "8081580508" 

def get_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Если это ты — сразу даем кнопки
    if str(chat_id) == MY_CHAT_ID:
        markup.add(types.KeyboardButton("📊 Статус системы"), types.KeyboardButton("📅 Моя смена"))
        markup.add(types.KeyboardButton("📱 Открыть Пульт"), types.KeyboardButton("🆔 Мой ID"))
        return markup

    # Для остальных проверяем базу
    is_auth = False
    try:
        admins = db.reference('admins').get() or {}
        for a in admins.values():
            if str(a.get('tgChatId', '')) == str(chat_id):
                is_auth = True
                break
        if not is_auth:
            ops = db.reference('operators').get() or {}
            for o in ops.values():
                if str(o.get('tgChatId', '')) == str(chat_id):
                    is_auth = True
                    break
    except: pass

    if is_auth:
        markup.add(types.KeyboardButton("📊 Статус системы"), types.KeyboardButton("📅 Моя смена"))
        markup.add(types.KeyboardButton("📱 Открыть Пульт"), types.KeyboardButton("🆔 Мой ID"))
    else:
        markup.add(types.KeyboardButton("🆔 Получить ID"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    name = message.from_user.first_name
    bot.send_message(message.chat.id, f"👋 Привет, <b>{name}</b>!\n\nДобро пожаловать в бот.", parse_mode='HTML', reply_markup=get_keyboard(message.chat.id))

@bot.message_handler(func=lambda message: message.text in ["🆔 Получить ID", "🆔 Мой ID", "/mychat"])
def send_id(message):
    bot.reply_to(message, f"🆔 Ваш Telegram ID:\n\n<code>{message.chat.id}</code>", parse_mode='HTML', reply_markup=get_keyboard(message.chat.id))

@bot.message_handler(func=lambda message: message.text == "📊 Статус системы")
def cmd_status(message):
    try:
        residents = db.reference('residents').get() or {}
        regions = db.reference('regions').get() or {}
        active_alerts = sum(1 for r in regions.values() if r.get('signal') and 'clear' not in r.get('signal'))
        bot.reply_to(message, f"📊 <b>Статус:</b>\nЖителей: {len(residents)}\nТревог: {active_alerts}", parse_mode='HTML')
    except:
        bot.reply_to(message, "Ошибка базы данных.")

@bot.message_handler(func=lambda message: message.text == "📅 Моя смена")
def cmd_duty(message):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        duty = db.reference(f'duty_schedule/{today}').get()
        if duty:
            bot.reply_to(message, f"📅 Сегодня дежурит: {duty.get('name', '?')}", parse_mode='HTML')
        else:
            bot.reply_to(message, "📅 Сегодня дежурный не назначен.")
    except:
        bot.reply_to(message, "Ошибка базы данных.")

@bot.message_handler(func=lambda message: message.text == "📱 Открыть Пульт")
def cmd_app(message):
    bot.reply_to(message, "📱 Откройте приложение «Пульт оператора».")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Используйте кнопки ниже. 👇", reply_markup=get_keyboard(message.chat.id))

def on_2fa_request(event):
    if event.data is None: return
    try:
        data = event.data
        code = data.get('code')
        chat_id = data.get('tgChatId')
        if chat_id and code:
            bot.send_message(chat_id, f"🔐 <b>Код входа:</b>\n\n<code>{code}</code>", parse_mode='HTML')
        db.reference(event.path).delete()
    except: pass

def start_listeners():
    try:
        db.reference('2fa_requests').listen(on_2fa_request)
        print("✅ Слушатель 2FA OK")
    except: pass

def run():
    print("✅ Бот запущен")
    bot.infinity_polling()

@app.route('/')
def health(): return "OK"

if __name__ == '__main__':
    threading.Thread(target=run, daemon=True).start()
    threading.Thread(target=start_listeners, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))