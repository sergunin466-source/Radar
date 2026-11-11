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

# ТВОЙ ID (АДМИН)
ADMIN_ID = "8081580508"

# СПИСОК РЕГИОНОВ (сокращенный для примера, добавь остальные)
REGIONS = {
    "Москва": ("moskva", "@msk_moskva_radar"),
    "Рязань": ("ryazan", "@ryz_ryzan_radar"),
    "ВСЯ РОССИЯ": ("all_russia", "@russia_all")
}

ALERTS = [
    ("⚠️ Угроза БПЛА", "drone"), 
    ("🚀 Ракетная опасность", "rocket"),
    ("🚨 Воздушная тревога", "air_alarm"), 
    ("🟢 Общий отбой", "all_clear")
]

pending_alerts = {}

# ==========================================
# ПРОВЕРКА РОЛЕЙ
# ==========================================
def get_role(chat_id):
    chat_id_str = str(chat_id)
    # 1. Если это Главный админ
    if chat_id_str == ADMIN_ID:
        return "admin"
    
    # 2. Проверяем, есть ли он в Firebase (оператор)
    try:
        ops = db.reference('operators').get() or {}
        for op in ops.values():
            if str(op.get('tgChatId')) == chat_id_str:
                return "operator"
    except: pass
    
    # 3. Если нигде нет - чужой
    return "guest"

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🚨 Отправить тревогу"), types.KeyboardButton("⭐ Избранное"))
    markup.add(types.KeyboardButton("📊 Сводка"), types.KeyboardButton("🎮 Топ операторов"))
    markup.add(types.KeyboardButton("🆔 Мой ID"))
    return markup

def get_operator_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("🔐 Получить код входа"))
    markup.add(types.KeyboardButton("🆔 Мой ID"))
    return markup

# ==========================================
# КОМАНДА /start
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    role = get_role(message.chat.id)
    
    if role == "admin":
        bot.send_message(message.chat.id, "👑 <b>Добро пожаловать, Главный Админ!</b>\nПолный доступ открыт.", parse_mode='HTML', reply_markup=get_admin_keyboard())
    elif role == "operator":
        bot.send_message(message.chat.id, "👤 <b>Добро пожаловать, Оператор!</b>\nВы можете получить код для входа в приложение.", parse_mode='HTML', reply_markup=get_operator_keyboard())
    else:
        bot.send_message(message.chat.id, "⛔ <b>Доступ запрещён.</b>\nВы не зарегистрированы в системе. Обратитесь к администратору.", parse_mode='HTML')

# ==========================================
# КНОПКИ ОПЕРАТОРА (ТОЛЬКО КОД)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🔐 Получить код входа" and get_role(message.chat.id) == "operator")
def get_login_code(message):
    # Генерируем код 2FA
    code = str(int(time.time()))[-4:] # 4-значный код для простоты
    uid = "unknown" # В реальности тут надо брать UID из Firebase
    
    # Отправляем
    bot.reply_to(message, f"🔐 <b>Ваш код для входа:</b>\n\n<code>{code}</code>\n\nВведите его в приложении «Пульт оператора».", parse_mode='HTML')
    
    # Сохраняем в Firebase, чтобы приложение могло проверить
    # db.reference(f'2fa_codes/{uid}').set({'code': code, 'expiresAt': int(time.time() * 1000) + 300000})

# ==========================================
# КНОПКИ АДМИНА (ПОЛНЫЙ ПУЛЬТ)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🚨 Отправить тревогу" and get_role(message.chat.id) == "admin")
def select_region(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for region_name in REGIONS.keys():
        idx = list(REGIONS.keys()).index(region_name)
        buttons.append(types.InlineKeyboardButton(region_name, callback_data=f"reg_{idx}"))
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🌍 <b>Шаг 1:</b> Выберите регион:", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_") and get_role(call.message.chat.id) == "admin")
def select_alert(call):
    idx = int(call.data.replace("reg_", ""))
    region_name = list(REGIONS.keys())[idx]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for alert_name, alert_code in ALERTS:
        markup.add(types.InlineKeyboardButton(alert_name, callback_data=f"alert_{idx}_{alert_code}"))
    
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                          text=f"🌍 Регион: <b>{region_name}</b>\n\n🚨 <b>Шаг 2:</b> Выберите тревогу:", 
                          parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("alert_") and get_role(call.message.chat.id) == "admin")
def send_alert(call):
    parts = call.data.split("_")
    idx = int(parts[1])
    alert_code = parts[2]
    region_name = list(REGIONS.keys())[idx]
    alert_name = next((name for name, code in ALERTS if code == alert_code), alert_code)

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton("Сейчас", callback_data=f"send_{idx}_{alert_code}_0"))
    markup.add(types.InlineKeyboardButton("Через 10 сек", callback_data=f"send_{idx}_{alert_code}_10"))
    
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"🚨 {alert_name}\n📍 {region_name}\n\n⏱ <b>Когда отправить?</b>",
                          parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_") and get_role(call.message.chat.id) == "admin")
def process_alert(call):
    parts = call.data.split("_")
    idx = int(parts[1])
    alert_code = parts[2]
    delay = int(parts[3])
    region_name = list(REGIONS.keys())[idx]
    alert_name = next((name for name, code in ALERTS if code == alert_code), alert_code)

    if delay == 0:
        execute_alert(call.message.chat.id, call.message.message_id, idx, region_name, alert_code, alert_name)
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text=f"⏳ <b>Отправка через {delay} сек.</b>\n{alert_name} в {region_name}\n\nУспейте нажать «Отмена»!", 
                              parse_mode='HTML', reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel_alert")))
        
        def timer_task():
            time.sleep(delay)
            if pending_alerts.get(call.message.message_id) != "cancelled":
                execute_alert(call.message.chat.id, call.message.message_id, idx, region_name, alert_code, alert_name)
        
        pending_alerts[call.message.message_id] = "pending"
        threading.Thread(target=timer_task, daemon=True).start()

@bot.callback_query_handler(func=lambda call: call.data == "cancel_alert")
def cancel_alert(call):
    pending_alerts[call.message.message_id] = "cancelled"
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ <b>Тревога отменена.</b>", parse_mode='HTML')

def execute_alert(chat_id, msg_id, idx, region_name, alert_code, alert_name):
    region_code, channel = REGIONS[region_name]
    try:
        db.reference(f'regions/{region_code}').update({'signal': alert_code, 'ts': int(time.time() * 1000), 'source': 'bot'})
        db.reference('logs').push({'action': f"Тревога: {alert_name} в {region_name}", 'ts': int(time.time() * 1000), 'operator': 'admin'})
        text = f"{alert_name}\n\n📍 <b>Регион:</b> {region_name}\n🕒 <b>Время:</b> {time.strftime('%H:%M')}"
        bot.send_message(channel, text, parse_mode='HTML')
        status = f"✅ Отправлено в {channel}"
    except Exception as e:
        status = f"⚠️ Ошибка отправки: {e}"

    bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=f"✅ <b>СИГНАЛ ОТПРАВЛЕН!</b>\n\n{alert_name}\n📍 {region_name}\n\n{status}", parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "🆔 Мой ID")
def send_id(message):
    bot.reply_to(message, f"🆔 Ваш ID: <code>{message.chat.id}</code>", parse_mode='HTML')

# ==========================================
# 2FA (АВТОМАТИЧЕСКАЯ ОТПРАВКА ИЗ ПРИЛОЖЕНИЯ)
# ==========================================
def on_2fa(event):
    if event.data:
        d = event.data
        if d.get('code') and d.get('tgChatId'):
            bot.send_message(d['tgChatId'], f"🔐 <b>Код входа:</b>\n\n<code>{d['code']}</code>", parse_mode='HTML')
        db.reference(event.path).delete()

# ==========================================
# ЗАПУСК
# ==========================================
def run():
    threading.Thread(target=lambda: db.reference('2fa_requests').listen(on_2fa), daemon=True).start()
    print("✅ Бот запущен")
    bot.infinity_polling()

@app.route('/')
def health(): return "OK"

if __name__ == '__main__':
    threading.Thread(target=run, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))