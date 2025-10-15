import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен и URL Render
TOKEN = os.getenv("TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот запущен и работает через Render webhook!")

# Основная функция запуска
async def main():
    try:
        logger.info("🚀 Инициализация бота...")
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))

        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
        logger.info(f"📡 Устанавливаем webhook на {webhook_url}")

        # Удаляем старый webhook (на случай конфликтов)
        await app.bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)

        # Ставим новый webhook
        await app.bot.set_webhook(webhook_url)
        logger.info("✅ Webhook установлен успешно!")

        # Запуск сервера webhook
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=webhook_url
        )

    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске бота: {e}")
        await asyncio.sleep(5)
        # Повторный запуск при ошибке
        asyncio.create_task(main())

# Точка входа
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(main())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота вручную")
    except Exception as e:
        logger.exception(f"⚠️ Критическая ошибка: {e}")
