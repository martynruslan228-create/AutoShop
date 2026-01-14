async def main():
    init_db()
    # Заглушка для порта Render
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), Health).serve_forever(), daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # ... (ваши хэндлеры тут остаются без изменений) ...

    await app.initialize()
    
    # КРИТИЧЕСКАЯ СТРОЧКА: она говорит Telegram "забудь про все старые процессы и вебхуки"
    await app.bot.delete_webhook(drop_pending_updates=True)
    
    logging.info("Бот успешно запущен и очистил очередь обновлений.")
    
    # Запуск через Updater, а не polling напрямую, для стабильности на Render
    await app.updater.start_polling(drop_pending_updates=True) 
    
    await asyncio.Event().wait()
