import os, sqlite3, threading, logging, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa" 
CHANNEL_LINK = "https://t.me/autochopOdessa"
BOT_NAME = "AutoChop Bot"
DB_PATH = "ads.db"

# Стан (оновлений порядок)
(MAKE, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESCRIPTION, 
 PRICE, PHOTOS, DISTRICT, TOWN, SHOW_TG, PHONE, CONFIRM, EDIT_PRICE) = range(16)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, details TEXT, msg_id INTEGER)')
    conn.commit()
    conn.close()

def generate_summary(data):
    tg_status = f"@{data['username']}" if data.get('show_tg') == "Так" else "приховано"
    return (f"🚘 <b>{data['make']} {data['model']}</b>\n"
            f"📅 Рік: {data['year']}\n"
            f"🔌 Об'єм: {data['engine']} л.\n"
            f"⛽️ Паливо: {data['fuel']}\n"
            f"⚙️ КПП: {data['gearbox']}\n"
            f"⛓ Привід: {data['drive']}\n"
            f"📍 {data['district']} р-н, {data['town']}\n"
            f"💰 <b>Ціна: {data['price']}$</b>\n\n"
            f"📝 <b>Опис:</b> {data['description']}\n\n"
            f"📞 Тел: <code>{data['phone']}</code>\n👤 TG: {tg_status}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        f"👋 <b>Вітаю! Я — {BOT_NAME}.</b>\n\n"
        f"Допоможу вам викласти оголошення у телеграм-каналі "
        f"<a href='{CHANNEL_LINK}'>autochopOdessa</a>. Почнемо!"
    )
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute('SELECT id, details, msg_id FROM ads WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("У вас немає оголошень.")
        return
    for r in rows:
        kb = [[InlineKeyboardButton("💰 Змінити ціну", callback_data=f"edit_{r[0]}"), 
               InlineKeyboardButton("🗑 Видалити", callback_data=f"del_{r[0]}_{r[2]}")]]
        await update.message.reply_text(r[1], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    if data[0] == "del":
        try: await context.bot.delete_message(CHANNEL_ID, int(data[2]))
        except: pass
        conn = sqlite3.connect(DB_PATH); conn.execute('DELETE FROM ads WHERE id = ?', (data[1],)); conn.commit(); conn.close()
        await query.edit_message_text("🗑 Видалено всюди.")
    elif data[0] == "edit":
        context.user_data['edit_db_id'] = data[1]
        await query.message.reply_text("Введіть НОВУ ціну ($):")
        return EDIT_PRICE

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    db_id = context.user_data['edit_db_id']
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute('SELECT details, msg_id FROM ads WHERE id = ?', (db_id,))
    res = cursor.fetchone()
    if res:
        old_text, msg_id = res[0], res[1]
        new_text = old_text.split("Ціна:")[0] + f"Ціна: {new_price}$</b>" + old_text.split("$</b>")[1]
        cursor.execute('UPDATE ads SET details = ? WHERE id = ?', (new_text, db_id))
        conn.commit()
        try: await context.bot.edit_message_caption(CHANNEL_ID, msg_id, caption=new_text, parse_mode=ParseMode.HTML)
        except: await context.bot.edit_message_text(CHANNEL_ID, msg_id, text=new_text, parse_mode=ParseMode.HTML)
        await update.message.reply_text("✅ Ціну оновлено!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True))
    conn.close()
    return ConversationHandler.END

# --- АНКЕТА (НОВИЙ ПОРЯДОК) ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Марка авто:", reply_markup=ReplyKeyboardRemove())
    return MAKE

async def get_make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['make'] = update.message.text
    await update.message.reply_text("Модель:")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Рік:")
    return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['year'] = update.message.text
    await update.message.reply_text("Об'єм двигуна (наприклад, 2.0):")
    return ENGINE

async def get_engine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['engine'] = update.message.text
    await update.message.reply_text("Паливо:", reply_markup=ReplyKeyboardMarkup([["Бензин", "Дизель", "Газ/Бензин", "Гібрид", "Електро"]], resize_keyboard=True))
    return FUEL

async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fuel'] = update.message.text
    await update.message.reply_text("КПП:", reply_markup=ReplyKeyboardMarkup([["Механіка", "Автомат"]], resize_keyboard=True))
    return GEARBOX

async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gearbox'] = update.message.text
    await update.message.reply_text("Привід:", reply_markup=ReplyKeyboardMarkup([["Передній", "Задній", "Повний"]], resize_keyboard=True))
    return DRIVE

async def get_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['drive'] = update.message.text
    await update.message.reply_text("Опис:")
    return DESCRIPTION

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Ціна ($):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Надішліть фото (до 5) та натисніть /done")
    context.user_data['photos'] = []
    return PHOTOS

async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo: context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTOS

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Район:")
    return DISTRICT

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    await update.message.reply_text("Населений пункт:")
    return TOWN

async def get_town(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['town'] = update.message.text
    await update.message.reply_text("Показувати ваш Telegram?", reply_markup=ReplyKeyboardMarkup([["Так", "Ні"]], resize_keyboard=True))
    return SHOW_TG

async def get_show_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['show_tg'] = update.message.text
    context.user_data['username'] = update.effective_user.username or "немає"
    await update.message.reply_text("Ваш номер телефону:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    summary = generate_summary(context.user_data)
    context.user_data['summary'] = summary
    await update.message.reply_text(f"Ваш пост:\n\n{summary}", parse_mode=ParseMode.HTML)
    await update.message.reply_text("Публікуємо?", reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True))
    return CONFIRM

async def final_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Так":
        ps = context.user_data.get('photos', [])
        cap = context.user_data['summary']
        if not ps: sent_msg = await context.bot.send_message(CHANNEL_ID, cap, parse_mode=ParseMode.HTML)
        elif len(ps) == 1: sent_msg = await context.bot.send_photo(CHANNEL_ID, ps[0], caption=cap, parse_mode=ParseMode.HTML)
        else:
            msgs = await context.bot.send_media_group(CHANNEL_ID, [InputMediaPhoto(p, caption=cap if i==0 else "", parse_mode=ParseMode.HTML) for i,p in enumerate(ps[:10])])
            sent_msg = msgs[0]
        conn = sqlite3.connect(DB_PATH); conn.execute('INSERT INTO ads (user_id, details, msg_id) VALUES (?, ?, ?)', (update.effective_user.id, cap, sent_msg.message_id)); conn.commit(); conn.close()
        await update.message.reply_text("✅ Опубліковано!")
    return ConversationHandler.END

async def main():
    init_db()
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), BaseHTTPRequestHandler).serve_forever(), daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad), CallbackQueryHandler(handle_callbacks, pattern="^edit_")],
        states={
            MAKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_make)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            ENGINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_engine)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fuel)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gearbox)],
            DRIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            PHOTOS: [MessageHandler(filters.PHOTO, get_photos), CommandHandler('done', done_photos)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_district)],
            TOWN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_town)],
            SHOW_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_show_tg)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CONFIRM: [MessageHandler(filters.Regex("^(✅ Так|❌ Ні)$"), final_post)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads))
    app.add_handler(CallbackQueryHandler(handle_callbacks, pattern="^del_"))
    app.add_handler(conv)
    
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
 
