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

def get_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    is_auth = False
    try:
        # Проверяем админов
        admins = db.reference('admins').get() or {}
        for a in admins.values():
            if str(a.get('tgChatId', '')) == str(chat_id):
                is_auth = True
                break
        # Проверяем операторов (если не админ)
        if not is_auth:
            ops = db.reference('operators').get() or {}
            for o in ops.values():
                if str(o.get('tgChatId', '')) == str(chat_id):
                    is_auth = True
                    break
    except Exception as e:
        print("DB Error:", e)

    if is_auth:
        markup.add(types.KeyboardButton("📊 Статус"), types.KeyboardButton("📅 Смена"))
        markup.add(types.KeyboardButton("📱 Пульт"), types.KeyboardButton("🆔 ID"))
    else:
        markup.add(types.KeyboardButton("🆔 Получить ID"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Используй кнопки ниже.", reply_markup=get_keyboard(message.chat.id))

@bot.message_handler(content_types=['text'])
def text_handler(message):
    if "ID" in message.text:
        bot.reply_to(message, f"Ваш ID: `{message.chat.id}`", parse_mode='Markdown')
    else:
        bot.reply_to(message, "Кнопки обновлены.", reply_markup=get_keyboard(message.chat.id))

def run():
    bot.infinity_polling()

@app.route('/')
def health(): return "OK"

if __name__ == '__main__':
    threading.Thread(target=run, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))