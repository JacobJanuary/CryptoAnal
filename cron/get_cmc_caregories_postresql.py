import requests
import os
import psycopg2
import psycopg2.extras
import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация API
API_KEY = os.getenv('CMC_API_KEY')
if not API_KEY:
    raise ValueError("API ключ не найден. Пожалуйста, установите переменную CMC_API_KEY в файле .env")

# Конфигурация базы данных PostgreSQL
DB_NAME = os.getenv('POSTGRES_DB', 'crypto_db')
DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')


def log_message(message):
    """Выводит сообщение с временной меткой."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} - {message}")


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
        log_message(f"Ошибка: {response.status_code}")
        log_message(response.text)
        return None


def create_database_connection():
    """
    Создание подключения к базе данных PostgreSQL
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=int(DB_PORT)
        )
        log_message("Подключение к базе данных PostgreSQL успешно установлено")
        return conn
    except psycopg2.Error as err:
        log_message(f"Ошибка подключения к базе данных: {err}")
        raise


def create_categories_table(conn):
    """
    Создание таблицы категорий в базе данных PostgreSQL с оптимальной структурой и индексами
    """
    cursor = conn.cursor()

    # Создание таблицы categories, если она не существует
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS categories
                   (
                       id
                       VARCHAR
                   (
                       255
                   ) PRIMARY KEY,
                       name VARCHAR
                   (
                       255
                   ) NOT NULL,
                       title VARCHAR
                   (
                       500
                   ),
                       description TEXT,
                       num_tokens INTEGER DEFAULT 0,
                       last_updated TIMESTAMP,
                       avg_price_change DECIMAL
                   (
                       20,
                       8
                   ),
                       market_cap DECIMAL
                   (
                       30,
                       6
                   ),
                       market_cap_change DECIMAL
                   (
                       20,
                       9
                   ),
                       volume DECIMAL
                   (
                       30,
                       7
                   ),
                       volume_change DECIMAL
                   (
                       20,
                       9
                   ),
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       )
                   ''')

    # Создание индексов для оптимизации запросов
    indexes = [
        # Индекс для поиска по названию категории
        "CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name)",

        # Индекс для сортировки по рыночной капитализации
        "CREATE INDEX IF NOT EXISTS idx_categories_market_cap ON categories(market_cap DESC)",

        # Индекс для сортировки по объему торгов
        "CREATE INDEX IF NOT EXISTS idx_categories_volume ON categories(volume DESC)",

        # Индекс для сортировки по количеству токенов
        "CREATE INDEX IF NOT EXISTS idx_categories_num_tokens ON categories(num_tokens DESC)",

        # Индекс для фильтрации по изменению цены
        "CREATE INDEX IF NOT EXISTS idx_categories_avg_price_change ON categories(avg_price_change)",

        # Индекс для временных запросов
        "CREATE INDEX IF NOT EXISTS idx_categories_last_updated ON categories(last_updated DESC)",

        # Индекс для audit trail
        "CREATE INDEX IF NOT EXISTS idx_categories_updated_at ON categories(updated_at DESC)",

        # Составной индекс для популярных запросов (категории с большой капитализацией)
        "CREATE INDEX IF NOT EXISTS idx_categories_cap_tokens ON categories(market_cap DESC, num_tokens DESC)",

        # Индекс для поиска активно торгуемых категорий
        "CREATE INDEX IF NOT EXISTS idx_categories_volume_change ON categories(volume DESC, volume_change)",

        # Partial index для категорий с положительным изменением цены
        "CREATE INDEX IF NOT EXISTS idx_categories_positive_change ON categories(market_cap DESC) WHERE avg_price_change > 0"
    ]

    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
            log_message(
                f"Индекс создан: {index_sql.split('idx_')[1].split(' ')[0] if 'idx_' in index_sql else 'unknown'}")
        except psycopg2.Error as e:
            log_message(f"Ошибка создания индекса: {e}")

    # Создание триггера для автоматического обновления updated_at
    cursor.execute('''
                   CREATE
                   OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
                   BEGIN
        NEW.updated_at
                   = CURRENT_TIMESTAMP;
                   RETURN NEW;
                   END;
    $$
                   language 'plpgsql';
                   ''')

    cursor.execute('''
    DROP TRIGGER IF EXISTS update_categories_updated_at ON categories;
    CREATE TRIGGER update_categories_updated_at
        BEFORE UPDATE ON categories
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    ''')

    conn.commit()
    log_message("Таблица categories создана или уже существует с оптимизированными индексами")


def save_categories_to_db(categories, conn):
    """
    Сохранение данных о категориях в базу данных PostgreSQL.
    Обновляет существующие записи или добавляет новые.
    """
    cursor = conn.cursor()

    # Подготавливаем SQL запрос для вставки или обновления данных (UPSERT)
    upsert_sql = '''
                 INSERT INTO categories (id, name, title, description, num_tokens, last_updated, \
                                         avg_price_change, market_cap, market_cap_change, volume, volume_change) \
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO \
                 UPDATE SET
                     name = EXCLUDED.name, \
                     title = EXCLUDED.title, \
                     description = EXCLUDED.description, \
                     num_tokens = EXCLUDED.num_tokens, \
                     last_updated = EXCLUDED.last_updated, \
                     avg_price_change = EXCLUDED.avg_price_change, \
                     market_cap = EXCLUDED.market_cap, \
                     market_cap_change = EXCLUDED.market_cap_change, \
                     volume = EXCLUDED.volume, \
                     volume_change = EXCLUDED.volume_change, \
                     updated_at = CURRENT_TIMESTAMP \
                 '''

    # Получаем список всех существующих ID для подсчета статистики
    cursor.execute("SELECT id FROM categories")
    existing_ids = {row[0] for row in cursor.fetchall()}

    # Подготавливаем данные для пакетной обработки
    log_message("Подготовка данных категорий для пакетной обработки...")
    batch_data = []

    for category in categories:
        # Преобразование строковой даты в объект datetime для PostgreSQL
        last_updated = None
        if category.get('last_updated'):
            try:
                last_updated = datetime.datetime.fromisoformat(category.get('last_updated').replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                last_updated = None

        values = (
            category.get('id'),
            category.get('name'),
            category.get('title'),
            category.get('description'),
            category.get('num_tokens', 0),
            last_updated,
            category.get('avg_price_change'),
            category.get('market_cap'),
            category.get('market_cap_change'),
            category.get('volume'),
            category.get('volume_change')
        )

        batch_data.append(values)

    # Выполняем пакетную операцию
    log_message(f"Выполнение пакетной операции для {len(batch_data)} категорий...")
    psycopg2.extras.execute_batch(cursor, upsert_sql, batch_data)
    conn.commit()

    # Подсчитываем количество новых и обновленных записей
    cursor.execute("SELECT id FROM categories")
    current_ids = {row[0] for row in cursor.fetchall()}

    new_category_ids = {values[0] for values in batch_data}
    inserted_count = len(new_category_ids - existing_ids)
    updated_count = len(batch_data) - inserted_count

    log_message(
        f"Добавлено {inserted_count} новых категорий и обновлено {updated_count} существующих категорий в базе данных")

    # Выводим статистику по топ категориям
    cursor.execute('''
                   SELECT name, market_cap, num_tokens, avg_price_change
                   FROM categories
                   WHERE market_cap IS NOT NULL
                   ORDER BY market_cap DESC LIMIT 5
                   ''')

    top_categories = cursor.fetchall()
    if top_categories:
        log_message("Топ-5 категорий по рыночной капитализации:")
        for i, (name, market_cap, num_tokens, price_change) in enumerate(top_categories, 1):
            log_message(f"  {i}. {name}: ${market_cap:,.2f} ({num_tokens} токенов, {price_change:.2f}% изменение)")


def analyze_categories_data(conn):
    """
    Анализ данных категорий для получения полезной статистики
    """
    cursor = conn.cursor()

    log_message("Анализ данных категорий...")

    # Общая статистика
    cursor.execute('''
                   SELECT COUNT(*)                                         as total_categories,
                          COUNT(CASE WHEN avg_price_change > 0 THEN 1 END) as growing_categories,
                          COUNT(CASE WHEN avg_price_change < 0 THEN 1 END) as declining_categories,
                          ROUND(AVG(num_tokens), 2)                        as avg_tokens_per_category,
                          SUM(market_cap)                                  as total_market_cap
                   FROM categories
                   WHERE market_cap IS NOT NULL
                   ''')

    stats = cursor.fetchone()
    if stats:
        total, growing, declining, avg_tokens, total_cap = stats
        log_message(f"Общая статистика:")
        log_message(f"  - Всего категорий: {total}")
        log_message(f"  - Растущие категории: {growing}")
        log_message(f"  - Падающие категории: {declining}")
        log_message(f"  - Среднее количество токенов: {avg_tokens}")
        log_message(
            f"  - Общая рыночная капитализация: ${total_cap:,.2f}" if total_cap else "  - Общая рыночная капитализация: N/A")


def main():
    try:
        import time
        start_time = time.time()

        # Получение категорий из API
        log_message("Получение данных о категориях из API CoinMarketCap...")
        categories = fetch_categories()

        api_time = time.time()
        log_message(f"API запрос занял {api_time - start_time:.2f} секунд")

        if not categories:
            log_message("Не удалось получить данные о категориях.")
            return

        log_message(f"Успешно получено {len(categories)} категорий")

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Создание таблицы categories с индексами
        create_categories_table(conn)

        # Сохранение данных в базу
        save_categories_to_db(categories, conn)

        # Анализ данных
        analyze_categories_data(conn)

        db_time = time.time()
        log_message(f"Работа с базой данных заняла {db_time - api_time:.2f} секунд")

        # Закрытие соединения с базой данных
        conn.close()
        log_message("Соединение с базой данных закрыто")

        total_time = time.time() - start_time
        log_message(f"Общее время выполнения: {total_time:.2f} секунд")
        log_message("Процесс успешно завершен.")

    except Exception as e:
        log_message(f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
    main()