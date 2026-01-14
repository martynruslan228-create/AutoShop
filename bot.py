import os, asyncio, logging, threading, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния анкеты
BRAND, MODEL, YEAR, REGION, CITY, GEARBOX, DRIVE, FUEL, PRICE, DESC, PHOTO, CONTACT, EDIT_PRICE = range(13)

def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       text TEXT, photo_id TEXT, price TEXT)''')
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text(
        f"🚗 Вітаємо в Auto Shop Odessa!\nНаш канал: {CHANNEL_ID}\n\nОберіть дію:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        disable_web_page_preview=True
    )
    return ConversationHandler.END

# --- НАЧАЛО АНКЕТЫ ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть марку авто:", reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True))
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Скасувати": return await start(update, context)
    context.user_data['brand'] = update.message.text
    await update.message.reply_text("Введіть модель:")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Введіть рік випуску:")
    return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['year'] = update.message.text
    regions = [["Одеська", "Київська"], ["Львівська", "Дніпропетровська"], ["Інша область"]]
    await update.message.reply_text("Оберіть область:", reply_markup=ReplyKeyboardMarkup(regions, resize_keyboard=True))
    return REGION

async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['region'] = update.message.text
    await update.message.reply_text("Введіть населений пункт:")
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['city'] = update.message.text
    kb = [["Автомат", "Механіка"]]
    await update.message.reply_text("Тип КПП:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return GEARBOX

async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gearbox'] = update.message.text
    kb = [["Передній", "Задній", "Повний"]]
    await update.message.reply_text("Привід:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return DRIVE

async def get_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['drive'] = update.message.text
    kb = [["Бензин", "Дизель"], ["Газ/Бензин", "Електро"]]
    await update.message.reply_text("Тип палива:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return FUEL

async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fuel'] = update.message.text
    await update.message.reply_text("Введіть ціну ($):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Додайте опис:")
    return DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    kb = [["⏩ Пропустити фото"]]
    await update.message.reply_text("Надішліть фото або пропустіть:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['photo_id'] = update.message.photo[-1].file_id if update.message.photo else None
    kb = [["✅ Так, додати", "❌ Ні, анонімно"]]
    await update.message.reply_text("Додати ваш контакт у пост?", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return CONTACT

async def finish_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ud = context.user_data
    contact = f"@{user.username}" if update.message.text == "✅ Так, додати" and user.username else "Приватна особа"
    
    caption = (
        f"🚗 {ud['brand']} {ud['model']} ({ud['year']})\n"
        f"📍 {ud['region']} обл., {ud['city']}\n"
        f"⚙️ {ud['gearbox']} | {ud['drive']} | {ud['fuel']}\n"
        f"💰 Ціна: {ud['price']}$\n"
        f"📝 Опис: {ud['desc']}\n\n"
        f"👤 Контакт: {contact}"
    )

    try:
        if ud['photo_id']:
            msg = await context.bot.send_photo(chat_id=CHANNEL_ID, photo=ud['photo_id'], caption=caption)
        else:
            msg = await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        
        conn = sqlite3.connect("ads.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ads (user_id, msg_id, text, photo_id, price) VALUES (?, ?, ?, ?, ?)",
                       (user.id, msg.message_id, caption, ud['photo_id'], ud['price']))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Опубліковано!")
    except Exception as e:
        await update.message.reply_text(f"Помилка: {e}")

    return await start(update, context)

# --- УПРАВЛЕНИЕ ОБЪЯВЛЕНИЯМИ (МОИ ОБЪЯВЛЕНИЯ) ---
async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, text FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("У вас немає активних оголошень.")
        return

    for ad_id, text in ads:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Редагувати ціну", callback_query_data=f"edit_{ad_id}")],
            [InlineKeyboardButton("🗑 Видалити", callback_query_data=f"del_{ad_id}")]
        ])
        await update.message.reply_text(text, reply_markup=kb)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("del_"):
        ad_id = data.split("_")[1]
        conn = sqlite3.connect("ads.db")
        cursor = conn.cursor()
        cursor.execute("SELECT msg_id FROM ads WHERE id = ?", (ad_id,))
        res = cursor.fetchone()
        if res:
            try: await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=res[0])
            except: pass
            cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
            conn.commit()
        conn.close()
        await query.edit_message_text("🗑 Видалено.")
    elif data.startswith("edit_"):
        context.user_data['edit_ad_id'] = data.split("_")[1]
        await query.message.reply_text("Введіть нову ціну ($):")
        return EDIT_PRICE

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    ad_id = context.user_data.get('edit_ad_id')
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute("SELECT msg_id, text, photo_id FROM ads WHERE id = ?", (ad_id,))
    res = cursor.fetchone()
    
    if res:
        msg_id, old_text, photo_id = res
        lines = old_text.split('\n')
        for i, line in enumerate(lines):
            if "💰 Ціна:" in line: lines[i] = f"💰 Ціна: {new_price}$"
        new_text = '\n'.join(lines)
        
        try:
            if photo_id: await context.bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_id, caption=new_text)
            else: await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=msg_id, text=new_text)
            cursor.execute("UPDATE ads SET price = ?, text = ? WHERE id = ?", (new_price, new_text, ad_id))
            conn.commit()
            await update.message.reply_text("✅ Ціну оновлено!")
        except Exception as e: await update.message.reply_text(f"Помилка: {e}")
    conn.close()
    return await start(update, context)

# --- СЕРВЕР ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad), 
                      CallbackQueryHandler(callback_router, pattern="^edit_")],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_region)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gearbox)],
            DRIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fuel)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc)],
            PHOTO: [MessageHandler(filters.PHOTO | filters.Regex("^⏩ Пропустити фото$"), get_photo)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_ad)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_router))

    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
