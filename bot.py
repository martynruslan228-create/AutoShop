import os, asyncio, logging, sqlite3, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = -1003568390240

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

# ------------------- START -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [["➕ Нове оголошення"], ["💰 Змінити ціну", "🗑 Видалити"]]
    text = (
        "👋 Вітаю! я ваш помічник на каналі **Для воїх**.\n\n"
        "Я допоможу вам опублікувати ваше оголошення на канал. Оберіть потрібну дію на панелі нижче.\n"
        "Щоб перейти на канал натисніть сюди 👉🏼https://t.me/+HjaDCqwnESo2MGNi"
    )
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="Markdown")
    return ConversationHandler.END

# ------------------- Health check -------------------
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

# ------------------- MAIN -------------------
async def main():
    # HTTP сервер для хостинга (если нужно)
    threading.Thread(
        target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), Health).serve_forever(), 
        daemon=True
    ).start()

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^➕ Нове оголошення$"), start),  # временно для проверки
            MessageHandler(filters.Regex("^(💰 Змінити ціну|🗑 Видалити)$"), start)
        ],
        states={},
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv)
    # Run polling
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
