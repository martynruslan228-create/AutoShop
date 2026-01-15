import os, asyncio, logging, threading, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Этапы анкеты (Публикация)
BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESC, PRICE, PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE = range(14)
# Этапы редактирования
EDIT_SELECT_FIELD, EDIT_INPUT_VALUE = range(14, 16)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    # Создаем таблицу с отдельными полями для каждого параметра
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, year TEXT, engine TEXT, fuel TEXT, 
                       gearbox TEXT, drive TEXT, desc TEXT, price TEXT, 
                       district TEXT, city TEXT, tg_link TEXT, phone TEXT, photo_ids TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = "Вітаємо! Я — бот Auto Shop Odessa.\nОберіть дію:"
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text(welcome, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

def build_caption(ad_data):
    # Универсальная функция сборки текста объявления
    return (f"🚗 {ad_data['brand']} {ad_data['model']} ({ad_data['year']})\n\n"
            f"🔹 Об'єм: {ad_data['engine']} л.\n⛽️ Паливо: {ad_data['fuel']}\n"
            f"⚙️ КПП: {ad_data['gearbox']}\n☸️ Привід: {ad_data['drive']}\n"
            f"📍 Місце: {ad_data['district']} р-н, {ad_data['city']}\n\n"
            f"📝 Опис:\n{ad_data['desc']}\n\n"
            f"💰 Ціна: {ad_data['price']}$\n\n"
            f"📞 Телефон: {ad_data['phone']}\n👤 Контакт: {ad_data['tg_link']}")

# --- ЛОГИКА "МОЇ ОГОЛОШЕННЯ" (ПРОСМОТР, УДАЛЕНИЕ, РЕДАКТИРОВАНИЕ) ---
async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price, msg_id FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()
    
    if not ads:
        await update.message.reply_text("У вас немає активних оголошень.")
        return ConversationHandler.END

    for ad in ads:
        info = f"🚗 {ad[1]} {ad[2]} | 💰 {ad[3]}$"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Редагувати ціну", callback_query_data=f"ed_price_{ad[0]}")],
            [InlineKeyboardButton("🗑 Видалити", callback_query_data=f"del_{ad[0]}")]
        ])
        await update.message.reply_text(info, reply_markup=kb)
    return ConversationHandler.END

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; data = query.data; await query.answer()
    
    # Удаление
    if data.startswith("del_"):
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

    # Редактирование цены
    elif data.startswith("ed_price_"):
        context.user_data['edit_ad_id'] = data.split("_")[2]
        await query.message.reply_text("Введіть нову ціну ($):")
        return EDIT_INPUT_VALUE

async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    ad_id = context.user_data.get('edit_ad_id')
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    # 1. Получаем все данные объявления
    cursor.execute("SELECT * FROM ads WHERE id = ?", (ad_id,))
    row = cursor.fetchone()
    if not row: return ConversationHandler.END
    
    # Мапим данные из БД в словарь
    ad = {
        'msg_id': row[2], 'brand': row[3], 'model': row[4], 'year': row[5],
        'engine': row[6], 'fuel': row[7], 'gearbox': row[8], 'drive': row[9],
        'desc': row[10], 'price': new_price, 'district': row[12], 'city': row[13],
        'tg_link': row[14], 'phone': row[15], 'photo_ids': row[16]
    }
    
    # 2. Обновляем в БД
    cursor.execute("UPDATE ads SET price = ? WHERE id = ?", (new_price, ad_id))
    conn.commit(); conn.close()
    
    # 3. Обновляем пост в канале
    new_caption = build_caption(ad)
    try:
        if ad['photo_ids']:
            await context.bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=ad['msg_id'], caption=new_caption, parse_mode=None)
        else:
            await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=ad['msg_id'], text=new_caption, parse_mode=None)
        await update.message.reply_text("✅ Ціну оновлено!")
    except Exception as e:
        await update.message.reply_text(f"Помилка оновлення: {e}")
    
    await start(update, context)
    return ConversationHandler.END

# --- ЛОГИКА ПУБЛИКАЦИИ (АНКЕТА) ---
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
    ud['phone'] = update.message.text
    caption = build_caption(ud)
    
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
        cursor.execute('''INSERT INTO ads (user_id, msg_id, brand, model, year, engine, fuel, 
                          gearbox, drive, desc, price, district, city, tg_link, phone, photo_ids) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (update.effective_user.id, msg_id, ud['brand'], ud['model'], ud['year'], 
                        ud['engine'], ud['fuel'], ud['gearbox'], ud['drive'], ud['desc'], 
                        ud['price'], ud['district'], ud['city'], ud['tg_link'], ud['phone'], ",".join(photos)))
        conn.commit(); conn.close()
        await update.message.reply_text("✅ Опубліковано!")
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")

    await start(update, context)
    return ConversationHandler.END

# --- СЕРВЕР И ЗАПУСК ---
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
        entry_points=[
            MessageHandler(filters.Regex(re_new_ad), new_ad),
            MessageHandler(filters.Regex(re_my_ads), my_ads)
        ],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_brand)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_year)],
            ENGINE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_engine)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_fuel)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_gearbox)],
            DRIVE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_drive)],
            DESC: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_desc)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_price)],
            PHOTO: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.Regex(re_cancel), get_photo)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_district)],
            CITY: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_city)],
            TG_CONTACT: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), get_tg_contact)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), finish_ad)],
            EDIT_INPUT_VALUE: [MessageHandler(filters.TEXT & ~filters.Regex(re_cancel), save_edit)],
        },
        fallbacks=[MessageHandler(filters.Regex(re_cancel) | filters.Regex(re_my_ads), start)],
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
        
