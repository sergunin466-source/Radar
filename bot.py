import os
import json
import threading
import time
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

# ==========================================
# ВСЕ 89 РЕГИОНОВ И ИХ КАНАЛЫ
# Формат: "Название": ("код_базы", "@канал")
# ==========================================
REGIONS = {
    "Москва": ("moskva", "@msk_moskva_radar"),
    "Московская обл.": ("moskovskaya_obl", "@mo_alerts"),
    "Санкт-Петербург": ("spb", "@spb_alerts"),
    "Ленинградская обл.": ("leningradskaya_obl", "@lo_alerts"),
    "Рязань": ("ryazan", "@ryz_ryzan_radar"),
    "Рязанская обл.": ("ryazanskaya_obl", "@ryz_ryzan_radar"),
    "Тверская обл.": ("tverskaya_obl", "@tver_alerts"),
    "Тульская обл.": ("tulskaya_obl", "@tula_alerts"),
    "Калужская обл.": ("kaluzhskaya_obl", "@kaluga_alerts"),
    "Смоленская обл.": ("smolenskaya_obl", "@smolensk_alerts"),
    "Брянская обл.": ("bryanskaya_obl", "@bryansk_alerts"),
    "Орловская обл.": ("orlovskaya_obl", "@orel_alerts"),
    "Курская обл.": ("kurskaya_obl", "@kursk_alerts"),
    "Белгородская обл.": ("belgorodskaya_obl", "@belgorod_alerts"),
    "Воронежская обл.": ("voronezhskaya_obl", "@voronezh_alerts"),
    "Липецкая обл.": ("lipetskaya_obl", "@lipetsk_alerts"),
    "Тамбовская обл.": ("tambovskaya_obl", "@tambov_alerts"),
    "Пензенская обл.": ("penzenskaya_obl", "@penza_alerts"),
    "Саратовская обл.": ("saratovskaya_obl", "@saratov_alerts"),
    "Волгоградская обл.": ("volgogradskaya_obl", "@volgograd_alerts"),
    "Астраханская обл.": ("astrahanskaya_obl", "@astrahan_alerts"),
    "Ростовская обл.": ("rostovskaya_obl", "@ros_rostov_radar"),
    "Краснодарский край": ("krasnodarsky_kray", "@krasnodar_alerts"),
    "Ставропольский край": ("stavropolsky_kray", "@stavropol_alerts"),
    "Республика Крым": ("krym", "@crimea_alerts"),
    "Севастополь": ("sevastopol", "@sevastopol_alerts"),
    "Республика Дагестан": ("dagestan", "@dagestan_alerts"),
    "Чеченская Республика": ("chechnya", "@chechnya_alerts"),
    "Нижегородская обл.": ("nizhegorodskaya_obl", "@nizhny_alerts"),
    "Кировская обл.": ("kirovskaya_obl", "@kirov_alerts"),
    "Костромская обл.": ("kostromskaya_obl", "@kostroma_alerts"),
    "Ярославская обл.": ("yaroslavskaya_obl", "@yaroslavl_alerts"),
    "Владимирская обл.": ("vladimirskaya_obl", "@vladimir_alerts"),
    "Ивановская обл.": ("ivanovskaya_obl", "@ivanovo_alerts"),
    "Архангельская обл.": ("arhangelskaya_obl", "@arhangelsk_alerts"),
    "Вологодская обл.": ("vologodskaya_obl", "@vologda_alerts"),
    "Мурманская обл.": ("murmanskaya_obl", "@murmansk_alerts"),
    "Новгородская обл.": ("novgorodskaya_obl", "@novgorod_alerts"),
    "Псковская обл.": ("pskovskaya_obl", "@pskov_alerts"),
    "Калининградская обл.": ("kaliningradskaya_obl", "@kaliningrad_alerts"),
    "Республика Карелия": ("karelia", "@karelia_alerts"),
    "Республика Коми": ("komi", "@komi_alerts"),
    "Пермский край": ("permsky_kray", "@perm_alerts"),
    "Удмуртия": ("udmurtia", "@udmurtia_alerts"),
    "Свердловская обл.": ("sverdlovskaya_obl", "@sverdlovsk_alerts"),
    "Курганская обл.": ("kurganskaya_obl", "@kurgan_alerts"),
    "Тюменская обл.": ("tyumenskaya_obl", "@tyumen_alerts"),
    "Челябинская обл.": ("chelyabinskaya_obl", "@chelyabinsk_alerts"),
    "Оренбургская обл.": ("orenburgskaya_obl", "@orenburg_alerts"),
    "Самарская обл.": ("samarskaya_obl", "@samara_alerts"),
    "Ульяновская обл.": ("ulyanovskaya_obl", "@ulyanovsk_alerts"),
    "Башкортостан": ("bashkortostan", "@bashkortostan_alerts"),
    "Татарстан": ("tatarstan", "@tatarstan_alerts"),
    "Марий Эл": ("mari_el", "@mari_alerts"),
    "Мордовия": ("mordovia", "@mordovia_alerts"),
    "Чувашия": ("chuvashia", "@chuvashia_alerts"),
    "Ханты-Мансийский АО": ("hmao", "@hmao_alerts"),
    "Ямало-Ненецкий АО": ("yamal", "@yamal_alerts"),
    "Новосибирская обл.": ("novosibirskaya_obl", "@novosibirsk_alerts"),
    "Омская обл.": ("omskaya_obl", "@omsk_alerts"),
    "Томская обл.": ("tomskaya_obl", "@tomsk_alerts"),
    "Кемеровская обл.": ("kemerovskaya_obl", "@kemerovo_alerts"),
    "Алтайский край": ("altaysky_kray", "@altai_alerts"),
    "Красноярский край": ("krasnoyarsky_kray", "@krasnoyarsk_alerts"),
    "Иркутская обл.": ("irkutskaya_obl", "@irkutsk_alerts"),
    "Забайкальский край": ("zabaykalsky_kray", "@zabaykalsky_alerts"),
    "Республика Алтай": ("altai_rep", "@altai_rep_alerts"),
    "Тыва": ("tyva", "@tyva_alerts"),
    "Хакасия": ("hakasia", "@hakasia_alerts"),
    "Бурятия": ("buryatia", "@buryatia_alerts"),
    "Приморский край": ("primorsky_kray", "@primorsky_alerts"),
    "Хабаровский край": ("habarovsky_kray", "@habarovsk_alerts"),
    "Амурская обл.": ("amurskaya_obl", "@amur_alerts"),
    "Магаданская обл.": ("magadanskaya_obl", "@magadan_alerts"),
    "Сахалинская обл.": ("sakhalinskaya_obl", "@sakhalin_alerts"),
    "Еврейская АО": ("evreyskaya_ao", "@jao_alerts"),
    "Чукотский АО": ("chukotsky_ao", "@chukotka_alerts"),
    "Камчатский край": ("kamchatsky_kray", "@kamchatka_alerts"),
    "Якутия": ("saha", "@saha_alerts"),
    "ВСЯ РОССИЯ": ("all_russia", "@russia_all")
}

