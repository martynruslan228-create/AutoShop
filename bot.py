import os, sqlite3, threading, logging, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGNFYLPXaKUuzb5Y3Or51Udv-vZFmkwoOk"
CHANNEL_ID = "@autochopOdessa"
DB_PATH = "ads.db"

(MAKE, MODEL, YEAR, GEARBOX, FUEL, DRIVE, DISTRICT, TOWN, PRICE, 
 DESCRIPTION, PHOTOS, PHONE, SHOW_CONTACT, CONFIRM, EDIT_PRICE) = range(15)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, details TEXT, msg_id INTEGER)')
    conn.commit()
    conn.close()

def generate_summary(data):
    username = data.get('username', 'приховано')
    tg_status = f"@{username}" if data.get('show_tg') == "Так" else "приховано"
    return (f"🚘 <b>{data.get('make','')} {data.get('model','')}</b>\n"
            f"📅 Рік: {data.get('year','')}\n"
            f"⚙️ КПП: {data.get('gearbox','')} | ⛽️ {data.get('fuel','')}\n"
            f"🛣 Привід: {data.get('drive','')}\n"
            f"📍 {data.get('district','')} р-н, {data.get('town','')}\n"
            f"💰 <b>Ціна: {data.get('price','')}$</b>\n\n"
            f"📝 <b>Опис:</b> {data.get('description','')}\n\n"
            f"📞 Тел: <code>{data.get('phone','')}</code>\n👤 TG: {tg_status}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚗 Вітаємо в Auto Shop Odessa!", 
        reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True))
    return ConversationHandler.END

async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['photos'] = []
    await update.message.reply_text("Введіть марку авто:", reply_markup=ReplyKeyboardRemove())
    return MAKE

async def get_make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['make'] = update.message.text
    await update.message.reply_text("Модель:"); return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Рік:"); return YEAR

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
    context.user_data['drive'] = update.message.text
    await update.message.reply_text("Район Одеси:"); return DISTRICT

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    await update.message.reply_text("Місто:"); return TOWN

async def get_town(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['town'] = update.message.text
    await update.message.reply_text("Ціна ($):"); return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Опис авто:"); return DESCRIPTION

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Фото (до 10 шт) + /done:", reply_markup=ReplyKeyboardMarkup([["➡️ Без фото"]], resize_keyboard=True))
    return PHOTOS

async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo: context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTOS

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Номер телефону:", reply_markup=ReplyKeyboardRemove()); return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Показати TG?", reply_markup=ReplyKeyboardMarkup([["Так", "Ні"]], resize_keyboard=True)); return SHOW_CONTACT

async def get_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['show_tg'] = update.message.text
    context.user_data['username'] = update.effective_user.username or "user"
    res = generate_summary(context.user_data)
    context.user_data['summary'] = res
    await update.message.reply_text(f"ПЕРЕВІРКА:\n\n{res}\n\nПублікуємо?", 
        reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True), parse_mode=ParseMode.HTML); return CONFIRM

async def final_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Так":
        ps = context.user_data.get('photos', [])
        cap = context.user_data['summary']
        try:
            if not ps: msg = await context.bot.send_message(CHANNEL_ID, cap, parse_mode=ParseMode.HTML)
            elif len(ps) == 1: msg = await context.bot.send_photo(CHANNEL_ID, ps[0], caption=cap, parse_mode=ParseMode.HTML)
            else:
                media = [InputMediaPhoto(p, caption=cap if i==0 else "", parse_mode=ParseMode.HTML) for i,p in enumerate(ps[:10])]
                msgs = await context.bot.send_media_group(CHANNEL_ID, media); msg = msgs[0]
            conn = sqlite3.connect(DB_PATH)
            conn.execute('INSERT INTO ads (user_id, details, msg_id) VALUES (?, ?, ?)', (update.effective_user.id, cap, msg.message_id))
            conn.commit(); conn.close()
            await update.message.reply_text("✅ Опубліковано!")
        except Exception as e: await update.message.reply_text(f"❌ Помилка: {e}")
    return ConversationHandler.END

async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute('SELECT id, details, msg_id FROM ads WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cur.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("У вас немає оголошень.")
        return
    for r in rows:
        kb = [[InlineKeyboardButton("💰 Ціна", callback_data=f"price_{r[0]}")], [InlineKeyboardButton("🗑 Видалити", callback_data=f"del_{r[0]}_{r[2]}")]]
        await update.message.reply_text(r[1], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; d = q.data.split("_")
    if d[0] == "del":
        try: await context.bot.delete_message(CHANNEL_ID, int(d[2]))
        except: pass
        conn = sqlite3.connect(DB_PATH); conn.execute('DELETE FROM ads WHERE id = ?', (d[1],)); conn.commit(); conn.close()
        await q.edit_message_text("🗑 Видалено.")
    elif d[0] == "price":
        context.user_data['edit_id'] = d[1]; await q.message.reply_text("Нова ціна ($):"); return EDIT_PRICE

async def update_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_p = update.message.text; db_id = context.user_data['edit_id']
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('SELECT details, msg_id FROM ads WHERE id = ?', (db_id,)); res = cur.fetchone()
    if res:
        txt = res[0].split("Ціна:")[0] + f"Ціна: {new_p}$</b>" + res[0].split("$</b>")[1]
        conn.execute('UPDATE ads SET details = ? WHERE id = ?', (txt, db_id)); conn.commit()
        try: await context.bot.edit_message_caption(CHANNEL_ID, res[1], caption=txt, parse_mode=ParseMode.HTML)
        except: await context.bot.edit_message_text(CHANNEL_ID, res[1], text=txt, parse_mode=ParseMode.HTML)
        await update.message.reply_text("✅ Оновлено!")
    conn.close(); return ConversationHandler.END

class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    init_db()
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), Health).serve_forever(), daemon=True).start()
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
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_price)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(conv)
    
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
 
