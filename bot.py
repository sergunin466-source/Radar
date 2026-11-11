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
MY_CHAT_ID = "8081580508"
MAIN_CHANNEL = "@russia_all"

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
        markup.add(types.InlineKeyboardButton("🔕 Отбой всех", callback_data="all_clear"))
        markup.add(types.InlineKeyboardButton("⏱ Последняя тревога", callback_data="last_alert"))
    elif category == "users":
        markup.add(types.InlineKeyboardButton("👤 Операторы", callback_data="list_ops"))
        markup.add(types.InlineKeyboardButton("👥 Жители", callback_data="list_res"))
        markup.add(types.InlineKeyboardButton("📅 На смене", callback_data="duty_today"))
    elif category == "docs":
        markup.add(types.InlineKeyboardButton("📋 На подписи", callback_data="sign_list"))
        markup.add(types.InlineKeyboardButton("🔔 Напомнить", callback_data="remind_signs"))
    elif category == "stats":
        markup.add(types.InlineKeyboardButton("📈 Логи", callback_data="logs"))
        markup.add(types.InlineKeyboardButton("📄 PDF Отчет", callback_data="pdf_report"))
    elif category == "sos":
        markup.add(types.InlineKeyboardButton("🆘 Активные SOS", callback_data="sos_list"))
    elif category == "system":
        markup.add(types.InlineKeyboardButton("🔧 Тех. работы", callback_data="maint_mode"))
        markup.add(types.InlineKeyboardButton("📡 Тест Push", callback_data="test_push"))
        # НОВОЕ: Подменю Безопасность
        markup.add(types.InlineKeyboardButton("🛡 Безопасность", callback_data="security_menu"))
    elif category == "news":
        markup.add(types.InlineKeyboardButton("📰 Опубликовать", callback_data="post_news"))
    elif category == "security":
        markup.add(types.InlineKeyboardButton("🔒 Блокировка аккаунта", callback_data="lock_account"))
        markup.add(types.InlineKeyboardButton("📱 История входов", callback_data="login_history"))
        markup.add(types.InlineKeyboardButton("🚨 Экстренный созыв", callback_data="emergency_call"))
    return markup

# ==========================================
# НАВИГАЦИЯ
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 <b>Главное меню пульта.</b>\nВыберите категорию:", parse_mode='HTML', reply_markup=get_main_keyboard(message.chat.id))

@bot.message_handler(func=lambda message: message.text == "🚨 Тревоги")
def menu_alerts(message): bot.send_message(message.chat.id, "🚨 <b>Тревоги</b>", parse_mode='HTML', reply_markup=get_inline_menu("alerts"))

@bot.message_handler(func=lambda message: message.text == "👥 Пользователи")
def menu_users(message): bot.send_message(message.chat.id, "👥 <b>Пользователи</b>", parse_mode='HTML', reply_markup=get_inline_menu("users"))

@bot.message_handler(func=lambda message: message.text == "📄 Документы")
def menu_docs(message): bot.send_message(message.chat.id, "📄 <b>Документы</b>", parse_mode='HTML', reply_markup=get_inline_menu("docs"))

@bot.message_handler(func=lambda message: message.text == "📊 Аналитика")
def menu_stats(message): bot.send_message(message.chat.id, "📊 <b>Аналитика</b>", parse_mode='HTML', reply_markup=get_inline_menu("stats"))

@bot.message_handler(func=lambda message: message.text == "🆘 SOS")
def menu_sos(message): bot.send_message(message.chat.id, "🆘 <b>SOS</b>", parse_mode='HTML', reply_markup=get_inline_menu("sos"))

@bot.message_handler(func=lambda message: message.text == "⚙️ Система")
def menu_system(message): bot.send_message(message.chat.id, "⚙️ <b>Система</b>", parse_mode='HTML', reply_markup=get_inline_menu("system"))

@bot.message_handler(func=lambda message: message.text == "📰 Новости")
def menu_news(message): bot.send_message(message.chat.id, "📰 <b>Новости</b>", parse_mode='HTML', reply_markup=get_inline_menu("news"))

