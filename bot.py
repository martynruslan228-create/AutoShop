import os, threading, asyncio, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Настройка логов, чтобы видеть КАЖДОЕ действие
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8076199435:AAEun5vwRl7f89vFZ1E5fJ5C1H4CDe7LLtw"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Получен /start от пользователя {update.effective_user.id}")
    await update.message.reply_text("🚀 СИСТЕМА ЗАПУЩЕНА! Если ты это видишь — всё работает!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Бот будет повторять любое твое слово
    logging.info(f"Получено сообщение: {update.message.text}")
    await update.message.reply_text(f"Ты написал: {update.message.text}")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.environ.get("PORT", 8080))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    # 1. Запуск веб-сервера для Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    # 2. Настройка бота
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # 3. Запуск
    print("--- БОТ ВКЛЮЧЕН ---")
    app.run_polling(drop_pending_updates=True)
 
