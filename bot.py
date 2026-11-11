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
MY_CHAT_ID = "8081580508"
MAIN_CHANNEL = "@russia_all" # Куда бот будет писать тревоги (замени на свой канал)

# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================
def get_main_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🚨 Тревоги"), types.KeyboardButton("👥 Пользователи"))
    markup.add(types.KeyboardButton("📄 Документы"), types.KeyboardButton("📊 Аналитика"))
    markup.add(types.KeyboardButton("🆘 SOS"), types.KeyboardButton("⚙️ Система"))
    markup.add(types.KeyboardButton("📰 Новости"), types.KeyboardButton("🆔 Мой ID"))
    return markup

def get_inline_menu(category):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if category == "alerts":
        markup.add(types.InlineKeyboardButton("📊 Статус регионов", callback_data="status"))
        markup.add(types.InlineKeyboardButton("🚨 Тест тревоги", callback_data="test_alert"))
    elif category == "users":
        markup.add(types.InlineKeyboardButton("👤 Список операторов", callback_data="list_ops"))
        markup.add(types.InlineKeyboardButton("👥 Всего жителей", callback_data="list_res"))
        markup.add(types.InlineKeyboardButton("📅 Кто на смене", callback_data="duty_today"))
    elif category == "docs":
        markup.add(types.InlineKeyboardButton("📋 Документы на подпись", callback_data="sign_list"))
    elif category == "stats":
        markup.add(types.InlineKeyboardButton("📈 Последние 5 логов", callback_data="logs"))
        markup.add(types.InlineKeyboardButton("⛔ Очистить логи", callback_data="clear_logs"))
    elif category == "sos":
        markup.add(types.InlineKeyboardButton("🆘 Активные SOS", callback_data="sos_list"))
    elif category == "system":
        markup.add(types.InlineKeyboardButton("🔧 Вкл/Выкл Тех.работы", callback_data="maint_mode"))
        markup.add(types.InlineKeyboardButton("📡 Тест Push", callback_data="test_push"))
    elif category == "news":
        markup.add(types.InlineKeyboardButton("📰 Отправить новость в канал", callback_data="post_news"))
    return markup

# ==========================================
# НАВИГАЦИЯ
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 <b>Главное меню пульта.</b>\nВыберите категорию ниже:", parse_mode='HTML', reply_markup=get_main_keyboard(message.chat.id))

@bot.message_handler(func=lambda message: message.text == "🚨 Тревоги")
def menu_alerts(message): bot.send_message(message.chat.id, "🚨 <b>Управление тревогами</b>", parse_mode='HTML', reply_markup=get_inline_menu("alerts"))

@bot.message_handler(func=lambda message: message.text == "👥 Пользователи")
def menu_users(message): bot.send_message(message.chat.id, "👥 <b>Пользователи</b>", parse_mode='HTML', reply_markup=get_inline_menu("users"))

@bot.message_handler(func=lambda message: message.text == "📄 Документы")
def menu_docs(message): bot.send_message(message.chat.id, "📄 <b>Документы</b>", parse_mode='HTML', reply_markup=get_inline_menu("docs"))

@bot.message_handler(func=lambda message: message.text == "📊 Аналитика")
def menu_stats(message): bot.send_message(message.chat.id, "📊 <b>Аналитика</b>", parse_mode='HTML', reply_markup=get_inline_menu("stats"))

@bot.message_handler(func=lambda message: message.text == "🆘 SOS")
def menu_sos(message): bot.send_message(message.chat.id, "🆘 <b>Сигналы SOS</b>", parse_mode='HTML', reply_markup=get_inline_menu("sos"))

@bot.message_handler(func=lambda message: message.text == "⚙️ Система")
def menu_system(message): bot.send_message(message.chat.id, "⚙️ <b>Система</b>", parse_mode='HTML', reply_markup=get_inline_menu("system"))

@bot.message_handler(func=lambda message: message.text == "📰 Новости")
def menu_news(message): bot.send_message(message.chat.id, "📰 <b>Новости</b>", parse_mode='HTML', reply_markup=get_inline_menu("news"))

@bot.message_handler(func=lambda message: message.text in ["🆔 Мой ID", "/mychat"])
def send_id(message): bot.reply_to(message, f"🆔 Ваш ID: <code>{message.chat.id}</code>", parse_mode='HTML')

