import os
import traceback
import requests
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def create_history_365_table_full():
    """
    Создает таблицу coin_history_365, если она не существует.
    Таблица содержит:
      - coin_id VARCHAR(255) PRIMARY KEY,
      - min365_usd DECIMAL(20,8) DEFAULT NULL,
      - min365_date DATE DEFAULT NULL,
      - max365_usd DECIMAL(20,8) DEFAULT NULL,
      - max365_date DATE DEFAULT NULL,
      - дополнительные столбцы для каждой даты из specific_dates.
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
    Запрашивает исторические данные цены для монеты coin_id за 365 дней через API CoinGecko.
    Использует endpoint /coins/{coin_id}/market_chart с параметром days=365.
    Возвращает кортеж: (min_price, min_date, max_price, max_date).
    Если данные отсутствуют – возвращает (None, None, None, None).
    """
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
    Запрашивает историческую цену для монеты coin_id на дату date_str (формат dd-mm-yyyy)
    через endpoint /coins/{coin_id}/history.
    Возвращает цену в USD или None, если данные отсутствуют.
    """
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
    для которых category_id = 'made-in-usa'.
    """
    coin_ids = []
    query = "SELECT coin_id FROM coin_category_relation WHERE category_id = 'made-in-usa'"
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
      - Получает данные по 365-дневному графику (минимальная и максимальная цена с датами).
      - Для каждой заданной даты из specific_dates запрашивает цену через API CoinGecko.
      - Выполняет upsert в таблицу coin_history_365, обновляя/вставляя:
            min365_usd, min365_date, max365_usd, max365_date,
            а также цену для каждой даты из specific_dates.
    """
    print(f"Обработка 365-дневных данных для монеты {coin_id}...")
    min_price, min_date, max_price, max_date = fetch_365_data(coin_id)
    if min_price is None or max_price is None:
        print(f"Нет данных 365 дней для монеты {coin_id}. Пропускаем.")
        return

    # Получаем цену для каждой конкретной даты
    date_prices = {}
    for col, date_str in specific_dates.items():
        price = fetch_history_price(coin_id, date_str)
        date_prices[col] = price
        print(f"Монета {coin_id}, дата {date_str}: цена = {price}")

    # Формируем списки столбцов и значений
    base_columns = ["min365_usd", "min365_date", "max365_usd", "max365_date"]
    base_values = [min_price, min_date, max_price, max_date]
    additional_columns = list(specific_dates.keys())
    additional_values = [date_prices[col] for col in additional_columns]

    columns = base_columns + additional_columns
    values = base_values + additional_values

    # Формируем SQL-запрос с upsert
    cols_formatted = ", ".join([f"`{col}`" for col in columns])
    num_params = 1 + len(columns)  # 1 для coin_id + количество столбцов
    placeholders = ", ".join(["%s"] * num_params)
    update_clause = ", ".join([f"`{col}` = VALUES(`{col}`)" for col in columns])
    query = f"""
        INSERT INTO coin_history_365 (coin_id, {cols_formatted})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """
    params = [coin_id] + values
    print("SQL-запрос:")
    print(query)
    print("Число параметров:", len(params))
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()
        print(f"Обновлены данные 365 дней для монеты {coin_id}: min {min_price} ({min_date}), max {max_price} ({max_date})")
    except mysql.connector.Error as e:
        print(f"Ошибка обновления данных 365 дней для монеты {coin_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def process_made_in_usa_coins():
    """
    Для каждой монеты из категории 'made-in-usa':
      - Если в таблице coin_history_365 еще нет записи, запрашивает данные по 365-дневному графику
        и по конкретным датам, затем обновляет таблицу.
    """
    create_history_365_table_full()
    coin_ids = get_made_in_usa_coin_ids()
    print(f"Найдено {len(coin_ids)} монет категории 'made-in-usa' для обновления данных за 365 дней.")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(update_365_full_for_coin, coin_id): coin_id for coin_id in coin_ids}
        for future in as_completed(futures):
            coin_id = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Ошибка обработки 365-дневных данных для монеты {coin_id}: {e}")


def main():
    process_made_in_usa_coins()


if __name__ == "__main__":
    main()