import os
import threading
from flask import Flask
import telebot
from telebot import types

app = Flask(__name__)

# Берем только токен бота
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    print("ОШИБКА: BOT_TOKEN не задан!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def cmd_start(message):
    name = message.from_user.first_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = f"👋 Привет, <b>{name}</b>!\n\nВаш ID: <code>{message.chat.id}</code>\n\nСкопируйте его и вставьте в приложении «Пульт оператора» → Профиль → Привязать Telegram."
    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Ваш ID: <code>{message.chat.id}</code>", parse_mode='HTML')

def run_bot():
    print("✅ Бот запущен...")
    bot.infinity_polling()

@app.route('/')
def health():
    return "Bot is running"

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)