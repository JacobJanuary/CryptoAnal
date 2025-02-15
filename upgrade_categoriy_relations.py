import os
import traceback
import requests
import mysql.connector
import time
from dotenv import load_dotenv
from datetime import datetime
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

# Глобальный счётчик вызовов к API
api_calls_count = 0

def fetch_coin_details(coin_id):
    """
    Запрашивает данные монеты по coin_id через API CoinGecko и возвращает JSON-словарь.
    Если не удалось — возвращает None.
    Увеличиваем глобальный счётчик api_calls_count при каждом успешном запросе.
    """
    global api_calls_count
    url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_id}"
    headers = {
        "accept": "application/json",
        "x-cg-pro-api-key": COINGECKO_API_KEY
    }
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "false",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        api_calls_count += 1  # увеличиваем счётчик обращений
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API для монеты {coin_id}: {e}")
        return None

def parse_datetime(dt_str):
    try:
        return datetime.fromisoformat(dt_str.rstrip("Z"))
    except Exception:
        return None

def update_coin_categories(data):
    """
    Обновляет связи монеты с категориями в таблице coin_category_relation.
    Возвращает количество УСПЕШНО добавленных/найденных категорий (>=1 => монета получила хотя бы одну категорию).

    Для каждой категории из data['categories']:
      - проверяем, есть ли такая категория в CG_Categories (по имени);
        - если нет, выводим: "нет категории <cat> в таблице (для монеты <coin_id>)"
      - если категория найдена, проверяем, существует ли связь (coin_id, category_id);
        - если связи нет, добавляем и выводим: "для монеты <coin_id> добавлена категория <category_id>"
        - если связь есть, выводим: "Связь уже существует..."
    Если произошла ошибка добавления в БД, выводим: "Ошибка: для монеты <coin_id> добавление категории <cat>"
    """
    coin_id = data.get("id")
    if not coin_id:
        print("Нет coin_id для обновления категорий.")
        return 0

    categories = data.get("categories", [])
    if not categories:
        print(f"Для монеты {coin_id} нет категорий для обновления.")
        return 0

    assigned_count_for_this_coin = 0

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        select_cat_query = "SELECT category_id FROM CG_Categories WHERE name = %s"
        select_relation_query = "SELECT 1 FROM coin_category_relation WHERE coin_id = %s AND category_id = %s"
        insert_query = "INSERT INTO coin_category_relation (coin_id, category_id) VALUES (%s, %s)"

        for cat in categories:
            # Ищем category_id по имени
            cursor.execute(select_cat_query, (cat,))
            row = cursor.fetchone()
            if row:
                category_id = row[0]
                # Проверяем, существует ли связь
                cursor.execute(select_relation_query, (coin_id, category_id))
                relation_exists = cursor.fetchone()
                if not relation_exists:
                    # Пытаемся добавить
                    try:
                        cursor.execute(insert_query, (coin_id, category_id))
                        conn.commit()
                        print(f"для монеты {coin_id} добавлена категория {category_id}")
                        assigned_count_for_this_coin += 1
                    except mysql.connector.Error as e:
                        print(f"Ошибка: для монеты {coin_id} добавление категории {category_id}: {e}")
                else:
                    print(f"Связь для монеты {coin_id} с категорией {category_id} ({cat}) уже существует.")
                    # Даже если связь существует, считаем что монета "имеет" категорию => increment
                    assigned_count_for_this_coin += 1
            else:
                print(f"нет категории '{cat}' в таблице (для монеты {coin_id})")

    except mysql.connector.Error as e:
        print(f"Ошибка обновления категорий для монеты {coin_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

    return assigned_count_for_this_coin

def get_coin_ids_for_update():
    """
    Возвращает список coin_id из таблицы coin_gesco_coins,
    для которых еще не выбраны категории (нет записей в coin_category_relation).
    """
    coin_ids = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            SELECT id FROM coin_gesco_coins
            WHERE id NOT IN (SELECT DISTINCT coin_id FROM coin_category_relation)
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        coin_ids = [row[0] for row in rows]
    except mysql.connector.Error as e:
        print(f"Ошибка при выборке coin_id для обновления: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return coin_ids

def remove_coin_from_db(coin_id):
    """
    Удаляет монету из таблицы coin_gesco_coins по coin_id.
    Возвращает True, если монета была удалена, иначе False.
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM coin_gesco_coins WHERE id = %s", (coin_id,))
        conn.commit()
        deleted_rows = cursor.rowcount
        return deleted_rows > 0
    except mysql.connector.Error as e:
        print(f"Ошибка при удалении монеты {coin_id}: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def process_coin(coin_id):
    """
    Обрабатывает монету:
      - Запрашивает данные через API CoinGecko (fetch_coin_details).
      - Если данные не получены, удаляет монету из базы.
      - Если данные получены, обновляет связи категорий.
    Возвращает True, если монете было добавлено хотя бы 1 категорию (либо связь уже существовала),
    иначе False.
    """
    print(f"\nОбработка монеты {coin_id}...")
    coin_data = fetch_coin_details(coin_id)
    if not coin_data:
        removed = remove_coin_from_db(coin_id)
        print(f"Нет данных для монеты {coin_id} -> монета удалена: {removed}")
        return False

    added_count = update_coin_categories(coin_data)
    if added_count > 0:
        print(f"Монета {coin_id} успешно обновлена (итого категорий: {added_count}).")
        return True
    else:
        print(f"У монеты {coin_id} по итогу нет добавленных категорий.")
        return False

def main():
    start_time = time.time()

    # Получаем список монет без категорий
    coin_ids = get_coin_ids_for_update()
    total_no_category = len(coin_ids)
    print(f"Найдено {total_no_category} монет без категории.")

    # Запускаем параллельную обработку
    from concurrent.futures import ThreadPoolExecutor, as_completed
    assigned_count = 0  # сколько монет получили хотя бы 1 категорию

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_coin = {executor.submit(process_coin, cid): cid for cid in coin_ids}
        for future in as_completed(future_to_coin):
            coin_id = future_to_coin[future]
            try:
                result = future.result()  # True/False
                if result:
                    assigned_count += 1
            except Exception as e:
                print(f"Ошибка обработки монеты {coin_id}: {e}")

    # Считаем, сколько осталось без категорий:
    remain_no_category = total_no_category - assigned_count

    end_time = time.time()
    elapsed = end_time - start_time

    print("\n--- РЕЗУЛЬТАТЫ ---")
    print(f"Всего обращений к API: {api_calls_count}")
    print(f"Монет без категории было обнаружено: {total_no_category}")
    print(f"Для {assigned_count} монет успешно добавлены категории (или уже существовали).")
    print(f"Осталось без категории: {remain_no_category}")
    print(f"Время выполнения скрипта: {elapsed:.2f} секунд.")

if __name__ == "__main__":
    main()