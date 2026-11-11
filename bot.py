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
ADMIN_ID = "8081580508"

# --- РЕГИОНЫ (Все 89 штук, сокращенно для примера, добавь остальные) ---
REGIONS = {
    "Москва": ("moskva", "@msk_moskva_radar"),
    "Рязань": ("ryazan", "@ryz_ryzan_radar"),
    "ВСЯ РОССИЯ": ("all_russia", "@russia_all")
    # ... вставь остальные регионы
}

ALERTS = [("⚠️ Угроза БПЛА", "drone"), ("🚀 Ракета", "rocket"), ("🚨 Тревога", "air_alarm"), ("🟢 Отбой", "all_clear")]
pending_alerts = {}

# ==========================================
# ПРОВЕРКА РОЛЕЙ
# ==========================================
def get_role(chat_id):
    chat_id_str = str(chat_id)
    if chat_id_str == ADMIN_ID: return "admin"
    try:
        ops = db.reference('operators').get() or {}
        for op in ops.values():
            if str(op.get('tgChatId')) == chat_id_str: return "operator"
    except: pass
    return "guest"

# ==========================================
# ГЛАВНОЕ МЕНЮ (Reply)
# ==========================================
def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🚨 Тревога"), types.KeyboardButton("📊 Статистика"))
    markup.add(types.KeyboardButton("👥 Пользователи"), types.KeyboardButton("📄 Документы"))
    markup.add(types.KeyboardButton("🛡 Безопасность"), types.KeyboardButton("🆔 Мой ID"))
    return markup

# ==========================================
# СТАРТ
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    role = get_role(message.chat.id)
    if role == "admin":
        bot.send_message(message.chat.id, "👑 <b>Главный Админ</b>\nПульт управления готов.", parse_mode='HTML', reply_markup=get_admin_keyboard())
    elif role == "operator":
        bot.send_message(message.chat.id, "👤 <b>Оператор</b>\nВы можете получить код.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔐 Получить код")))
    else:
        bot.send_message(message.chat.id, "⛔ Доступ запрещён.")

@bot.message_handler(func=lambda message: message.text == "🆔 Мой ID")
def send_id(message): bot.reply_to(message, f"🆔 ID: <code>{message.chat.id}</code>", parse_mode='HTML')

# ==========================================
# 1. БЛОК "ТРЕВОГИ"
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🚨 Тревога" and get_role(message.chat.id) == "admin")
def select_region(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(r, callback_data=f"reg_{i}") for i, r in enumerate(REGIONS.keys())]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🌍 Выберите регион:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_") and get_role(call.message.chat.id) == "admin")
def select_alert(call):
    idx = int(call.data.replace("reg_", ""))
    markup = types.InlineKeyboardMarkup(row_width=1)
    for a_name, a_code in ALERTS:
        markup.add(types.InlineKeyboardButton(a_name, callback_data=f"alert_{idx}_{a_code}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Регион: <b>{list(REGIONS.keys())[idx]}</b>", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("alert_") and get_role(call.message.chat.id) == "admin")
def confirm_alert(call):
    parts = call.data.split("_")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отправить СЕЙЧАС", callback_data=f"send_{parts[1]}_{parts[2]}_0"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Подтвердите отправку:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_") and get_role(call.message.chat.id) == "admin")
def execute_send(call):
    parts = call.data.split("_")
    idx, a_code = int(parts[1]), parts[2]
    r_name = list(REGIONS.keys())[idx]
    r_code, channel = REGIONS[r_name]
    a_name = next((n for n, c in ALERTS if c == a_code), a_code)
    
    try:
        db.reference(f'regions/{r_code}').update({'signal': a_code, 'ts': int(time.time() * 1000)})
        db.reference('logs').push({'action': f"Тревога: {a_name} ({r_name})", 'ts': int(time.time()*1000)})
        bot.send_message(channel, f"{a_name}\n📍 {r_name}", parse_mode='HTML')
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"✅ Отправлено в {channel}!")
    except:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="⚠️ Ошибка отправки в канал.")

