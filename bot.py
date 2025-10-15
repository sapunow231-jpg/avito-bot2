import os
import asyncio
import threading
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import Conflict

# === Загрузка переменных окружения ===
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "samara")
DEFAULT_QUERY = os.getenv("DEFAULT_QUERY", "iphone")
PORT = int(os.environ.get("PORT", 10000))  # Render назначает порт

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ TOKEN и CHAT_ID обязательны.")

sent_ads = set()
search_city = DEFAULT_CITY
search_query = DEFAULT_QUERY

# === Мини HTTP-сервер для Render Web Service ===
def run_webserver():
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f"[INFO] HTTP-сервер запущен на порту {PORT}")
    httpd.serve_forever()

threading.Thread(target=run_webserver, daemon=True).start()

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

# === Отправка новых объявлений ===
async def send_new_ads(app):
    global sent_ads
    ads = get_avito_ads()
    new_ads = [ad for ad in ads if ad["id"] not in sent_ads]

    for ad in new_ads:
        try:
            await app.bot.send_message(chat_id=CHAT_ID, text=ad["text"])
            sent_ads.add(ad["id"])
        except Exception as e:
            print(f"[Ошибка отправки] {e}")

    if new_ads:
        print(f"[INFO] Новых объявлений: {len(new_ads)}")
    else:
        print("[INFO] Нет новых объявлений.")

async def scheduled_task(app):
    while True:
        await send_new_ads(app)
        await asyncio.sleep(CHECK_INTERVAL * 60)

# === Команды Telegram ===
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

# === Safe polling ===
async def safe_polling(app):
    while True:
        try:
            print("✅ Запуск бота...")
            await app.run_polling()
        except Conflict:
            print("⚠️ Конфликт. Ждём 30 сек...")
            await asyncio.sleep(30)
        except Exception as e:
            print(f"❌ Ошибка: {e}. Перезапуск через 15 сек...")
            await asyncio.sleep(15)

# === Main ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("city", set_city))
    app.add_handler(CommandHandler("query", set_query))
    asyncio.create_task(scheduled_task(app))
    await safe_polling(app)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "close a running event loop" in str(e).lower():
            loop = asyncio.get_event_loop()
            loop.create_task(main())
            loop.run_forever()
        else:
            raise


