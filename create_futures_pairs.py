import os
import sys
import logging
import requests
import psycopg2
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- Загрузка переменных окружения из .env файла ---
load_dotenv()

# --- Конфигурация логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

# --- Константы ---
EXCHANGES = {'binance': 1, 'bybit': 2}
# ОБНОВЛЕНО: Добавлен тип контракта 'SPOT'
CONTRACT_TYPES = {'PERPETUAL': 1, 'SPOT': 2}
# Белый список квотируемых активов для фильтрации
ALLOWED_QUOTE_ASSETS = {'USDT', 'USDC', 'BUSD', 'BTC'}  # BUSD для совместимости со старыми парами Binance


def get_db_connection():
    """
    Устанавливает соединение с БД, используя переменные окружения.
    Возвращает объект соединения psycopg2.
    """
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT")
        )
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        sys.exit(1)


def setup_database():
    """
    Создает необходимые для скрипта таблицы, индексы и заполняет начальные данные.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            logging.info("Настройка структуры базы данных...")
            # Таблица типов контрактов
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS contract_type
                        (
                            id
                            SMALLINT
                            PRIMARY
                            KEY,
                            contract_type_name
                            VARCHAR
                        (
                            50
                        ) UNIQUE NOT NULL
                            );
                        """)
            # Заполнение типов контрактов
            cur.execute("""
                        INSERT INTO contract_type (id, contract_type_name)
                        VALUES (%s, 'PERPETUAL'),
                               (%s, 'SPOT') ON CONFLICT (id) DO NOTHING;
                        """, (CONTRACT_TYPES['PERPETUAL'], CONTRACT_TYPES['SPOT']))

            # Таблица токенов
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS tokens
                        (
                            id
                            SERIAL
                            PRIMARY
                            KEY,
                            symbol
                            VARCHAR
                        (
                            20
                        ) UNIQUE NOT NULL,
                            cmc_token_id INTEGER
                            );
                        """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tokens_symbol ON tokens(symbol);")

            # Таблица торговых пар
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS trading_pairs
                        (
                            id
                            SERIAL
                            PRIMARY
                            KEY,
                            token_id
                            INTEGER
                            NOT
                            NULL
                            REFERENCES
                            tokens
                        (
                            id
                        ) ON DELETE CASCADE,
                            exchange_id SMALLINT NOT NULL,
                            pair_symbol VARCHAR
                        (
                            30
                        ) NOT NULL,
                            contract_type_id SMALLINT NOT NULL REFERENCES contract_type
                        (
                            id
                        ),
                            created_at TIMESTAMP
                          WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP
                          WITH TIME ZONE DEFAULT NOW(),
                            CONSTRAINT uq_trading_pair UNIQUE
                        (
                            token_id,
                            exchange_id,
                            pair_symbol,
                            contract_type_id
                        )
                            );
                        """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_trading_pairs_token_id ON trading_pairs(token_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_trading_pairs_exchange_id ON trading_pairs(exchange_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_trading_pairs_pair_symbol ON trading_pairs(pair_symbol);")

            conn.commit()
            logging.info("Структура базы данных успешно настроена.")
    except psycopg2.Error as e:
        logging.error(f"Ошибка при настройке БД: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()


def fetch_cmc_data_from_db() -> dict[str, int]:
    """
    Загружает данные из таблицы cmc_crypto для сопоставления.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT symbol, MIN(id) FROM cmc_crypto GROUP BY symbol;")
            cmc_records = cur.fetchall()
            cmc_map = dict(cmc_records)
            logging.info(f"Загружено {len(cmc_map)} уникальных токенов из таблицы cmc_crypto.")
            return cmc_map
    except psycopg2.errors.UndefinedTable:
        logging.warning("Таблица `cmc_crypto` не найдена. Продолжение работы без сопоставления с CMC ID.")
        return {}
    except psycopg2.Error as e:
        logging.error(f"Ошибка при загрузке данных из cmc_crypto: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def fetch_binance_pairs() -> list[dict]:
    """Получает активные фьючерсные пары с Binance."""
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        pairs = [
            {
                'base_asset': item['baseAsset'],
                'pair_symbol': item['symbol'],
                'exchange': 'binance',
                'contract_type': 'PERPETUAL'  # ИЗМЕНЕНИЕ: Добавлен тип контракта
            }
            for item in data.get('symbols', [])
            if item.get('status') == 'TRADING'
               and item.get('contractType') == 'PERPETUAL'
               and item.get('quoteAsset') in ALLOWED_QUOTE_ASSETS
        ]
        logging.info(f"Binance Futures: Найдено {len(pairs)} активных PERPETUAL пар.")
        return pairs
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе к API Binance Futures: {e}")
        return []


# НОВАЯ ФУНКЦИЯ
def fetch_binance_spot_pairs() -> list[dict]:
    """Получает активные спотовые пары с Binance."""
    url = "https://api.binance.com/api/v3/exchangeInfo"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        pairs = [
            {
                'base_asset': item['baseAsset'],
                'pair_symbol': item['symbol'],
                'exchange': 'binance',
                'contract_type': 'SPOT'  # Тип контракта - спот
            }
            for item in data.get('symbols', [])
            if item.get('status') == 'TRADING'
               and item.get('quoteAsset') in ALLOWED_QUOTE_ASSETS
        ]
        logging.info(f"Binance Spot: Найдено {len(pairs)} активных SPOT пар.")
        return pairs
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе к API Binance Spot: {e}")
        return []


def fetch_bybit_pairs() -> list[dict]:
    """Получает активные фьючерсные пары с Bybit."""
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {'category': 'linear'}
    pairs = []
    try:
        while True:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            for item in data.get('result', {}).get('list', []):
                if (item.get('status') == 'Trading'
                        and item.get('contractType') == 'LinearPerpetual'
                        and item.get('quoteCoin') in ALLOWED_QUOTE_ASSETS):
                    pairs.append({
                        'base_asset': item['baseCoin'],
                        'pair_symbol': item['symbol'],
                        'exchange': 'bybit',
                        'contract_type': 'PERPETUAL'  # ИЗМЕНЕНИЕ: Добавлен тип контракта
                    })
            cursor = data.get('result', {}).get('nextPageCursor')
            if cursor:
                params['cursor'] = cursor
            else:
                break
        logging.info(f"Bybit Futures: Найдено {len(pairs)} активных LINEAR PERPETUAL пар.")
        return pairs
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе к API Bybit Futures: {e}")
        return []


# НОВАЯ ФУНКЦИЯ
def fetch_bybit_spot_pairs() -> list[dict]:
    """Получает активные спотовые пары с Bybit."""
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {'category': 'spot'}  # Категория для спота
    pairs = []
    try:
        while True:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            for item in data.get('result', {}).get('list', []):
                if (item.get('status') == 'Trading'
                        and item.get('quoteCoin') in ALLOWED_QUOTE_ASSETS):
                    pairs.append({
                        'base_asset': item['baseCoin'],
                        'pair_symbol': item['symbol'],
                        'exchange': 'bybit',
                        'contract_type': 'SPOT'  # Тип контракта - спот
                    })
            cursor = data.get('result', {}).get('nextPageCursor')
            if cursor:
                params['cursor'] = cursor
            else:
                break
        logging.info(f"Bybit Spot: Найдено {len(pairs)} активных SPOT пар.")
        return pairs
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе к API Bybit Spot: {e}")
        return []


# ОБНОВЛЕННАЯ ФУНКЦИЯ
def process_and_store_data(all_pairs: list[dict], cmc_map: dict[str, int]):
    """Обрабатывает и сохраняет данные о токенах и торговых парах в БД."""
    if not all_pairs:
        logging.warning("Нет данных для обработки.")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Вставка уникальных токенов
            unique_base_assets = {p['base_asset'] for p in all_pairs}
            logging.info(f"Обнаружено {len(unique_base_assets)} уникальных базовых активов для обработки.")
            token_insert_data = [(asset, cmc_map.get(asset)) for asset in unique_base_assets]
            cur.executemany("""
                            INSERT INTO tokens (symbol, cmc_token_id)
                            VALUES (%s, %s) ON CONFLICT (symbol) DO NOTHING;
                            """, token_insert_data)
            logging.info(f"Таблица 'tokens' обновлена.")

            # Получаем актуальный ID токенов из БД
            cur.execute("SELECT symbol, id FROM tokens;")
            db_token_map = dict(cur.fetchall())

            # Подготовка данных для вставки пар
            pairs_insert_data = [
                (
                    db_token_map[pair['base_asset']],
                    EXCHANGES[pair['exchange']],
                    pair['pair_symbol'],
                    # ИЗМЕНЕНИЕ: Динамическое получение ID типа контракта
                    CONTRACT_TYPES[pair['contract_type']],
                    datetime.now(timezone.utc)
                )
                for pair in all_pairs if pair['base_asset'] in db_token_map
            ]

            # Вставка/обновление торговых пар
            cur.executemany("""
                            INSERT INTO trading_pairs (token_id, exchange_id, pair_symbol, contract_type_id, updated_at)
                            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (token_id, exchange_id, pair_symbol, contract_type_id)
                DO
                            UPDATE SET updated_at = EXCLUDED.updated_at;
                            """, pairs_insert_data)

            logging.info(f"Вставлено/обновлено {len(pairs_insert_data)} торговых пар в БД.")
            conn.commit()
    except psycopg2.Error as e:
        logging.error(f"Ошибка при работе с БД: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()


# ОБНОВЛЕННАЯ ФУНКЦИЯ
def main():
    """Основная функция для запуска скрипта."""
    logging.info("🚀 Запуск скрипта синхронизации торговых пар...")
    setup_database()
    cmc_map = fetch_cmc_data_from_db()

    # Сбор всех пар (фьючерсы + спот)
    binance_futures_pairs = fetch_binance_pairs()
    bybit_futures_pairs = fetch_bybit_pairs()
    binance_spot_pairs = fetch_binance_spot_pairs()
    bybit_spot_pairs = fetch_bybit_spot_pairs()

    all_pairs = binance_futures_pairs + bybit_futures_pairs + binance_spot_pairs + bybit_spot_pairs

    logging.info(f"Всего собрано {len(all_pairs)} пар для обработки.")

    process_and_store_data(all_pairs, cmc_map)
    logging.info("✅ Скрипт успешно завершил работу.")


if __name__ == "__main__":
    required_vars = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"]
    if not all(os.getenv(var) for var in required_vars):
        logging.error(
            f"Одна или несколько переменных окружения отсутствуют. Убедитесь, что в .env файле есть все из списка: {required_vars}"
        )
    else:
        main()