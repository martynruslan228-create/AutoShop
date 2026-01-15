import os, asyncio, logging, threading, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния анкеты (не меняем)
BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESC, PRICE, PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE = range(14)
# Состояния редактирования
EDIT_SELECT_FIELD, EDIT_INPUT_VALUE = range(14, 16)

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
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
    welcome = "Вітаємо! Я — бот Auto Shop Odessa. Оберіть дію:"
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text(welcome, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

def build_caption(ad):
    # Собираем текст так же, как в оригинале
    return (f"🚗 {ad['brand']} {ad['model']} ({ad['year']})\n\n"
            f"🔹 Об'єм: {ad['engine']} л.\n⛽️ Паливо: {ad['fuel']}\n"
            f"⚙️ КПП: {ad['gearbox']}\n☸️ Привід: {ad['drive']}\n"
            f"📍 Місце: {ad['district']} р-н, {ad['city']}\n\n"
            f"📝 Опис:\n{ad['desc']}\n\n"
            f"💰 Ціна: {ad['price']}$\n\n"
            f"📞 Телефон: {ad['phone']}\n👤 Контакт: {ad['tg_link']}")

# --- НОВАЯ ФУНКЦИЯ "МОЇ ОГОЛОШЕННЯ" ---
async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()
    
    if not ads:
        await update.message.reply_text("У вас ще немає оголошень.")
        return ConversationHandler.END

    for ad in ads:
        text = f"🚗 {ad[1]} {ad[2]} — {ad[3]}$"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Редагувати", callback_query_data=f"edit_init_{ad[0]}")],
            [InlineKeyboardButton("🗑 Видалити", callback_query_data=f"del_{ad[0]}")]
        ])
        await update.message.reply_text(text, reply_markup=kb)
    return ConversationHandler.END

# --- ОБРАБОТКА УДАЛЕНИЯ И РЕДАКТИРОВАНИЯ ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; data = query.data; await query.answer()
    
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

    elif data.startswith("edit_init_"):
        context.user_data['edit_ad_id'] = data.split("_")[2]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Ціна", callback_query_data="f_price"), InlineKeyboardButton("Опис", callback_query_data="f_desc")],
            [InlineKeyboardButton("Телефон", callback_query_data="f_phone"), InlineKeyboardButton("⏩ Пропустити", callback_query_data="edit_cancel")]
        ])
        await query.edit_message_text("Оберіть пункт для зміни:", reply_markup=kb)
        return EDIT_SELECT_FIELD

async def edit_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; data = query.data; await query.answer()
    if data == "edit_cancel":
        await query.edit_message_text("Редагування скасовано.")
        return ConversationHandler.END
    
    field = data.split("_")[1]
    context.user_data['edit_field'] = field
    prompts = {"price": "нову ціну ($)", "desc": "новий опис", "phone": "новий номер телефону"}
    await query.edit_message_text(f"Введіть {prompts[field]}:")
    return EDIT_INPUT_VALUE

async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_val = update.message.text
    ad_id = context.user_data['edit_ad_id']
    field = context.user_data['edit_field']
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute(f"UPDATE ads SET {field} = ? WHERE id = ?", (new_val, ad_id))
    cursor.execute("SELECT * FROM ads WHERE id = ?", (ad_id,))
    r = cursor.fetchone(); conn.commit(); conn.close()
    
    ad = {'msg_id': r[2], 'brand': r[3], 'model': r[4], 'year': r[5], 'engine': r[6], 'fuel': r[7], 
          'gearbox': r[8], 'drive': r[9], 'desc': r[10], 'price': r[11], 'district': r[12], 
          'city': r[13], 'tg_link': r[14], 'phone': r[15], 'photo_ids': r[16]}
    
    try:
        if ad['photo_ids']: await context.bot.edit_message_caption(CHANNEL_ID, ad['msg_id'], caption=build_caption(ad), parse_mode=None)
        else: await context.bot.edit_message_text(build_caption(ad), CHANNEL_ID, ad['msg_id'], parse_mode=None)
        await update.message.reply_text("✅ Оновлено!")
    except: await update.message.reply_text("Змінено в базі, не вдалося оновити пост.")
    
    await start(update, context)
    return ConversationHandler.END

# --- ОРИГИНАЛЬНАЯ АНКЕТА (БЕЗ ИЗМЕНЕНИЙ) ---
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
    await update.message.reply_text("12. Введіть місто/село вручную:", reply_markup=ReplyKeyboardRemove())
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['city'] = update.message.text
    await update.message.reply_text("13. Показати посилання на ваш Telegram?", reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True))
    return TG_CONTACT

async def get_tg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    context.user_data['tg_link'] = f"@{u.username}" if update.message.text == "✅ Так" and u.username else "Приватна особа"
    await update.message.reply_text("14. Введіть номер телефону вручную:", reply_markup=ReplyKeyboardRemove())
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
            msgs = await context.bot.send_media_group(CHANNEL_ID, media=media)
            msg_id = msgs[0].message_id
        else:
            m = await context.bot.send_message(CHANNEL_ID, caption, parse_mode=None)
            msg_id = m.message_id
        
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute('''INSERT INTO ads (user_id, msg_id, brand, model, year, engine, fuel, gearbox, drive, desc, price, district, city, tg_link, phone, photo_ids) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (update.effective_user.id, msg_id, ud['brand'], ud['model'], ud['year'], ud['engine'], ud['fuel'], ud['gearbox'], ud['drive'], ud['desc'], ud['price'], ud['district'], ud['city'], ud['tg_link'], ud['phone'], ",".join(photos)))
        conn.commit(); conn.close()
        await update.message.reply_text("✅ Опубліковано!")
    except Exception as e: await update.message.reply_text(f"❌ Помилка: {e}")
    await start(update, context)
    return ConversationHandler.END

# --- ЗАПУСК ---
async def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad),
            MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads)
        ],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex("^❌ Скасувати$") & ~filters.Regex("^🗂 Мої оголошення$"), get_brand)],
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
            EDIT_SELECT_FIELD: [CallbackQueryHandler(edit_select_field)],
            EDIT_INPUT_VALUE: [MessageHandler(filters.TEXT, save_edit)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$") | filters.Regex("^🗂 Мої оголошення$"), start)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))

    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
        
