import os, asyncio, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Дані бота та каналу
TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Етапи анкетування
BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESC, PRICE, PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE = range(14)

# --- СТАРТ ТА ГОЛОВНЕ МЕНЮ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Вітаємо!\n\nЯ — офіційний бот Auto Shop Odessa\n"
        "Допоможу вам опублікувати оголошення:\n👉 https://t.me/autochopOdessa"
    )
    kb = [["➕ Нове оголошення"]]
    await update.message.reply_text(
        welcome_text, 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        disable_web_page_preview=True
    )
    return ConversationHandler.END

# --- ПОЧАТОК АНКЕТИ ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "1. Введіть марку авто:", 
        reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True)
    )
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
    u = update.effective_user
    context.user_data['tg_link'] = f"@{u.username}" if update.message.text == "✅ Так" and u.username else "Приватна особа"
    await update.message.reply_text("14. Введіть номер телефону вручну:", reply_markup=ReplyKeyboardRemove())
    return PHONE

# --- ПУБЛІКАЦІЯ ---
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
            await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        await update.message.reply_text("✅ Опубліковано!")
    except Exception as e:
        await update.message.reply_text(f"Помилка при публікації: {e}")
    
    await start(update, context)
    return ConversationHandler.END

# --- СЕРВЕР ТА ЗАПУСК ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex("^❌ Скасувати$"), get_brand)],
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
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$"), start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
