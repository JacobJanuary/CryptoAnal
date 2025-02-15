#

import os
import traceback
import requests
import mysql.connector
import time
from dotenv import load_dotenv
from datetime import datetime
import json

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем API-ключ CoinGecko (если требуется)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Конфигурация подключения к базе данных
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}


def fetch_coin_details(coin_id):
    """
    Запрашивает данные монеты по coin_id через API CoinGecko и возвращает JSON-словарь.
    """
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
        coin_data = response.json()
        return coin_data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API для монеты {coin_id}: {e}")
        return None


def parse_datetime(dt_str):
    """
    Преобразует строку формата ISO-8601 в объект datetime.
    Если преобразование не удаётся – возвращает None.
    """
    try:
        return datetime.fromisoformat(dt_str.rstrip("Z"))
    except Exception:
        return None

def update_coin_categories(data):
    """
    Обновляет связи монеты с категориями в таблице coin_category_relation.
    Для данной монеты:
      - Для каждого элемента из data['categories']:
            ищет в таблице CG_Categories запись по совпадению имени,
            если найдена, проверяет, существует ли уже связь (coin_id, category_id)
            в таблице coin_category_relation.
            Если связи ещё нет, вставляет новую связь (coin_id, category_id).
    Если для монеты уже существуют какие-либо связи, они не удаляются.
    """
    coin_id = data.get("id")
    if not coin_id:
        print("Нет coin_id для обновления категорий.")
        return

    categories = data.get("categories", [])
    if not categories:
        print(f"Для монеты {coin_id} нет категорий для обновления.")
        return

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        select_cat_query = "SELECT category_id FROM CG_Categories WHERE name = %s"
        # Новый запрос для проверки существования связи:
        select_relation_query = "SELECT 1 FROM coin_category_relation WHERE coin_id = %s AND category_id = %s"
        insert_query = "INSERT INTO coin_category_relation (coin_id, category_id) VALUES (%s, %s)"

        for cat in categories:
            cursor.execute(select_cat_query, (cat,))
            row = cursor.fetchone()
            if row:
                category_id = row[0]
                # Проверяем, существует ли связь (coin_id, category_id)
                cursor.execute(select_relation_query, (coin_id, category_id))
                relation_exists = cursor.fetchone()
                if not relation_exists:
                    cursor.execute(insert_query, (coin_id, category_id))
                    print(f"Добавлена связь: монета {coin_id} ↔ категория {category_id} ({cat})")
                else:
                    print(f"Связь для монеты {coin_id} с категорией {category_id} ({cat}) уже существует.")
            else:
                print(f"Не найдена категория с именем: {cat}")

        conn.commit()
    except mysql.connector.Error as e:
        print(f"Ошибка обновления категорий для монеты {coin_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def get_coin_ids_for_update():
    """
    Возвращает список coin_id из таблицы coin_gesco_coins,
    для которых еще не выбраны категории (т.е. отсутствуют записи в coin_category_relation).
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
    Здесь не производится удаление связанных записей (удаление категорий убрано).
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
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def main():
    # Получаем список coin_id для обновления (монеты, у которых ещё не выбраны категории)
    coin_ids = get_coin_ids_for_update()
    print(f"Найдено {len(coin_ids)} монет для обновления категорий.")

    # Используем пул потоков для параллельной обработки монет (2 потоков)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(process_coin, coin_id): coin_id for coin_id in coin_ids}
        for future in as_completed(futures):
            coin_id = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Ошибка обработки монеты {coin_id}: {e}")


def process_coin(coin_id):
    """
    Обрабатывает монету:
      - Запрашивает данные через API CoinGecko.
      - Если данные не получены, удаляет монету из базы.
      - Если данные получены, обновляет связи категорий.
    """
    print(f"\nОбработка монеты {coin_id}...")
    coin_data = fetch_coin_details(coin_id)
    if not coin_data:
        removed = remove_coin_from_db(coin_id)
        print(f"Нет данных для монеты {coin_id} -> монета удалена: {removed}")
        return

    update_coin_categories(coin_data)
    print(f"Монета {coin_id} успешно обновлена.")


if __name__ == "__main__":
    main()