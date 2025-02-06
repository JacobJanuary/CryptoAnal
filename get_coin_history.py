import os
import traceback
import requests
import mysql.connector
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем API-ключ для CoinGecko
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

# URL для запроса исторических данных по монете
# Документация: https://docs.coingecko.com/reference/coins-id-history
# Параметр date должен быть в формате dd-mm-yyyy
def fetch_history_price(coin_id, date_str):
    """
    Запрашивает у CoinGecko историю цены для монеты coin_id на дату date_str (формат dd-mm-yyyy)
    и возвращает цену в USD или None, если данные отсутствуют.
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
        # Извлекаем цену из data["market_data"]["current_price"]["usd"]
        market_data = data.get("market_data")
        if market_data:
            current_price = market_data.get("current_price", {}).get("usd")
            return current_price
        else:
            print(f"Нет market_data для монеты {coin_id} на дату {date_str}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе исторических данных для монеты {coin_id} на дату {date_str}: {e}")
        return None

# Список дат для запроса (формат dd-mm-yyyy)
dates = {
    "02-02-2025": "02-02-2025",
    "03-02-2025": "03-02-2025",
    "04-02-2025": "04-02-2025",
    "04-08-2024": "04-08-2024",
    "05-08-2024": "05-08-2024",
    "06-08-2024": "06-08-2024",
    "07-12-2024": "07-12-2024"
}

# Глобальная конфигурация подключения к базе данных
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

def create_history_table():
    """
    Создаёт таблицу coin_history_date, если она не существует.
    Структура таблицы:
      - coin_id VARCHAR(255) PRIMARY KEY,
      - колонки для каждой даты с типом DECIMAL(20,8)
    Используются обратные кавычки для имен столбцов с дефисами.
    """
    create_query = """
    CREATE TABLE IF NOT EXISTS coin_history_date (
        coin_id VARCHAR(255) PRIMARY KEY,
        `02-02-2025` DECIMAL(20,8) DEFAULT NULL,
        `03-02-2025` DECIMAL(20,8) DEFAULT NULL,
        `04-02-2025` DECIMAL(20,8) DEFAULT NULL,
        `04-08-2024` DECIMAL(20,8) DEFAULT NULL,
        `05-08-2024` DECIMAL(20,8) DEFAULT NULL,
        `06-08-2024` DECIMAL(20,8) DEFAULT NULL,
        `07-12-2024` DECIMAL(20,8) DEFAULT NULL
    )
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(create_query)
        conn.commit()
        print("Таблица coin_history_date создана (если не существовала).")
    except mysql.connector.Error as e:
        print(f"Ошибка создания таблицы coin_history_date: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def get_favourite_coin_ids():
    """
    Возвращает список coin_id из таблицы coin_gesco_coins, у которых isFavourites = 1.
    """
    coin_ids = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "SELECT id FROM coin_gesco_coins WHERE isFavourites = 1"
        cursor.execute(query)
        rows = cursor.fetchall()
        coin_ids = [row[0] for row in rows]
    except mysql.connector.Error as e:
        print(f"Ошибка при выборке избранных монет: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return coin_ids

def record_exists(coin_id):
    """
    Проверяет, существует ли уже запись для данной монеты в таблице coin_history_date.
    Возвращает True, если запись существует, иначе False.
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "SELECT coin_id FROM coin_history_date WHERE coin_id = %s"
        cursor.execute(query, (coin_id,))
        result = cursor.fetchone()
        return result is not None
    except mysql.connector.Error as e:
        print(f"Ошибка при проверке существования записи для монеты {coin_id}: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def insert_coin_history(coin_id, prices):
    """
    Вставляет новую запись в таблицу coin_history_date для монеты coin_id.
    prices – словарь, где ключи совпадают с именами столбцов (например, "02-02-2025")
             и значения – цена в USD.
    Если prices пустой, запись не вставляется.
    """
    if not prices:
        print(f"Нет данных для вставки для монеты {coin_id}.")
        return

    # Формируем строку столбцов, например: `02-02-2025`, `03-02-2025`, ...
    columns = ", ".join([f"`{col}`" for col in prices.keys()])
    # Количество параметров: 1 (coin_id) + количество ключей в prices
    num_placeholders = len(prices) + 1
    placeholders = ", ".join(["%s"] * num_placeholders)

    insert_query = f"INSERT INTO coin_history_date (coin_id, {columns}) VALUES ({placeholders})"
    values = [coin_id] + list(prices.values())

    # Вывод для отладки: проверяем сформированный запрос и список параметров
    print("Executing query:")
    print(insert_query)
    print("With values:")
    print(values)

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(insert_query, tuple(values))
        conn.commit()
        print(f"Запись для монеты {coin_id} успешно добавлена в coin_history_date.")
    except mysql.connector.Error as e:
        print(f"Ошибка вставки записи для монеты {coin_id} в coin_history_date: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def process_favourite_coins():
    """
    Для каждой избранной монеты, если в таблице coin_history_date ещё нет записи,
    запрашивает цену в USD по заданным датам и заносит данные в таблицу.
    """
    # Создаем таблицу, если она не существует
    create_history_table()

    coin_ids = get_favourite_coin_ids()
    print(f"Найдено {len(coin_ids)} избранных монет для обновления истории цен.")

    for coin_id in coin_ids:
        if record_exists(coin_id):
            print(f"Запись для монеты {coin_id} уже существует. Пропускаем.")
            continue

        prices = {}
        for key, date_str in dates.items():
            # Запрашиваем цену для coin_id на дату date_str (формат dd-mm-yyyy)
            price = fetch_history_price(coin_id, date_str)
            prices[key] = price
            print(f"Монета {coin_id}, дата {date_str}: цена = {price}")
        # Вставляем запись, даже если некоторые цены отсутствуют (будут NULL)
        insert_coin_history(coin_id, prices)


if __name__ == "__main__":
    process_favourite_coins()