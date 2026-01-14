import os, sqlite3, threading, logging, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa" 
CHANNEL_LINK = "https://t.me/autochopOdessa"
BOT_NAME = "AutoChop Bot"
DB_PATH = "ads.db"

# Стан розмови
(MAKE, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE, DESCRIPTION, 
 PRICE, PHOTOS, DISTRICT, TOWN, SHARE_TG, PHONE, CONFIRM, EDIT_PRICE) = range(16)

# --- БАЗА ДАНИХ ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, details TEXT, msg_id INTEGER)')
    conn.commit()
    conn.close()

def generate_summary(data):
    tg_status = f"@{data['username']}" if data.get('share_tg') == "Так" else "приховано"
    return (f"🚘 <b>{data['make']} {data['model']}</b>\n"
            f"📅 Рік: {data['year']}\n"
            f"🔌 Об'єм: {data['engine']} л.\n"
            f"⛽️ Паливо: {data['fuel']}\n"
            f"⚙️ КПП: {data['gearbox']}\n"
            f"⛓ Привід: {data['drive']}\n"
            f"📍 {data['district']} р-н, {data['town']}\n"
            f"💰 <b>Ціна: {data['price']}$</b>\n\n"
            f"📝 <b>Опис:</b> {data['description']}\n\n"
            f"📞 Тел: <code>{data['phone']}</code>\n👤 TG: {tg_status}")

# --- КОМАНДИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        f"👋 <b>Вітаю! Я — {BOT_NAME}.</b>\n\n"
        f"Я допоможу вам швидко та зручно розмістити оголошення про продаж авто в нашому каналі: "
        f"<a href='{CHANNEL_LINK}'>autochopOdessa</a>.\n\n"
        f"Оберіть дію на клавіатурі нижче 👇"
    )
    kb = [["➕ Нове оголошення"], ["🗂 Мої оголошення"]]
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- ПРОЦЕС СТВОРЕННЯ ОГОЛОШЕННЯ ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear() # Очищення даних перед новим записом
    await update.message.reply_text("Введіть марку авто (наприклад, BMW):", reply_markup=ReplyKeyboardRemove())
    return MAKE

async def get_make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['make'] = update.message.text
    await update.message.reply_text("Введіть модель авто:")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Введіть рік випуску:")
    return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['year'] = update.message.text
    await update.message.reply_text("Введіть об'єм двигуна (наприклад, 2.0):")
    return ENGINE