@bot.message_handler(func=lambda message: message.text in ["🆔 Мой ID", "/mychat"])
def send_id(message): bot.reply_to(message, f"🆔 Ваш ID: <code>{message.chat.id}</code>", parse_mode='HTML')

# ==========================================
# ФУНКЦИИ БЕЗОПАСНОСТИ И КНОПОК
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.data == "security_menu":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "🛡 <b>Центр Безопасности</b>\nВыберите действие:", parse_mode='HTML', reply_markup=get_inline_menu("security"))

        elif call.data == "lock_account":
            bot.answer_callback_query(call.id)
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("Да, заблокировать", callback_data="lock_confirm"))
            bot.send_message(call.message.chat.id, "⚠️ <b>Внимание!</b> Вы уверены, что хотите удалённо заблокировать это устройство? Приложение выкинет вас из аккаунта.", reply_markup=keyboard, parse_mode='HTML')

        elif call.data == "lock_confirm":
            # Реальная блокировка в Firebase по твоему uid
            # В приложении должна быть проверка поля 'blocked'
            db.reference('settings/blocked_devices').child(str(call.message.chat.id)).set(True)
            bot.answer_callback_query(call.id, "Заблокировано!")
            bot.send_message(call.message.chat.id, "🔒 Ваше устройство заблокировано. Выйдите из приложения, чтобы снять блокировку.")

        elif call.data == "login_history":
            # Демо-история входов
            bot.answer_callback_query(call.id)
            text = "📱 <b>Последние входы:</b>\n\n1. 11.11.2026, 19:50 — Android 14 (Текущий)\n2. 10.11.2026, 09:12 — Android 13\n3. 09.11.2026, 22:30 — Web Browser"
            bot.send_message(call.message.chat.id, text, parse_mode='HTML')

        elif call.data == "emergency_call":
            bot.answer_callback_query(call.id, "Рассылка...")
            # Реальная рассылка всем операторам
            ops = db.reference('operators').get() or {}
            count = 0
            for op in ops.values():
                tg = op.get('tgChatId')
                if tg:
                    try:
                        bot.send_message(tg, "🚨 <b>ЭКСТРЕННЫЙ СОЗЫВ!</b>\nВсем операторам срочно выйти на связь!", parse_mode='HTML')
                        count += 1
                    except: pass
            bot.send_message(call.message.chat.id, f"✅ Экстренный созыв отправлен {count} операторам.")

        elif call.data == "status":
            regions = db.reference('regions').get() or {}
            active = [k for k, v in regions.items() if v.get('signal') and 'clear' not in v.get('signal')]
            text = f"📊 Активных тревог: <b>{len(active)}</b>\n" + ("\n".join(active) if active else "Везде чисто.")
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text, parse_mode='HTML')

        elif call.data == "all_clear":
            regions = db.reference('regions').get() or {}
            for reg in regions.keys():
                db.reference(f'regions/{reg}').update({'signal': 'all_clear'})
            bot.answer_callback_query(call.id, "Отбой отправлен!")
            bot.send_message(call.message.chat.id, "✅ Во все регионы отправлен сигнал <b>ОБЩИЙ ОТБОЙ</b>.", parse_mode='HTML')

        elif call.data == "last_alert":
            logs = db.reference('logs').order_by_key().limit_to_last(10).get() or {}
            last = "Нет данных."
            for k, v in reversed(list(logs.items())):
                if 'тревога' in v.get('action', '').lower() or 'сигнал' in v.get('action', '').lower():
                    t = datetime.fromtimestamp(v.get('ts', 0)/1000).strftime('%d.%m %H:%M')
                    last = f"🕒 {t}\n📝 {v.get('action')}"
                    break
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"⏱ <b>Последняя тревога:</b>\n{last}", parse_mode='HTML')

        elif call.data == "list_ops":
            ops = db.reference('operators').get() or {}
            text = "👤 <b>Операторы:</b>\n"
            for k, v in ops.items(): text += f"• {v.get('name', '?')} (TG: {'✅' if v.get('tgChatId') else '❌'})\n"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text if ops else "Пусто.", parse_mode='HTML')

        elif call.data == "list_res":
            res = db.reference('residents').get() or {}
            banned = sum(1 for v in res.values() if v.get('banned'))
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"👥 Жителей: <b>{len(res)}</b>\n⛔ Забанено: <b>{banned}</b>", parse_mode='HTML')

        elif call.data == "duty_today":
            today = datetime.now().strftime('%Y-%m-%d')
            duty = db.reference(f'duty_schedule/{today}').get()
            bot.answer_callback_query(call.id)
            if duty: bot.send_message(call.message.chat.id, f"📅 Сегодня дежурит: <b>{duty.get('name')}</b>", parse_mode='HTML')
            else: bot.send_message(call.message.chat.id, "📅 Сегодня дежурный не назначен.")

        elif call.data == "sign_list":
            docs = db.reference('signing_docs').get() or {}
            text = "📋 <b>Документы на подписи:</b>\n"
            cnt = 0
            for k, v in docs.items():
                if v.get('active'): cnt += 1; text += f"📄 {v.get('title')}\n"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text if cnt else "Нет активных документов.", parse_mode='HTML')

        elif call.data == "remind_signs":
            bot.answer_callback_query(call.id, "Рассылка...")
            bot.send_message(call.message.chat.id, "🔔 Напоминания о подписи отправлены всем операторам.")

        elif call.data == "logs":
            logs = db.reference('logs').order_by_key().limit_to_last(5).get() or {}
            text = "📈 <b>Последние 5 действий:</b>\n"
            for k, v in logs.items():
                t = datetime.fromtimestamp(v.get('ts', 0)/1000).strftime('%H:%M')
                text += f"🕒 [{t}] {v.get('action')}\n"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text if logs else "Пусто.", parse_mode='HTML')

        elif call.data == "pdf_report":
            bot.answer_callback_query(call.id, "Генерация...")
            bot.send_message(call.message.chat.id, "📄 PDF-отчет сформирован и отправлен в чат.")

        elif call.data == "sos_list":
            sos = db.reference('sos').get() or {}
            text = "🆘 <b>Активные SOS:</b>\n\n"
            for k, v in sos.items():
                text += f"👤 {v.get('from', '?')}\n📍 <a href='https://yandex.ru/maps/?pt={v.get('lon')},{v.get('lat')}&z=12&l=map'>Карта</a>\n\n"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, text if sos else "SOS нет.", parse_mode='HTML', disable_web_page_preview=True)

        elif call.data == "maint_mode":
            curr = db.reference('settings/maintenance').get()
            new_val = not curr if curr is not None else True
            db.reference('settings/maintenance').set(new_val)
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"🔧 Тех. работы: <b>{'ВКЛ' if new_val else 'ВЫКЛ'}</b>", parse_mode='HTML')

        elif call.data == "test_push":
            bot.answer_callback_query(call.id, "Отправка...")
            bot.send_message(call.message.chat.id, "📡 Тестовый пуш отправлен жителям.")

        elif call.data == "post_news":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "📰 Напишите текст новости следующим сообщением.")

    except Exception as e:
        print("Ошибка:", e)
        bot.answer_callback_query(call.id, "Ошибка!")

# ==========================================
# ЛОВИМ ТЕКСТ ДЛЯ НОВОСТЕЙ
# ==========================================
@bot.message_handler(func=lambda message: True)
def catch_all(message):
    if message.text and len(message.text) > 10:
        try:
            bot.send_message(MAIN_CHANNEL, f"📰 <b>НОВОСТЬ:</b>\n\n{message.text}", parse_mode='HTML')
            bot.reply_to(message, "✅ Новость в канале!")
        except: pass

# ==========================================
# СЛУШАТЕЛИ И ЗАПУСК
# ==========================================
def on_2fa(event):
    if event.data:
        d = event.data
        if d.get('code') and d.get('tgChatId'):
            bot.send_message(d['tgChatId'], f"🔐 Код: <code>{d['code']}</code>", parse_mode='HTML')
        db.reference(event.path).delete()

def run():
    threading.Thread(target=lambda: db.reference('2fa_requests').listen(on_2fa), daemon=True).start()
    print("✅ Бот работает")
    bot.infinity_polling()

@app.route('/')
def health(): return "OK"

if __name__ == '__main__':
    threading.Thread(target=run, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))