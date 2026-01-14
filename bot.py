import os, asyncio, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Детальне логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logging.info(f"✅ ОТРИМАНО СТАРТ ВІД: {user_id}")
    
    try:
        # Відправляємо текст без жодного оформлення для тесту
        await update.message.reply_text("Я ПРАЦЮЮ! Зв'язок встановлено успішно.")
        logging.info(f"🚀 ВІДПОВІДЬ ВІДПРАВЛЕНА КОРИСТУВАЧУ {user_id}")
    except Exception as e:
        logging.error(f"❌ ПОМИЛКА ВІДПРАВКИ: {str(e)}")

class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

async def main():
    # Налаштування порту для Railway
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    
    # Створення додатка з розширеними налаштуваннями мережі
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    
    logging.info("=== БОТ ЗАПУСКАЄТЬСЯ (DEBUG MODE) ===")
    
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling()
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
