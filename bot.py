import os, sqlite3, threading, logging, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAEun5vwRl7f89vFZ1E5fJ5C1H4CDe7LLtw"
CHANNEL_ID = "@autochopOdessa" # Убедись, что бот админ здесь!
DB_PATH = "ads.db"

# Состояния
(MAKE, MODEL, YEAR, GEARBOX, FUEL, DRIVE, DISTRICT, TOWN, PRICE, 
 DESCRIPTION, PHOTOS, PHONE, SHOW_CONTACT, CONFIRM, EDIT_PRICE) = range(15)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # Добавлена колонка msg_id для связи с постом в канале
    conn.execute('CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, details TEXT, msg_id INTEGER)')
    conn.commit()
    conn.close()

def generate_summary(data):
    tg_status = f"@{data['username']}" if data.get('show_tg') == "Так" else "приховано"
    return (f"🚘 <b>{data['make']} {data['model']}</b>\n"
            f"📅 Рік: {data['year']}\n"
            f"⚙️ КПП: {data['gearbox']} | ⛽️ {data['fuel']}\n"
            f"📍 {data['district']} р-н, {data['town']}\n"
            f"💰 <b>Ціна: {data['price']}$</b>\n\n"
            f"📝 <b>Опис:</b> {data['description']}\n\n"
            f"📞 Тел: <code>{data['phone']}</code>\n👤 TG: {tg_status}")

# --- ПРОСМОТР И РЕДАКТИРОВАНИЕ ---

async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute('SELECT id, details, msg_id FROM ads WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall(); conn.close()
    
    if not rows:
        await update.message.reply_text("У вас немає активних оголошень.")
        return

    for r in rows:
        kb = [
            [InlineKeyboardButton("💰 Змінити ціну", callback_data=f"editprice_{r[0]}")],
            [InlineKeyboardButton("🗑 Видалити всюди", callback_data=f"del_{r[0]}_{r[2]}")]
        ]
        await update.message.reply_text(f"Ваше оголошення:\n\n{r[1]}", 
                                       parse_mode=ParseMode.HTML, 
                                       reply_markup=InlineKeyboardMarkup(kb))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    action = data[0]
    db_id = data[1]

    if action == "del":
        msg_id = data[2]
        # Удаляем из канала
        try: await context.bot.delete_message(CHANNEL_ID, int(msg_id))
        except: pass
        # Удаляем из базы
        conn = sqlite3.connect(DB_PATH); conn.execute('DELETE FROM ads WHERE id = ?', (db_id,))
        conn.commit(); conn.close()
        await query.edit_message_text("🗑 Оголошення видалено з бази та каналу.")

    elif action == "editprice":
        context.user_data['edit_db_id'] = db_id
        await query.message.reply_text("Введіть НОВУ ціну ($):")
        return EDIT_PRICE

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    db_id = context.user_data['edit_db_id']
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute('SELECT details, msg_id FROM ads WHERE id = ?', (db_id,))
    res = cursor.fetchone()
    
    if res:
        old_text = res[0]
        msg_id = res[1]
        # Простая замена цены в тексте (регуляркой или поиском строки)
        # Для надежности в реальном боте лучше пересобрать summary, но здесь мы просто обновим базу
        new_text = old_text.split("Ціна:")[0] + f"Ціна: {new_price}$</b>" + old_text.split("$</b>")[1]
        
        cursor.execute('UPDATE ads SET details = ? WHERE id = ?', (new_text, db_id))
        conn.commit()
        
        # Обновляем пост в канале
        try:
            await context.bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_id, caption=new_text, parse_mode=ParseMode.HTML)
        except:
            await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=msg_id, text=new_text, parse_mode=ParseMode.HTML)
        
        await update.message.reply_text("✅ Ціну оновлено всюди!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True))
    
    conn.close()
    return ConversationHandler.END

# --- ОСНОВНОЙ ФУНКЦИОНАЛ (АНКЕТА) ---
# (Тут остаются все шаги get_make, get_model и т.д. из предыдущего кода)
# Важное изменение только в final_post:

async def final_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Так, публікуємо":
        ps = context.user_data.get('photos', [])
        cap = context.user_data['summary']
        sent_msg = None
        try:
            if not ps:
                sent_msg = await context.bot.send_message(CHANNEL_ID, cap, parse_mode=ParseMode.HTML)
            elif len(ps) == 1:
                sent_msg = await context.bot.send_photo(CHANNEL_ID, ps[0], caption=cap, parse_mode=ParseMode.HTML)
            else:
                msgs = await context.bot.send_media_group(CHANNEL_ID, [InputMediaPhoto(p, caption=cap if i==0 else "", parse_mode=ParseMode.HTML) for i,p in enumerate(ps[:10])])
                sent_msg = msgs[0] # Запоминаем ID первого фото в альбоме
            
            # Сохраняем с msg_id
            conn = sqlite3.connect(DB_PATH)
            conn.execute('INSERT INTO ads (user_id, details, msg_id) VALUES (?, ?, ?)', (update.effective_user.id, cap, sent_msg.message_id))
            conn.commit(); conn.close()
            await update.message.reply_text("✅ Готово!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"]], resize_keyboard=True))
        except Exception as e:
            logging.error(e)
            await update.message.reply_text("Помилка прав.")
    return ConversationHandler.END

# --- СТАРТ И ЗАПУСК ---

async def main():
    init_db()
    # Запуск Health Check для Render
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), BaseHTTPRequestHandler).serve_forever(), daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad),
            CallbackQueryHandler(handle_callbacks, pattern="^editprice_")
        ],
        states={
            # ... тут все твои состояния (MAKE, MODEL и т.д.) ...
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price)],
            CONFIRM: [MessageHandler(filters.Regex("^(✅ Так, публікуємо|❌ Ні, заново)$"), final_post)],
            # Добавь остальные состояния из предыдущего кода сюда
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads))
    app.add_handler(CallbackQueryHandler(handle_callbacks, pattern="^del_"))
    app.add_handler(conv)
    
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
 
