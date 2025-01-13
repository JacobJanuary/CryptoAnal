import requests
import mysql.connector
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем API-ключ для CoinGecko из переменных окружения (если требуется)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

# URL для получения списка категорий монет
url = "https://pro-api.coingecko.com/api/v3/coins/categories/list"

headers = {
    "accept": "application/json",
    "x-cg-pro-api-key": COINGECKO_API_KEY
}

def fetch_categories():
    """
    Получает список категорий через API CoinGecko.
    Каждая категория содержит поля, например:
      - category_id
      - name
    """
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Выбросит исключение при HTTP ошибке
        categories = response.json()
        return categories
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API: {e}")
        return []

def save_categories_to_db(categories):
    """
    Сохраняет список категорий в таблицу CG_Categories.
    Если таблица не существует — создаёт её.
    Используется INSERT IGNORE для добавления только новых записей.
    Возвращает количество новых категорий, добавленных в таблицу.
    """
    # Параметры подключения к БД (подставьте свои параметры или задайте через .env)
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

        # Создаем таблицу CG_Categories, если она не существует
        create_table_query = """
            CREATE TABLE IF NOT EXISTS CG_Categories (
                category_id VARCHAR(255) NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );
        """
        cursor.execute(create_table_query)

        # Запрос для вставки категорий (INSERT IGNORE для предотвращения дублирования)
        insert_query = """
            INSERT IGNORE INTO CG_Categories (category_id, name)
            VALUES (%s, %s);
        """

        for category in categories:
            # Предполагается, что ответ содержит поля 'category_id' и 'name'
            category_id = category.get("category_id")
            name = category.get("name")
            if category_id and name:
                cursor.execute(insert_query, (category_id, name))
                if cursor.rowcount == 1:
                    new_categories_count += 1

        conn.commit()
        print("Данные успешно сохранены в таблицу CG_Categories")
        return new_categories_count

    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL: {e}")
        return 0

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def main():
    categories = fetch_categories()
    if categories:
        print(f"Получено {len(categories)} категорий от CoinGecko")
        new_count = save_categories_to_db(categories)
        print(f"Всего добавлено новых категорий: {new_count}")
    else:
        print("Нет данных для сохранения.")

if __name__ == "__main__":
    main()