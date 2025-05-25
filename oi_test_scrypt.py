import asyncio
import logging
import os
import ssl
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import aiohttp
import certifi
import pymysql
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Настройка логирования
logging.basicConfig(
    filename="script.log",
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Конфигурация MySQL
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "your_user"),
    "password": os.getenv("MYSQL_PASSWORD", "your_password"),
    "database": os.getenv("MYSQL_DATABASE", "your_database"),
}

# Конфигурация API (пример для Binance)
BINANCE_API_URL = "https://fapi.binance.com"
COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY")


class APIError(Exception):
    """Исключение для ошибок API."""
    pass


async def fetch_json(session: aiohttp.ClientSession, url: str, params: Optional[Dict] = None) -> Dict:
    """Асинхронный запрос к API с получением JSON-ответа.

    Args:
        session: Сессия aiohttp для выполнения запроса.
        url: URL эндпоинта API.
        params: Параметры запроса.

    Returns:
        Словарь с данными ответа.

    Raises:
        APIError: Если запрос завершился с ошибкой.
    """
    headers = {}
    if "coinmarketcap" in url.lower():
        if not COINMARKETCAP_API_KEY:
            error_msg = "API-ключ CoinMarketCap не найден в переменной окружения COINMARKETCAP_API_KEY"
            logger.error(error_msg)
            raise APIError(error_msg)
        headers["X-CMC_PRO_API_KEY"] = COINMARKETCAP_API_KEY

    try:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                error_msg = f"Ошибка API: {response.status} {await response.text()}"
                logger.error(error_msg)
                raise APIError(error_msg)
            return await response.json()
    except aiohttp.ClientSSLError as e:
        error_msg = f"Ошибка SSL: {str(e)}. Проверьте сертификаты или сетевые настройки."
        logger.error(error_msg)
        raise APIError(error_msg)
    except aiohttp.ClientError as e:
        error_msg = f"Ошибка подключения: {str(e)}"
        logger.error(error_msg)
        raise APIError(error_msg)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(APIError),
)
async def get_binance_futures_pairs(session: aiohttp.ClientSession) -> List[Dict]:
    """Получение списка фьючерсных пар с Binance.

    Args:
        session: Сессия aiohttp.

    Returns:
        Список словарей с информацией о парах.

    Raises:
        APIError: Если запрос к API завершился с ошибкой.
    """
    logger.info("Запрос списка фьючерсных пар с Binance")
    data = await fetch_json(session, f"{BINANCE_API_URL}/fapi/v1/exchangeInfo")
    return data["symbols"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(APIError),
)
async def get_binance_open_interest(
    session: aiohttp.ClientSession, symbol: str
) -> Dict:
    """Получение открытого интереса для пары с Binance.

    Args:
        session: Сессия aiohttp.
        symbol: Символ пары (например, SUIUSDT).

    Returns:
        Словарь с данными об открытом интересе.

    Raises:
        APIError: Если запрос к API завершился с ошибкой.
    """
    logger.info(f"Запрос OI для {symbol} с Binance")
    return await fetch_json(
        session, f"{BINANCE_API_URL}/fapi/v1/openInterest", params={"symbol": symbol}
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(APIError),
)
async def get_binance_funding_rate(
    session: aiohttp.ClientSession, symbol: str
) -> Dict:
    """Получение фандинговой ставки для пары с Binance.

    Args:
        session: Сессия aiohttp.
        symbol: Символ пары (например, SUIUSDT).

    Returns:
        Словарь с данными о фандинговой ставке.

    Raises:
        APIError: Если запрос к API завершился с ошибкой.
    """
    logger.info(f"Запрос фандинговой ставки для {symbol} с Binance")
    return await fetch_json(
        session, f"{BINANCE_API_URL}/fapi/v1/premiumIndex", params={"symbol": symbol}
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(APIError),
)
async def get_binance_price(
    session: aiohttp.ClientSession, symbol: str
) -> Dict:
    """Получение текущей цены для пары с Binance.

    Args:
        session: Сессия aiohttp.
        symbol: Символ пары (например, SUIUSDT).

    Returns:
        Словарь с данными о цене.

    Raises:
        APIError: Если запрос к API завершился с ошибкой.
    """
    logger.info(f"Запрос цены для {symbol} с Binance")
    return await fetch_json(
        session, f"{BINANCE_API_URL}/fapi/v1/ticker/price", params={"symbol": symbol}
    )


async def get_btc_usd_price(session: aiohttp.ClientSession) -> Decimal:
    """Получение текущей цены BTC/USD с CoinMarketCap.

    Args:
        session: Сессия aiohttp.

    Returns:
        Цена BTC в USD.

    Raises:
        APIError: Если запрос к API завершился с ошибкой.
    """
    logger.info("Запрос цены BTC/USD с CoinMarketCap")
    data = await fetch_json(
        session,
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
        params={"symbol": "BTC"},
    )
    return Decimal(str(data["data"]["BTC"]["quote"]["USD"]["price"]))


def extract_token_symbol(pair_symbol: str) -> str:
    """Извлечение символа токена из пары.

    Args:
        pair_symbol: Символ пары (например, SUIUSDT).

    Returns:
        Символ токена (например, SUI).
    """
    return pair_symbol.replace("USDT", "").replace("USD", "")


