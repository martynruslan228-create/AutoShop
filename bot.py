import os, asyncio, logging, sqlite3, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = -1003568390240

# Состояния (добавлено MILEAGE)
(BRAND, MODEL, YEAR, MILEAGE, ENGINE, FUEL, GEARBOX, DESC, PRICE, 
 PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE, CHOOSE_CAR, WAIT_NEW_PRICE) = range(16)

def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, year TEXT, mileage TEXT, engine TEXT, fuel TEXT, 
                       gearbox TEXT, desc TEXT, price TEXT, district TEXT, city TEXT, 
                       phone TEXT, tg_link TEXT, photo_ids TEXT, full_text TEXT)''')
    conn.commit(); conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [["➕ Нове оголошення"], ["💰 Змінити ціну", "🗑 Видалити"]]
    await update.message.reply_text(
        f"👋 Вітаю! я ваш помічник на каналі Для воїх.\n\n",
        f"Я допоможу вам опублікувати ваше оголошення на канал  Оберіть потрібну дію на панелі нижче:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- ЛОГИКА ВЫБОРА ---
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = "edit" if "Змінити ціну" in update.message.text else "del"
    context.user_data['mode'] = mode
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()
    if not ads:
        await update.message.reply_text("❌ У вас ще немає активних оголошень.")
        return ConversationHandler.END
    car_buttons = [[f"ID:{ad[0]} | {ad[1]} {ad[2]} (${ad[3]})"] for ad in ads]
    car_buttons.append(["❌ Скасувати"])
    txt = "Оберіть авто для зміни ціни:" if mode == "edit" else "Оберіть авто для видалення:"
    await update.message.reply_text(txt, reply_markup=ReplyKeyboardMarkup(car_buttons, resize_keyboard=True))
    return CHOOSE_CAR

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "❌ Скасувати": return await start(update, context)
    try:
        ad_id = choice.split("|")[0].replace("ID:", "").strip()
        conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT id, msg_id, photo_ids FROM ads WHERE id = ?", (ad_id,))
        res = cursor.fetchone(); conn.close()
        if res:
            context.user_data['sel_id'], context.user_data['msg_id'], context.user_data['p_ids'] = res
            if context.user_data['mode'] == "del":
                try: await context.bot.delete_message(CHANNEL_ID, res[1])
                except: pass
                conn = sqlite3.connect("ads.db"); c = conn.cursor()
                c.execute("DELETE FROM ads WHERE id = ?", (ad_id,)); conn.commit(); conn.close()
                await update.message.reply_text("🗑 Оголошення видалено!")
                return await start(update, context)
            else:
                await update.message.reply_text(f"💰 Введіть НОВУ ЦІНУ ($):", reply_markup=ReplyKeyboardRemove())
                return WAIT_NEW_PRICE
    except: pass
    return await start(update, context)

async def update_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    ad_id, msg_id, photo_ids = context.user_data['sel_id'], context.user_data['msg_id'], context.user_data.get('p_ids', "")
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT brand, model, year, mileage, engine, fuel, gearbox, desc, district, city, phone, tg_link FROM ads WHERE id = ?", (ad_id,))
    r = cursor.fetchone()
    bot_link = f"https://t.me/{(await context.bot.get_me()).username}"
    new_text = (f"🚗 {r[0]} {r[1]} ({r[2]})\n\n🛣 Пробіг: {r[3]} тис. км\n🔹 Об'єм: {r[4]} л.\n⛽️ Паливо: {r[5]}\n⚙️ КПП: {r[6]}\n"
                f"📍 Район: {r[8]}, {r[9]}\n\n📝 Опис:\n{r[7]}\n\n💰 Ціна: {new_price}$\n\n📞 Тел: {r[10]}\n👤 Контакт: {r[11]}\n\n"
                f"➖➖➖➖➖➖➖➖➖➖\n📩 Щоб викласти своє оголошення, натисніть сюди 👉 {bot_link}")
    try:
        if photo_ids: await context.bot.edit_message_caption(CHANNEL_ID, msg_id, caption=new_text)
        else: await context.bot.edit_message_text(new_text, CHANNEL_ID, msg_id)
        cursor.execute("UPDATE ads SET price = ?, full_text = ? WHERE id = ?", (new_price, new_text, ad_id))
        conn.commit()
        await update.message.reply_text("✅ Ціну оновлено!")
    except: await update.message.reply_text("❌ Помилка оновлення.")
    conn.close()
    return await start(update, context)

# --- АНКЕТА ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1. Марка авто:", reply_markup=ReplyKeyboardRemove()); return BRAND
async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['brand'] = update.message.text; await update.message.reply_text("2. Модель:"); return MODEL
async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['model'] = update.message.text; await update.message.reply_text("3. Рік випуску:"); return YEAR
async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['year'] = update.message.text; await update.message.reply_text("4. Пробіг (тис. км):"); return MILEAGE
async def get_mileage(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['mileage'] = update.message.text; await update.message.reply_text("5. Об'єм двигуна (л):"); return ENGINE
async def get_engine(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['engine'] = update.message.text
    kb = [["Бензин", "Дизель"], ["Газ/Бензин", "Гібрид", "Електро"]]
    await update.message.reply_text("6. Паливо:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)); return FUEL
async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['fuel'] = update.message.text
    kb = [["Автомат", "Механіка"], ["Робот", "Варіатор"]]
    await update.message.reply_text("7. КПП:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)); return GEARBOX
async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['gearbox'] = update.message.text
    await update.message.reply_text("8. Опис авто:", reply_markup=ReplyKeyboardRemove()); return DESC
async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['desc'] = update.message.text; await update.message.reply_text("9. Ціна ($):"); return PRICE
async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text; context.user_data['photos'] = []
    await update.message.reply_text("10. Надішліть фото (МАКСИМУМ 10). Після завершення натисніть «✅ Готово»:", 
                                   reply_markup=ReplyKeyboardMarkup([["✅ Готово"], ["⏩ Пропустити"]], resize_keyboard=True))
