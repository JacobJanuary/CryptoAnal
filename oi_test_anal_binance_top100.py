
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime, UTC
import certifi
import ssl
from dotenv import load_dotenv
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,  # Переключите на DEBUG для диагностики
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка .env файла
load_dotenv()


@dataclass
class FuturesData:
    """Класс для хранения данных о фьючерсной паре."""
    symbol: str
    open_interest: float
    price: float
    spot_volume: Optional[float]
    market_cap: Optional[float]
    timestamp: datetime


class BinanceFuturesOITracker:
    """Класс для отслеживания данных фьючерсных пар на Binance с капитализацией из CoinMarketCap."""

    def __init__(self, max_retries: int = 3, bypass_ssl: bool = False):
        self.max_retries = max_retries  # Максимум повторных попыток
        self.bypass_ssl = bypass_ssl  # Флаг отключения SSL
        self.binance_url = "https://fapi.binance.com"  # URL Binance Futures API
        self.binance_spot_url = "https://api.binance.com"  # URL Binance Spot API
        self.cmc_url = "https://pro-api.coinmarketcap.com"  # URL CoinMarketCap API
        self.cmc_api_key = os.getenv("COINMARKETCAP_API_KEY")  # Ключ CMC из .env
        self.session: Optional[aiohttp.ClientSession] = None  # HTTP-сессия
        self.valid_pairs: Set[str] = set()  # Кэш фьючерсных пар

    async def initialize_session(self) -> None:
        """Инициализация HTTP-сессии с настройкой SSL."""
        if self.session is None or self.session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            if self.bypass_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=30))
            logger.debug("HTTP-сессия инициализирована")

    async def close_session(self) -> None:
        """Закрытие HTTP-сессии."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("HTTP-сессия закрыта")

    async def get_binance_futures_pairs(self) -> Set[str]:
        """
        Получение списка доступных бессрочных фьючерсных пар с Binance.

        Возвращает:
            Set[str]: Множество символов фьючерсных пар.

        Исключения:
            aiohttp.ClientError: Если запрос к API не удался.
        """
        for attempt in range(self.max_retries):
            try:
                await self.initialize_session()
                logger.debug(f"Запрос фьючерсных пар: {self.binance_url}/fapi/v1/exchangeInfo")
                async with self.session.get(f"{self.binance_url}/fapi/v1/exchangeInfo") as response:
                    if response.status == 429:
                        logger.warning(f"Достигнут лимит запросов Binance, повтор через {2 ** attempt}с")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = await response.json()
                    if not isinstance(data, dict) or 'symbols' not in data:
                        logger.error(f"Некорректные данные от Binance: {data}")
                        return set()
                    pairs = {pair['symbol'] for pair in data['symbols'] if pair['contractType'] == 'PERPETUAL'}
                    logger.info(f"Получено {len(pairs)} фьючерсных пар с Binance")
                    return pairs
            except aiohttp.ClientError as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries} не удалась: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
        logger.error("Не удалось получить фьючерсные пары Binance")
        return set()

    async def get_spot_volume(self, symbol: str) -> Optional[float]:
        """
        Получение 24-часового спотового объема для указанного символа из Binance API.

        Аргументы:
            symbol (str): Символ пары (например, BTCUSDT).

        Возвращает:
            Optional[float]: Спотовый объем в USDT или None, если не удалось.

        Исключения:
            aiohttp.ClientError: Если запрос к API не удался.
        """
        for attempt in range(self.max_retries):
            try:
                await self.initialize_session()
                logger.debug(f"Запрос спотового объема: {self.binance_spot_url}/api/v3/ticker/24hr?symbol={symbol}")
                async with self.session.get(
                        f"{self.binance_spot_url}/api/v3/ticker/24hr?symbol={symbol}"
                ) as response:
                    if response.status == 429:
                        logger.warning(f"Достигнут лимит запросов Binance, повтор через {2 ** attempt}с")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get('quoteVolume', 0))
                    else:
                        logger.warning(f"Нет данных о спотовом объеме для {symbol}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries} не удалась для {symbol}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
        logger.error(f"Не удалось получить спотовый объем для {symbol}")
        return None

    async def get_open_interest(self, symbol: str) -> Optional[float]:
        """
        Получение открытого интереса для указанного символа из Binance API.

        Аргументы:
            symbol (str): Символ фьючерсной пары (например, BTCUSDT).

        Возвращает:
            Optional[float]: Открытый интерес или None, если не удалось.

        Исключения:
            aiohttp.ClientError: Если запрос к API не удался.
        """
        for attempt in range(self.max_retries):
            try:
                await self.initialize_session()
                logger.debug(f"Запрос открытого интереса: {self.binance_url}/fapi/v1/openInterest?symbol={symbol}")
                async with self.session.get(
                        f"{self.binance_url}/fapi/v1/openInterest?symbol={symbol}"
                ) as response:
                    if response.status == 429:
                        logger.warning(f"Достигнут лимит запросов Binance, повтор через {2 ** attempt}с")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get('openInterest', 0))
                    else:
                        logger.warning(f"Нет данных об открытом интересе для {symbol}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries} не удалась для {symbol}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
        logger.error(f"Не удалось получить открытый интерес для {symbol}")
        return None

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Получение текущей цены для указанного символа из Binance API.

        Аргументы:
            symbol (str): Символ фьючерсной пары (например, BTCUSDT).

        Возвращает:
            Optional[float]: Текущая цена или None, если не удалось.

        Исключения:
            aiohttp.ClientError: Если запрос к API не удался.
        """
        for attempt in range(self.max_retries):
            try:
                await self.initialize_session()
                logger.debug(f"Запрос цены: {self.binance_url}/fapi/v1/ticker/price?symbol={symbol}")
                async with self.session.get(
                        f"{self.binance_url}/fapi/v1/ticker/price?symbol={symbol}"
                ) as response:
                    if response.status == 429:
                        logger.warning(f"Достигнут лимит запросов Binance, повтор через {2 ** attempt}с")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get('price', 0))
                    else:
                        logger.warning(f"Нет данных о цене для {symbol}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries} не удалась для {symbol}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
        logger.error(f"Не удалось получить цену для {symbol}")
        return None

    async def get_market_cap_cmc(self, symbol: str) -> Optional[float]:
        """
        Получение рыночной капитализации из CoinMarketCap API.

        Аргументы:
            symbol (str): Символ пары (например, BTCUSDT).

        Возвращает:
            Optional[float]: Рыночная капитализация или None, если не удалось.

        Исключения:
            aiohttp.ClientError: Если запрос к API не удался.
        """
        if not self.cmc_api_key:
            logger.error("Отсутствует API-ключ CoinMarketCap")
            return None
        base_symbol = symbol.replace('USDT', '')
        for attempt in range(self.max_retries):
            try:
                await self.initialize_session()
                headers = {'X-CMC_PRO_API_KEY': self.cmc_api_key}
                params = {'symbol': base_symbol}
                logger.debug(
                    f"Запрос капитализации CMC для {base_symbol}: {self.cmc_url}/v1/cryptocurrency/quotes/latest")
                async with self.session.get(
                        f"{self.cmc_url}/v1/cryptocurrency/quotes/latest",
                        headers=headers,
                        params=params
                ) as response:
                    if response.status == 429:
                        logger.warning(f"Достигнут лимит запросов CMC, повтор через {2 ** attempt}с")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = await response.json()
                    if 'data' not in data or base_symbol not in data['data']:
                        logger.warning(f"Нет данных о капитализации CMC для {base_symbol}. Ответ: {data}")
                        return None
                    market_cap = data['data'][base_symbol]['quote']['USD'].get('market_cap')
                    if market_cap is None:
                        logger.warning(f"Капитализация для {base_symbol} равна None. Ответ: {data}")
                        return None
                    return float(market_cap)
            except aiohttp.ClientError as e:
                logger.error(f"Попытка {attempt + 1}/{self.max_retries} не удалась для {base_symbol}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
        logger.error(f"Не удалось получить капитализацию CMC для {base_symbol} после всех попыток")
        return None

    async def track_open_interest(self) -> List[FuturesData]:
        """
        Отслеживание данных для всех фьючерсных пар Binance с сортировкой по капитализации.

        Возвращает:
            List[FuturesData]: Отсортированный список данных о парах.

        Исключения:
            Exception: Если произошли критические ошибки.
        """
        try:
            logger.info("Начало отслеживания открытого интереса")
            await self.initialize_session()
            # Обновление списка фьючерсных пар
            self.valid_pairs = await self.get_binance_futures_pairs()
            if not self.valid_pairs:
                logger.error("Не удалось загрузить фьючерсные пары")
                return []

            results = []
            for symbol in self.valid_pairs:
                logger.debug(f"Обработка символа: {symbol}")
                open_interest = await self.get_open_interest(symbol)
                price = await self.get_current_price(symbol)
                spot_volume = await self.get_spot_volume(symbol)
                market_cap = await self.get_market_cap_cmc(symbol)

                if open_interest is not None and price is not None:
                    futures_data = FuturesData(
                        symbol=symbol,
                        open_interest=open_interest,
                        price=price,
                        spot_volume=spot_volume,
                        market_cap=market_cap,
                        timestamp=datetime.now(UTC)
                    )
                    results.append(futures_data)
                    logger.info(
                        f"Отслеживается {symbol}: OI={open_interest:.2f}, Цена={price:.2f}, "
                        f"Объем={spot_volume or 'N/A'}, Капитализация={market_cap or 'N/A'}"
                    )

                await asyncio.sleep(0.5)  # Задержка для лимитов API (Binance + CMC)

            # Сортировка по капитализации (по убыванию, None в конце)
            results.sort(key=lambda x: x.market_cap if x.market_cap is not None else float('-inf'), reverse=True)
            logger.info(f"Завершено отслеживание, получено {len(results)} пар")
            return results
        except Exception as e:
            logger.error(f"Ошибка при отслеживании открытого интереса: {e}", exc_info=True)
            return []
        finally:
            await self.close_session()


async def main():
    """Основная функция для запуска трекера."""
    tracker = BinanceFuturesOITracker(max_retries=3, bypass_ssl=False)
    while True:
        logger.info("Запуск нового цикла отслеживания")
        results = await tracker.track_open_interest()
        for data in results:
            print(
                f"{data.timestamp}: {data.symbol} - "
                f"OI: {data.open_interest:.2f}, Цена: {data.price:.2f}, "
                f"Объем: {data.spot_volume or 'N/A'}, Капитализация: {data.market_cap or 'N/A'}"
            )
        logger.info("Цикл завершен, ожидание следующего запуска")
        await asyncio.sleep(300)  # Каждые 5 минут


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