async def get_engine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['engine'] = update.message.text
    kb = [["Бензин", "Дизель"], ["Гібрид", "Електро"], ["Газ/Бензин"]]
    await update.message.reply_text("Оберіть тип палива:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return FUEL

async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fuel'] = update.message.text
    kb = [["Механіка", "Автомат"], ["Робот", "Варіатор"]]
    await update.message.reply_text("Оберіть КПП:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return GEARBOX

async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gearbox'] = update.message.text
    kb = [["Передній", "Задній"], ["Повний"]]
    await update.message.reply_text("Оберіть привід:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return DRIVE

async def get_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['drive'] = update.message.text
    await update.message.reply_text("Напишіть опис авто (пробіг, стан тощо):")
    return DESCRIPTION

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Введіть ціну в $ (тільки число):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Надішліть фото авто (до 5 шт). Коли закінчите, натисніть /done")
    context.user_data['photos'] = []
    return PHOTOS

async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTOS

async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('photos'):
        await update.message.reply_text("Будь ласка, надішліть хоча б одне фото.")
        return PHOTOS
    await update.message.reply_text("Введіть район (наприклад, Приморський):")
    return DISTRICT

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    await update.message.reply_text("Введіть населений пункт (наприклад, Одеса):")
    return TOWN

async def get_town(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['town'] = update.message.text
    kb = [["Так", "Ні"]]
    await update.message.reply_text("Показувати посилання на ваш Telegram профіль?", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return SHARE_TG

async def get_share_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['share_tg'] = update.message.text
    context.user_data['username'] = update.effective_user.username or "немає"
    await update.message.reply_text("Введіть ваш контактний номер телефону:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    summary = generate_summary(context.user_data)
    context.user_data['summary'] = summary
    await update.message.reply_text(f"Подивіться, як буде виглядати пост:\n\n{summary}", parse_mode=ParseMode.HTML)
    kb = [["✅ Так, публікуємо"], ["❌ Ні, заново"]]
    await update.message.reply_text("Все правильно?", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return CONFIRM

async def final_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Так, публікуємо":
        ps = context.user_data.get('photos', [])
        cap = context.user_data['summary']
        try:
            if len(ps) == 1:
                sent_msg = await context.bot.send_photo(CHANNEL_ID, ps[0], caption=cap, parse_mode=ParseMode.HTML)
            else:
                msgs = await context.bot.send_media_group(CHANNEL_ID, [InputMediaPhoto(p, caption=cap if i==0 else "", parse_mode=ParseMode.HTML) for i,p in enumerate(ps[:10])])
                sent_msg = msgs[0]
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute('INSERT INTO ads (user_id, details, msg_id) VALUES (?, ?, ?)', (update.effective_user.id, cap, sent_msg.message_id))
            conn.commit(); conn.close()
            await update.message.reply_text("✅ Опубліковано!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True))
        except Exception as e:
            logging.error(f"Error in final_post: {e}")
            await update.message.reply_text("Помилка публікації. Перевірте, чи є бот адміном каналу.")
    else:
        await update.message.reply_text("Скасовано. Ви можете почати заново.", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"]], resize_keyboard=True))
    return ConversationHandler.END

# --- МОЇ ОГОЛОШЕННЯ ТА РЕДАКГУВАННЯ ---
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
            [InlineKeyboardButton("📝 Редагувати ціну", callback_data=f"editprice_{r[0]}")],
            [InlineKeyboardButton("🗑 Видалити", callback_data=f"del_{r[0]}_{r[2]}")]
        ]
        await update.message.reply_text(f"Ваше оголошення:\n\n{r[1]}", 
                                       parse_mode=ParseMode.HTML, 
                                       reply_markup=InlineKeyboardMarkup(kb))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    action = data[0]
    db_id = data[1]

    if action == "del":
        msg_id = data[2]
        try: await context.bot.delete_message(CHANNEL_ID, int(msg_id))
        except: pass
        conn = sqlite3.connect(DB_PATH); conn.execute('DELETE FROM ads WHERE id = ?', (db_id,))
        conn.commit(); conn.close()
        await query.edit_message_text("🗑 Оголошення видалено з каналу та бази.")

    elif action == "editprice":
        context.user_data['edit_db_id'] = db_id
        await query.message.reply_text("Введіть НОВУ ціну ($):")
        return EDIT_PRICE

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    db_id = context.user_data.get('edit_db_id')
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute('SELECT details, msg_id FROM ads WHERE id = ?', (db_id,))
    res = cursor.fetchone()
    
    if res:
        old_text = res[0]
        msg_id = res[1]
        try:
            # Логіка заміни ціни в тексті
            parts = old_text.split("Ціна: ")
            header = parts[0]
            after_price = parts[1].split("$</b>")[1]
            new_text = f"{header}Ціна: {new_price}$</b>{after_price}"
            
            cursor.execute('UPDATE ads SET details = ? WHERE id = ?', (new_text, db_id))
            conn.commit()
            
            # Оновлення в каналі
            try:
                await context.bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_id, caption=new_text, parse_mode=ParseMode.HTML)
            except:
                await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=msg_id, text=new_text, parse_mode=ParseMode.HTML)
            
            await update.message.reply_text("✅ Ціну успішно змінено всюди!", reply_markup=ReplyKeyboardMarkup([["➕ Нове оголошення"], ["🗂 Мої оголошення"]], resize_keyboard=True))
        except Exception as e:
            logging.error(f"Error updating price: {e}")
            await update.message.reply_text("Сталася помилка при оновленні. Спробуйте ще раз.")
    conn.close()
    return ConversationHandler.END

# --- ЗАПУСК ---
async def main():
    init_db()
    # Health Check для хостингів
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), BaseHTTPRequestHandler).serve_forever(), daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad),
            CallbackQueryHandler(handle_callbacks, pattern="^editprice_")
        ],
        states={
            MAKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_make)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            ENGINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_engine)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fuel)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gearbox)],
            DRIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_drive)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            PHOTOS: [MessageHandler(filters.PHOTO, get_photos), CommandHandler('done', done_photos)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_district)],
            TOWN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_town)],
            SHARE_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_share_tg)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CONFIRM: [MessageHandler(filters.Regex("^(✅ Так, публікуємо|❌ Ні, заново)$"), final_post)],
            EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price)],
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
            
