import os
import requests
import mysql.connector
from dotenv import load_dotenv

# Загрузим переменные окружения из .env (если используется)
load_dotenv()

# --- Конфигурация Telegram (опционально, если нужно отправлять уведомления) ---
BOT_TOKEN = os.getenv("MY_TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("MY_TELEGRAM_CHAT_ID", "")  # строка или int

def send_telegram_message(text: str):
    """Отправляет сообщение 'text' в указанный Telegram-чат, используя BOT_TOKEN."""
    if not BOT_TOKEN or not CHAT_ID:
        print("[WARN] Не задан токен бота или chat_id — пропускаем отправку.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": text}

    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        print(f"[INFO] Сообщение отправлено в Telegram: {text}")
    except Exception as e:
        print(f"[ERROR] Не удалось отправить сообщение в Telegram: {e}")


# --- Конфигурация БД ---
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "crypto_db")

def get_connection():
    """Возвращает соединение с MySQL."""
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB
    )

# --- Параметры запроса к CoinGecko ---
COINGECKO_URL = (
    "https://pro-api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd"
    "&category=made-in-usa"        # категория монет made-in-usa
    "&order=market_cap_desc"
    "&per_page=250"               # до 250 монет
    "&sparkline=false"
    "&price_change_percentage=1h"
)

# Если у вас CoinGecko Pro, и требуется API-ключ, прочитайте его из .env:
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
HEADERS = {}
if COINGECKO_API_KEY:
    HEADERS = {"X-Cg-Pro-Api-Key": COINGECKO_API_KEY}

# --- Порог изменения цены и объёма (в %). Можно настроить в коде или через .env ---
PRICE_THRESHOLD_PERCENT = 3.0     # Если цена меняется на 3% или больше
VOLUME_THRESHOLD_PERCENT = 10.0   # Если объём меняется на 10% или больше

def main():
    # 1) Получаем данные от CoinGecko
    try:
        response = requests.get(COINGECKO_URL, headers=HEADERS)
        response.raise_for_status()
        coins_data = response.json()  # список словарей
    except Exception as e:
        print(f"[ERROR] Не удалось получить данные от CoinGecko: {e}")
        return

    # 2) Подключаемся к БД
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Подготовленные запросы для чтения/обновления
    select_sql = """
        SELECT id, name, symbol, current_price_usd, total_volume_usd
        FROM coin_gesco_coins
        WHERE id = %s
        LIMIT 1
    """
    update_sql = """
        UPDATE coin_gesco_coins
           SET current_price_usd = %s,
               total_volume_usd = %s
         WHERE id = %s
    """

    # Если нужно добавлять новые монеты, можно использовать INSERT:
    insert_sql = """
        INSERT INTO coin_gesco_coins (id, name, symbol, current_price_usd, total_volume_usd)
        VALUES (%s, %s, %s, %s, %s)
    """

    # 3) Обрабатываем каждую монету из API (до 250 штук)
    for coin in coins_data:
        # Пример структуры coin: {
        #   "id": "bitcoin",
        #   "symbol": "btc",
        #   "name": "Bitcoin",
        #   "current_price": 23123.12,
        #   "total_volume": 123456789, ...
        # }

        coingecko_id = coin.get("id")  # Совпадает с тем, что храните в coin_gesco_coins.id
        coin_name = coin.get("name")
        coin_symbol = coin.get("symbol")
        new_price = coin.get("current_price")
        new_volume = coin.get("total_volume")

        # Пропускаем, если нет критичных полей
        if not coingecko_id or new_price is None or new_volume is None:
            continue

        # 3.1) Ищем запись в coin_gesco_coins по PRIMARY KEY = coingecko_id
        cursor.execute(select_sql, (coingecko_id,))
        row = cursor.fetchone()

        if row is None:
            # Нет записи — возможно, хотим создать новую.
            # Если нужно — делаем INSERT.
            try:
                cursor.execute(insert_sql, (coingecko_id, coin_name, coin_symbol, new_price, new_volume))
                print(f"[INFO] Добавлена новая монета: {coin_name} ({coin_symbol}), id={coingecko_id}")
                # Если требуется какое-то уведомление:
                # send_telegram_message(f"Добавлена новая монета {coin_name} ({coin_symbol}) в таблицу.")
            except Exception as ex:
                print(f"[ERROR] Не удалось вставить новую запись для {coingecko_id}: {ex}")
            continue

        # 4) Если запись уже есть, проверяем изменение цены и объёма
        old_price = row["current_price_usd"] or 0
        old_volume = row["total_volume_usd"] or 0

        price_diff_percent = 0.0
        volume_diff_percent = 0.0

        if old_price > 0:
            price_diff_percent = (new_price - old_price) / old_price * 100
        if old_volume > 0:
            volume_diff_percent = (new_volume - old_volume) / old_volume * 100

        # 4.1) Проверка изменения цены, сравниваем с PRICE_THRESHOLD_PERCENT
        if abs(price_diff_percent) >= PRICE_THRESHOLD_PERCENT:
            if price_diff_percent > 0:
                # Рост
                msg = (
                    f"🚀 {coin_name} ({coin_symbol}) цена выросла на "
                    f"{price_diff_percent:.2f}%. Текущая цена ${new_price:.2f}"
                )
            else:
                # Падение
                msg = (
                    f"🔻 {coin_name} ({coin_symbol}) цена упала на "
                    f"{abs(price_diff_percent):.2f}%. Текущая цена ${new_price:.2f}"
                )
            send_telegram_message(msg)

        # 4.2) Проверка изменения объёма, сравниваем с VOLUME_THRESHOLD_PERCENT
        if abs(volume_diff_percent) >= VOLUME_THRESHOLD_PERCENT:
            if volume_diff_percent > 0:
                msg = (
                    f"{coin_name} ({coin_symbol}) объём вырос на "
                    f"{volume_diff_percent:.2f}%. (Объём: {new_volume})"
                )
            else:
                msg = (
                    f"{coin_name} ({coin_symbol}) объём упал на "
                    f"{abs(volume_diff_percent):.2f}%. (Объём: {new_volume})"
                )
            send_telegram_message(msg)

        # 5) Обновляем данные в БД
        try:
            cursor.execute(update_sql, (new_price, new_volume, coingecko_id))
        except Exception as ex:
            print(f"[ERROR] Не удалось обновить запись {coingecko_id}: {ex}")

    # 6) Сохраняем изменения и закрываем соединение
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()