import os
import sqlite3
import threading
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAEun5vwRl7f89vFZ1E5fJ5C1H4CDe7LLtw"
CHANNEL_ID = "@autochopOdessa"
DB_PATH = "ads.db"

# Состояния
(MAKE, MODEL, YEAR, GEARBOX, FUEL, DRIVE, DISTRICT, TOWN, PRICE,
 DESCRIPTION, PHOTOS, PHONE, SHOW_CONTACT, CONFIRM, EDIT_PRICE) = range(15)

# --- Инициализация БД ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, details TEXT, msg_id INTEGER)')
    conn.commit()
    conn.close()

# --- Генерация текста объявления ---
def generate_summary(data):
    tg_status = "@%s" % data.get('username', '') if data.get('show_tg') == "Так" else "приховано"
    text = (
        "🚘 <b>%s %s</b>\n"
        "📅 Рік: %s\n"
        "⚙️ КПП: %s | ⛽️ %s\n"
        "🛣 Привід: %s\n"
        "📍 %s р-н, %s\n"
        "💰 <b>Ціна: %s$</b>\n\n"
        "📝 <b>Опис:</b> %s\n\n"
        "📞 Тел: <code>%s</code>\n👤 TG: %s"
    ) % (
        data.get('make', ''), data.get('model', ''), data.get('year', ''),
        data.get('gearbox', ''), data.get('fuel', ''), data.get('drive', ''),
        data.get('district', ''), data.get('town', ''), data.get('price', ''),
        data.get('description', ''), data.get('phone', ''), tg_status
    )
    return text

# --- Хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚗 Вітаємо в Auto Shop Odessa!",
        reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True)
    )
    return ConversationHandler.END

async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['photos'] = []
    await update.message.reply_text("Введіть марку авто:", reply_markup=ReplyKeyboardRemove())
    return MAKE

async def get_make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['make'] = update.message.text
    await update.message.reply_text("Введіть модель:")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Введіть рік:")
    return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['year'] = update.message.text
    await update.message.reply_text("КПП:", reply_markup=ReplyKeyboardMarkup([["Автомат", "Механіка"]], resize_keyboard=True))
    return GEARBOX

async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gearbox'] = update.message.text
    await update.message.reply_text("Паливо:", reply_markup=ReplyKeyboardMarkup([["Бензин", "Дизель", "Газ", "Електро"]], resize_keyboard=True))
    return FUEL

async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fuel'] = update.message.text
    await update.message.reply_text("Привід:", reply_markup=ReplyKeyboardMarkup([["Передній", "Задній", "Повний"]], resize_keyboard=True))
    return DRIVE

async def get_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['drive'] = update.message.text
    await update.message.reply_text("Район Одеси:")
    return DISTRICT

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    await update.message.reply_text("Місто:")
    return TOWN

async def get_town(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['town'] = update.message.text
    await update.message.reply_text("Ціна ($):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Опис авто:")
    return DESCRIPTION

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text(
        "Надішліть фото (до 10 шт) і натисніть /done:",
        reply_markup=ReplyKeyboardMarkup([["➡️ Без фото"]], resize_keyboard=True)
    )
    return PHOTOS

async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTOS

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваш номер телефону:", reply_markup=ReplyKeyboardRemove())
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text(
        "Показувати ваш TG?",
        reply_markup=ReplyKeyboardMarkup([["Так", "Ні"]], resize_keyboard=True)
    )
    return SHOW_CONTACT

async def get_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['show_tg'] = update.message.text
    context.user_data['username'] = update.effective_user.username
    summary = generate_summary(context.user_data)
    context.user_data['summary'] = summary
    await update.message.reply_text(
        "ПЕРЕВІРКА:\n\n%s\n\nПублікуємо?" % summary,
        reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True),
        parse_mode=ParseMode.HTML
    )
    return CONFIRM

async def final_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Так":
        photos = context.user_data.get('photos', [])
        text = context.user_data['summary']
        sent_msg = None
        conn = sqlite3.connect(DB_PATH)
        try:
            if not photos:
                sent_msg = await context.bot.send_message(CHANNEL_ID, text, parse_mode=ParseMode.HTML)
            elif len(photos) == 1:
                sent_msg = await context.bot.send_photo(CHANNEL_ID, photos[0], caption=text, parse_mode=ParseMode.HTML)
            else:
                media = [InputMediaPhoto(photos[0], caption=text, parse_mode=ParseMode.HTML)]
                for p in photos[1:10]:
                    media.append(InputMediaPhoto(p))
                msgs = await context.bot.send_media_group(CHANNEL_ID, media)
                sent_msg = msgs[0]
            conn.execute('INSERT INTO ads (user_id, details, msg_id) VALUES (?, ?, ?)', (update.effective_user.id, text, sent_msg.message_id))
            conn.commit()
            await update.message.reply_text("✅ Опубліковано!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"]], resize_keyboard=True))
        except Exception as e:
            await update.message.reply_text("❌ Помилка: %s" % str(e))
        conn.close()
    return ConversationHandler.END

# --- Просмотр и редактирование объявлений ---
async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, details, msg_id FROM ads WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("У вас немає активних оголошень.")
        return
    for r in rows:
        kb = [[InlineKeyboardButton("💰 Змінити ціну", callback_data="editprice_%s" % r[0])],
              [InlineKeyboardButton("🗑 Видалити всюди", callback_data="del_%s_%s" % (r[0], r[2]))]]
        await update.message.reply_text("Оголошення:\n\n%s" % r[1], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboard
