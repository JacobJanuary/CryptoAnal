import os
import traceback
import requests
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time  # для замера времени скрипта

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем API-ключ CoinGecko
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

# Конфигурация подключения к базе данных
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

# Список дат, для которых нужно получить цену (формат dd-mm-yyyy)
specific_dates = {
    "02-02-2025": "02-02-2025",
    "03-02-2025": "03-02-2025",
    "04-02-2025": "04-02-2025",
    "04-08-2024": "04-08-2024",
    "05-08-2024": "05-08-2024",
    "06-08-2024": "06-08-2024",
    "07-12-2024": "07-12-2024"
}

# Глобальная переменная для подсчёта обращений к API
api_calls_count = 0


def create_history_365_table_full():
    """
    Создает таблицу coin_history_365, если она не существует.
    """
    additional_columns = ",\n".join([f"`{col}` DECIMAL(20,8) DEFAULT NULL" for col in specific_dates.keys()])
    create_query = f"""
    CREATE TABLE IF NOT EXISTS coin_history_365 (
        coin_id VARCHAR(255) PRIMARY KEY,
        `min365_usd` DECIMAL(20,8) DEFAULT NULL,
        `min365_date` DATE DEFAULT NULL,
        `max365_usd` DECIMAL(20,8) DEFAULT NULL,
        `max365_date` DATE DEFAULT NULL,
        {additional_columns}
    )
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(create_query)
        conn.commit()
        print("Таблица coin_history_365 создана (если не существовала).")
    except mysql.connector.Error as e:
        print(f"Ошибка создания таблицы coin_history_365: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def fetch_365_data(coin_id):
    """
    Запрашивает исторические данные цены за 365 дней для монеты coin_id.
    Возвращает (min_price, min_date, max_price, max_date) или (None, None, None, None).
    """
    global api_calls_count
    url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    headers = {
        "accept": "application/json",
        "x-cg-pro-api-key": COINGECKO_API_KEY
    }
    params = {
        "vs_currency": "usd",
        "days": "365"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        api_calls_count += 1  # увеличиваем счётчик API
        response.raise_for_status()
        data = response.json()
        prices = data.get("prices", [])
        if not prices:
            print(f"Для монеты {coin_id} отсутствуют данные в 'prices'.")
            return None, None, None, None

        min_price = float('inf')
        max_price = float('-inf')
        min_ts = None
        max_ts = None
        for point in prices:
            ts, price = point[0], point[1]
            if price < min_price:
                min_price = price
                min_ts = ts
            if price > max_price:
                max_price = price
                max_ts = ts

        if min_ts is None or max_ts is None:
            return None, None, None, None

        min_date = datetime.fromtimestamp(min_ts / 1000).strftime("%Y-%m-%d")
        max_date = datetime.fromtimestamp(max_ts / 1000).strftime("%Y-%m-%d")
        return min_price, min_date, max_price, max_date

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе 365-дневных данных для монеты {coin_id}: {e}")
        return None, None, None, None


def fetch_history_price(coin_id, date_str):
    """
    Запрашивает историческую цену монеты coin_id на дату date_str (dd-mm-yyyy).
    Возвращает цену в USD или None, если данные отсутствуют.
    """
    global api_calls_count
    url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_id}/history"
    headers = {
        "accept": "application/json",
        "x-cg-pro-api-key": COINGECKO_API_KEY
    }
    params = {
        "date": date_str,
        "localization": "false"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        api_calls_count += 1  # увеличиваем счётчик API
        response.raise_for_status()
        data = response.json()
        market_data = data.get("market_data")
        if market_data:
            return market_data.get("current_price", {}).get("usd")
        else:
            print(f"Нет market_data для монеты {coin_id} на дату {date_str}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе исторических данных для монеты {coin_id} на дату {date_str}: {e}")
        return None


def get_made_in_usa_coin_ids():
    """
    Возвращает список coin_id из таблицы coin_category_relation,
    где category_id='made-in-usa'.
    """
    coin_ids = []
    query = "SELECT coin_id FROM coin_category_relation WHERE category_id='made-in-usa'"
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        coin_ids = [row[0] for row in rows]
    except mysql.connector.Error as e:
        print(f"Ошибка при выборке монет категории 'made-in-usa': {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return coin_ids


def update_365_full_for_coin(coin_id):
    """
    Для монеты coin_id:
      - Получаем min/max за 365 дней (fetch_365_data).
      - Для каждой даты из specific_dates запрашиваем цену (fetch_history_price).
      - Выполняем upsert (INSERT ... ON DUPLICATE KEY UPDATE) в coin_history_365.
    """
    print(f"[coin_id={coin_id}] Обработка 365-дневных данных...")
    min_price, min_date, max_price, max_date = fetch_365_data(coin_id)
    if min_price is None or max_price is None:
        print(f"[coin_id={coin_id}] Нет данных 365 дней. Пропускаем.")
        return

    # Получаем цену на каждую дату
    date_prices = {}
    for col, date_str in specific_dates.items():
        price = fetch_history_price(coin_id, date_str)
        date_prices[col] = price
        print(f"[coin_id={coin_id}] Дата {date_str} => цена {price}")

    # Списки столбцов и значений
    base_columns = ["min365_usd", "min365_date", "max365_usd", "max365_date"]
    base_values = [min_price, min_date, max_price, max_date]
    additional_columns = list(specific_dates.keys())
    additional_values = [date_prices[col] for col in additional_columns]

    columns = base_columns + additional_columns
    values = base_values + additional_values

    # SQL upsert
    cols_formatted = ", ".join([f"`{col}`" for col in columns])
    placeholders = ", ".join(["%s"] * (1 + len(columns)))  # 1 для coin_id
    update_clause = ", ".join([f"`{col}`=VALUES(`{col}`)" for col in columns])
    query = f"""
        INSERT INTO coin_history_365 (coin_id, {cols_formatted})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """
    params = [coin_id] + values

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()
        print(f"[coin_id={coin_id}] Обновили coin_history_365: min {min_price} ({min_date}), max {max_price} ({max_date})")
    except mysql.connector.Error as e:
        print(f"[coin_id={coin_id}] Ошибка обновления данных 365: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def process_made_in_usa_coins():
    """
    Для каждой монеты из категории 'made-in-usa' обновляем/вставляем (upsert) данные 365.
    """
    create_history_365_table_full()
    coin_ids = get_made_in_usa_coin_ids()
    print(f"Найдено {len(coin_ids)} монет категории 'made-in-usa' для обновления (365 дней).")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(update_365_full_for_coin, cid): cid for cid in coin_ids}
        for future in as_completed(futures):
            coin_id = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[coin_id={coin_id}] Ошибка в процессе обновления: {e}")


def main():
    start_time = time.time()

    process_made_in_usa_coins()

    end_time = time.time()
    elapsed = end_time - start_time
    print("\nСкрипт завершён.")
    print(f"Всего обращений к API: {api_calls_count}")
    print(f"Время выполнения скрипта: {elapsed:.2f} секунд.")


if __name__ == "__main__":
    main()