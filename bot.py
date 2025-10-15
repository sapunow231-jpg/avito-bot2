import os
import asyncio
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === Загрузка переменных окружения ===
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "samara")
DEFAULT_QUERY = os.getenv("DEFAULT_QUERY", "iphone")
PORT = int(os.environ.get("PORT", 10000))
DOMAIN = os.environ.get("RENDER_EXTERNAL_URL")  # Live URL от Render

if not TOKEN or not DOMAIN:
    raise ValueError("❌ Обязательно задать TOKEN и RENDER_EXTERNAL_URL")

sent_ads = set()
search_city = DEFAULT_CITY
search_query = DEFAULT_QUERY
WEBHOOK_PATH = "webhook"

# === Парсер Avito ===
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
        print(f"[Ошибка запроса] {e}")
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

# === Telegram команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 Бот запущен!\nПроверка каждые {CHECK_INTERVAL} мин.\n"
        f"Команды:\n/city <город>\n/query <запрос>"
    )

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global search_city, sent_ads
    if context.args:
        search_city = context.args[0].lower()
        sent_ads.clear()
        await update.message.reply_text(f"🏙 Город: {search_city}")
    else:
        await update.message.reply_text("❗ Пример: /city kazan")

async def set_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global search_query, sent_ads
    if context.args:
        search_query = " ".join(context.args).lower()
        sent_ads.clear()
        await update.message.reply_text(f"🔍 Запрос: {search_query}")
    else:
        await update.message.reply_text("❗ Пример: /query ноутбук")

# === Отправка новых объявлений ===
async def send_new_ads(app):
    global sent_ads
    ads = get_avito_ads()
    new_ads = [ad for ad in ads if ad["id"] not in sent_ads]
    for ad in new_ads:
        try:
            await app.bot.send_message(chat_id=app.bot.id, text=ad["text"])
            sent_ads.add(ad["id"])
        except Exception as e:
            print(f"[Ошибка отправки] {e}")
    if new_ads:
        print(f"[INFO] Новых объявлений: {len(new_ads)}")
    else:
        print("[INFO] Новых объявлений нет.")

async def scheduled_task(app):
    while True:
        await send_new_ads(app)
        await asyncio.sleep(CHECK_INTERVAL * 60)

# === Main ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("city", set_city))
    app.add_handler(CommandHandler("query", set_query))

    # Фоновая проверка объявлений
    asyncio.create_task(scheduled_task(app))

    # Настройка webhook
    webhook_url = f"https://{DOMAIN}/{WEBHOOK_PATH}"
    print(f"[INFO] Настраиваем webhook: {webhook_url}")
    await app.bot.set_webhook(url=webhook_url)

    # Запуск webhook сервера
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    asyncio.run(main())


