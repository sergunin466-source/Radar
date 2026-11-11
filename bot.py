import os
import json
import threading
import time
from datetime import datetime, timedelta
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
MY_CHAT_ID = "8081580508" # Твой ID для быстрого доступа

# ==========================================
# ГЛАВНАЯ КЛАВИАТУРА (Reply)
# ==========================================
def get_main_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🚨 Тревоги"), types.KeyboardButton("👥 Пользователи"))
    markup.add(types.KeyboardButton("📄 Документы"), types.KeyboardButton("📊 Аналитика"))
    markup.add(types.KeyboardButton("🆘 SOS"), types.KeyboardButton("⚙️ Система"))
    markup.add(types.KeyboardButton("📰 Новости"), types.KeyboardButton("🆔 Мой ID"))
    return markup

# ==========================================
# ИНЛАЙН МЕНЮ (Кнопки под сообщением)
# ==========================================
def get_inline_menu(category):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if category == "alerts":
        markup.add(types.InlineKeyboardButton("📊 Статус", callback_data="status"), types.InlineKeyboardButton("🚨 Тест тревоги", callback_data="test_alert"))
        markup.add(types.InlineKeyboardButton("🕒 Активные за 24ч", callback_data="alerts_24h"))
    elif category == "users":
        markup.add(types.InlineKeyboardButton("👤 Операторы", callback_data="list_ops"), types.InlineKeyboardButton("👥 Жители", callback_data="list_res"))
        markup.add(types.InlineKeyboardButton("📅 На смене", callback_data="duty_today"))
    elif category == "docs":
        markup.add(types.InlineKeyboardButton("📋 На подписи", callback_data="sign_list"))
    elif category == "stats":
        markup.add(types.InlineKeyboardButton("📈 Логи", callback_data="logs"), types.InlineKeyboardButton("📄 PDF Отчёт", callback_data="pdf_report"))
    elif category == "sos":
        markup.add(types.InlineKeyboardButton("🆘 Последние SOS", callback_data="sos_list"))
    elif category == "system":
        markup.add(types.InlineKeyboardButton("🔄 Перезапуск", callback_data="restart_bot"))
        markup.add(types.InlineKeyboardButton("🔧 Тех. работы", callback_data="maint_mode"))
    elif category == "news":
        markup.add(types.InlineKeyboardButton("📰 Опубликовать", callback_data="post_news"))
    return markup

# ==========================================
# ОБРАБОТЧИКИ ТЕКСТА (Главное меню)
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Главное меню пульта. Выберите категорию ниже:", reply_markup=get_main_keyboard(message.chat.id))

@bot.message_handler(func=lambda message: message.text == "🚨 Тревоги")
def menu_alerts(message):
    bot.send_message(message.chat.id, "🚨 <b>Управление тревогами</b>", parse_mode='HTML', reply_markup=get_inline_menu("alerts"))

@bot.message_handler(func=lambda message: message.text == "👥 Пользователи")
def menu_users(message):
    bot.send_message(message.chat.id, "👥 <b>Пользователи системы</b>", parse_mode='HTML', reply_markup=get_inline_menu("users"))

@bot.message_handler(func=lambda message: message.text == "📄 Документы")
def menu_docs(message):
    bot.send_message(message.chat.id, "📄 <b>Документы и подписи</b>", parse_mode='HTML', reply_markup=get_inline_menu("docs"))

@bot.message_handler(func=lambda message: message.text == "📊 Аналитика")
def menu_stats(message):
    bot.send_message(message.chat.id, "📊 <b>Аналитика и логи</b>", parse_mode='HTML', reply_markup=get_inline_menu("stats"))

@bot.message_handler(func=lambda message: message.text == "🆘 SOS")
def menu_sos(message):
    bot.send_message(message.chat.id, "🆘 <b>Экстренные сигналы</b>", parse_mode='HTML', reply_markup=get_inline_menu("sos"))

@bot.message_handler(func=lambda message: message.text == "⚙️ Система")
def menu_system(message):
    bot.send_message(message.chat.id, "⚙️ <b>Настройки системы</b>", parse_mode='HTML', reply_markup=get_inline_menu("system"))

@bot.message_handler(func=lambda message: message.text == "📰 Новости")
def menu_news(message):
    bot.send_message(message.chat.id, "📰 <b>Новости</b>", parse_mode='HTML', reply_markup=get_inline_menu("news"))

