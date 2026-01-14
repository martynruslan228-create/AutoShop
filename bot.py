import os, asyncio, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Максимально детальні логи
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("--- ФУНКЦІЯ START ВИКЛИКАНА ---")
    await update.message.reply_text("Я ПРАЦЮЮ! Це повідомлення відправлене через новий метод.")

class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    # Запуск сервера для Railway
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    
    # Створення додатка
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    
    logger.info("=== ЗАПУСК БОТА В РЕЖИМІ FORCE POLLING ===")
    
    # Очищуємо всі старі оновлення
    await application.initialize()
    await application.bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    # Тримаємо працюючим
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
