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


def fetch_crypto_listings(start=1, limit=5000):
    """
    Получение данных о последних листингах криптовалют через API CoinMarketCap
    с поддержкой пагинации
    """
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'

    headers = {
        'X-CMC_PRO_API_KEY': API_KEY,
        'Accept': 'application/json'
    }

    # Параметры для запроса
    params = {
        'start': start,
        'limit': limit,
        'convert': 'USD'  # Получаем данные в USD
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка: {response.status_code}")
        print(response.text)
        return None


def fetch_all_crypto_listings():
    """
    Получение всех доступных листингов криптовалют с использованием пагинации
    """
    all_data = []
    start = 1
    limit = 5000  # Максимальное количество результатов на страницу

    while True:
        print(f"Получение данных, начиная с позиции {start}...")
        response = fetch_crypto_listings(start, limit)

        if not response or 'data' not in response:
            print("Не удалось получить данные или получены все доступные данные.")
            break

        data = response['data']
        if not data:
            print("Все данные получены.")
            break

        all_data.extend(data)
        print(f"Получено {len(data)} листингов. Всего: {len(all_data)}")

        # Если получено меньше записей, чем запрошено, значит это последняя страница
        if len(data) < limit:
            break

        # Переходим к следующей странице
        start += limit

        # Добавляем задержку, чтобы избежать превышения лимитов API
        time.sleep(1)

    return all_data


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


def create_crypto_listings_table(conn):
    """
    Создание таблицы для данных о листингах криптовалют в базе данных, если она не существует
    """
    cursor = conn.cursor()

    # Создание таблицы cmc_crypto, если она не существует

    # Создание таблицы cmc_crypto, если она не существует
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cmc_crypto (
        id BIGINT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        symbol VARCHAR(50) NOT NULL,
        slug VARCHAR(255) NOT NULL,
        num_market_pairs INT,
        date_added VARCHAR(255),
        tags TEXT,
        max_supply DECIMAL(65, 18),
        circulating_supply DECIMAL(65, 18),
        total_supply DECIMAL(65, 18),
        infinite_supply TINYINT(1),
        cmc_rank INT,
        last_updated VARCHAR(255),
        price_usd DECIMAL(65, 18),
        volume_24h DECIMAL(65, 2),
        percent_change_1h DECIMAL(65, 18),
        percent_change_24h DECIMAL(65, 18),
        percent_change_7d DECIMAL(65, 18),
        percent_change_30d DECIMAL(65, 18),
        percent_change_60d DECIMAL(65, 18),
        percent_change_90d DECIMAL(65, 18),
        market_cap DECIMAL(65, 2),
        fully_diluted_market_cap DECIMAL(65, 2),
        tvl DECIMAL(65, 18),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    print("Таблица cmc_crypto создана или уже существует")


def save_crypto_listings_to_db(listings, conn):
    """
    Сохранение данных о листингах криптовалют в базу данных.
    Использует пакетную обработку для ускорения операций.
    """
    cursor = conn.cursor()

    # Подготавливаем SQL запрос для вставки или обновления данных (UPSERT)
    upsert_sql = '''
    INSERT INTO cmc_crypto (
        id, name, symbol, slug, num_market_pairs, date_added, tags,
        max_supply, circulating_supply, total_supply, infinite_supply,
        cmc_rank, last_updated, price_usd, volume_24h, percent_change_1h,
        percent_change_24h, percent_change_7d, percent_change_30d,
        percent_change_60d, percent_change_90d, market_cap,
        fully_diluted_market_cap, tvl
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        symbol = VALUES(symbol),
        slug = VALUES(slug),
        num_market_pairs = VALUES(num_market_pairs),
        date_added = VALUES(date_added),
        tags = VALUES(tags),
        max_supply = VALUES(max_supply),
        circulating_supply = VALUES(circulating_supply),
        total_supply = VALUES(total_supply),
        infinite_supply = VALUES(infinite_supply),
        cmc_rank = VALUES(cmc_rank),
        last_updated = VALUES(last_updated),
        price_usd = VALUES(price_usd),
        volume_24h = VALUES(volume_24h),
        percent_change_1h = VALUES(percent_change_1h),
        percent_change_24h = VALUES(percent_change_24h),
        percent_change_7d = VALUES(percent_change_7d),
        percent_change_30d = VALUES(percent_change_30d),
        percent_change_60d = VALUES(percent_change_60d),
        percent_change_90d = VALUES(percent_change_90d),
        market_cap = VALUES(market_cap),
        fully_diluted_market_cap = VALUES(fully_diluted_market_cap),
        tvl = VALUES(tvl)
    '''

    # Размер пакета для обработки
    batch_size = 100
    total_processed = 0

    # Получаем список всех существующих ID для подсчета статистики
    cursor.execute("SELECT id FROM cmc_crypto")
    existing_ids = {row[0] for row in cursor.fetchall()}

    # Подготавливаем пакеты данных
    print("Подготовка данных для пакетной обработки...")
    all_values = []

    for crypto in listings:
        quote = crypto.get('quote', {}).get('USD', {})

        # Преобразование списка тегов в строку, разделенную запятыми
        tags = ','.join(crypto.get('tags', [])) if crypto.get('tags') else None

        values = (
            crypto.get('id'),
            crypto.get('name'),
            crypto.get('symbol'),
            crypto.get('slug'),
            crypto.get('num_market_pairs'),
            crypto.get('date_added'),
            tags,
            crypto.get('max_supply'),
            crypto.get('circulating_supply'),
            crypto.get('total_supply'),
            crypto.get('infinite_supply'),
            crypto.get('cmc_rank'),
            crypto.get('last_updated'),
            quote.get('price'),
            quote.get('volume_24h'),
            quote.get('percent_change_1h'),
            quote.get('percent_change_24h'),
            quote.get('percent_change_7d'),
            quote.get('percent_change_30d'),
            quote.get('percent_change_60d'),
            quote.get('percent_change_90d'),
            quote.get('market_cap'),
            quote.get('fully_diluted_market_cap'),
            quote.get('tvl')
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
    cursor.execute("SELECT id FROM cmc_crypto")
    current_ids = {row[0] for row in cursor.fetchall()}

    inserted_count = len(current_ids - existing_ids)
    updated_count = len(all_values) - inserted_count

    print(
        f"Добавлено {inserted_count} новых криптовалют и обновлено {updated_count} существующих криптовалют в базе данных")


def main():
    try:
        import time
        start_time = time.time()

        # Получение данных о листингах криптовалют из API
        print("Получение данных о листингах криптовалют из API CoinMarketCap...")
        listings = fetch_all_crypto_listings()

        api_time = time.time()
        print(f"API запросы заняли {api_time - start_time:.2f} секунд")

        if not listings:
            print("Не удалось получить данные о листингах криптовалют.")
            return

        print(f"Успешно получено {len(listings)} листингов криптовалют")

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Создание таблицы cmc_crypto
        create_crypto_listings_table(conn)

        # Сохранение данных в базу
        save_crypto_listings_to_db(listings, conn)

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