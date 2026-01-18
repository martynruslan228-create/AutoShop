import os, asyncio, logging, sqlite3
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния анкеты (можно добавить все 14)
BRAND, MODEL, PRICE, CITY, PHONE, CHOOSE_CAR, WAIT_NEW_PRICE = range(7)

def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, price TEXT, city TEXT, phone TEXT, full_text TEXT)''')
    conn.commit(); conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [["➕ Нове оголошення"], ["📝 Редагувати", "🗑 Видалити"]]
    await update.message.reply_text("🚗 Головне меню:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# --- ВЫБОР АВТО (РАБОЧИЙ МЕТОД) ---
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['mode'] = "edit" if "Редагувати" in update.message.text else "del"
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()

    if not ads:
        await update.message.reply_text("❌ Оголошень не знайдено.")
        return ConversationHandler.END

    # Кнопки с названиями авто
    car_buttons = [[f"{ad[1]} {ad[2]} (${ad[3]})"] for ad in ads]
    car_buttons.append(["❌ Скасувати"])
    
    await update.message.reply_text("🔍 Оберіть авто для дії:", 
        reply_markup=ReplyKeyboardMarkup(car_buttons, resize_keyboard=True))
    return CHOOSE_CAR

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "❌ Скасувати": return await start(update, context)
    
    # Парсим название обратно для поиска
    car_info = choice.split(" ($")[0] 
    brand, model = car_info.split(" ", 1)
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, msg_id FROM ads WHERE brand = ? AND model = ?", (brand, model))
    res = cursor.fetchone(); conn.close()

    if res:
        context.user_data['sel_id'], context.user_data['msg_id'] = res
        if context.user_data['mode'] == "del":
            try: await context.bot.delete_message(CHANNEL_ID, res[1])
            except: pass
            conn = sqlite3.connect("ads.db"); c = conn.cursor()
            c.execute("DELETE FROM ads WHERE id = ?", (res[0],)); conn.commit(); conn.close()
            await update.message.reply_text("🗑 Видалено!")
            return await start(update, context)
        else:
            await update.message.reply_text(f"📝 Введіть НОВУ ЦІНУ для {car_info}:", reply_markup=ReplyKeyboardRemove())
            return WAIT_NEW_PRICE
    return await start(update, context)

# --- ОБНОВЛЕНИЕ ЦЕНЫ В КАНАЛЕ ---
async def update_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    ad_id = context.user_data['sel_id']
    msg_id = context.user_data['msg_id']
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT brand, model, city, phone FROM ads WHERE id = ?", (ad_id,))
    brand, model, city, phone = cursor.fetchone()
    
    new_text = f"🚗 {brand} {model}\n💰 НОВА ЦІНА: {new_price}$\n📍 Місто: {city}\n📞 Тел: {phone}"
    
    try:
        await context.bot.edit_message_text(new_text, CHANNEL_ID, msg_id)
        cursor.execute("UPDATE ads SET price = ?, full_text = ? WHERE id = ?", (new_price, new_text, ad_id))
        conn.commit()
        await update.message.reply_text("✅ Ціну оновлено в каналі!")
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка оновлення: {e}")
    
    conn.close()
    return await start(update, context)

# --- АНКЕТА (Укороченная для теста, легко добавить все поля) ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1. Марка:", reply_markup=ReplyKeyboardRemove())
    return BRAND
async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['b'] = update.message.text; await update.message.reply_text("2. Модель:"); return MODEL
async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['m'] = update.message.text; await update.message.reply_text("3. Ціна ($):"); return PRICE
async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p'] = update.message.text; await update.message.reply_text("4. Місто:"); return CITY
async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['c'] = update.message.text; await update.message.reply_text("5. Телефон:"); return PHONE
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data; phone = update.message.text
    full_text = f"🚗 {ud['b']} {ud['m']}\n💰 Ціна: {ud['p']}$\n📍 Місто: {ud['c']}\n📞 Тел: {phone}"
    
    msg = await context.bot.send_message(CHANNEL_ID, full_text)
    conn = sqlite3.connect("ads.db"); c = conn.cursor()
    c.execute("INSERT INTO ads (user_id, msg_id, brand, model, price, city, phone, full_text) VALUES (?,?,?,?,?,?,?,?)",
              (update.effective_user.id, msg.message_id, ud['b'], ud['m'], ud['p'], ud['c'], phone, full_text))
    conn.commit(); conn.close()
    await update.message.reply_text("✅ Опубліковано!")
    return await start(update, context)

async def main():
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad),
            MessageHandler(filters.Regex("^(📝 Редагувати|🗑 Видалити)$"), show_list)
        ],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CHOOSE_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice)],
            WAIT_NEW_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_price)]
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(conv); app.add_handler(CommandHandler("start", start))
    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling(); await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
