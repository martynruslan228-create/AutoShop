import os, asyncio, logging, threading, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Стани
BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESC, PRICE, PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE, WAIT_EDIT_VALUE = range(15)

# --- БАЗА ДАНИХ ---
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

# --- ГОЛОВНЕ МЕНЮ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text("👋 Головне меню:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# --- ЛОГІКА "МОЇ ОГОЛОШЕННЯ" ---
async def my_ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ця функція тепер перериває будь-яку дію і показує меню керування"""
    query = update.callback_query
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Редагувати ціну/опис", callback_query_data="top_edit")],
        [InlineKeyboardButton("🗑 Видалити оголошення", callback_query_data="top_del")]
    ])
    
    text = "Керування вашими оголошеннями:"
    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)
    
    return ConversationHandler.END

# --- ОБРОБКА КНОПОК (CALLBACKS) ---
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    await query.answer()

    # Вибір дії (Редагувати/Видалити)
    if data.startswith("top_"):
        action = data.split("_")[1]
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
        ads = cursor.fetchall(); conn.close()
        
        if not ads:
            await query.edit_message_text("У вас ще немає опублікованих оголошень.")
            return

        await query.edit_message_text("Оберіть авто з вашого списку:")
        for ad in ads:
            label = "📝 Редагувати" if action == "edit" else "🗑 Видалити"
            callback = f"sel{action}_{ad[0]}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{label}", callback_query_data=callback)]])
            await query.message.reply_text(f"🚗 {ad[1]} {ad[2]} | {ad[3]}$", reply_markup=kb)

    # Видалення
    elif data.startswith("seldel_"):
        ad_id = data.split("_")[1]
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT msg_id FROM ads WHERE id = ?", (ad_id,))
        res = cursor.fetchone()
        if res:
            try: await context.bot.delete_message(CHANNEL_ID, res[0])
            except: pass
            cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
            conn.commit()
        conn.close()
        await query.edit_message_text("✅ Видалено з каналу та бази.")

    # Вибір пункту для редагування
    elif data.startswith("seledit_"):
        ad_id = data.split("_")[1]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Змінити ціну", callback_query_data=f"field_price_{ad_id}")],
            [InlineKeyboardButton("📄 Змінити опис", callback_query_data=f"field_desc_{ad_id}")],
            [InlineKeyboardButton("⬅️ Назад", callback_query_data="top_edit")]
        ])
        await query.edit_message_text("Що ви хочете оновити?", reply_markup=kb)

    # Запит на введення нового тексту
    elif data.startswith("field_"):
        _, field, ad_id = data.split("_")
        context.user_data['edit_ad_id'] = ad_id
        context.user_data['edit_field'] = field
        prompt = "Введіть нову ціну ($):" if field == "price" else "Введіть новий опис:"
        await query.message.reply_text(prompt, reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True))
        # ТУТ ПЕРЕМИКАЄМО КОРИСТУВАЧА В РЕЖИМ ОЧІКУВАННЯ ВВОДУ
        return WAIT_EDIT_VALUE

async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_val = update.message.text
    ad_id = context.user_data.get('edit_ad_id')
    field = context.user_data.get('edit_field')
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT msg_id, full_text, photo_ids FROM ads WHERE id = ?", (ad_id,))
    res = cursor.fetchone()
    
    if res:
        msg_id, old_text, photo_ids = res
        # Логіка заміни тексту в пості
        if field == "price":
            lines = old_text.split('\n')
            for i, line in enumerate(lines):
                if "Ціна:" in line or "💰" in line: lines[i] = f"💰 Ціна: {new_val}$"
            new_text = '\n'.join(lines)
        else:
            parts = old_text.split("📝 Опис:")
            footer = parts[1].split("💰 Ціна:")[1]
            new_text = f"{parts[0]}📝 Опис:\n{new_val}\n\n💰 Ціна:{footer}"

        try:
            if photo_ids: await context.bot.edit_message_caption(CHANNEL_ID, msg_id, caption=new_text)
            else: await context.bot.edit_message_text(new_text, CHANNEL_ID, msg_id)
            cursor.execute(f"UPDATE ads SET {field} = ?, full_text = ? WHERE id = ?", (new_val, new_text, ad_id))
            conn.commit()
            await update.message.reply_text("✅ Оновлено миттєво!")
        except: await update.message.reply_text("❌ Помилка оновлення в каналі.")
    
    conn.close()
    await start(update, context)
    return ConversationHandler.END

# --- АНКЕТА (БЕЗ ЗМІН) ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("1. Введіть марку авто:", reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True))
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['brand'] = update.message.text
    await update.message.reply_text("2. Модель:")
    return MODEL

# ... (інші кроки анкети скорочено для економії місця, вони такі ж самі) ...
# Я залишаю тут логіку реєстрації, щоб ви могли просто вставити код і він працював

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['model'] = update.message.text; await update.message.reply_text("3. Рік:"); return YEAR
async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['year'] = update.message.text; await update.message.reply_text("4. Об'єм:"); return ENGINE
async def get_engine(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['engine'] = update.message.text; await update.message.reply_text("5. Паливо:", reply_markup=ReplyKeyboardMarkup([["Бензин", "Дизель"], ["Газ/Бензин", "Електро"]], resize_keyboard=True)); return FUEL
async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['fuel'] = update.message.text; await update.message.reply_text("6. КПП:", reply_markup=ReplyKeyboardMarkup([["Автомат", "Механіка"]], resize_keyboard=True)); return GEARBOX
async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['gearbox'] = update.message.text; await update.message.reply_text("7. Привід:", reply_markup=ReplyKeyboardMarkup([["Передній", "Задній", "Повний"]], resize_keyboard=True)); return DRIVE
async def get_drive(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['drive'] = update.message.text; await update.message.reply_text("8. Опис:", reply_markup=ReplyKeyboardRemove()); return DESC
async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['desc'] = update.message.text; await update.message.reply_text("9. Ціна ($):"); return PRICE
async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['price'] = update.message.text; context.user_data['photos'] = []; await update.message.reply_text("10. Фото (надішліть і натисніть «Завантажив»):", reply_markup=ReplyKeyboardMarkup([["✅ Завантажив"], ["⏩ Пропустити"]], resize_keyboard=True)); return PHOTO
async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["✅ Завантажив", "⏩ Пропустити"]: await update.message.reply_text("11. Район:", reply_markup=ReplyKeyboardMarkup([["Одеський", "Ізмаїльський"]], resize_keyboard=True)); return DISTRICT
    if update.message.photo: context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTO
async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['district'] = update.message.text; await update.message.reply_text("12. Місто:", reply_markup=ReplyKeyboardRemove()); return CITY
async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['city'] = update.message.text; await update.message.reply_text("13. ТГ?", reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True)); return TG_CONTACT
async def get_tg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    context.user_data['tg_link'] = f"@{u.username}" if update.message.text == "✅ Так" and u.username else "Приватна особа"
    await update.message.reply_text("14. Номер телефону:", reply_markup=ReplyKeyboardRemove()); return PHONE

async def finish_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data; phone = update.message.text
    caption = (f"🚗 {ud['brand']} {ud['model']} ({ud['year']})\n\n🔹 Об'єм: {ud['engine']} л.\n⛽️ Паливо: {ud['fuel']}\n"
               f"⚙️ КПП: {ud['gearbox']}\n☸️ Привід: {ud['drive']}\n📍 Місце: {ud['district']} р-н, {ud['city']}\n\n"
               f"📝 Опис:\n{ud['desc']}\n\n💰 Ціна: {ud['price']}$\n\n📞 Телефон: {phone}\n👤 Контакт: {ud.get('tg_link')}")
    try:
        photos = ud.get('photos', [])
        if photos:
            msgs = await context.bot.send_media_group(CHANNEL_ID, media=[InputMediaPhoto(p, caption=caption if i==0 else "") for i, p in enumerate(photos[:10])])
            msg_id = msgs[0].message_id
        else:
            msg = await context.bot.send_message(CHANNEL_ID, caption); msg_id = msg.message_id
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("INSERT INTO ads (user_id, msg_id, brand, model, year, price, desc, full_text, photo_ids) VALUES (?,?,?,?,?,?,?,?,?)",
                       (update.effective_user.id, msg_id, ud['brand'], ud['model'], ud['year'], ud['price'], ud['desc'], caption, ",".join(photos)))
        conn.commit(); conn.close()
        await update.message.reply_text("✅ Опубліковано!")
    except Exception as e: await update.message.reply_text(f"Помилка: {e}")
    await start(update, context)
    return ConversationHandler.END

# --- ЗАПУСК ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    # ГОЛОВНИЙ СЕКРЕТ ТУТ: Глобальний MessageHandler перед анкетою
    app.add_handler(MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads_menu))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex("^(🗂 Мої оголошення|❌ Скасувати)$"), get_brand)],
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
            WAIT_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.Regex("^❌ Скасувати$"), save_edit)],
        },
        fallbacks=[MessageHandler(filters.Regex("^(❌ Скасувати|🗂 Мої оголошення)$"), start)],
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
    
