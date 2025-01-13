import requests
import mysql.connector
import os
import time
from dotenv import load_dotenv
from datetime import datetime

# Загружаем переменные окружения из файла .env
load_dotenv()

# Параметры подключения к базе данных
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

# API-ключ для CoinGecko (если требуется)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Параметры API
MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
VS_CURRENCY = "usd"
# Максимальное количество id за один запрос; обычно можно передать до 250, можно настроить по необходимости
BATCH_SIZE = 250


def get_all_coin_ids():
    """
    Извлекает список coin_id из таблицы coin_gesco_coins.
    Возвращает список строк.
    """
    coin_ids = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "SELECT id FROM coin_gesco_coins"
        cursor.execute(query)
        rows = cursor.fetchall()
        coin_ids = [row[0] for row in rows]
    except mysql.connector.Error as e:
        print(f"Ошибка при выборке coin_id: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return coin_ids


def batch_list(lst, batch_size):
    """Разбивает список lst на батчи по batch_size элементов."""
    for i in range(0, len(lst), batch_size):
        yield lst[i:i + batch_size]


def fetch_market_data_for_ids(ids_batch):
    """
    Выполняет запрос к API CoinGecko /coins/markets для батча идентификаторов.
    ids_batch – список идентификаторов монет.
    Возвращает список монет (JSON-объекты).
    """
    ids_str = ",".join(ids_batch)
    params = {
        "vs_currency": VS_CURRENCY,
        "ids": ids_str
    }
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": COINGECKO_API_KEY
    }
    try:
        response = requests.get(MARKETS_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к /coins/markets: {e}")
        return []


def parse_datetime(dt_str):
    """Пытается преобразовать ISO-8601 дату в объект datetime; возвращает None, если не удается."""
    try:
        return datetime.fromisoformat(dt_str.rstrip("Z"))
    except Exception:
        return None


def update_coin_in_db(coin):
    """
    Обновляет запись монеты в таблице coin_gesco_coins по её id.
    Обновляются следующие поля:
      - current_price_usd
      - market_cap_rank
      - market_cap_usd
      - total_volume_usd
      - high_24h_usd
      - low_24h_usd
      - price_change_24h_usd
      - price_change_percentage_24h
      - ath_usd
      - ath_change_percentage_usd
      - ath_date_usd
      - atl_usd
      - atl_change_percentage_usd
      - atl_date_usd
      - lastupdate (текущее время)
    """
    coin_id = coin.get("id")
    if not coin_id:
        return

    current_price = coin.get("current_price")
    market_cap_rank = coin.get("market_cap_rank")
    market_cap = coin.get("market_cap")
    total_volume = coin.get("total_volume")
    high_24h = coin.get("high_24h")
    low_24h = coin.get("low_24h")
    price_change_24h = coin.get("price_change_24h")
    price_change_percentage_24h = coin.get("price_change_percentage_24h")
    ath = coin.get("ath")
    ath_change_percentage = coin.get("ath_change_percentage")
    ath_date_str = coin.get("ath_date")
    atl = coin.get("atl")
    atl_change_percentage = coin.get("atl_change_percentage")
    atl_date_str = coin.get("atl_date")

    ath_date = parse_datetime(ath_date_str) if ath_date_str else None
    atl_date = parse_datetime(atl_date_str) if atl_date_str else None

    update_query = """
        UPDATE coin_gesco_coins SET
            current_price_usd = %s,
            market_cap_rank = %s,
            market_cap_usd = %s,
            total_volume_usd = %s,
            high_24h_usd = %s,
            low_24h_usd = %s,
            price_change_24h_usd = %s,
            price_change_percentage_24h = %s,
            ath_usd = %s,
            ath_change_percentage_usd = %s,
            ath_date_usd = %s,
            atl_usd = %s,
            atl_change_percentage_usd = %s,
            atl_date_usd = %s,
            lastupdate = NOW()
        WHERE id = %s
    """
    values = (
        current_price,
        market_cap_rank,
        market_cap,
        total_volume,
        high_24h,
        low_24h,
        price_change_24h,
        price_change_percentage_24h,
        ath,
        ath_change_percentage,
        ath_date,
        atl,
        atl_change_percentage,
        atl_date,
        coin_id
    )
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(update_query, values)
        conn.commit()
        print(f"Запись для монеты {coin_id} обновлена. (Передано: {len(ids_batch)}; Получено: {1})")
    except mysql.connector.Error as e:
        print(f"Ошибка обновления монеты {coin_id}: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def main():
    coin_ids = get_all_coin_ids()
    print(f"Найдено {len(coin_ids)} монет в таблице coin_gesco_coins.")

    updated_count = 0
    total_batches = 0
    # Разбиваем список на батчи по BATCH_SIZE
    for batch in batch_list(coin_ids, BATCH_SIZE):
        total_batches += 1
        print(f"\nОбработка батча {total_batches} (монет: {len(batch)})...")
        coins_data = fetch_market_data_for_ids(batch)
        print(f"Передано монет: {len(batch)}; Получено данных: {len(coins_data)}")
        if not coins_data:
            print("Нет данных для данного батча.")
            continue
        for coin in coins_data:
            update_coin_in_db(coin)
            updated_count += 1
        # Задержка в 2 секунды для соблюдения лимита 30 запросов в минуту
        time.sleep(2)

    print(f"\nОбновлено записей: {updated_count}")


if __name__ == "__main__":
    main()