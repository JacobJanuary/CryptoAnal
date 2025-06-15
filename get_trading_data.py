import asyncio
import ssl
import certifi
import aiohttp
import orjson
import os
from dotenv import load_dotenv
import asyncpg
import websockets
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import random

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
# Временно включаем DEBUG для Bybit OI
logger.setLevel(logging.DEBUG)

# --- 1. Настройки и вспомогательные функции ---
load_dotenv()
MARKET_STATE: Dict[str, Dict] = {}
QUOTE_ASSETS = ['USDT', 'USDC', 'USD', 'FDUSD', 'TUSD', 'BTC', 'ETH']

# Список User-Agent для ротации
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
]


def get_random_user_agent() -> str:
    """Возвращает случайный User-Agent для ротации."""
    return random.choice(USER_AGENTS)


def parse_symbol(symbol_str: str) -> Tuple[str, str]:
    """Парсит символ торговой пары на базовый и котировочный актив."""
    for quote in QUOTE_ASSETS:
        if symbol_str.endswith(quote):
            base = symbol_str[:-len(quote)]
            return base, quote
    parts = symbol_str.split('-')
    if len(parts) == 2:
        return parts[0], parts[1]
    return symbol_str, "N/A"


# --- 2. WebSocket Воркеры (без изменений) ---
async def binance_worker(pairs_to_track: List[str]) -> None:
    """WebSocket воркер для Binance."""
    logger.info(f"[Binance] Запуск WebSocket воркера для {len(pairs_to_track)} пар.")
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async def handle_binance_chunk(pairs_chunk: List[str]) -> None:
        streams = [f"{p.lower()}@ticker" for p in pairs_chunk] + [f"{p.lower()}@markPrice@1s" for p in pairs_chunk]
        url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"

        while True:
            try:
                async with websockets.connect(url, ssl=ssl_context) as websocket:
                    logger.info(f"[Binance Chunk] Подключен к {len(pairs_chunk)} парам.")
                    while True:
                        wrapper = orjson.loads(await websocket.recv())
                        data = wrapper['data']
                        symbol = data['s']

                        if data['e'] == '24hrTicker':
                            MARKET_STATE.setdefault(f"BINANCE:{symbol}", {}).update({
                                'volume_base_24h': float(data.get('v', 0)),
                                'volume_quote_24h': float(data.get('q', 0))
                            })
                        elif data['e'] == 'markPriceUpdate':
                            MARKET_STATE.setdefault(f"BINANCE:{symbol}", {}).update({
                                'mark_price': float(data.get('p', 0)),
                                'index_price': float(data.get('i', 0)),
                                'funding_rate': float(data.get('r', 0))
                            })
            except Exception as e:
                logger.error(f"[Binance Chunk] Ошибка: {e}. Переподключение через 10 сек...")
                await asyncio.sleep(10)

    chunk_size = 100
    tasks = [handle_binance_chunk(pairs_to_track[i:i + chunk_size])
             for i in range(0, len(pairs_to_track), chunk_size)]
    await asyncio.gather(*tasks)


