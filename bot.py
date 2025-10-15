import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio

load_dotenv()  # Загружает .env

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "samara")
DEFAULT_QUERY = os.getenv("DEFAULT_QUERY", "iphone")

if not TOKEN or not CHAT_ID:
    raise ValueError("TOKEN и CHAT_ID должны быть установлены через .env или Environment Variables")

sent_ads = set()
search_city = DEFAULT_CITY
search_query = DEFAULT_QUERY

def build_search_url(city: str, query: str) -> str:
    query_encoded = "+".join(query.strip().split())
    return f"https://www.avito.ru/{city}/telefony?p=1&q={query_encoded}"

def get_avito_ads() -> list:
    url = build_search_url(search_city, search_query)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка при запросе: {e}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    ads = []
    for item in soup.select("div[data-marker='item']"):
        title_tag = item.select_one("h3")
        price_tag = item.select_one("span[data-marker='item-price']")
        link_tag = item.select_one("a[href]")
        if not title_tag or not price_tag or not link_tag:
            continue
        title = title_tag.text.strip()
        price = price_tag.text.strip()
        link = "https://www.avito.ru" + link_tag["href"]
        ad_id = link.split("/")[-1]
        ads.append({"id": ad_id, "text": f"{title}\n{price}\n{link}"})
    return ads

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

# --- Основная часть ---
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("city", set_city))
    app.add_handler(CommandHandler("query", set_query))

    # Фоновая проверка новых объявлений
    async def periodic_check():
        while True:
            await send_new_ads(app)
            await asyncio.sleep(CHECK_INTERVAL * 60)

    # Запуск фоновой задачи
    app.create_task(periodic_check())

    print("Бот запущен и готов к работе!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
