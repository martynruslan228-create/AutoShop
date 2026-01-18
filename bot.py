import os, asyncio, logging, sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния
BRAND, MODEL, PRICE, WAIT_EDIT = range(4)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    # Чистим старую таблицу, чтобы не было конфликтов
    cursor.execute("DROP TABLE IF EXISTS ads")
    cursor.execute('''CREATE TABLE ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, price TEXT, full_text TEXT)''')
    conn.commit(); conn.close()

# Вызываем инициализацию (Внимание: старая БД удалится для чистоты теста!)
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["➕ Нове оголошення"], ["📝 Редагувати", "🗑 Видалити"]]
    await update.message.reply_text("🚗 Выберите действие:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# --- ДИНАМИЧЕСКИЕ КНОПКИ (Имена из базы) ---
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action_type = "edit" if "Редагувати" in update.message.text else "del"
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()

    if not ads:
        await update.message.reply_text("❌ У вас еще нет объявлений.")
        return

    await update.message.reply_text(f"🔍 Найдено {len(ads)} авто. Нажмите на название для выбора:")

    for ad in ads:
        ad_id, brand, model, price = ad
        # Текст на самой кнопке теперь уникальный:
        btn_text = f"🚗 {brand} {model} ({price}$)"
        # Кодируем действие максимально коротко: 'e12' (edit 12) или 'd12' (del 12)
        cb_data = f"{action_type[0]}{ad_id}" 
        
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(text=btn_text, callback_query_data=cb_data)]])
        
        await update.message.reply_text(f"Управление объявлением:", reply_markup=kb)

# --- ОБРАБОТЧИК НАЖАТИЯ ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data # Например 'e1' или 'd1'
    await query.answer()

    action = data[0] # 'e' или 'd'
    ad_id = data[1:] # сам ID

    if action == 'd': # УДАЛЕНИЕ
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT msg_id FROM ads WHERE id = ?", (ad_id,))
        res = cursor.fetchone()
        if res:
            try: await context.bot.delete_message(CHANNEL_ID, res[0])
            except: pass
            cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
            conn.commit()
        conn.close()
        await query.edit_message_text("🗑 Удалено из канала и базы.")

    elif action == 'e': # РЕДАКТИРОВАНИЕ
        context.user_data['edit_id'] = ad_id
        await query.message.reply_text(f"📝 Введите новую цену ($) для этого авто:")
        return WAIT_EDIT

# --- СОХРАНЕНИЕ ЦЕНЫ ---
async def save_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    ad_id = context.user_data.get('edit_id')
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT msg_id, brand, model FROM ads WHERE id = ?", (ad_id,))
    res = cursor.fetchone()
    
    if res:
        msg_id, brand, model = res
        new_text = f"🚗 {brand} {model}\n💰 Нова ціна: {new_price}$"
        try:
            await context.bot.edit_message_text(new_text, CHANNEL_ID, msg_id)
            cursor.execute("UPDATE ads SET price = ?, full_text = ? WHERE id = ?", (new_price, new_text, ad_id))
            conn.commit()
            await update.message.reply_text("✅ Цена обновлена!")
        except: await update.message.reply_text("❌ Не удалось обновить пост в канале.")
    conn.close()
    return await start(update, context)

# --- МИНИ-АНКЕТА ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Марка:", reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True))
    return BRAND
async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Отмена": return await start(update, context)
    context.user_data['b'] = update.message.text; await update.message.reply_text("Модель:"); return MODEL
async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['m'] = update.message.text; await update.message.reply_text("Цена:"); return PRICE
async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data; price = update.message.text
    full_text = f"🚗 {ud['b']} {ud['m']}\n💰 Ціна: {price}$"
    msg = await context.bot.send_message(CHANNEL_ID, full_text)
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("INSERT INTO ads (user_id, msg_id, brand, model, price, full_text) VALUES (?,?,?,?,?,?)",
                   (update.effective_user.id, msg.message_id, ud['b'], ud['m'], price, full_text))
    conn.commit(); conn.close()
    await update.message.reply_text("✅ Опубликовано!")
    return await start(update, context)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(📝 Редагувати|🗑 Видалити)$"), show_list))

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex("^(📝|🗑|/)"), get_brand)],
            MODEL: [MessageHandler(filters.TEXT, get_model)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
            WAIT_EDIT: [MessageHandler(filters.TEXT, save_price)]
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_callback))

    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
