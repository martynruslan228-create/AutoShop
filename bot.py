import os, asyncio, logging, threading, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния
BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESC, PRICE, PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE, WAIT_EDIT_VALUE = range(15)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, year TEXT, price TEXT, desc TEXT, 
                       full_text TEXT, photo_ids TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- СТАРТ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text("Головне меню:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# --- МЕНЮ "МОЇ ОГОЛОШЕННЯ" ---
async def my_ads_top_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Редагувати оголошення", callback_query_data="top_edit")],
        [InlineKeyboardButton("🗑 Видалити оголошення", callback_query_data="top_del")]
    ])
    if update.message:
        await update.message.reply_text("Керування вашими оголошеннями:", reply_markup=kb)
    else:
        await update.callback_query.message.reply_text("Керування вашими оголошеннями:", reply_markup=kb)
    return ConversationHandler.END

# --- ОБРАБОТКА КНОПОК (РЕДАКТИРОВАНИЕ/УДАЛЕНИЕ) ---
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    await query.answer()

    # Показать список для выбора
    if data.startswith("top_"):
        action = data.split("_")[1]
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
        ads = cursor.fetchall(); conn.close()
        
        if not ads:
            await query.edit_message_text("У вас немає активних оголошень.")
            return ConversationHandler.END

        await query.edit_message_text("Оберіть оголошення для дії:")
        for ad in ads:
            prefix = "📝" if action == "edit" else "🗑"
            btn_data = f"sel{action}_{ad[0]}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{prefix} Вибрати {ad[1]}", callback_query_data=btn_data)]])
            await query.message.reply_text(f"🚗 {ad[1]} {ad[2]} | {ad[3]}$", reply_markup=kb)
        return ConversationHandler.END

    # Удаление
    elif data.startswith("seldel_"):
        ad_id = data.split("_")[1]
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT msg_id FROM ads WHERE id = ?", (ad_id,))
        res = cursor.fetchone()
        if res:
            try: await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=res[0])
            except: pass
            cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
            conn.commit()
        conn.close()
        await query.edit_message_text("✅ Оголошення видалено.")
        return ConversationHandler.END

    # Выбор пункта редактирования
    elif data.startswith("seledit_"):
        ad_id = data.split("_")[1]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Змінити ціну", callback_query_data=f"field_price_{ad_id}")],
            [InlineKeyboardButton("📄 Змінити опис", callback_query_data=f"field_desc_{ad_id}")],
            [InlineKeyboardButton("⬅️ Назад", callback_query_data="top_edit")]
        ])
        await query.edit_message_text("Що саме ви хочете змінити у цьому оголошенні?", reply_markup=kb)
        return ConversationHandler.END

    # Ожидание ввода нового значения
    elif data.startswith("field_"):
        _, field, ad_id = data.split("_")
        context.user_data['edit_ad_id'] = ad_id
        context.user_data['edit_field'] = field
        prompt = "Введіть нову ціну ($):" if field == "price" else "Введіть новий опис авто:"
        await query.message.reply_text(prompt, reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True))
        return WAIT_EDIT_VALUE

async def process_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_val = update.message.text
    ad_id = context.user_data.get('edit_ad_id')
    field = context.user_data.get('edit_field')
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT msg_id, full_text, photo_ids FROM ads WHERE id = ?", (ad_id,))
    res = cursor.fetchone()
    
    if res:
        msg_id, old_text, photo_ids = res
        lines = old_text.split('\n')
        if field == "price":
            for i, line in enumerate(lines):
                if "Ціна:" in line or "💰" in line: lines[i] = f"💰 Ціна: {new_val}$"
        else: # desc
            parts = old_text.split("📝 Опис:")
            footer = parts[1].split("💰 Ціна:")[1]
            lines = [parts[0] + f"📝 Опис:\n{new_val}\n\n💰 Ціна:" + footer]
        
        new_caption = '\n'.join(lines) if field == "price" else lines[0]
        
        try:
            if photo_ids: await context.bot.edit_message_caption(CHANNEL_ID, msg_id, caption=new_caption)
            else: await context.bot.edit_message_text(new_caption, CHANNEL_ID, msg_id)
            cursor.execute(f"UPDATE ads SET {field} = ?, full_text = ? WHERE id = ?", (new_val, new_caption, ad_id))
            conn.commit()
            await update.message.reply_text("✅ Оновлено!")
        except: await update.message.reply_text("Помилка оновлення в каналі.")
    
    conn.close()
    return await start(update, context)

# --- АНКЕТА ---
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
    if update.message.photo: context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTO

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    await update.message.reply_text("12. Введіть місто/село вручну:", reply_markup=ReplyKeyboardRemove())
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['city'] = update.message.text
    await update.message.reply_text("13. Показати Telegram?", reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True))
    return TG_CONTACT

async def get_tg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    context.user_data['tg_link'] = f"@{u.username}" if update.message.text == "✅ Так" and u.username else "Приватна особа"
    await update.message.reply_text("14. Введіть номер телефону:", reply_markup=ReplyKeyboardRemove())
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
            msgs = await context.bot.send_media_group(CHANNEL_ID, media=[InputMediaPhoto(p, caption=caption if i==0 else "") for i, p in enumerate(photos[:10])])
            msg_id = msgs[0].message_id
        else:
            msg = await context.bot.send_message(CHANNEL_ID, caption)
            msg_id = msg.message_id
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("INSERT INTO ads (user_id, msg_id, brand, model, year, price, desc, full_text, photo_ids) VALUES (?,?,?,?,?,?,?,?,?)",
                       (update.effective_user.id, msg_id, ud['brand'], ud['model'], ud['year'], ud['price'], ud['desc'], caption, ",".join(photos)))
        conn.commit(); conn.close()
        await update.message.reply_text("✅ Опубліковано!")
    except Exception as e: await update.message.reply_text(f"Помилка: {e}")
    return await start(update, context)

# --- ЗАПУСК ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad),
            MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads_top_menu)
        ],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex("^(➕ Нове оголошення|🗂 Мої оголошення|❌ Скасувати)$"), get_brand)],
            MODEL: [MessageHandler(filters.TEXT, get_model)],
            YEAR: [MessageHandler(filters.TEXT, get_year)],
            ENGINE: [MessageHandler(filters.TEXT, get_engine)],
            FUEL: [MessageHandler(filters.TEXT, get_fuel)],
            GEARBOX: [MessageHandler(filters.TEXT, get_gearbox)],
            DRIVE: [MessageHandler(filters.TEXT, get_drive)],
            DESC: [MessageHandler(filters.TEXT, get_desc)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
            PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, get_photo)],
            DISTRICT: [MessageHandler(filters.TEXT, get_district)],
            CITY: [MessageHandler(filters.TEXT, get_city)],
            TG_CONTACT: [MessageHandler(filters.TEXT, get_tg_contact)],
            PHONE: [MessageHandler(filters.TEXT, finish_ad)],
            WAIT_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.Regex("^❌ Скасувати$"), process_edit_input)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Скасувати$"), start),
            MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads_top_menu)
        ],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_router))

    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