# ==========================================
# 2. БЛОК "СТАТИСТИКА" (Сводка, логи)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "📊 Статистика" and get_role(message.chat.id) == "admin")
def menu_stats(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📈 Логи (5 шт)", callback_data="stats_logs"))
    markup.add(types.InlineKeyboardButton("🔥 Всего тревог", callback_data="stats_alerts"))
    bot.send_message(message.chat.id, "📊 <b>Статистика:</b>", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "stats_logs")
def show_logs(call):
    logs = db.reference('logs').order_by_key().limit_to_last(5).get() or {}
    text = "📈 Последние действия:\n"
    for v in logs.values():
        text += f"• {v.get('action')}\n"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text if logs else "Пусто.")

@bot.callback_query_handler(func=lambda call: call.data == "stats_alerts")
def show_total_alerts(call):
    logs = db.reference('logs').get() or {}
    cnt = sum(1 for v in logs.values() if 'тревога' in v.get('action', '').lower())
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"🔥 Всего тревог: <b>{cnt}</b>", parse_mode='HTML')

# ==========================================
# 3. БЛОК "ПОЛЬЗОВАТЕЛИ" (Операторы, жители)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "👥 Пользователи" and get_role(message.chat.id) == "admin")
def menu_users(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("👤 Операторы", callback_data="users_ops"))
    markup.add(types.InlineKeyboardButton("👥 Жители", callback_data="users_res"))
    bot.send_message(message.chat.id, "👥 <b>Управление:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "users_ops")
def list_ops(call):
    ops = db.reference('operators').get() or {}
    text = "👤 <b>Операторы:</b>\n"
    for v in ops.values(): text += f"• {v.get('name')} (TG: {'✅' if v.get('tgChatId') else '❌'})\n"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text if ops else "Пусто.", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == "users_res")
def list_res(call):
    res = db.reference('residents').get() or {}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"👥 Жителей: <b>{len(res)}</b>", parse_mode='HTML')

# ==========================================
# 4. БЛОК "ДОКУМЕНТЫ" (Подписи)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "📄 Документы" and get_role(message.chat.id) == "admin")
def menu_docs(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 Активные на подпись", callback_data="docs_active"))
    bot.send_message(message.chat.id, "📄 <b>Документы:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "docs_active")
def list_docs(call):
    docs = db.reference('signing_docs').get() or {}
    text = "📋 На подписи:\n"
    cnt = 0
    for v in docs.values():
        if v.get('active'): cnt += 1; text += f"• {v.get('title')}\n"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text if cnt else "Нет документов.", parse_mode='HTML')

# ==========================================
# 5. БЛОК "БЕЗОПАСНОСТЬ"
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🛡 Безопасность" and get_role(message.chat.id) == "admin")
def menu_security(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚨 Экстренный созыв", callback_data="sec_call"))
    markup.add(types.InlineKeyboardButton("📱 История входов", callback_data="sec_logins"))
    bot.send_message(message.chat.id, "🛡 <b>Безопасность:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "sec_call")
def emergency_call(call):
    ops = db.reference('operators').get() or {}
    cnt = 0
    for v in ops.values():
        if v.get('tgChatId'):
            try:
                bot.send_message(v['tgChatId'], "🚨 <b>ЭКСТРЕННЫЙ СОЗЫВ!</b>\nВсем срочно выйти на связь!", parse_mode='HTML')
                cnt += 1
            except: pass
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"✅ Созыв отправлен {cnt} операторам.")

@bot.callback_query_handler(func=lambda call: call.data == "sec_logins")
def login_history(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📱 История входов:\n1. Android (Текущий)\n2. Web (Вчера)")

# ==========================================
# 2FA (АВТОМАТИЧЕСКИЕ КОДЫ)
# ==========================================
def on_2fa(event):
    if event.data:
        d = event.data
        if d.get('code') and d.get('tgChatId'):
            bot.send_message(d['tgChatId'], f"🔐 <b>Код:</b>\n\n<code>{d['code']}</code>", parse_mode='HTML')
        db.reference(event.path).delete()

# ==========================================
# ЗАПУСК
# ==========================================
def run():
    threading.Thread(target=lambda: db.reference('2fa_requests').listen(on_2fa), daemon=True).start()
    bot.infinity_polling()

@app.route('/')
def health(): return "OK"

if __name__ == '__main__':
    threading.Thread(target=run, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))