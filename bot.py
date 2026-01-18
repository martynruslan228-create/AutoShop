import os, asyncio, logging, threading, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния
(BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESC, PRICE, 
 PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE, WAIT_EDIT_VALUE) = range(15)

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

# --- ГЛАВНОЕ МЕНЮ (3 КНОПКИ) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [
        ["➕ Нове оголошення"],
        ["📝 Редагувати", "🗑 Видалити"]
    ]
    await update.message.reply_text(
        "🚗 **Головне меню**\nОберіть дію:", 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- ЛОГИКА СПИСКА (ДЛЯ РЕДАКТИРОВАНИЯ ИЛИ УДАЛЕНИЯ) ---
async def show_ads_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text # "📝 Редагувати" или "🗑 Видалити"
    action = "edit" if "Редагувати" in text else "del"
    
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()

    if not ads:
        await update.message.reply_text("У вас ще немає активних оголошень.")
        return ConversationHandler.END

    await update.message.reply_text(f"Оберіть авто для {'редагування' if action == 'edit' else 'видалення'}:")
    for ad in ads:
        callback_data = f"sel{action}_{ad[0]}" # seledit_1 или seldel_1
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Вибрати цей автомобіль", callback_query_data=callback_data)]])
        await update.message.reply_text(f"🚗 {ad[1]} {ad[2]} | {ad[3]}$", reply_markup=kb)
    return ConversationHandler.END

# --- ОБРАБОТКА ИНЛАЙН КНОПОК ---
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # Удаление
    if data.startswith("seldel_"):
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
        await query.edit_message_text("🗑 Оголошення видалено з каналу.")

    # Выбор поля для правки
    elif data.startswith("seledit_"):
        ad_id = data.split("_")[1]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Змінити ціну", callback_query_data=f"field_price_{ad_id}")],
            [InlineKeyboardButton("📄 Змінити опис", callback_query_data=f"field_desc_{ad_id}")]
        ])
        await query.edit_message_text("Що саме хочете змінити?", reply_markup=kb)

    # Запрос нового значения
    elif data.startswith("field_"):
        _, field, ad_id = data.split("_")
        context.user_data['edit_ad_id'] = ad_id
        context.user_data['edit_field'] = field
        
        prompt = "Введіть нову ціну ($):" if field == "price" else "Введіть новий опис авто:"
        await query.message.reply_text(prompt, reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True))
        return WAIT_EDIT_VALUE

# --- СОХРАНЕНИЕ ПРАВОК ---
async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_val = update.message.text
    if new_val == "❌ Скасувати": return await start(update, context)

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
        except: await update.message.reply_text("❌ Помилка зв'язку з каналом.")
    
    conn.close()
    return await start(update, context)

# --- АНКЕТА ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1. Марка авто:", reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True))
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['brand'] = update.message.text
    await update.message.reply_text("2. Модель:")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("9. Ціна ($):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("14. Номер телефону:")
    return PHONE

async def finish_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    caption = f"🚗 {ud['brand']} {ud['model']}\n\n💰 Ціна: {ud['price']}$\n📞 Тел: {update.message.text}"
    msg = await context.bot.send_message(CHANNEL_ID, caption)
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("INSERT INTO ads (user_id, msg_id, brand, model, price, full_text) VALUES (?,?,?,?,?,?)",
                   (update.effective_user.id, msg.message_id, ud['brand'], ud['model'], ud['price'], caption))
    conn.commit(); conn.close()
    await update.message.reply_text("✅ Опубліковано!")
    return await start(update, context)

# --- СЕРВЕР И ЗАПУСК ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    app = Application.builder().token(TOKEN).build()

    # Глобальные команды (приоритет над анкетой)
    app.add_handler(MessageHandler(filters.Regex("^(📝 Редагувати|🗑 Видалити)$"), show_ads_list))
    app.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.Regex("^(📝 Редагувати|🗑 Видалити|❌ Скасувати)$"), get_brand)],
            MODEL: [MessageHandler(filters.TEXT, get_model)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
            PHONE: [MessageHandler(filters.TEXT, finish_ad)],
            WAIT_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.Regex("^❌ Скасувати$"), save_edit)],
        },
        fallbacks=[MessageHandler(filters.Regex("^(❌ Скасувати|📝 Редагувати|🗑 Видалити)$"), start)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_router))

    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
