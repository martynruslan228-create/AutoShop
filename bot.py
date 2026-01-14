import os, asyncio, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Налаштування логування для Railway
logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGNFYLPXaKUuzb5Y3Or51Udv-vZFmkwoOk"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("!!! КОМАНДА СТАРТ ОТРИМАНА !!!")
    await update.message.reply_text("Бот працює! Я бачу твою команду.")

# Міні-сервер для підтримки життя на Railway
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

async def main():
    # Запуск сервера перевірки
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    
    # Ініціалізація бота
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    logging.info("--- БОТ ЗАПУСКАЄТЬСЯ ---")
    
    # Очищуємо всі старі запити (це прибере завислі повідомлення)
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling(drop_pending_updates=True)
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
