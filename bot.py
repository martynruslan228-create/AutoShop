import os, asyncio, logging, sqlite3
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния
BRAND, MODEL, CHOOSE_CAR, WAIT_EDIT = range(4)

# --- БД (Чистая база для теста) ---
def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS ads") # Удаляем старое, чтобы не мешало
    cursor.execute('''CREATE TABLE ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, full_text TEXT)''')
    conn.commit(); conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["➕ Нове оголошення"], ["📝 Редагувати", "🗑 Видалити"]]
    await update.message.reply_text("🚗 Оберіть дію:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# --- ВЫВОД СПИСКА МАШИН В КНОПКИ МЕНЮ ---
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['mode'] = "edit" if "Редагувати" in update.message.text else "del"
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()

    if not ads:
        await update.message.reply_text("❌ Оголошень не знайдено.")
        return ConversationHandler.END

    # Создаем кнопки: Текст на кнопке = "Марка Модель"
    car_buttons = [[f"{ad[1]} {ad[2]}"] for ad in ads]
    car_buttons.append(["❌ Скасувати"])
    
    await update.message.reply_text("🔍 Оберіть авто зі списку нижче:", 
        reply_markup=ReplyKeyboardMarkup(car_buttons, resize_keyboard=True))
    return CHOOSE_CAR

# --- ОБРАБОТКА ВЫБОРА ---
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    car_name = update.message.text
    if car_name == "❌ Скасувати": return await start(update, context)
    
    # Ищем в базе по названию, которое нажал юзер
    brand, model = car_name.split(" ", 1)
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, msg_id FROM ads WHERE brand = ? AND model = ?", (brand, model))
    res = cursor.fetchone()
    conn.close()

    if res:
        ad_id, msg_id = res
        context.user_data['sel_id'] = ad_id
        if context.user_data['mode'] == "del":
            try: await context.bot.delete_message(CHANNEL_ID, msg_id)
            except: pass
            conn = sqlite3.connect("ads.db"); c = conn.cursor()
            c.execute("DELETE FROM ads WHERE id = ?", (ad_id,)); conn.commit(); conn.close()
            await update.message.reply_text("🗑 Видалено!")
            return await start(update, context)
        else:
            await update.message.reply_text(f"📝 Ви обрали {car_name}. Введіть новий текст:")
            return WAIT_EDIT
    return await start(update, context)

# --- АНКЕТА ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Марка:", reply_markup=ReplyKeyboardRemove())
    return BRAND
async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['b'] = update.message.text; await update.message.reply_text("Модель:"); return MODEL
async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data; model = update.message.text
    text = f"🚗 {ud['b']} {model}\n✅ В наявності"
    msg = await context.bot.send_message(CHANNEL_ID, text)
    conn = sqlite3.connect("ads.db"); c = conn.cursor()
    c.execute("INSERT INTO ads (user_id, msg_id, brand, model, full_text) VALUES (?,?,?,?,?)",
              (update.effective_user.id, msg.message_id, ud['b'], model, text))
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
            CHOOSE_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice)],
            WAIT_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, start)] # Просто возврат для теста
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(conv); app.add_handler(CommandHandler("start", start))
    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling(); await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
