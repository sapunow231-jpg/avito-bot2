import os
from dotenv import load_dotenv
import feedparser
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio

load_dotenv()  # Загружает .env

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = 5  # интервал проверки в минутах
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "samara")
DEFAULT_QUERY = os.getenv("DEFAULT_QUERY", "iphone")

if not TOKEN or not CHAT_ID:
    raise ValueError("TOKEN и CHAT_ID должны быть установлены через .env или Environment Variables")

sent_ads = set()
search_city = DEFAULT_CITY
search_query = DEFAULT_QUERY

# --- RSS парсинг ---
def build_rss_url(city: str, query: str) -> str:
    query_encoded = "+".join(query.strip().split())
    return f"https://www.avito.ru/{city}/telefony/{query_encoded}/rss"

def get_avito_ads() -> list:
    url = build_rss_url(search_city, search_query)
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"Ошибка при запросе RSS: {e}")
        return []

    ads = []
    for entry in feed.entries:
        ad_id = entry.link.split("/")[-1]
        text = f"{entry.title}\n{entry.link}"
        ads.append({"id": ad_id, "text": text})
    return ads

# --- Отправка новых объявлений ---
async def send_new_ads(application):
    global sent_ads
    ads = get_avito_ads()
    new_count = 0
    for ad in ads:
        if ad["id"] not in sent_ads:
            try:
                await application.bot.send_message(chat_id=CHAT_ID, text=ad["text"])
                sent_ads.add(ad["id"])
                new_count += 1
            except Exception as e:
                print(f"Ошибка при отправке: {e}")
    print(f"Отправлено новых объявлений: {new_count}")

# --- Хэндлеры команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Бот запущен! Проверка каждые {CHECK_INTERVAL} минуты(ы).\n"
        "Используйте команды:\n"
        "/city <город> — изменить город\n"
        "/query <запрос> — изменить поисковый запрос"
    )

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global search_city, sent_ads
    if context.args:
        search_city = context.args[0].lower()
        sent_ads.clear()
        await update.message.reply_text(f"Город поиска изменен на: {search_city}")
    else:
        await update.message.reply_text("Укажите город после команды. Пример: /city kazan")

async def set_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global search_query, sent_ads
    if context.args:
        search_query = " ".join(context.args).lower()
        sent_ads.clear()
        await update.message.reply_text(f"Поисковый запрос изменен на: {search_query}")
    else:
        await update.message.reply_text("Укажите запрос после команды. Пример: /query ноутбук")

# --- Основная функция ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("city", set_city))
    app.add_handler(CommandHandler("query", set_query))

    # Фоновая проверка новых объявлений после старта
    async def on_startup(application):
        async def periodic_check():
            while True:
                await send_new_ads(application)
                await asyncio.sleep(CHECK_INTERVAL * 60)
        application.create_task(periodic_check())

    app.post_init(on_startup)

    print("Бот запущен и готов к работе!")
    app.run_polling()  # безопасно запускает цикл событий

if __name__ == "__main__":
    main()
