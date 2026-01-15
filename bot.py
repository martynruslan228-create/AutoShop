import os, asyncio, logging, threading, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESC, PRICE, PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE, EDIT_PRICE = range(15)

def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       text TEXT, photo_ids TEXT, price TEXT)''')
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Вітаємо!\n\nЯ — офіційний бот Auto Shop Odessa\n"
        "Допоможу вам опублікувати оголошення:\n👉 https://t.me/autochopOdessa"
    )
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text(welcome, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), disable_web_page_preview=True)
    return ConversationHandler.END

async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, text FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()
    
    if not ads:
        await update.message.reply_text("У вас немає активних оголошень.")
    else:
        for ad_id, text in ads:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Редагувати ціну", callback_query_data=f"edit_{ad_id}")],
                [InlineKeyboardButton("🗑 Видалити", callback_query_data=f"del_{ad_id}")]
            ])
            # Вимкнено parse_mode для запобігання помилок парсингу
            await update.message.reply_text(text, reply_markup=kb, parse_mode=None)
    
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text("Оберіть наступну дію:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# --- ПРОЦЕС АНКЕТИ ---

async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("1. Введіть марку авто:", reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True))
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['brand'] = update.message.text
    await update.message.reply_text("2. Введіть модель:")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("3. Введіть рік випуску:")
    return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['year'] = update.message.text
    await update.message.reply_text("4. Введіть об'єм двигуна:")
    return ENGINE

async def get_engine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['engine'] = update.message.text
    kb = [["Бензин", "Дизель"], ["Газ / Бензин", "Електро", "Гібрид"]]
    await update.message.reply_text("5. Оберіть тип палива:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return FUEL

async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fuel'] = update.message.text
    kb = [["Автомат", "Механіка"], ["Робот", "Варіатор"]]
    await update.message.reply_text("6. Тип КПП:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return GEARBOX

async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gearbox'] = update.message.text
    kb = [["Передній", "Задній", "Повний"]]
    await update.message.reply_text("7. Привід:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return DRIVE

async def get_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['drive'] = update.message.text
    await update.message.reply_text("8. Додайте опис авто:", reply_markup=ReplyKeyboardRemove())
    return DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    await update.message.reply_text("9. Введіть ціну ($):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    context.user_data['photos'] = []
    kb = [["✅ Завантажив (продовжити)"], ["⏩ Пропустити фото"]]
    await update.message.reply_text("10. Надішліть фото і натисніть «Завантажив»:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["✅ Завантажив (продовжити)", "⏩ Пропустити фото"]:
        districts = [["Березівський", "Білгород-Дністровський"], ["Болградський", "Ізмаїльський"], ["Одеський", "Подільський"], ["Роздільнянський"]]
        await update.message.reply_text("11. Оберіть район:", reply_markup=ReplyKeyboardMarkup(districts, resize_keyboard=True))
        return DISTRICT
    if update.message.photo:
        context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTO

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    await update.message.reply_text("12. Введіть місто/село вручну:", reply_markup=ReplyKeyboardRemove())
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['city'] = update.message.text
    kb = [["✅ Так", "❌ Ні"]]
    await update.message.reply_text("13. Показати посилання на ваш Telegram?", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return TG_CONTACT

async def get_tg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data['tg_link'] = f"@{user.username}" if update.message.text == "✅ Так" and user.username else "Приватна особа"
    await update.message.reply_text("14. Введіть номер телефону вручну:", reply_markup=ReplyKeyboardRemove())
    return PHONE

async def finish_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    phone = update.message.text
    caption = (f"🚗 {ud['brand']} {ud['model']} ({ud['year']})\n\n🔹 Об'єм: {ud['engine']} л.\n⛽️ Паливо: {ud['fuel']}\n"
               f"⚙️ КПП: {ud['gearbox']}\n☸️ Привід: {ud['drive']}\n📍 Місце: {ud['district']} р-н, {ud['city']}\n\n"
               f"📝 Опис:\n{ud['desc']}\n\n💰 Ціна: {ud['price']}$\n\n📞 Телефон: {phone}\n👤 Контакт: {ud.get('tg_link')}")
    
    try:
        photos = ud.get('photos', [])
        if photos:
            media = [InputMediaPhoto(photos[0], caption=caption)]
            for p in photos[1:10]: media.append(InputMediaPhoto(p))
            msgs = await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
            msg_id = msgs[0].message_id
        else:
            msg = await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode=None)
            msg_id = msg.message_id
        
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("INSERT INTO ads (user_id, msg_id, text, photo_ids, price) VALUES (?, ?, ?, ?, ?)",
                       (update.effective_user.id, msg_id, caption, ",".join(photos), ud['price']))
        conn.commit(); conn.close()
        await update.message.reply_text("✅ Опубліковано!")
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")

    # ПРИМУСОВЕ ПОВЕРНЕННЯ ДО ГОЛОВНОГО МЕНЮ ТА ЗАВЕРШЕННЯ ДІАЛОГУ
    await start(update, context)
    return ConversationHandler.END

# --- РЕДАГУВАННЯ ТА ТЕХНІЧНА ЧАСТИНА ---

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; data = query.data; await query.answer()
    if data.startswith("del_"):
        ad_id = data.split("_")[1]; conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT msg_id FROM ads WHERE id = ?", (ad_id,)); res = cursor.fetchone()
        if res:
            try: await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=res[0])
            except: pass
            cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,)); conn.commit()
        conn.close(); await query.edit_message_text("🗑 Видалено.")
    elif data.startswith("edit_"):
        context.user_data['edit_ad_id'] = data.split("_")[1]
        await query.message.reply_text("Введіть нову ціну ($):")
        return EDIT_PRICE

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text; ad_id = context.user_data.get('edit_ad_id')
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT msg_id, text, photo_ids FROM ads WHERE id = ?", (ad_id,)); res = cursor.fetchone()
    if res:
        msg_id, old_text, photo_ids = res
        lines = old_text.split('\n')
        for i, line in enumerate(lines):
            if "Ціна:" in line: lines[i] = f"💰 Ціна: {new_price}$"
        new_text = '\n'.join(lines)
        try:
            if photo_ids: await context.bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_id, caption=new_text, parse_mode=None)
            else: await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=msg_id, text=new_text, parse_mode=None)
            cursor.execute("UPDATE ads SET price = ?, text = ? WHERE id = ?", (new_price, new_text, ad_id)); conn.commit()
            await update.message.reply_text("✅ Ціну оновлено!")
        except Exception as e: await update.message.reply_text(f"Помилка: {e}")
    conn.close()
    await start(update, context)
    return ConversationHandler.END

class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    re_new_ad = "^➕ Нове оголошення$"
    re_my_ads = "^🗂 Мої оголошення$"
    re_cancel = "^❌ Скасувати$"

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(re_new_ad), new_ad)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_brand)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_year)],
            ENGINE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_engine)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_fuel)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_gearbox)],
            DRIVE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_drive)],
            DESC: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_desc)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_price)],
            PHOTO: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_photo)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_district)],
            CITY: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_city)],
            TG_CONTACT: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), get_tg_contact)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), finish_ad)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel) & ~filters.Regex(re_my_ads), save_new_price)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(re_cancel), start),
            MessageHandler(filters.Regex(re_my_ads), my_ads)
        ],
        allow_reentry=True
    )

    # ВАЖЛИВО: MessageHandler для "Мої оголошення" стоїть ПЕРЕД conv_handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(re_my_ads), my_ads))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_router))

    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