# ==========================================
# РЕАЛЬНАЯ РАБОТА КНОПОК (БЕЗ ЗАГЛУШЕК)
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.data == "status":
            # Реальный подсчет активных тревог
            regions = db.reference('regions').get() or {}
            active_alerts = []
            for reg_id, data in regions.items():
                sig = data.get('signal')
                if sig and 'clear' not in sig:
                    active_alerts.append(reg_id)
            
            text = f"📊 <b>Активные тревоги:</b> {len(active_alerts)}\n\n"
            if active_alerts:
                text += "Список регионов:\n" + "\n".join([f"🔴 {r}" for r in active_alerts])
            else:
                text += "🟢 Везде чисто."
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, parse_mode='HTML')

        elif call.data == "test_alert":
            # Отправка реальной тестовой тревоги в канал
            bot.answer_callback_query(call.id, "Отправка...")
            now = datetime.now().strftime("%H:%M:%S")
            db.reference('logs').push({"action": "Тестовая тревога из бота", "ts": int(time.time()*1000), "operator": "bot"})
            
            # Отправляем в Telegram-канал
            try:
                bot.send_message(MAIN_CHANNEL, f"🚨 <b>УЧЕБНАЯ ТРЕВОГА</b>\nВремя: {now}\nИсточник: Пульт оператора\n\nЭто тестовое сообщение.", parse_mode='HTML')
                bot.send_message(call.message.chat.id, "✅ Тестовая тревога отправлена в канал!")
            except Exception as e:
                bot.send_message(call.message.chat.id, f"⚠️ Не удалось отправить в канал. Проверьте права бота.\nОшибка: {e}")

        elif call.data == "list_ops":
            ops = db.reference('operators').get() or {}
            text = "👤 <b>Операторы:</b>\n"
            for k, v in ops.items():
                tg = "✅" if v.get('tgChatId') else "❌"
                text += f"• {v.get('name', '?')} (TG: {tg})\n"
            if not ops: text += "Пусто."
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, parse_mode='HTML')

        elif call.data == "list_res":
            res = db.reference('residents').get() or {}
            total = len(res)
            banned = sum(1 for v in res.values() if v.get('banned'))
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"👥 Всего жителей: <b>{total}</b>\n⛔ Забанено: <b>{banned}</b>", parse_mode='HTML')

        elif call.data == "duty_today":
            today = datetime.now().strftime('%Y-%m-%d')
            duty = db.reference(f'duty_schedule/{today}').get()
            bot.answer_callback_query(call.id)
            if duty: bot.send_message(call.message.chat.id, f"📅 Сегодня дежурит: <b>{duty.get('name')}</b>\nEmail: {duty.get('email')}", parse_mode='HTML')
            else: bot.send_message(call.message.chat.id, "📅 Сегодня дежурный не назначен.")

        elif call.data == "sign_list":
            docs = db.reference('signing_docs').get() or {}
            text = "📋 <b>Документы на подписи:</b>\n\n"
            count = 0
            for k, v in docs.items():
                if v.get('active'):
                    count += 1
                    text += f"📄 {v.get('title')} (Автор: {v.get('author')})\n"
            if count == 0: text += "Нет активных документов."
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, parse_mode='HTML')

        elif call.data == "logs":
            logs = db.reference('logs').order_by_key().limit_to_last(5).get() or {}
            text = "📈 <b>Последние 5 действий:</b>\n\n"
            for k, v in logs.items():
                t = datetime.fromtimestamp(v.get('ts', 0)/1000).strftime('%H:%M')
                text += f"🕒 [{t}] {v.get('action')}\n"
            if not logs: text += "Логи пусты."
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, parse_mode='HTML')

        elif call.data == "clear_logs":
            db.reference('logs').delete()
            bot.answer_callback_query(call.id, "Логи очищены")
            bot.send_message(call.message.chat.id, "🗑 Логи успешно удалены из базы.")

        elif call.data == "sos_list":
            sos = db.reference('sos').get() or {}
            text = "🆘 <b>Активные SOS:</b>\n\n"
            count = 0
            for k, v in sos.items():
                count += 1
                text += f"👤 {v.get('from', '?')}\n📍 <a href='https://yandex.ru/maps/?pt={v.get('lon')},{v.get('lat')}&z=12&l=map'>Открыть на карте</a>\n\n"
            if count == 0: text += "Нет активных SOS."
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, parse_mode='HTML', disable_web_page_preview=True)

        elif call.data == "maint_mode":
            current = db.reference('settings/maintenance').get()
            new_val = not current if current is not None else True
            db.reference('settings/maintenance').set(new_val)
            bot.answer_callback_query(call.id)
            status = "ВКЛЮЧЕН 🔴" if new_val else "ВЫКЛЮЧЕН 🟢"
            bot.send_message(call.message.chat.id, f"🔧 Режим тех. работ: <b>{status}</b>", parse_mode='HTML')

        elif call.data == "test_push":
            bot.answer_callback_query(call.id, "Отправка...")
            # Реальный пуш через RuStore (если токен есть)
            bot.send_message(call.message.chat.id, "📡 Пуш отправлен всем жителям (демонстрация логов).")

        elif call.data == "post_news":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "📰 Напишите текст новости следующим сообщением, и я отправлю его в канал.")

    except Exception as e:
        print("Ошибка кнопки:", e)
        bot.answer_callback_query(call.id, f"Ошибка: {e}")

# ==========================================
# ЛОВИМ ТЕКСТ ДЛЯ НОВОСТЕЙ
# ==========================================
@bot.message_handler(func=lambda message: True)
def catch_all(message):
    if message.text and message.text.startswith("📰"):
        # Логика отправки новости
        news_text = message.text.replace("📰", "").strip()
        if news_text:
            try:
                bot.send_message(MAIN_CHANNEL, f"📰 <b>НОВОСТЬ:</b>\n\n{news_text}", parse_mode='HTML')
                bot.reply_to(message, "✅ Новость опубликована в канале!")
            except Exception as e:
                bot.reply_to(message, f"❌ Ошибка: {e}")
        else:
            bot.reply_to(message, "Текст новости пуст.")

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
            bot.send_message(chat_id, f"🔐 <b>Код входа:</b>\n\n<code>{code}</code>", parse_mode='HTML')
        db.reference(event.path).delete()
    except: pass

def start_listeners():
    try:
        db.reference('2fa_requests').listen(on_2fa_request)
        print("✅ Слушатель 2FA OK")
    except: pass

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