import os
import json
import threading
import time
from datetime import datetime
from flask import Flask
import telebot
import firebase_admin
from firebase_admin import credentials, db

# ==========================================
# 1. ИНИЦИАЛИЗАЦИЯ
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
# 2. КОМАНДЫ
# ==========================================
@bot.message_handler(commands=['start', 'mychat'])
def send_welcome(message):
    chat_id = message.chat.id
    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Ваш chat_id:\n"
        f"`{chat_id}`\n\n"
        f"Скопируйте это число и вставьте в приложении «Пульт оператора» → Профиль → 🔐 Привязать Telegram."
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, "Команды:\n/start — chat_id\n/mychat — ID\n/help — справка")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Нажмите /start, чтобы получить ваш ID.")

# ==========================================
# 3. СЛУШАТЕЛИ FIREBASE
# ==========================================
def on_2fa_request(event):
    if event.data is None: return
    try:
        data = event.data
        code = data.get('code')
        chat_id = data.get('tgChatId')
        if chat_id and code:
            bot.send_message(chat_id, f"🔐 <b>Код входа в пульт:</b>\n\n<code>{code}</code>\n\nДействителен 5 минут.", parse_mode='HTML')
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
                bot.send_message(tg, f"📋 <b>Новый документ на подпись:</b>\n{title}\n\nЗайдите в приложение → ✍️ Подписание.", parse_mode='HTML')
    except Exception as e:
        print(f"Ошибка on_signing_doc: {e}")

# ==========================================
# 4. ДЕЖУРСТВА
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
                            bot.send_message(op['tgChatId'], f"📅 <b>Напоминание:</b>\n{name}, сегодня ваша смена!", parse_mode='HTML')
                            time.sleep(3600)
        except Exception as e:
            print(f"Ошибка duty: {e}")
        time.sleep(3600)

# ==========================================
# 5. ЗАПУСК
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
    print("✅ Бот запущен...")
    bot.infinity_polling()

@app.route('/')
def health():
    return "Bot is running"

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=start_firebase_listeners, daemon=True).start()
    threading.Thread(target=check_duty, daemon=True).start()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)