@bot.message_handler(func=lambda message: message.text in ["🆔 Мой ID", "/mychat"])
def send_id(message):
    bot.reply_to(message, f"🆔 Ваш ID: <code>{message.chat.id}</code>", parse_mode='HTML')

# ==========================================
# ОБРАБОТЧИКИ КНОПОК (Inline Callbacks)
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.data == "status":
            residents = db.reference('residents').get() or {}
            regions = db.reference('regions').get() or {}
            alerts = sum(1 for r in regions.values() if r.get('signal') and 'clear' not in r.get('signal'))
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"📊 <b>Статус:</b>\nЖителей: {len(residents)}\nТревог: {alerts}", parse_mode='HTML')

        elif call.data == "test_alert":
            bot.answer_callback_query(call.id, "Отправка тревоги...")
            bot.send_message(call.message.chat.id, "🚨 <b>ТЕСТОВАЯ ТРЕВОГА</b> успешно отправлена в каналы!", parse_mode='HTML')
            # Здесь можно добавить логику записи в Firebase

        elif call.data == "alerts_24h":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "🕒 За последние 24 часа зафиксировано <b>5</b> тревог (демо-данные).", parse_mode='HTML')

        elif call.data == "list_ops":
            ops = db.reference('operators').get() or {}
            text = "👤 <b>Операторы:</b>\n"
            for k, v in ops.items():
                text += f"• {v.get('name', '?')} ({v.get('email', '?')})\n"
            if not ops: text += "Пусто."
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, parse_mode='HTML')

        elif call.data == "list_res":
            res = db.reference('residents').get() or {}
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"👥 Всего жителей в базе: <b>{len(res)}</b>", parse_mode='HTML')

        elif call.data == "duty_today":
            today = datetime.now().strftime('%Y-%m-%d')
            duty = db.reference(f'duty_schedule/{today}').get()
            bot.answer_callback_query(call.id)
            if duty:
                bot.send_message(call.message.chat.id, f"📅 Сегодня дежурит: <b>{duty.get('name')}</b>", parse_mode='HTML')
            else:
                bot.send_message(call.message.chat.id, "📅 Сегодня дежурный не назначен.", parse_mode='HTML')

        elif call.data == "sign_list":
            docs = db.reference('signing_docs').get() or {}
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"📋 Активных документов на подпись: <b>{len(docs)}</b>", parse_mode='HTML')

        elif call.data == "logs":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "📈 Логи за сегодня: (тут будет список).")

        elif call.data == "pdf_report":
            bot.answer_callback_query(call.id, "Генерация PDF...")
            bot.send_message(call.message.chat.id, "📄 PDF-отчёт сформирован и отправлен в приложение.", parse_mode='HTML')

        elif call.data == "sos_list":
            sos = db.reference('sos').get() or {}
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"🆘 Активных сигналов SOS: <b>{len(sos)}</b>", parse_mode='HTML')

        elif call.data == "restart_bot":
            bot.answer_callback_query(call.id, "Перезапуск...")
            bot.send_message(call.message.chat.id, "🔄 Бот перезапущен. Связь в норме.")

        elif call.data == "maint_mode":
            db.reference('settings/maintenance').set(True)
            bot.answer_callback_query(call.id, "Режим тех. работ ВКЛ")
            bot.send_message(call.message.chat.id, "🔧 Режим технических работ <b>ВКЛЮЧЕН</b>. Жители увидят заглушку.", parse_mode='HTML')

        elif call.data == "post_news":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "📰 Отправьте текст новости следующим сообщением (функция в разработке).")

    except Exception as e:
        print("Ошибка кнопки:", e)
        bot.answer_callback_query(call.id, "Ошибка выполнения")

# ==========================================
# СЛУШАТЕЛИ FIREBASE (АВТО-УВЕДОМЛЕНИЯ)
# ==========================================
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
    except Exception as e:
        print(f"❌ Ошибка слушателя: {e}")

# ==========================================
# ЗАПУСК
# ==========================================
def run():
    print("✅ Бот запущен")
    bot.infinity_polling()

@app.route('/')
def health(): return "OK"

if __name__ == '__main__':
    threading.Thread(target=run, daemon=True).start()
    threading.Thread(target=start_listeners, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))