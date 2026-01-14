import os, asyncio, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Максимально детальные логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logging.info(f"!!! ПРИШЕЛ СТАРТ ОТ CHAT_ID: {chat_id} !!!")
    
    try:
        # Попытка №1: Обычный ответ
        await update.message.reply_text("Проверка связи: Попытка 1")
        logging.info(">>> ПОПЫТКА 1 УСПЕШНА")
    except Exception as e:
        logging.error(f"!!! ОШИБКА ПОПЫТКИ 1: {e}")
        
        try:
            # Попытка №2: Прямая отправка через объект бота
            await context.bot.send_message(chat_id=chat_id, text="Проверка связи: Попытка 2 (прямая)")
            logging.info(">>> ПОПЫТКА 2 УСПЕШНА")
        except Exception as e2:
            logging.error(f"!!! КРИТИЧЕСКАЯ ОШИБКА: {e2}")

class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', port), Health).serve_forever(), daemon=True).start()
    
    # Настройка приложения с увеличенным временем ожидания
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    logging.info("=== БОТ ЗАПУЩЕН, ЖДУ НАЖАТИЯ СТАРТ ===")
    
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