def create_mysql_connection() -> pymysql.connections.Connection:
    """Создание соединения с MySQL.

    Returns:
        Объект соединения с базой данных.

    Raises:
        pymysql.MySQLError: Если соединение не удалось.
    """
    try:
        return pymysql.connect(
            **MYSQL_CONFIG,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except pymysql.MySQLError as e:
        logger.error(f"Ошибка подключения к MySQL: {str(e)}")
        raise


def save_token_to_db(connection: pymysql.connections.Connection, symbol: str) -> int:
    """Сохранение символа токена в таблицу tokens.

    Args:
        connection: Соединение с MySQL.
        symbol: Символ токена (например, SUI).

    Returns:
        ID токена.

    Raises:
        pymysql.MySQLError: Если запрос завершился с ошибкой.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT IGNORE INTO tokens (symbol) VALUES (%s)
            """,
            (symbol,),
        )
        cursor.execute("SELECT id FROM tokens WHERE symbol = %s", (symbol,))
        token_id = cursor.fetchone()["id"]
        connection.commit()
        return token_id


def save_pair_to_db(
    connection: pymysql.connections.Connection,
    token_id: int,
    exchange: str,
    pair_symbol: str,
) -> int:
    """Сохранение пары в таблицу futures_pairs.

    Args:
        connection: Соединение с MySQL.
        token_id: ID токена.
        exchange: Название биржи.
        pair_symbol: Символ пары.

    Returns:
        ID пары.

    Raises:
        pymysql.MySQLError: Если запрос завершился с ошибкой.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT IGNORE INTO futures_pairs (token_id, exchange, pair_symbol)
            VALUES (%s, %s, %s)
            """,
            (token_id, exchange, pair_symbol),
        )
        cursor.execute(
            """
            SELECT id FROM futures_pairs
            WHERE exchange = %s AND pair_symbol = %s
            """,
            (exchange, pair_symbol),
        )
        pair_id = cursor.fetchone()["id"]
        connection.commit()
        return pair_id


def save_futures_data(
    connection: pymysql.connections.Connection,
    pair_id: int,
    data: Dict,
) -> None:
    """Сохранение данных о фьючерсной паре в таблицу futures_data.

    Args:
        connection: Соединение с MySQL.
        pair_id: ID пары.
        data: Данные для сохранения.

    Raises:
        pymysql.MySQLError: Если запрос завершился с ошибкой.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO futures_data (
                pair_id, open_interest_contracts, open_interest_usd,
                funding_rate, volume_btc, price_usd
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                pair_id,
                data["open_interest_contracts"],
                data["open_interest_usd"],
                data["funding_rate"],
                data["volume_btc"],
                data["price_usd"],
            ),
        )
        connection.commit()


async def process_pair(
    session: aiohttp.ClientSession,
    pair: Dict,
    btc_usd_price: Decimal,
    connection: pymysql.connections.Connection,
) -> None:
    """Обработка данных для одной фьючерсной пары.

    Args:
        session: Сессия aiohttp.
        pair: Данные о паре.
        btc_usd_price: Цена BTC/USD.
        connection: Соединение с MySQL.
    """
    pair_symbol = pair["symbol"]
    try:
        # Извлечение символа токена
        token_symbol = extract_token_symbol(pair_symbol)
        token_id = save_token_to_db(connection, token_symbol)
        pair_id = save_pair_to_db(connection, token_id, "Binance", pair_symbol)

        # Получение данных
        oi_data = await get_binance_open_interest(session, pair_symbol)
        funding_data = await get_binance_funding_rate(session, pair_symbol)
        price_data = await get_binance_price(session, pair_symbol)

        # Конвертация OI в USD
        oi_contracts = Decimal(str(oi_data["openInterest"]))
        price_usd = Decimal(str(price_data["price"]))
        oi_usd = oi_contracts * price_usd

        # Конвертация объема в BTC (предполагаем, что объем в USDT)
        volume_usd = oi_usd  # Упрощение, реальный объем из API
        volume_btc = volume_usd / btc_usd_price

        # Сохранение данных
        futures_data = {
            "open_interest_contracts": oi_contracts,
            "open_interest_usd": oi_usd,
            "funding_rate": Decimal(str(funding_data["lastFundingRate"])),
            "volume_btc": volume_btc,
            "price_usd": price_usd,
        }
        save_futures_data(connection, pair_id, futures_data)
        logger.info(f"Успешно обработана пара {pair_symbol}")

    except APIError as e:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO api_errors (exchange, error_message)
                VALUES (%s, %s)
                """,
                ("Binance", str(e)),
            )
            connection.commit()
        logger.error(f"Ошибка обработки пары {pair_symbol}: {str(e)}")


async def main() -> None:
    """Основная функция для запуска скрипта."""
    logger.info("Запуск скрипта сбора данных")
    try:
        # Создание SSL-контекста с использованием certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            # Получение цены BTC/USD
            btc_usd_price = await get_btc_usd_price(session)

            # Подключение к MySQL
            connection = create_mysql_connection()

            try:
                # Получение списка пар
                pairs = await get_binance_futures_pairs(session)

                # Обработка пар
                tasks = [
                    process_pair(session, pair, btc_usd_price, connection)
                    for pair in pairs
                    if pair["status"] == "TRADING"
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

            finally:
                connection.close()

        logger.info("Скрипт успешно завершен")

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())