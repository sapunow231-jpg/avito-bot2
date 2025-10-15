import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Настройки логов ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Переменные окружения ---
TOKEN = os.getenv("TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот запущен и работает через Render webhook!")

# --- Основная функция бота ---
async def main():
    try:
        logger.info("🚀 Инициализация Telegram бота...")
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))

        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
        logger.info(f"📡 Настраиваем webhook: {webhook_url}")

        # Удаляем старый webhook и сбрасываем старые обновления
        await app.bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)

        # Ставим новый webhook
        await app.bot.set_webhook(webhook_url)
        logger.info("✅ Webhook успешно установлен!")

        # Запуск webhook-сервера Telegram
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=webhook_url,
        )

    except Exception as e:
        logger.exception(f"❌ Ошибка при запуске бота: {e}")
        await asyncio.sleep(5)
        asyncio.create_task(main())

# --- Мини веб-сервер для Render ---
async def ping_server():
    async def handle(request):
        return web.Response(text="✅ Bot is alive!", content_type="text/plain")

    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Порт {PORT} открыт для Render")

# --- Точка входа ---
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(ping_server())  # Открываем порт
        loop.create_task(main())         # Запускаем Telegram бота
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота вручную")
    except Exception as e:
        logger.exception(f"⚠️ Критическая ошибка: {e}")
