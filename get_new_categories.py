#Скрипт проверяет новые категории для монеток и добавляет а также обновляет веса категории


import os
import traceback
import requests
import mysql.connector
from dotenv import load_dotenv
import time  # для замера времени

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем API-ключ для CoinGecko из переменных окружения
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

# URL для получения базового списка категорий (только category_id и name)
CATEGORIES_LIST_URL = "https://pro-api.coingecko.com/api/v3/coins/categories/list"

# URL для получения детализированного списка категорий (с рыночной капитализацией)
CATEGORIES_DETAILED_URL = "https://pro-api.coingecko.com/api/v3/coins/categories?order=market_cap_desc"

headers = {
    "accept": "application/json",
    "x-cg-pro-api-key": COINGECKO_API_KEY
}

# Глобальная конфигурация подключения к БД
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

# Счётчик обращений к API
api_calls_count = 0

def fetch_categories_list():
    """
    Получает базовый список категорий (category_id, name).
    """
    global api_calls_count
    try:
        response = requests.get(CATEGORIES_LIST_URL, headers=headers)
        api_calls_count += 1  # увеливаем счётчик
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API (fetch_categories_list): {e}")
        return []

def fetch_categories_detailed():
    """
    Получает детализированный список категорий, отсортированный по убыванию market_cap.
    """
    global api_calls_count
    try:
        response = requests.get(CATEGORIES_DETAILED_URL, headers=headers)
        api_calls_count += 1  # увеливаем счётчик
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API (fetch_categories_detailed): {e}")
        return []

def save_categories_to_db(categories):
    """
    Сохраняет базовый список категорий (category_id, name) в таблицу CG_Categories.
    Если категория уже существует, пропускаем.
    Новым категориям присваиваем Weight=999 и about_what=0.
    """
    new_categories_count = 0
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO CG_Categories (category_id, name, Weight, about_what)
            VALUES (%s, %s, 999, 0)
        """
        select_query = "SELECT category_id FROM CG_Categories WHERE category_id = %s"

        for category in categories:
            category_id = category.get("category_id")
            name = category.get("name")
            if category_id and name:
                cursor.execute(select_query, (category_id,))
                result = cursor.fetchone()
                if not result:
                    cursor.execute(insert_query, (category_id, name))
                    new_categories_count += 1

        conn.commit()
        print("Данные о категориях успешно сохранены в таблицу CG_Categories.")
        return new_categories_count
    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL при сохранении категорий: {e}")
        return 0
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

def reset_all_weights_to_999():
    """
    Сбрасывает Weight до 999 для всех категорий в таблице CG_Categories.
    """
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        update_query = "UPDATE CG_Categories SET Weight = 999"
        cursor.execute(update_query)
        conn.commit()
        print("Weight=999 проставлен для всех категорий.")
    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL при сбросе весов: {e}")
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

def update_weights_and_market_cap():
    """
    Получает детализированный список категорий (с рыночной капитализацией) и обновляет:
      - Weight: 1 для самой большой cap, 2 для следующей, ...
      - market_cap: записываем значение рыночной капитализации.
    """
    categories_detailed = fetch_categories_detailed()
    if not categories_detailed:
        print("Не удалось получить детализированный список категорий (market_cap_desc).")
        return

    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        rank = 1
        update_query = "UPDATE CG_Categories SET Weight = %s, market_cap = %s WHERE category_id = %s"

        for cat in categories_detailed:
            cat_id = cat.get("id")  # В detailed ответе поле называется "id"
            market_cap = cat.get("market_cap")
            if cat_id is not None and market_cap is not None:
                cursor.execute(update_query, (rank, market_cap, cat_id))
                rank += 1

        conn.commit()
        print("Weight и market_cap обновлены согласно рыночной капитализации.")
    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL при обновлении весов/market_cap: {e}")
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

def main():
    start_time = time.time()  # время начала

    # 1) Получаем базовый список категорий
    categories = fetch_categories_list()
    if not categories:
        print("Не удалось получить базовый список категорий.")
        return
    print(f"Получено {len(categories)} категорий от CoinGecko (list).")

    # 2) Сохраняем новые категории в БД
    new_count = save_categories_to_db(categories)
    print(f"Добавлено новых категорий: {new_count}")

    # 3) Сбрасываем Weight до 999
    reset_all_weights_to_999()

    # 4) Обновляем Weight и market_cap на основе детализированных данных
    update_weights_and_market_cap()

    end_time = time.time()  # время конца
    elapsed = end_time - start_time

    # Выводим итоги
    print(f"\nСкрипт завершён.")
    print(f"Всего обращений к API: {api_calls_count}")
    print(f"Время выполнения скрипта: {elapsed:.2f} секунд.")

if __name__ == "__main__":
    main()