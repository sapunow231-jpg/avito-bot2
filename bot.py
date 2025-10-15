import os
import asyncio
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === Загружаем переменные окружения ===
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "samara")
DEFAULT_QUERY = os.getenv("DEFAULT_QUERY", "iphone")

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Ошибка: переменные TOKEN и CHAT_ID должны быть заданы в .env или через Render Environment.")

sent_ads = set()
search_city = DEFAULT_CITY
search_query = DEFAULT_QUERY


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
        print(f"[INFO] Отправлено новых объявлений: {len(new_ads)}")
    else:
        print("[INFO] Новых объявлений нет.")


async def scheduled_task(app):
    while True:
        await send_new_ads(app)
        await asyncio.sleep(CHECK_INTERVAL * 60)


# === Команды Telegram ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 Бот запущен!\n"
        f"Проверка каждые {CHECK_INTERVAL} мин.\n\n"
        f"Команды:\n"
        f"/city <город> — сменить город\n"
        f"/query <запрос> — сменить поисковый запрос"
    )


async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global search_city, sent_ads
    if context.args:
        search_city = context.args[0].lower()
        sent_ads.clear()
        await update.message.reply_text(f"🏙 Город изменён на: {search_city}")
    else:
        await update.message.reply_text("❗ Пример: /city kazan")


async def set_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global search_query, sent_ads
    if context.args:
        search_query = " ".join(context.args).lower()
        sent_ads.clear()
        await update.message.reply_text(f"🔍 Поисковый запрос изменён на: {search_query}")
    else:
        await update.message.reply_text("❗ Пример: /query ноутбук")


# === Основная логика ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("city", set_city))
    app.add_handler(CommandHandler("query", set_query))

    asyncio.create_task(scheduled_task(app))
    print("✅ Бот запущен и работает.")
    await app.run_polling()


# === Безопасный запуск (Render, Python 3.12, Jupyter) ===
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        if loop.is_running():
            print("[INFO] Цикл уже запущен — создаём задачу вручную.")
            loop.create_task(main())
            loop.run_forever()
        else:
            print("[INFO] Запускаем новый event loop.")
            loop.run_until_complete(main())
    except RuntimeError as e:
        if "running event loop" in str(e).lower():
            print("[INFO] Активный цикл обнаружен — создаём задачу.")
            loop.create_task(main())
            loop.run_forever()
        else:
            raise
