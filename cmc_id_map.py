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


def fetch_cryptocurrencies():
    """
    Получение данных о всех криптовалютах через API CoinMarketCap
    """
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/map'

    headers = {
        'X-CMC_PRO_API_KEY': API_KEY,
        'Accept': 'application/json'
    }

    # Параметры для запроса
    params = {
        'listing_status': 'active,inactive'  # Получение как активных, так и неактивных криптовалют
        # Убрано ограничение на количество результатов для получения всех доступных монет
    }

    response = requests.get(url, headers=headers, params=params)

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


def create_cryptocurrencies_table(conn):
    """
    Создание таблицы криптовалют в базе данных, если она не существует
    """
    cursor = conn.cursor()

    # Создание таблицы cmc_cryptocurrencies, если она не существует
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cmc_cryptocurrencies (
        id BIGINT PRIMARY KEY,
        cmc_rank INT,
        name VARCHAR(255) NOT NULL,
        symbol VARCHAR(50) NOT NULL,
        slug VARCHAR(255) NOT NULL,
        is_active TINYINT(1),
        first_historical_data VARCHAR(255),
        last_historical_data VARCHAR(255),
        platform_id BIGINT,
        platform_name VARCHAR(255),
        platform_symbol VARCHAR(50),
        platform_slug VARCHAR(255),
        platform_token_address VARCHAR(255),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    print("Таблица cmc_cryptocurrencies создана или уже существует")


def save_cryptocurrencies_to_db(cryptocurrencies, conn):
    """
    Сохранение данных о криптовалютах в базу данных.
    Использует пакетную обработку для ускорения операций.
    """
    cursor = conn.cursor()

    # Подготавливаем SQL запрос для вставки или обновления данных (UPSERT)
    upsert_sql = '''
    INSERT INTO cmc_cryptocurrencies (
        id, cmc_rank, name, symbol, slug, is_active, 
        first_historical_data, last_historical_data,
        platform_id, platform_name, platform_symbol, 
        platform_slug, platform_token_address
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        cmc_rank = VALUES(cmc_rank),
        name = VALUES(name),
        symbol = VALUES(symbol),
        slug = VALUES(slug),
        is_active = VALUES(is_active),
        first_historical_data = VALUES(first_historical_data),
        last_historical_data = VALUES(last_historical_data),
        platform_id = VALUES(platform_id),
        platform_name = VALUES(platform_name),
        platform_symbol = VALUES(platform_symbol),
        platform_slug = VALUES(platform_slug),
        platform_token_address = VALUES(platform_token_address)
    '''

    # Размер пакета для обработки
    batch_size = 100
    total_processed = 0

    # Получаем список всех существующих ID для подсчета статистики
    cursor.execute("SELECT id FROM cmc_cryptocurrencies")
    existing_ids = {row[0] for row in cursor.fetchall()}

    # Подготавливаем пакеты данных
    print("Подготовка данных для пакетной обработки...")
    all_values = []

    for crypto in cryptocurrencies:
        # Извлекаем информацию о платформе, если она есть
        platform = crypto.get('platform', {})
        platform_id = platform.get('id') if platform else None
        platform_name = platform.get('name') if platform else None
        platform_symbol = platform.get('symbol') if platform else None
        platform_slug = platform.get('slug') if platform else None
        platform_token_address = platform.get('token_address') if platform else None

        values = (
            crypto.get('id'),
            crypto.get('rank'),
            crypto.get('name'),
            crypto.get('symbol'),
            crypto.get('slug'),
            crypto.get('is_active'),
            crypto.get('first_historical_data'),
            crypto.get('last_historical_data'),
            platform_id,
            platform_name,
            platform_symbol,
            platform_slug,
            platform_token_address
        )

        all_values.append(values)

    # Обрабатываем данные пакетами
    print(f"Начало пакетной обработки данных (размер пакета: {batch_size})...")

    for i in range(0, len(all_values), batch_size):
        batch = all_values[i:i + batch_size]
        cursor.executemany(upsert_sql, batch)
        conn.commit()

        total_processed += len(batch)
        print(f"Обработано {total_processed} из {len(all_values)} криптовалют...")

    # Подсчитываем количество новых и обновленных записей
    cursor.execute("SELECT id FROM cmc_cryptocurrencies")
    current_ids = {row[0] for row in cursor.fetchall()}

    inserted_count = len(current_ids - existing_ids)
    updated_count = len(all_values) - inserted_count

    print(
        f"Добавлено {inserted_count} новых криптовалют и обновлено {updated_count} существующих криптовалют в базе данных")


def main():
    try:
        import time
        start_time = time.time()

        # Получение данных о криптовалютах из API
        print("Получение данных о криптовалютах из API CoinMarketCap...")
        cryptocurrencies = fetch_cryptocurrencies()

        api_time = time.time()
        print(f"API запрос занял {api_time - start_time:.2f} секунд")

        if not cryptocurrencies:
            print("Не удалось получить данные о криптовалютах.")
            return

        print(f"Успешно получено {len(cryptocurrencies)} криптовалют")

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Создание таблицы cmc_cryptocurrencies
        create_cryptocurrencies_table(conn)

        # Сохранение данных в базу
        save_cryptocurrencies_to_db(cryptocurrencies, conn)

        db_time = time.time()
        print(f"Сохранение в базу данных заняло {db_time - api_time:.2f} секунд")

        # Закрытие соединения с базой данных
        conn.close()
        print("Соединение с базой данных закрыто")

        total_time = time.time() - start_time
        print(f"Общее время выполнения: {total_time:.2f} секунд")
        print("Процесс успешно завершен.")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
    main()