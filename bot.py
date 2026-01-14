import os, sqlite3, threading, logging, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAEun5vwRl7f89vFZ1E5fJ5C1H4CDe7LLtw"
CHANNEL_ID = "@autochopOdessa"
DB_PATH = "ads.db"

# Состояния
(MAKE, MODEL, YEAR, GEARBOX, FUEL, DRIVE, DISTRICT, TOWN, PRICE, 
 DESCRIPTION, PHOTOS, PHONE, SHOW_CONTACT, CONFIRM, EDIT_PRICE) = range(15)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, details TEXT, msg_id INTEGER)')
    conn.commit()
    conn.close()

def generate_summary(data):
    tg_status = f"@{data['username']}" if data.get('show_tg') == "Так" else "приховано"
    return (f"🚘 <b>{data['make']} {data['model']}</b>\n"
            f"📅 Рік: {data['year']}\n"
            f"⚙️ КПП: {data['gearbox']} | ⛽️ {data['fuel']}\n"
            f"🛣 Привід: {data['drive']}\n"
            f"📍 {data['district']} р-н, {data['town']}\n"
            f"💰 <b>Ціна: {data['price']}$</b>\n\n"
            f"📝 <b>Опис:</b> {data['description']}\n\n"
            f"📞 Тел: <code>{data['phone']}</code>\n👤 TG: {tg_status}")

# --- ФУНКЦИИ МОИ ОБЪЯВЛЕНИЯ И РЕДАКТИРОВАНИЕ ---

async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute('SELECT id, details, msg_id FROM ads WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("У вас немає активних оголошень.")
        return
    for r in rows:
        kb = [[InlineKeyboardButton("💰 Змінити ціну", callback_data=f"editprice_{r[0]}")],
              [InlineKeyboardButton("🗑 Видалити всюди", callback_data=f"del_{r[0]}_{r[2]}")]]
        await update.message.reply_text(f"Ваше оголошення:\n\n{r[1]}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; data = query.data.split("_"); action = data[0]; db_id = data[1]
    if action == "del":
        try: await context.bot.delete_message(CHANNEL_ID, int(data[2]))
        except: pass
        conn = sqlite3.connect(DB_PATH); conn.execute('DELETE FROM ads WHERE id = ?', (db_id,)); conn.commit(); conn.close()
        await query.edit_message_text("🗑 Видалено всюди.")
    elif action == "editprice":
        context.user_data['edit_db_id'] = db_id
        await query.message.reply_text("Введіть НОВУ ціну ($):")
        return EDIT_PRICE

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text; db_id = context.user_data['edit_db_id']
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute('SELECT details, msg_id FROM ads WHERE id = ?', (db_id,)); res = cursor.fetchone()
    if res:
        old_text = res[0]; msg_id = res[1]
        try:
            new_text = old_text.split("Ціна:")[0] + f"Ціна: {new_price}$</b>" + old_text.split("$</b>")[1]
            cursor.execute('UPDATE ads SET details = ? WHERE id = ?', (new_text, db_id)); conn.commit()
            try: await context.bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_id, caption=new_text, parse_mode=ParseMode.HTML)
            except: await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=msg_id, text=new_text, parse_mode=ParseMode.HTML)
            await update.message.reply_text("✅ Ціну оновлено!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True))
        except Exception as e: await update.message.reply_text(f"Помилка оновлення.")
    conn.close(); return ConversationHandler.END

# --- ЦЕПОЧКА СОЗДАНИЯ ОБЪЯВЛЕНИЯ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚗 Auto Shop Odessa", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True))
    return ConversationHandler.END

async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear(); context.user_data['photos'] = []
    await update.message.reply_text("Марка авто:", reply_markup=ReplyKeyboardRemove()); return MAKE

async def get_make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['make'] = update.message.text; await update.message.reply_text("Модель:"); return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text; await update.message.reply_text("Рік:"); return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['year'] = update.message.text
    await update.message.reply_text("КПП:", reply_markup=ReplyKeyboardMarkup([["Автомат", "Механіка"]], resize_keyboard=True)); return GEARBOX

async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gearbox'] = update.message.text
    await update.message.reply_text("Паливо:", reply_markup=ReplyKeyboardMarkup([["Бензин", "Дизель", "Газ", "Електро"]], resize_keyboard=True)); return FUEL

async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fuel'] = update.message.text
    await update.message.reply_text("Привід:", reply_markup=ReplyKeyboardMarkup([["Передній", "Задній", "Повний"]], resize_keyboard=True)); return DRIVE

async def get_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['drive'] = update.message.text; await update.message.reply_text("Район Одеси:"); return DISTRICT

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text; await update.message.reply_text("Місто:"); return TOWN

async def get_town(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['town'] = update.message.text; await update.message.reply_text("Ціна ($):"); return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text; await update.message.reply_text("Опис:"); return DESCRIPTION

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Фото (до 10) + /done:", reply_markup=ReplyKeyboardMarkup([["➡️ Без фото"]], resize_keyboard=True)); return PHOTOS

async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo: context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTOS

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Телефон:", reply_markup=ReplyKeyboardRemove()); return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Показати TG?", reply_markup=ReplyKeyboardMarkup([["Так", "Ні"]], resize_keyboard=True)); return SHOW_CONTACT

async def get_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['show_tg'] = update.message.text; context.user_data['username'] = update.effective_user.username
    res = generate_summary(context.user_data); context.user_data['summary'] = res
    await update.message.reply_text(f"{res}\n\nПублікуємо?", reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True), parse_mode=ParseMode.HTML); return CONFIRM

async def final_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Так":
        ps = context.user_data.get('photos', []); cap = context.user_data['summary']; sent_msg = None
        try:
            if not ps: sent_msg = await context.bot.send_message(CHANNEL_ID, cap, parse_mode=ParseMode.HTML)
            elif len(ps) == 1: sent_msg = await context.bot.send_photo(CHANNEL_ID, ps[0], caption=cap, parse_mode=ParseMode.HTML)
            else:
                msgs = await context.bot.send_media_group(CHANNEL_ID, [InputMediaPhoto(p, caption=cap if i==0 else "", parse_mode=ParseMode.HTML) for i,p in enumerate(ps[:10])])
                sent_msg = msgs[0]
            conn = sqlite3.connect(DB_PATH); conn.execute('INSERT INTO ads (user_id, details, msg_id) VALUES (?, ?, ?)', (update.effective_user.id, cap, sent_msg.message_id)); conn.commit(); conn.close()
            await update.message.reply_text("✅ Опубліковано!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"]], resize_keyboard=True))
        except: await update.message.reply_text("Помилка прав.")
    return ConversationHandler.END

# --- ЗАПУСК ---
class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    init_db()
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), H).serve_forever(), daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad)],
        states={
            MAKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_make)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gearbox)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fuel)],
            DRIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_district)],
            TOWN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_town)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc)],
            PHOTOS: [MessageHandler(filters.PHOTO, get_photos), CommandHandler('done', done_photos), MessageHandler(filters.Regex("^➡️ Без фото$"), done_photos)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            SHOW_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tg)],
            CONFIRM: [MessageHandler(filters.Regex("^(✅ Так|❌ Ні)$"), final_post)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(conv)
    
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
                       
