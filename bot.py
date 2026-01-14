import os, asyncio, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Логування, щоб ми бачили все в Railway
logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGNFYLPXaKUuzb5Y3Or51Udv-vZFmkwoOk"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Отримано команду /start")
    await update.message.reply_text("Привіт! Я працюю! Якщо ти бачиш це повідомлення, значить зв'язок встановлено.")

# Міні-сервер для Railway, щоб він не вимикав бота
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

async def main():
    # Запуск сервера перевірки працездатності в окремому потоці
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    
    # Налаштування бота
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    logging.info("Бот запускається...")
    
    # Очищаємо чергу і запускаємо опитування
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling()
    
    # Тримаємо програму запущеною
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