async def bybit_worker(pairs_to_track: List[str]) -> None:
    """WebSocket воркер для Bybit."""
    logger.info(f"[Bybit] Запуск WebSocket воркера для {len(pairs_to_track)} пар.")
    topics = [f"tickers.{pair}" for pair in pairs_to_track]
    url = "wss://stream.bybit.com/v5/public/linear"
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    while True:
        try:
            async with websockets.connect(url, ssl=ssl_context) as websocket:
                chunk_size = 10
                for i in range(0, len(topics), chunk_size):
                    await websocket.send(orjson.dumps({"op": "subscribe", "args": topics[i:i + chunk_size]}))
                    await asyncio.sleep(0.1)
                logger.info(f"[Bybit] Отправлены запросы на подписку для {len(topics)} тем.")

                while True:
                    data = orjson.loads(await websocket.recv())
                    if data.get('op') == 'ping':
                        await websocket.send(orjson.dumps({"op": "pong"}))
                    elif 'topic' in data and data['topic'].startswith('tickers'):
                        ticker_data = data['data']
                        update_payload = {}
                        if 'markPrice' in ticker_data:
                            update_payload['mark_price'] = float(ticker_data['markPrice'])
                        if 'indexPrice' in ticker_data:
                            update_payload['index_price'] = float(ticker_data['indexPrice'])
                        if 'fundingRate' in ticker_data:
                            update_payload['funding_rate'] = float(ticker_data['fundingRate'])
                        if 'volume24h' in ticker_data:
                            update_payload['volume_base_24h'] = float(ticker_data['volume24h'])
                        if 'turnover24h' in ticker_data:
                            update_payload['volume_quote_24h'] = float(ticker_data['turnover24h'])
                        MARKET_STATE.setdefault(f"BYBIT:{ticker_data['symbol']}", {}).update(update_payload)
        except Exception as e:
            logger.error(f"[Bybit] Ошибка: {e}. Переподключение через 10 сек...")
            await asyncio.sleep(10)