# Список тревог
ALERTS = [
    ("⚠️ Угроза БПЛА", "drone"), 
    ("🚀 Ракетная опасность", "rocket"),
    ("🚨 Воздушная тревога", "air_alarm"), 
    ("🟢 Общий отбой", "all_clear")
]

# ==========================================
# МЕНЮ
# ==========================================
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🚨 Отправить тревогу"))
    markup.add(types.KeyboardButton("🆔 Мой ID"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 <b>Быстрый пульт оператора.</b>\nНажмите кнопку ниже:", parse_mode='HTML', reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🆔 Мой ID")
def send_id(message):
    bot.reply_to(message, f"🆔 Ваш ID: <code>{message.chat.id}</code>", parse_mode='HTML')

# ==========================================
# ЛОГИКА ОТПРАВКИ ТРЕВОГИ
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🚨 Отправить тревогу")
def select_region(message):
    markup = types.InlineKeyboardMarkup(row_width=3) # По 3 кнопки в ряд
    buttons = []
    for region_name in REGIONS.keys():
        # В callback_data нельзя передавать длинные строки, используем индекс
        idx = list(REGIONS.keys()).index(region_name)
        buttons.append(types.InlineKeyboardButton(region_name, callback_data=f"reg_{idx}"))
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🌍 <b>Шаг 1:</b> Выберите регион:", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_"))
def select_alert(call):
    idx = int(call.data.replace("reg_", ""))
    region_name = list(REGIONS.keys())[idx]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for alert_name, alert_code in ALERTS:
        markup.add(types.InlineKeyboardButton(alert_name, callback_data=f"alert_{idx}_{alert_code}"))
    
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                          text=f"🌍 Регион: <b>{region_name}</b>\n\n🚨 <b>Шаг 2:</b> Выберите тревогу:", 
                          parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("alert_"))
def send_alert(call):
    parts = call.data.split("_")
    idx = int(parts[1])
    alert_code = parts[2]
    
    region_name = list(REGIONS.keys())[idx]
    region_code, channel = REGIONS[region_name]
    alert_name = next((name for name, code in ALERTS if code == alert_code), alert_code)

    # 1. Запись в Firebase
    db.reference(f'regions/{region_code}').update({
        'signal': alert_code,
        'ts': int(time.time() * 1000),
        'source': 'telegram_bot'
    })
    
    # 2. Лог
    db.reference('logs').push({
        'action': f"Тревога из бота: {alert_name} в {region_name}",
        'ts': int(time.time() * 1000),
        'operator': 'bot'
    })

    # 3. Отправка в канал
    try:
        text = f"{alert_name}\n\n📍 <b>Регион:</b> {region_name}\n🕒 <b>Время:</b> {time.strftime('%H:%M')}\n📡 <b>Источник:</b> Пульт оператора"
        bot.send_message(channel, text, parse_mode='HTML')
        channel_status = f"✅ Отправлено в {channel}"
    except Exception as e:
        print(f"Ошибка канала {channel}: {e}")
        channel_status = f"⚠️ Ошибка отправки в канал {channel}"

    # 4. Ответ пользователю
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"✅ <b>СИГНАЛ ОТПРАВЛЕН!</b>\n\n{alert_name}\n📍 {region_name}\n\n{channel_status}",
                          parse_mode='HTML')

# ==========================================
# 2FA (КОДЫ ВХОДА)
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