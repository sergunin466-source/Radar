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

# Секретные данные из Render
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
# КЛАВИАТУРА (Проверяет и операторов, и админов)
# ==========================================
def get_main_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    is_authorized = False
    
    try:
        # 1. Ищем в операторах
        ops = db.reference('operators').get() or {}
        for op in ops.values():
            if str(op.get('tgChatId', '')) == str(chat_id):
                is_authorized = True
                break
                
        # 2. Если не нашли, ищем в админах
        if not is_authorized:
            admins = db.reference('admins').get() or {}
            for adm in admins.values():
                if str(adm.get('tgChatId', '')) == str(chat_id):
                    is_authorized = True
                    break
    except Exception as e:
        print(f"Ошибка БД при проверке клавиатуры: {e}")

    if is_authorized:
        markup.add(types.KeyboardButton("📊 Статус системы"), types.KeyboardButton("📅 Моя смена"))
        markup.add(types.KeyboardButton("📱 Открыть Пульт"), types.KeyboardButton("🆔 Мой ID"))
    else:
        markup.add(types.KeyboardButton("🆔 Получить chat_id"))

    return markup

# ==========================================
# ОБРАБОТЧИКИ КОМАНД
# ==========================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    name = message.from_user.first_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = f"👋 Привет, <b>{name}</b>!\n\nДобро пожаловать в бот системы оповещения."
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=get_main_keyboard(message.chat.id))

@bot.message_handler(func=lambda message: message.text in ["🆔 Получить chat_id", "🆔 Мой ID", "/mychat"])
def cmd_get_id(message):
    chat_id = message.chat.id
    text = f"🆔 <b>Ваш Telegram ID:</b>\n\n<code>{chat_id}</code>\n\nСкопируйте это число и вставьте в приложении «Пульт оператора» → Профиль → 🔐 Привязать Telegram (2FA)."
    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=get_main_keyboard(chat_id))

@bot.message_handler(func=lambda message: message.text == "📊 Статус системы")
def cmd_status(message):
    try:
        residents = db.reference('residents').get() or {}
        regions = db.reference('regions').get() or {}
        total_residents = len(residents)
        active_alerts = sum(1 for r in regions.values() if r.get('signal') and 'clear' not in r.get('signal'))
        text = f"📊 <b>Статус системы</b>\n\n👥 Жителей в базе: <b>{total_residents}</b>\n🚨 Активных тревог: <b>{active_alerts}</b>\n🟢 Система работает в штатном режиме."
        bot.reply_to(message, text, parse_mode='HTML')
    except:
        bot.reply_to(message, "❌ Ошибка при получении статуса.")

@bot.message_handler(func=lambda message: message.text == "📅 Моя смена")
def cmd_duty(message):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        duty = db.reference(f'duty_schedule/{today}').get()
        if duty and duty.get('email'):
            name = duty.get('name', 'Неизвестно')
            email = duty.get('email', '')
            ops = db.reference('operators').get() or {}
            is_me = any(str(op.get('tgChatId')) == str(message.chat.id) and op.get('email') == email for op in ops.values())
            if is_me:
                bot.reply_to(message, f"📅 <b>Ваша смена сегодня!</b>\n\nДежурный: {name}\nДата: {today}", parse_mode='HTML')
            else:
                bot.reply_to(message, f"📅 <b>Сегодня на смене:</b>\n{name}\n\nВы не дежурите сегодня.", parse_mode='HTML')
        else:
            bot.reply_to(message, "📅 На сегодня дежурный не назначен.")
    except:
        bot.reply_to(message, "❌ Ошибка при получении данных о смене.")

@bot.message_handler(func=lambda message: message.text == "📱 Открыть Пульт")
def cmd_app(message):
    bot.reply_to(message, "📱 Откройте приложение <b>«Пульт оператора»</b> на телефоне для подачи сигналов.", parse_mode='HTML')

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Пожалуйста, используйте кнопки внизу экрана. 👇", reply_markup=get_main_keyboard(message.chat.id))

# ==========================================
# СЛУШАТЕЛИ FIREBASE
# ==========================================
def on_2fa_request(event):
    if event.data is None: return
    try:
        data = event.data
        code = data.get('code')
        chat_id = data.get('tgChatId')
        if chat_id and code:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Я ввел код", callback_data="code_entered"))
            bot.send_message(chat_id, f"🔐 <b>Код входа в пульт:</b>\n\n<code>{code}</code>\n\nДействителен 5 минут.", parse_mode='HTML', reply_markup=markup)
        db.reference(event.path).delete()
    except Exception as e:
        print(f"Ошибка 2FA: {e}")

def on_signing_doc(event):
    if event.data is None: return
    try:
        data = event.data
        title = data.get('title', 'Без названия')
        targets = data.get('targets', [])
        if time.time() * 1000 - data.get('createdAt', 0) > 60000: return
        ops = db.reference('operators').get() or {}
        for op in ops.values():
            email = op.get('email', '').lower()
            tg = op.get('tgChatId')
            if not tg: continue
            if '*' in targets or email in targets:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📄 Ознакомиться и подписать", callback_data=f"read_doc_{title}"))
                bot.send_message(tg, f"📋 <b>Новый документ на подпись:</b>\n\n«{title}»\n\nЗайдите в приложение.", parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        print(f"Ошибка on_signing_doc: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "code_entered":
        bot.answer_callback_query(call.id, "Отлично! Введите код в приложении.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    elif call.data.startswith("read_doc_"):
        bot.answer_callback_query(call.id, "Откройте приложение → ✍️ Подписание")
        bot.send_message(call.message.chat.id, "Для просмотра документа перейдите в раздел «✍️ Подписание».")

# ==========================================
# ДЕЖУРСТВА
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
# ЗАПУСК
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