# --- 3. Улучшенные воркеры для сбора Open Interest ---
async def oi_collector_binance(pairs: List[str]) -> None:
    """Параллельный сборщик Open Interest для Binance с лимитом 400 req/min."""
    logger.info(f"[OI Collector - Binance] Запущен для {len(pairs)} пар.")

    # 400 запросов в минуту = ~6.67 запросов в секунду
    # С 10 параллельными воркерами = 0.15 сек задержка на воркер
    max_concurrent_requests = 10
    delay_between_requests = 0.15  # Задержка для каждого воркера

    # Настройки для экспоненциального отката
    max_retries = 3
    base_delay = 1.0

    # Семафор для ограничения параллельных запросов
    semaphore = asyncio.Semaphore(max_concurrent_requests)

    # Создаем сессию с правильными заголовками
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache'
    }

    connector = aiohttp.TCPConnector(limit=200, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30)

    async def fetch_oi(session: aiohttp.ClientSession, symbol: str) -> Tuple[str, bool, Optional[float]]:
        """Получить OI для одного символа."""
        async with semaphore:
            retry_count = 0

            while retry_count < max_retries:
                try:
                    # Ротация User-Agent
                    headers_copy = headers.copy()
                    headers_copy['User-Agent'] = get_random_user_agent()

                    url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}"

                    async with session.get(url, headers=headers_copy) as response:
                        if response.status == 200:
                            data = await response.json(loads=orjson.loads)
                            oi_value = float(data.get('openInterest', 0))
                            MARKET_STATE.setdefault(f"BINANCE:{symbol}", {})['open_interest'] = oi_value
                            return symbol, True, oi_value
                        elif response.status == 403:
                            logger.warning(f"[OI - Binance] 403 для {symbol}. Попытка {retry_count + 1}/{max_retries}")
                            retry_count += 1
                            if retry_count < max_retries:
                                wait_time = base_delay * (2 ** retry_count) + random.uniform(0, 1)
                                await asyncio.sleep(wait_time)
                        elif response.status == 429:
                            logger.warning(f"[OI - Binance] Rate limit для {symbol}")
                            await asyncio.sleep(30)
                            retry_count += 1
                        else:
                            logger.error(f"[OI - Binance] HTTP {response.status} для {symbol}")
                            return symbol, False, None

                except asyncio.TimeoutError:
                    logger.error(f"[OI - Binance] Таймаут для {symbol}")
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(base_delay * retry_count)
                except Exception as e:
                    logger.error(f"[OI - Binance] Ошибка для {symbol}: {type(e).__name__}: {e}")
                    return symbol, False, None

            return symbol, False, None

    async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            json_serialize=orjson.dumps
    ) as session:
        while True:
            start_time = datetime.now(timezone.utc)

            # Создаем задачи для всех символов
            tasks = []
            for i, symbol in enumerate(pairs):
                # Распределяем запросы во времени
                delay = (i // max_concurrent_requests) * delay_between_requests

                async def delayed_fetch(s, d):
                    if d > 0:
                        await asyncio.sleep(d)
                    return await fetch_oi(session, s)

                task = asyncio.create_task(delayed_fetch(symbol, delay))
                tasks.append(task)

            # Ждем завершения всех задач
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Подсчет результатов
            successful_requests = 0
            failed_requests = 0

            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                    logger.error(f"[OI - Binance] Исключение: {result}")
                elif isinstance(result, tuple) and result[1]:
                    successful_requests += 1
                else:
                    failed_requests += 1

            # Время выполнения
            end_time = datetime.now(timezone.utc)
            cycle_duration = (end_time - start_time).total_seconds()

            logger.info(
                f"[{end_time.strftime('%H:%M:%S')}] "
                f"OI Collector - Binance: Цикл завершен за {cycle_duration:.1f} сек. "
                f"Успешно: {successful_requests}, Ошибок: {failed_requests}"
            )

            # Пауза до следующего цикла (2 минуты минус время выполнения)
            next_cycle_delay = max(120 - cycle_duration, 5)  # Минимум 5 секунд паузы
            logger.info(f"[OI Collector - Binance] Следующий цикл через {next_cycle_delay:.1f} сек.")
            await asyncio.sleep(next_cycle_delay)


async def oi_collector_bybit(pairs: List[str]) -> None:
    """Параллельный сборщик Open Interest для Bybit с лимитом 400 req/min."""
    logger.info(f"[OI Collector - Bybit] Запущен для {len(pairs)} пар.")

    # 400 запросов в минуту с 10 параллельными воркерами
    max_concurrent_requests = 10
    delay_between_requests = 0.15

    max_retries = 3
    base_delay = 1.0

    # Семафор для ограничения параллельных запросов
    semaphore = asyncio.Semaphore(max_concurrent_requests)

    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.bybit.com/'
    }

    connector = aiohttp.TCPConnector(limit=200, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30)

    async def fetch_oi(session: aiohttp.ClientSession, symbol: str) -> Tuple[str, bool, Optional[float]]:
        """Получить OI для одного символа."""
        async with semaphore:
            retry_count = 0

            while retry_count < max_retries:
                try:
                    headers_copy = headers.copy()
                    headers_copy['User-Agent'] = get_random_user_agent()

                    url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min"

                    async with session.get(url, headers=headers_copy) as response:
                        response_text = await response.text()

                        if response.status == 200:
                            try:
                                data = orjson.loads(response_text)
                                if data.get('retCode') == 0:
                                    result = data.get('result', {})
                                    result_list = result.get('list', [])

                                    if result_list:
                                        oi_data = result_list[0]
                                        # Bybit возвращает OI в разных полях в зависимости от версии API
                                        oi_value = 0.0

                                        # Пробуем разные поля
                                        if 'openInterest' in oi_data:
                                            oi_value = float(oi_data['openInterest'])
                                        elif 'value' in oi_data:
                                            oi_value = float(oi_data['value'])
                                        elif 'openInterestValue' in oi_data:
                                            oi_value = float(oi_data['openInterestValue'])

                                        # Дополнительное логирование для первых нескольких символов
                                        if symbol in pairs[:5] or oi_value == 0:
                                            logger.info(
                                                f"[OI - Bybit DEBUG] {symbol}: openInterest={oi_value}, "
                                                f"all_fields={list(oi_data.keys())}, raw_data={oi_data}"
                                            )

                                        if oi_value > 0:
                                            MARKET_STATE.setdefault(f"BYBIT:{symbol}", {})['open_interest'] = oi_value
                                            return symbol, True, oi_value
                                        else:
                                            # Если OI все еще 0, пробуем tickers endpoint
                                            logger.debug(f"[OI - Bybit] {symbol}: OI=0, пробуем tickers endpoint")
                                            return await fetch_oi_from_tickers(session, symbol, headers_copy)
                                    else:
                                        logger.warning(f"[OI - Bybit] Пустой список для {symbol}, result={result}")
                                        # Пробуем tickers endpoint
                                        return await fetch_oi_from_tickers(session, symbol, headers_copy)
                                else:
                                    logger.warning(
                                        f"[OI - Bybit] Неверный ответ для {symbol}: "
                                        f"retCode={data.get('retCode')}, retMsg={data.get('retMsg')}"
                                    )
                                    return symbol, False, None
                            except orjson.JSONDecodeError:
                                logger.error(f"[OI - Bybit] JSON error для {symbol}")
                                return symbol, False, None
                        elif response.status == 403:
                            logger.warning(f"[OI - Bybit] 403 для {symbol}. Попытка {retry_count + 1}/{max_retries}")
                            retry_count += 1
                            if retry_count < max_retries:
                                wait_time = base_delay * (2 ** retry_count) + random.uniform(0, 1)
                                await asyncio.sleep(wait_time)
                        elif response.status == 429:
                            retry_after = response.headers.get('Retry-After', '30')
                            wait_time = int(retry_after) if retry_after.isdigit() else 30
                            logger.warning(f"[OI - Bybit] Rate limit. Ожидание {wait_time} сек")
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                        else:
                            logger.error(f"[OI - Bybit] HTTP {response.status} для {symbol}")
                            return symbol, False, None

                except asyncio.TimeoutError:
                    logger.error(f"[OI - Bybit] Таймаут для {symbol}")
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(base_delay * retry_count)
                except Exception as e:
                    logger.error(f"[OI - Bybit] Ошибка для {symbol}: {type(e).__name__}: {e}")
                    return symbol, False, None

            return symbol, False, None

    async def fetch_oi_from_tickers(session: aiohttp.ClientSession, symbol: str, headers: dict) -> Tuple[
        str, bool, Optional[float]]:
        """Альтернативный способ получения OI через tickers endpoint."""
        try:
            url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json(loads=orjson.loads)
                    if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                        ticker_data = data['result']['list'][0]

                        # Пробуем разные поля для OI
                        oi_value = 0.0
                        if 'openInterestValue' in ticker_data:
                            oi_value = float(ticker_data['openInterestValue'])
                        elif 'openInterest' in ticker_data:
                            oi_value = float(ticker_data['openInterest'])

                        # Логирование для отладки
                        logger.info(
                            f"[OI - Bybit Tickers DEBUG] {symbol}: oi_value={oi_value}, "
                            f"fields={[k for k in ticker_data.keys() if 'interest' in k.lower()]}"
                        )

                        if oi_value > 0:
                            MARKET_STATE.setdefault(f"BYBIT:{symbol}", {})['open_interest'] = oi_value
                            logger.info(f"[OI - Bybit] {symbol}: Получен OI из tickers = {oi_value}")
                            return symbol, True, oi_value

            return symbol, False, None
        except Exception as e:
            logger.error(f"[OI - Bybit] Ошибка в tickers для {symbol}: {e}")
            return symbol, False, None

    async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            json_serialize=orjson.dumps
    ) as session:
        while True:
            start_time = datetime.now(timezone.utc)

            # Создаем задачи для всех символов
            tasks = []
            for i, symbol in enumerate(pairs):
                # Распределяем запросы во времени
                delay = (i // max_concurrent_requests) * delay_between_requests

                async def delayed_fetch(s, d):
                    if d > 0:
                        await asyncio.sleep(d)
                    return await fetch_oi(session, s)

                task = asyncio.create_task(delayed_fetch(symbol, delay))
                tasks.append(task)

            # Ждем завершения всех задач
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Подсчет результатов
            successful_requests = 0
            failed_requests = 0

            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                    logger.error(f"[OI - Bybit] Исключение: {result}")
                elif isinstance(result, tuple) and result[1]:
                    successful_requests += 1
                else:
                    failed_requests += 1

            # Время выполнения
            end_time = datetime.now(timezone.utc)
            cycle_duration = (end_time - start_time).total_seconds()

            logger.info(
                f"[{end_time.strftime('%H:%M:%S')}] "
                f"OI Collector - Bybit: Цикл завершен за {cycle_duration:.1f} сек. "
                f"Успешно: {successful_requests}, Ошибок: {failed_requests}"
            )

            # Пауза до следующего цикла (2 минуты минус время выполнения)
            next_cycle_delay = max(120 - cycle_duration, 5)  # Минимум 5 секунд паузы
            logger.info(f"[OI Collector - Bybit] Следующий цикл через {next_cycle_delay:.1f} сек.")
            await asyncio.sleep(next_cycle_delay)


# --- 4. Логика Сохранения в БД ---
async def db_saver(db_pool: asyncpg.Pool, pairs_from_db: Dict[int, Dict]) -> None:
    """Сохранение данных в базу данных с учетом разных бирж."""
    logger.info("[DB Saver] Запущен.")
    required_keys_from_ws = ['mark_price', 'index_price', 'funding_rate', 'volume_base_24h', 'volume_quote_24h']

    # Создаем маппинг exchange_id к названию биржи
    exchange_map = {1: "BINANCE", 2: "BYBIT"}

    while True:
        now = datetime.now(timezone.utc)
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        sleep_seconds = (next_minute - now).total_seconds()

        logger.info(f"[{now.strftime('%H:%M:%S')}] DB Saver: следующая сессия через {sleep_seconds:.1f} сек.")
        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)

        capture_time = next_minute
        logger.info(f"[{capture_time.strftime('%H:%M:%S')}] DB Saver: Начало сессии сбора данных.")

        records_to_save_this_minute = {}
        pairs_needing_data = set(pairs_from_db.keys())

        # Сбор данных в течение 58 секунд
        for second in range(58):
            if not pairs_needing_data:
                logger.info(
                    f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] DB Saver: Все данные собраны досрочно.")
                break

            for pair_id in list(pairs_needing_data):
                pair_info = pairs_from_db[pair_id]
                pair_symbol = pair_info['symbol']
                exchange_name = exchange_map.get(pair_info['exchange_id'], "UNKNOWN")

                # Формируем ключ с учетом биржи
                market_key = f"{exchange_name}:{pair_symbol}"
                state = MARKET_STATE.get(market_key)

                # Диагностическое логирование для первых пар Bybit
                if exchange_name == "BYBIT" and second == 0 and pair_symbol in ['1000000PEIPEIUSDT', '10000COQUSDT',
                                                                                '1000000BABYDOGEUSDT']:
                    logger.info(
                        f"[DB Saver DEBUG] Проверка {market_key}: "
                        f"state={'EXISTS' if state else 'NOT FOUND'}, "
                        f"data={state if state else 'N/A'}"
                    )
                    # Также проверим все ключи в MARKET_STATE для этого символа
                    matching_keys = [k for k in MARKET_STATE.keys() if pair_symbol in k]
                    if matching_keys:
                        logger.info(f"[DB Saver DEBUG] Найдены ключи для {pair_symbol}: {matching_keys}")

                if state and all(key in state for key in required_keys_from_ws):
                    records_to_save_this_minute[pair_id] = state.copy()
                    pairs_needing_data.remove(pair_id)

            await asyncio.sleep(1)

        if pairs_needing_data:
            failed_info = []
            for pid in list(pairs_needing_data)[:10]:  # Показываем первые 10
                pair_info = pairs_from_db[pid]
                exchange_name = exchange_map.get(pair_info['exchange_id'], "UNKNOWN")
                failed_info.append(f"{exchange_name}:{pair_info['symbol']}")

            logger.warning(
                f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                f"DB Saver: Не удалось собрать данные для {len(pairs_needing_data)} пар. "
                f"Примеры: {failed_info}"
            )

        if not records_to_save_this_minute:
            logger.warning(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] DB Saver: Нет данных для сохранения.")
            continue

        # Подготовка данных для batch insert
        records_for_executemany = []
        bybit_oi_count = 0

        for pair_id, state in records_to_save_this_minute.items():
            pair_info = pairs_from_db[pair_id]
            base_asset, quote_asset = parse_symbol(pair_info['symbol'])
            open_interest = state.get('open_interest', 0.0)

            # Считаем количество Bybit записей с OI > 0
            if pair_info['exchange_id'] == 2 and open_interest > 0:
                bybit_oi_count += 1
                # Логируем первые несколько
                if bybit_oi_count <= 3:
                    logger.info(
                        f"[DB Saver] Bybit OI > 0: {pair_info['symbol']} = {open_interest}, "
                        f"pair_id={pair_id}"
                    )

            records_for_executemany.append((
                pair_id, capture_time, pair_info['symbol'], base_asset, quote_asset,
                state['mark_price'], state['index_price'], state['funding_rate'],
                state['volume_base_24h'], state['volume_quote_24h'], open_interest
            ))

        logger.info(f"[DB Saver] Bybit записей с OI > 0: {bybit_oi_count}")

        # Сохранение в БД
        try:
            async with db_pool.acquire() as conn:
                await conn.executemany("""
                                       INSERT INTO market_data (trading_pair_id, capture_time, pair_symbol, base_asset,
                                                                quote_asset,
                                                                mark_price, index_price, funding_rate, volume_base_24h,
                                                                volume_quote_24h, open_interest)
                                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                                               $11) ON CONFLICT (trading_pair_id, capture_time) DO NOTHING;
                                       """, records_for_executemany)

            logger.info(
                f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                f"УСПЕШНО СОХРАНЕНО {len(records_for_executemany)} записей в БД."
            )
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] DB_ERROR: {e}")


