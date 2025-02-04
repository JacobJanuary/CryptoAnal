import requests
import mysql.connector
import os
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
      - Удаляет старые связи,
      - Затем для каждого элемента из data['categories']:
            ищет в таблице CG_Categories запись по совпадению имени,
            если найдена, вставляет новую связь (coin_id, category_id).
    """
    coin_id = data.get("id")
    if not coin_id:
        print("Нет coin_id для обновления категорий.")
        return

    categories = data.get("categories", [])
    if not categories:
        print("Для монеты нет категорий для обновления.")
        return

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Удаляем старые связи для данной монеты
        delete_query = "DELETE FROM coin_category_relation WHERE coin_id = %s"
        cursor.execute(delete_query, (coin_id,))

        # Для каждой категории, ищем category_id в CG_Categories по совпадению имени
        select_query = "SELECT category_id FROM CG_Categories WHERE name = %s"
        insert_query = "INSERT INTO coin_category_relation (coin_id, category_id) VALUES (%s, %s)"

        for cat in categories:
            cursor.execute(select_query, (cat,))
            row = cursor.fetchone()
            if row:
                category_id = row[0]
                cursor.execute(insert_query, (coin_id, category_id))
                print(f"Добавлена связь: монета {coin_id} ↔ категория {category_id} ({cat})")
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
    Возвращает список coin_id из таблицы coin_gesco_coins, у которых поле description_en не пустое или не NULL.
    """
    coin_ids = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        # Выбираем все записи, где description_en  NULL иои пустое (после обрезки пробелов)
        query = "SELECT `id` FROM `coin_gesco_coins`"
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


def main():
    # Получаем список coin_id для обновления
    coin_ids = get_coin_ids_for_update()
    print(f"Найдено {len(coin_ids)} монет для обновления.")

    # Для ограничения API до 30 запросов в минуту устанавливаем задержку 2 секунды между запросами
    for coin_id in coin_ids:
        print(f"\nОбработка монеты {coin_id}...")
        coin_data = fetch_coin_details(coin_id)
        if coin_data:
            update_coin_categories(coin_data)
        else:
            print(f"Не удалось получить данные для монеты {coin_id}.")
        # Задержка в 2 секунды для соблюдения лимита 30 запросов в минуту
        #time.sleep(2)


if __name__ == "__main__":
    main()