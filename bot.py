import os, asyncio, logging, sqlite3, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

# Состояния
(BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DESC, PRICE, 
 PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE, CHOOSE_CAR, WAIT_NEW_PRICE) = range(15)

def init_db():
    conn = sqlite3.connect("ads.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, year TEXT, engine TEXT, fuel TEXT, 
                       gearbox TEXT, desc TEXT, price TEXT, district TEXT, city TEXT, 
                       phone TEXT, tg_link TEXT, photo_ids TEXT, full_text TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- ПРИВЕТСТВИЕ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [["➕ Нове оголошення"], ["💰 Змінити ціну", "🗑 Видалити"]]
    await update.message.reply_text(
        "👋 Вітаємо! Ви знаходитесь у головному меню бота **Auto Shop Odessa**.\n\n"
        "🚀 Я допоможу вам швидко та правильно опублікувати ваше оголошення на нашому каналі.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- ВЫБОР И ИЗМЕНЕНИЕ ---
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = "edit" if "Змінити ціну" in update.message.text else "del"
    context.user_data['mode'] = mode
    conn = sqlite3.connect("ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()
    if not ads:
        await update.message.reply_text("❌ У вас ще немає оголошень.")
        return ConversationHandler.END
    car_buttons = [[f"ID:{ad[0]} | {ad[1]} {ad[2]} (${ad[3]})"] for ad in ads]
    car_buttons.append(["❌ Скасувати"])
    await update.message.reply_text("🔍 Оберіть авто зі списку:", reply_markup=ReplyKeyboardMarkup(car_buttons, resize_keyboard=True))
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
                await update.message.reply_text("🗑 Видалено!")
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
    cursor.execute("SELECT brand, model, year, engine, fuel, gearbox, desc, district, city, phone, tg_link FROM ads WHERE id = ?", (ad_id,))
    r = cursor.fetchone()
    new_text = (f"🚗 {r[0]} {r[1]} ({r[2]})\n\n🔹 Об'єм: {r[3]} л.\n⛽️ Паливо: {r[4]}\n⚙️ КПП: {r[5]}\n"
                f"📍 Район: {r[7]}, {r[8]}\n\n📝 Опис:\n{r[6]}\n\n💰 Ціна: {new_price}$\n\n📞 Тел: {r[9]}\n👤 Контакт: {r[10]}")
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
async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['year'] = update.message.text; await update.message.reply_text("4. Об'єм двигуна (л):"); return ENGINE
async def get_engine(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['engine'] = update.message.text
    kb = [["Бензин", "Дизель"], ["Газ/Бензин", "Гібрид", "Електро"]]
    await update.message.reply_text("5. Паливо:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)); return FUEL
async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['fuel'] = update.message.text
    kb = [["Автомат", "Механіка"], ["Робот", "Варіатор"]]
    await update.message.reply_text("6. КПП:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)); return GEARBOX
async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['gearbox'] = update.message.text
    await update.message.reply_text("7. Опис авто:", reply_markup=ReplyKeyboardRemove()); return DESC
async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['desc'] = update.message.text; await update.message.reply_text("8. Ціна ($):"); return PRICE
async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text; context.user_data['photos'] = []
    await update.message.reply_text("9. Фото (Максимум 10). Надішліть фото та натисніть «✅ Готово»:", 
                                   reply_markup=ReplyKeyboardMarkup([["✅ Готово"], ["⏩ Пропустити"]], resize_keyboard=True))
    return PHOTO
async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["✅ Готово", "⏩ Пропустити"]:
        districts = [["Березівський", "Білгород-Дністровський"], ["Болградський", "Ізмаїльський"], 
                     ["Одеський", "Подільський"], ["Роздільнянський"]]
        await update.message.reply_text("10. Район:", reply_markup=ReplyKeyboardMarkup(districts, resize_keyboard=True)); return DISTRICT
    if update.message.photo:
        if len(context.user_data['photos']) < 10:
            context.user_data['photos'].append(update.message.photo[-1].file_id)
        else:
            await update.message.reply_text("⚠️ Ліміт 10 фото вичерпано. Натисніть «✅ Готово»")
    return PHOTO
async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['district'] = update.message.text
    await update.message.reply_text("11. Місто:", reply_markup=ReplyKeyboardRemove()); return CITY # Удаляем клавиатуру районов
async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['city'] = update.message.text
    await update.message.reply_text("12. Показати ваш ТГ?", reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True)); return TG_CONTACT
async def get_tg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; context.user_data['tg_link'] = f"@{u.username}" if update.message.text == "✅ Так" and u.username else "Приватна особа"
    await update.message.reply_text("13. Номер телефону:", reply_markup=ReplyKeyboardRemove()); return PHONE

async def finish_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data; phone = update.message.text
    caption = (f"🚗 {ud['brand']} {ud['model']} ({ud['year']})\n\n🔹 Об'єм: {ud['engine']} л.\n⛽️ Паливо: {ud['fuel']}\n"
               f"⚙️ КПП: {ud['gearbox']}\n📍 Район: {ud['district']}, {ud['city']}\n\n"
               f"📝 Опис:\n{ud['desc']}\n\n💰 Ціна: {ud['price']}$\n\n📞 Тел: {phone}\n👤 Контакт: {ud['tg_link']}")
    try:
        photos = ud.get('photos', [])
        if photos:
            msgs = await context.bot.send_media_group(CHANNEL_ID, media=[InputMediaPhoto(p, caption=caption if i==0 else "") for i, p in enumerate(photos[:10])])
            msg_id = msgs[0].message_id
        else:
            msg = await context.bot.send_message(CHANNEL_ID, caption); msg_id = msg.message_id
        conn = sqlite3.connect("ads.db"); c = conn.cursor()
        c.execute("""INSERT INTO ads (user_id, msg_id, brand, model, year, engine, fuel, gearbox, desc, price, district, city, phone, tg_link, photo_ids, full_text) 
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (update.effective_user.id, msg_id, ud['brand'], ud['model'], ud['year'], ud['engine'], ud['fuel'], ud['gearbox'], ud['desc'], ud['price'], ud['district'], ud['city'], phone, ud['tg_link'], ",".join(photos), caption))
        conn.commit(); conn.close()
        await update.message.reply_text("✅ Опубліковано успішно!")
    except Exception as e: await update.message.reply_text(f"Помилка: {e}")
    return await start(update, context)

# --- ЗАПУСК ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), Health).serve_forever(), daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad), MessageHandler(filters.Regex("^(💰 Змінити ціну|🗑 Видалити)$"), show_list)],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            ENGINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_engine)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fuel)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gearbox)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, get_photo)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_district)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            TG_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tg_contact)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_ad)],
            CHOOSE_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice)],
            WAIT_NEW_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_price)]
        },
        fallbacks=[CommandHandler("start", start)], allow_reentry=True
    )
    app.add_handler(conv); app.add_handler(CommandHandler("start", start))
    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling(); await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
