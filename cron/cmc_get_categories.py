import requests
import os
import mysql.connector
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


def fetch_categories():
    """
    Получение всех категорий криптовалют через API CoinMarketCap
    """
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/categories'

    headers = {
        'X-CMC_PRO_API_KEY': API_KEY,
        'Accept': 'application/json'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()['data']
    else:
        print(f"Ошибка: {response.status_code}")
        print(response.text)
        return None


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


def create_categories_table(conn):
    """
    Создание таблицы категорий в базе данных, только если она не существует
    """
    cursor = conn.cursor()

    # Создание таблицы categories, если она не существует
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id VARCHAR(255) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        title VARCHAR(255),
        description TEXT,
        num_tokens INT,
        last_updated VARCHAR(255),
        avg_price_change DECIMAL(20, 8),
        market_cap DECIMAL(30, 6),
        market_cap_change DECIMAL(20, 9),
        volume DECIMAL(30, 7),
        volume_change DECIMAL(20, 9)
    )
    ''')

    conn.commit()
    print("Таблица categories создана или уже существует")


def save_categories_to_db(categories, conn):
    """
    Сохранение данных о категориях в базу данных.
    Обновляет существующие записи или добавляет новые.
    """
    cursor = conn.cursor()

    # Подготавливаем SQL запрос для вставки или обновления данных (UPSERT)
    # В MySQL, для операции UPSERT используется INSERT ... ON DUPLICATE KEY UPDATE
    upsert_sql = '''
    INSERT INTO categories (
        id, name, title, description, num_tokens, last_updated,
        avg_price_change, market_cap, market_cap_change, volume, volume_change
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        title = VALUES(title),
        description = VALUES(description),
        num_tokens = VALUES(num_tokens),
        last_updated = VALUES(last_updated),
        avg_price_change = VALUES(avg_price_change),
        market_cap = VALUES(market_cap),
        market_cap_change = VALUES(market_cap_change),
        volume = VALUES(volume),
        volume_change = VALUES(volume_change)
    '''

    # Счетчики для статистики
    inserted_count = 0
    updated_count = 0

    # Вставляем или обновляем каждую категорию в базе данных
    for category in categories:
        # Проверяем, существует ли уже категория с таким id
        cursor.execute("SELECT COUNT(*) FROM categories WHERE id = %s", (category.get('id'),))
        exists = cursor.fetchone()[0] > 0

        values = (
            category.get('id'),
            category.get('name'),
            category.get('title'),
            category.get('description'),
            category.get('num_tokens'),
            category.get('last_updated'),
            category.get('avg_price_change'),
            category.get('market_cap'),
            category.get('market_cap_change'),
            category.get('volume'),
            category.get('volume_change')
        )

        cursor.execute(upsert_sql, values)

        # Увеличиваем соответствующий счетчик
        if exists:
            updated_count += 1
        else:
            inserted_count += 1

    conn.commit()
    print(
        f"Добавлено {inserted_count} новых категорий и обновлено {updated_count} существующих категорий в базе данных")


def main():
    try:
        # Получение категорий из API
        print("Получение данных о категориях из API CoinMarketCap...")
        categories = fetch_categories()

        if not categories:
            print("Не удалось получить данные о категориях.")
            return

        print(f"Успешно получено {len(categories)} категорий")

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Создание таблицы categories
        create_categories_table(conn)

        # Сохранение данных в базу
        save_categories_to_db(categories, conn)

        # Закрытие соединения с базой данных
        conn.close()
        print("Соединение с базой данных закрыто")

        print("Процесс успешно завершен.")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    main()