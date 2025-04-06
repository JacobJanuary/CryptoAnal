#сделать Cron и обновлять раз в неделю
import requests
import os
import mysql.connector
import time
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация API
API_KEY = os.getenv('CMC_API_KEY')
if not API_KEY:
    raise ValueError("API ключ не найден. Пожалуйста, установите переменную CMC_API_KEY в файле .env")

# Конфигурация базы данных
DB_TYPE = os.getenv('DB_TYPE', 'mysql')
DB_NAME = os.getenv('DB_NAME', 'crypto_db')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')


def create_database_connection():
    """
    Создание подключения к базе данных MySQL
    """
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=int(DB_PORT)
        )
        print("Подключение к базе данных успешно установлено")
        return conn
    except mysql.connector.Error as err:
        print(f"Ошибка подключения к базе данных: {err}")
        raise


def fetch_categories_from_db(conn):
    """
    Получение всех категорий из базы данных
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM categories")
    categories = cursor.fetchall()
    print(f"Получено {len(categories)} категорий из базы данных")
    return categories


def fetch_category_coins(category_id):
    """
    Получение монет для конкретной категории через API CoinMarketCap
    """
    url = f'https://pro-api.coinmarketcap.com/v1/cryptocurrency/category'

    headers = {
        'X-CMC_PRO_API_KEY': API_KEY,
        'Accept': 'application/json'
    }

    # Параметры для запроса
    params = {
        'id': category_id,
        'limit': 1000  # Получаем до 1000 монет для каждой категории
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при запросе категории {category_id}: {response.status_code}")
        print(response.text)
        return None


def create_relations_table(conn):
    """
    Создание таблицы связей категорий и монет, если она не существует
    """
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cmc_category_relations (
        relation_id INT AUTO_INCREMENT PRIMARY KEY,
        category_id VARCHAR(255) NOT NULL,
        coin_id BIGINT NOT NULL,
        UNIQUE KEY unique_category_coin (category_id, coin_id)
    )
    ''')

    conn.commit()
    print("Таблица cmc_category_relations создана или уже существует")


def save_category_coins_relations(conn, category_id, coins):
    """
    Сохранение связей категорий и монет в базу данных с проверкой существования
    """
    if not coins:
        print(f"Нет монет для категории {category_id}")
        return

    cursor = conn.cursor()

    # Для отслеживания статистики
    new_relations = 0
    existing_relations = 0

    for coin in coins:
        # Проверяем существует ли уже такая связь
        check_sql = '''
        SELECT COUNT(*) FROM cmc_category_relations 
        WHERE category_id = %s AND coin_id = %s
        '''
        cursor.execute(check_sql, (category_id, coin['id']))
        count = cursor.fetchone()[0]

        # Если связь не существует, добавляем ее
        if count == 0:
            insert_sql = '''
            INSERT INTO cmc_category_relations (category_id, coin_id)
            VALUES (%s, %s)
            '''
            cursor.execute(insert_sql, (category_id, coin['id']))
            new_relations += 1
        else:
            existing_relations += 1

    conn.commit()

    print(
        f"Категория {category_id}: добавлено {new_relations} новых связей, пропущено {existing_relations} существующих связей")

    return new_relations


def process_all_categories():
    """
    Обработка всех категорий и сохранение связей с монетами
    """
    try:
        start_time = time.time()

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Создание таблицы связей
        create_relations_table(conn)

        # Получение всех категорий из базы данных
        categories = fetch_categories_from_db(conn)

        total_relations = 0
        processed_categories = 0

        # Обработка каждой категории
        for category in categories:
            category_id = category['id']
            category_name = category['name']

            print(f"Обработка категории: {category_name} (ID: {category_id})")

            # Получение монет для категории
            response = fetch_category_coins(category_id)

            if response and 'data' in response:
                data = response['data']
                coins = data.get('coins', [])

                print(f"Получено {len(coins)} монет для категории {category_name}")

                # Сохранение связей в базу данных
                save_category_coins_relations(conn, category_id, coins)
                total_relations += len(coins)
            else:
                print(f"Не удалось получить данные для категории {category_name}")

            processed_categories += 1
            print(f"Обработано {processed_categories} из {len(categories)} категорий")

            # Добавляем задержку, чтобы избежать превышения лимитов API
            time.sleep(1)

        # Закрытие соединения с базой данных
        conn.close()

        total_time = time.time() - start_time
        print(f"Всего обработано {processed_categories} категорий")
        print(f"Всего сохранено {total_relations} связей")
        print(f"Общее время выполнения: {total_time:.2f} секунд")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
    process_all_categories()