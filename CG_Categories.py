import requests
import mysql.connector
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем API-ключ для CoinGecko из переменных окружения
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

# URL для получения списка категорий (только ID и Name)
CATEGORIES_LIST_URL = "https://pro-api.coingecko.com/api/v3/coins/categories/list"

# URL для получения списка категорий с деталями (market_cap_desc)
CATEGORIES_DETAILED_URL = "https://pro-api.coingecko.com/api/v3/coins/categories?order=market_cap_desc"

headers = {
    "accept": "application/json",
    "x-cg-pro-api-key": COINGECKO_API_KEY
}

def fetch_categories_list():
    """
    Получает базовый список категорий (category_id, name).
    """
    try:
        response = requests.get(CATEGORIES_LIST_URL, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API (fetch_categories_list): {e}")
        return []

def fetch_categories_detailed():
    """
    Получает детализированный список категорий,
    отсортированный по убыванию market_cap.
    Пример структуры для каждого элемента:
      {
        "id": "polkadot-ecosystem",
        "name": "Polkadot Ecosystem",
        "market_cap": 52440540325,
        ...
      }
    """
    try:
        response = requests.get(CATEGORIES_DETAILED_URL, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API (fetch_categories_detailed): {e}")
        return []


def save_categories_to_db(categories):
    """
    Сохраняет список категорий (минимальные поля) в таблицу CG_Categories.
    Перед вставкой проверяет, нет ли уже записи с таким category_id.
    Возвращает количество новых категорий.
    """
    db_config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "password"),
        "database": os.getenv("MYSQL_DATABASE", "crypto_db")
    }

    new_categories_count = 0

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Запрос для вставки категории (Weight по умолчанию 999)
        insert_query = """
            INSERT INTO CG_Categories (category_id, name, Weight, about_what)
            VALUES (%s, %s, 999, 0)
        """

        # Проверка существующей записи
        select_query = """
            SELECT category_id
            FROM CG_Categories
            WHERE category_id = %s
        """

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
        print("Данные о категориях успешно сохранены в таблицу CG_Categories")
        return new_categories_count

    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL: {e}")
        return 0

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def reset_all_weights_to_999():
    """
    Ставит Weight=999 для всех категорий в таблице CG_Categories.
    """
    db_config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "password"),
        "database": os.getenv("MYSQL_DATABASE", "crypto_db")
    }

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        update_query = "UPDATE CG_Categories SET Weight = 999"
        cursor.execute(update_query)
        conn.commit()

        print("Weight=999 проставлен для всех категорий.")

    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def update_weights_by_market_cap():
    """
    1. Получаем детализированный список категорий,
       отсортированный по убыванию market_cap.
    2. Присваиваем Weight = 1 категории с самым большим market_cap,
       Weight = 2 — следующей и т.д.
    """
    db_config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "password"),
        "database": os.getenv("MYSQL_DATABASE", "crypto_db")
    }

    categories_detailed = fetch_categories_detailed()
    if not categories_detailed:
        print("Не удалось получить детализированный список категорий (market_cap_desc).")
        return

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Пробегаемся по категориям в порядке убывания market_cap
        # i = 1 для первой (самый большой market_cap), i = 2 для второй и т.д.
        rank = 1
        update_query = "UPDATE CG_Categories SET Weight = %s WHERE category_id = %s"

        for cat in categories_detailed:
            cat_id = cat.get("id")  # В detailed-ответах поле называется "id"
            if cat_id:
                cursor.execute(update_query, (rank, cat_id))
                rank += 1

        conn.commit()
        print("Weight обновлён согласно рыночной капитализации (market_cap_desc).")

    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def main():
    # 1. Получаем первоначальный список категорий (category_id, name)
    categories = fetch_categories_list()
    if not categories:
        print("Не удалось получить базовый список категорий (list).")
        return

    print(f"Получено {len(categories)} категорий от CoinGecko (list).")

    # 2. Сохраняем новые категории в БД
    new_count = save_categories_to_db(categories)
    print(f"Добавлено новых категорий: {new_count}")

    # 3. Присваиваем Weight = 999 всем категориям
    reset_all_weights_to_999()

    # 4. Получаем детальные категории (с market_cap) и обновляем веса (Weight)
    update_weights_by_market_cap()

if __name__ == "__main__":
    main()