# --- 5. Главная функция ---
async def main():
    """Главная функция-оркестратор."""
    db_pool = None
    try:
        # Подключение к БД
        db_pool = await asyncpg.create_pool(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            database=os.getenv("POSTGRES_DB"),
            min_size=10,
            max_size=20
        )
        logger.info("Успешное подключение к PostgreSQL.")

        # Загрузка торговых пар
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, pair_symbol, exchange_id FROM trading_pairs  WHERE contract_type_id = 1")
            if not rows:
                logger.error("Таблица trading_pairs пуста. Завершение работы.")
                return

            pairs_from_db = {
                row['id']: {
                    'symbol': row['pair_symbol'],
                    'exchange_id': row['exchange_id']
                }
                for row in rows
            }

            binance_pairs = [p['symbol'] for p in pairs_from_db.values() if p['exchange_id'] == 1]
            bybit_pairs = [p['symbol'] for p in pairs_from_db.values() if p['exchange_id'] == 2]

        logger.info(
            f"Загружено {len(rows)} пар из БД: "
            f"{len(binance_pairs)} для Binance, {len(bybit_pairs)} для Bybit."
        )

        tasks = []

        # Запуск воркеров для Binance
        if binance_pairs:
            tasks.append(asyncio.create_task(binance_worker(binance_pairs)))
            tasks.append(asyncio.create_task(oi_collector_binance(binance_pairs)))

        # Запуск воркеров для Bybit
        if bybit_pairs:
            tasks.append(asyncio.create_task(bybit_worker(bybit_pairs)))
            tasks.append(asyncio.create_task(oi_collector_bybit(bybit_pairs)))

        if tasks:
            # Прогрев - даем время собрать начальные данные
            logger.info("Начальная задержка 30 секунд для сбора первоначальных данных OI...")
            await asyncio.sleep(30)

            # Запуск сохранения в БД
            tasks.append(asyncio.create_task(db_saver(db_pool, pairs_from_db)))

        # Запуск всех задач
        await asyncio.gather(*tasks)

    except Exception as e:
        logger.critical(f"Критическая ошибка в main: {e}")
    finally:
        if db_pool:
            await db_pool.close()
            logger.info("Пул соединений к БД закрыт.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем.")