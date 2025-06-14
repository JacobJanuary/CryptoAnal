#!/usr/bin/env python3
"""
Скрипт для создания связей между категориями и криптовалютами в PostgreSQL.
Предназначен для запуска через cron раз в неделю.

Пример crontab записи (каждое воскресенье в 02:00):
0 2 * * 0 /usr/bin/python3 /path/to/cmc_category_relations_postgresql.py

Автор: Crypto Data Processor
Дата создания: 2025
"""

import requests
import os
import psycopg2
import psycopg2.extras
import time
import datetime
import logging
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cmc_category_relations.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

# Конфигурация API лимитов
API_DELAY = float(os.getenv('API_DELAY', '1.0'))  # Задержка между запросами в секундах
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))  # Размер пакета для обработки


def log_message(message, level="info"):
    """Логирование с временной меткой."""
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


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
        log_message(f"Ошибка подключения к базе данных: {err}", "error")
        raise


def fetch_categories_from_db(conn):
    """
    Получение всех категорий из базы данных с дополнительной информацией
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Получаем категории с информацией о последнем обновлении связей
    cursor.execute('''
                   SELECT c.id,
                          c.name,
                          c.num_tokens,
                          MAX(cr.last_updated) as last_relations_update,
                          COUNT(cr.coin_id)    as current_relations_count
                   FROM categories c
                            LEFT JOIN cmc_category_relations cr ON c.id = cr.category_id
                   GROUP BY c.id, c.name, c.num_tokens
                   ORDER BY c.num_tokens DESC NULLS LAST
                   ''')

    categories = cursor.fetchall()
    log_message(f"Получено {len(categories)} категорий из базы данных")

    return categories


def fetch_category_coins(category_id, limit=1000):
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
        'limit': limit
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            log_message(f"Превышен лимит API для категории {category_id}, ожидание...", "warning")
            time.sleep(60)  # Ждем минуту при превышении лимита
            return None
        else:
            log_message(f"Ошибка при запросе категории {category_id}: {response.status_code}", "error")
            log_message(f"Ответ API: {response.text}", "error")
            return None

    except requests.exceptions.RequestException as e:
        log_message(f"Ошибка сети при запросе категории {category_id}: {e}", "error")
        return None


def create_relations_table(conn):
    """
    Создание оптимизированной таблицы связей категорий и монет с индексами
    """
    cursor = conn.cursor()

    # Создание основной таблицы связей
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS cmc_category_relations
                   (
                       relation_id
                       SERIAL
                       PRIMARY
                       KEY,
                       category_id
                       VARCHAR
                   (
                       255
                   ) NOT NULL,
                       coin_id BIGINT NOT NULL,
                       coin_name VARCHAR
                   (
                       255
                   ),
                       coin_symbol VARCHAR
                   (
                       50
                   ),
                       coin_rank INTEGER,
                       market_cap DECIMAL
                   (
                       30,
                       6
                   ),
                       price_usd DECIMAL
                   (
                       20,
                       8
                   ),
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       UNIQUE
                   (
                       category_id,
                       coin_id
                   )
                       )
                   ''')

    # Создание индексов для оптимизации запросов
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_category_relations_category_id ON cmc_category_relations(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_category_relations_coin_id ON cmc_category_relations(coin_id)",
        "CREATE INDEX IF NOT EXISTS idx_category_relations_last_updated ON cmc_category_relations(last_updated DESC)",
        "CREATE INDEX IF NOT EXISTS idx_category_relations_market_cap ON cmc_category_relations(market_cap DESC)",
        "CREATE INDEX IF NOT EXISTS idx_category_relations_coin_rank ON cmc_category_relations(coin_rank)",
        "CREATE INDEX IF NOT EXISTS idx_category_relations_composite ON cmc_category_relations(category_id, market_cap DESC)",
    ]

    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
        except psycopg2.Error as e:
            log_message(f"Ошибка создания индекса: {e}", "warning")

    # Создание триггера для автоматического обновления last_updated
    cursor.execute('''
                   CREATE
                   OR REPLACE FUNCTION update_relation_updated_at()
    RETURNS TRIGGER AS $$
                   BEGIN
        NEW.last_updated
                   = CURRENT_TIMESTAMP;
                   RETURN NEW;
                   END;
    $$
                   language 'plpgsql';
                   ''')

    cursor.execute('''
    DROP TRIGGER IF EXISTS update_relations_updated_at ON cmc_category_relations;
    CREATE TRIGGER update_relations_updated_at
        BEFORE UPDATE ON cmc_category_relations
        FOR EACH ROW
        EXECUTE FUNCTION update_relation_updated_at();
    ''')

    # Создание таблицы для отслеживания процесса обновления
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS cmc_update_log
                   (
                       log_id
                       SERIAL
                       PRIMARY
                       KEY,
                       process_type
                       VARCHAR
                   (
                       50
                   ) NOT NULL,
                       category_id VARCHAR
                   (
                       255
                   ),
                       status VARCHAR
                   (
                       20
                   ) NOT NULL,
                       records_processed INTEGER DEFAULT 0,
                       error_message TEXT,
                       started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       completed_at TIMESTAMP
                       )
                   ''')

    conn.commit()
    log_message("Таблицы связей созданы с оптимизированными индексами")


def save_category_coins_relations(conn, category_id, category_name, coins):
    """
    Сохранение связей категорий и монет в базу данных с пакетной обработкой
    """
    if not coins:
        log_message(f"Нет монет для категории {category_name}")
        return 0, 0

    cursor = conn.cursor()

    # Логируем начало процесса
    cursor.execute('''
                   INSERT INTO cmc_update_log (process_type, category_id, status, records_processed)
                   VALUES (%s, %s, %s, %s) RETURNING log_id
                   ''', ('category_relations', category_id, 'started', len(coins)))

    log_id = cursor.fetchone()[0]
    conn.commit()

    try:
        # Подготавливаем данные для пакетной обработки
        upsert_sql = '''
                     INSERT INTO cmc_category_relations (category_id, coin_id, coin_name, coin_symbol, \
                                                         coin_rank, market_cap, price_usd) \
                     VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (category_id, coin_id) DO \
                     UPDATE SET
                         coin_name = EXCLUDED.coin_name, \
                         coin_symbol = EXCLUDED.coin_symbol, \
                         coin_rank = EXCLUDED.coin_rank, \
                         market_cap = EXCLUDED.market_cap, \
                         price_usd = EXCLUDED.price_usd, \
                         last_updated = CURRENT_TIMESTAMP \
                     '''

        # Получаем существующие связи для подсчета статистики
        cursor.execute('''
                       SELECT coin_id
                       FROM cmc_category_relations
                       WHERE category_id = %s
                       ''', (category_id,))
        existing_coin_ids = {row[0] for row in cursor.fetchall()}

        batch_data = []
        new_coin_ids = set()

        for coin in coins:
            quote = coin.get('quote', {}).get('USD', {})

            coin_id = coin.get('id')
            new_coin_ids.add(coin_id)

            values = (
                category_id,
                coin_id,
                coin.get('name'),
                coin.get('symbol'),
                coin.get('cmc_rank'),
                quote.get('market_cap'),
                quote.get('price')
            )
            batch_data.append(values)

        # Выполняем пакетную операцию
        psycopg2.extras.execute_batch(cursor, upsert_sql, batch_data, page_size=BATCH_SIZE)

        # Удаляем устаревшие связи (монеты, которые больше не в категории)
        coins_to_remove = existing_coin_ids - new_coin_ids
        if coins_to_remove:
            cursor.execute('''
                           DELETE
                           FROM cmc_category_relations
                           WHERE category_id = %s
                             AND coin_id = ANY (%s)
                           ''', (category_id, list(coins_to_remove)))
            log_message(f"Удалено {len(coins_to_remove)} устаревших связей для категории {category_name}")

        conn.commit()

        # Подсчитываем статистику
        new_relations = len(new_coin_ids - existing_coin_ids)
        updated_relations = len(new_coin_ids & existing_coin_ids)

        # Обновляем лог успешного завершения
        cursor.execute('''
                       UPDATE cmc_update_log
                       SET status            = %s,
                           completed_at      = CURRENT_TIMESTAMP,
                           records_processed = %s
                       WHERE log_id = %s
                       ''', ('completed', len(batch_data), log_id))
        conn.commit()

        log_message(
            f"Категория {category_name}: добавлено {new_relations} новых, обновлено {updated_relations} существующих связей")
        return new_relations, updated_relations

    except Exception as e:
        # Логируем ошибку
        cursor.execute('''
                       UPDATE cmc_update_log
                       SET status        = %s,
                           error_message = %s,
                           completed_at  = CURRENT_TIMESTAMP
                       WHERE log_id = %s
                       ''', ('error', str(e), log_id))
        conn.commit()
        raise


def cleanup_old_logs(conn, days_to_keep=30):
    """
    Очистка старых логов обновления
    """
    cursor = conn.cursor()
    cursor.execute('''
                   DELETE
                   FROM cmc_update_log
                   WHERE started_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
                   ''', (days_to_keep,))

    deleted_count = cursor.rowcount
    conn.commit()

    if deleted_count > 0:
        log_message(f"Удалено {deleted_count} старых записей из лога обновлений")


def get_update_statistics(conn):
    """
    Получение статистики обновления
    """
    cursor = conn.cursor()

    # Общая статистика по связям
    cursor.execute('''
                   SELECT COUNT(DISTINCT category_id) as categories_count,
                          COUNT(*)                    as total_relations,
                          COUNT(DISTINCT coin_id)     as unique_coins,
                          AVG(market_cap)             as avg_market_cap
                   FROM cmc_category_relations
                   ''')

    stats = cursor.fetchone()
    if stats:
        categories_count, total_relations, unique_coins, avg_market_cap = stats
        log_message(f"Статистика связей:")
        log_message(f"  - Категорий с монетами: {categories_count}")
        log_message(f"  - Всего связей: {total_relations}")
        log_message(f"  - Уникальных монет: {unique_coins}")
        log_message(
            f"  - Средняя рыночная капитализация: ${avg_market_cap:,.2f}" if avg_market_cap else "  - Средняя рыночная капитализация: N/A")

    # Топ категории по количеству монет
    cursor.execute('''
                   SELECT cr.category_id,
                          c.name,
                          COUNT(cr.coin_id)  as coins_count,
                          SUM(cr.market_cap) as total_market_cap
                   FROM cmc_category_relations cr
                            LEFT JOIN categories c ON cr.category_id = c.id
                   GROUP BY cr.category_id, c.name
                   ORDER BY coins_count DESC LIMIT 5
                   ''')

    top_categories = cursor.fetchall()
    if top_categories:
        log_message("Топ-5 категорий по количеству монет:")
        for i, (cat_id, name, coins_count, total_cap) in enumerate(top_categories, 1):
            cap_str = f"${total_cap:,.2f}" if total_cap else "N/A"
            log_message(f"  {i}. {name or cat_id}: {coins_count} монет, капитализация: {cap_str}")


def process_all_categories():
    """
    Обработка всех категорий и сохранение связей с монетами
    """
    try:
        start_time = time.time()
        log_message("=== Начало процесса обновления связей категорий ===")

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Создание таблиц связей
        create_relations_table(conn)

        # Очистка старых логов
        cleanup_old_logs(conn)

        # Получение всех категорий из базы данных
        categories = fetch_categories_from_db(conn)

        if not categories:
            log_message("Нет категорий для обработки", "warning")
            return

        total_new_relations = 0
        total_updated_relations = 0
        processed_categories = 0
        failed_categories = 0

        # Обработка каждой категории
        for category in categories:
            category_id = category['id']
            category_name = category['name']
            expected_tokens = category.get('num_tokens', 0)

            log_message(
                f"Обработка категории: {category_name} (ID: {category_id}, ожидается {expected_tokens} токенов)")

            try:
                # Получение монет для категории
                response = fetch_category_coins(category_id)

                if response and 'data' in response:
                    data = response['data']
                    coins = data.get('coins', [])

                    log_message(f"Получено {len(coins)} монет для категории {category_name}")

                    # Сохранение связей в базу данных
                    new_relations, updated_relations = save_category_coins_relations(
                        conn, category_id, category_name, coins
                    )

                    total_new_relations += new_relations
                    total_updated_relations += updated_relations

                else:
                    log_message(f"Не удалось получить данные для категории {category_name}", "warning")
                    failed_categories += 1

            except Exception as e:
                log_message(f"Ошибка обработки категории {category_name}: {str(e)}", "error")
                failed_categories += 1

            processed_categories += 1

            # Прогресс-бар
            progress = (processed_categories / len(categories)) * 100
            log_message(f"Прогресс: {processed_categories}/{len(categories)} ({progress:.1f}%)")

            # Добавляем задержку, чтобы избежать превышения лимитов API
            time.sleep(API_DELAY)

        # Получение финальной статистики
        get_update_statistics(conn)

        # Закрытие соединения с базой данных
        conn.close()

        total_time = time.time() - start_time
        log_message("=== Результаты обновления ===")
        log_message(f"Успешно обработано категорий: {processed_categories - failed_categories}")
        log_message(f"Неудачных категорий: {failed_categories}")
        log_message(f"Новых связей добавлено: {total_new_relations}")
        log_message(f"Существующих связей обновлено: {total_updated_relations}")
        log_message(f"Общее время выполнения: {total_time:.2f} секунд")
        log_message("=== Процесс завершен ===")

    except Exception as e:
        log_message(f"Критическая ошибка: {str(e)}", "error")
        raise


if __name__ == "__main__":
    process_all_categories()