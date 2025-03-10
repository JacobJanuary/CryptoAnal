import os
import traceback
import requests
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json

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

# Глобальная переменная для подсчёта обращений к API
api_calls_count = 0

def create_history_365_table_full():
    """
    Создает таблицу coin_history_new365, если она не существует.
    """
    create_query = """
    CREATE TABLE IF NOT EXISTS coin_history_new365 (
        coin_id VARCHAR(255) PRIMARY KEY,
        trade_launch_date DATE DEFAULT NULL,
        min_price_oct23_mar25 DECIMAL(20,8) DEFAULT NULL,
        min_date_oct23_mar25 DATE DEFAULT NULL,
        max_price_oct23_mar25 DECIMAL(20,8) DEFAULT NULL,
        max_date_oct23_mar25 DATE DEFAULT NULL,
        perc_change_min_to_max DECIMAL(10,2) DEFAULT NULL,
        perc_change_max_to_current DECIMAL(10,2) DEFAULT NULL,
        volume_spikes TEXT DEFAULT NULL,
        anomalous_buybacks TEXT DEFAULT NULL
    )
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(create_query)
        conn.commit()
        print("Таблица coin_history_new365 создана (если не существовала).")
    except mysql.connector.Error as e:
        print(f"Ошибка создания таблицы coin_history_new365: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def fetch_trade_launch_date(coin_id):
    """
    Получает самую раннюю дату, когда появились данные о цене для монеты coin_id.
    """
    global api_calls_count
    url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    headers = {
        "accept": "application/json",
        "x-cg-pro-api-key": COINGECKO_API_KEY
    }
    params = {
        "vs_currency": "usd",
        "days": "max"  # Максимальный период данных
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        api_calls_count += 1
        response.raise_for_status()
        data = response.json()
        prices = data.get("prices", [])
        if not prices:
            print(f"Для монеты {coin_id} отсутствуют данные о ценах.")
            return None
        # Берем timestamp первой точки и преобразуем в дату
        earliest_ts = prices[0][0]
        earliest_date = datetime.fromtimestamp(earliest_ts / 1000).strftime("%Y-%m-%d")
        return earliest_date
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе данных для монеты {coin_id}: {e}")
        return None

def fetch_range_data(coin_id, start_date, end_date):
    """
    Запрашивает исторические данные цены и объема за указанный диапазон дат.
    Возвращает (prices, volumes) или (None, None).
    """
    global api_calls_count
    url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    headers = {
        "accept": "application/json",
        "x-cg-pro-api-key": COINGECKO_API_KEY
    }
    params = {
        "vs_currency": "usd",
        "from": int(start_date.timestamp()),
        "to": int(end_date.timestamp())
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        api_calls_count += 1
        response.raise_for_status()
        data = response.json()
        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        if not prices or not volumes:
            print(f"Для монеты {coin_id} отсутствуют данные за период.")
            return None, None
        return prices, volumes
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе данных для монеты {coin_id}: {e}")
        return None, None

def analyze_price_volume(prices, volumes):
    """
    Анализирует цены и объемы для нахождения минимумов, максимумов, всплесков объема и аномального откупа.
    """
    if not prices or not volumes:
        return None, None, None, None, None, None, None

    min_price = float('inf')
    max_price = float('-inf')
    min_ts = None
    max_ts = None
    current_price = prices[-1][1]  # Последняя цена

    for point in prices:
        ts, price = point[0], point[1]
        if price < min_price:
            min_price = price
            min_ts = ts
        if price > max_price:
            max_price = price
            max_ts = ts

    min_date = datetime.fromtimestamp(min_ts / 1000).strftime("%Y-%m-%d") if min_ts else None
    max_date = datetime.fromtimestamp(max_ts / 1000).strftime("%Y-%m-%d") if max_ts else None

    # Анализ всплесков объема (объем в 2 раза выше среднего)
    avg_volume = sum(v[1] for v in volumes) / len(volumes)
    volume_spikes = [{"date": datetime.fromtimestamp(v[0] / 1000).strftime("%Y-%m-%d"), "volume": v[1]}
                     for v in volumes if v[1] > avg_volume * 2]

    # Анализ аномального откупа (рост цены после падения с высоким объемом)
    anomalous_buybacks = []
    for i in range(1, len(prices) - 1):
        if prices[i-1][1] > prices[i][1] < prices[i+1][1]:  # Локальный минимум
            price_change = ((prices[i+1][1] - prices[i][1]) / prices[i][1]) * 100
            if volumes[i+1][1] > avg_volume * 1.5:  # Высокий объем при отскоке
                anomalous_buybacks.append({
                    "date": datetime.fromtimestamp(prices[i+1][0] / 1000).strftime("%Y-%m-%d"),
                    "price_change": price_change,
                    "volume": volumes[i+1][1]
                })

    return min_price, min_date, max_price, max_date, current_price, volume_spikes, anomalous_buybacks

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

def update_365_full_for_coin(coin_id, start_date, end_date):
    """
    Для монеты coin_id:
      - Получаем дату запуска торгов.
      - Получаем данные за период и анализируем их.
      - Выполняем upsert в coin_history_new365.
    """
    print(f"[coin_id={coin_id}] Обработка данных...")

    # Получаем дату запуска торгов
    trade_launch_date = fetch_trade_launch_date(coin_id)

    # Получаем данные за период
    prices, volumes = fetch_range_data(coin_id, start_date, end_date)
    if not prices or not volumes:
        print(f"[coin_id={coin_id}] Нет данных за период. Пропускаем.")
        return

    # Анализируем данные
    min_price, min_date, max_price, max_date, current_price, volume_spikes, anomalous_buybacks = analyze_price_volume(prices, volumes)

    if min_price is None or max_price is None:
        print(f"[coin_id={coin_id}] Недостаточно данных для анализа. Пропускаем.")
        return

    # Вычисляем процентные изменения
    perc_change_min_to_max = ((max_price - min_price) / min_price) * 100 if min_price else None
    perc_change_max_to_current = ((current_price - max_price) / max_price) * 100 if max_price else None

    # Преобразуем списки в JSON
    volume_spikes_json = json.dumps(volume_spikes)
    anomalous_buybacks_json = json.dumps(anomalous_buybacks)

    # SQL upsert
    columns = [
        "trade_launch_date", "min_price_oct23_mar25", "min_date_oct23_mar25",
        "max_price_oct23_mar25", "max_date_oct23_mar25", "perc_change_min_to_max",
        "perc_change_max_to_current", "volume_spikes", "anomalous_buybacks"
    ]
    values = [
        trade_launch_date, min_price, min_date, max_price, max_date,
        perc_change_min_to_max, perc_change_max_to_current, volume_spikes_json, anomalous_buybacks_json
    ]
    cols_formatted = ", ".join([f"`{col}`" for col in columns])
    placeholders = ", ".join(["%s"] * (1 + len(columns)))
    update_clause = ", ".join([f"`{col}`=VALUES(`{col}`)" for col in columns])
    query = f"""
        INSERT INTO coin_history_new365 (coin_id, {cols_formatted})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """
    params = [coin_id] + values

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()
        print(f"[coin_id={coin_id}] Данные обновлены.")
    except mysql.connector.Error as e:
        print(f"[coin_id={coin_id}] Ошибка обновления данных: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def process_made_in_usa_coins():
    """
    Для каждой монеты из категории 'made-in-usa' обновляем/вставляем данные.
    """
    create_history_365_table_full()
    coin_ids = get_made_in_usa_coin_ids()
    print(f"Найдено {len(coin_ids)} монет категории 'made-in-usa' для обновления.")

    # Устанавливаем даты для анализа (октябрь 2023 - март 2025)
    start_date = datetime(2023, 10, 1)
    end_date = datetime(2025, 3, 31)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(update_365_full_for_coin, cid, start_date, end_date): cid for cid in coin_ids}
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