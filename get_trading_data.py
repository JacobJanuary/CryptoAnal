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
from typing import Dict, List, Optional, Tuple, Any, Callable
import random

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- 1. Настройки и глобальные переменные ---
load_dotenv()
MARKET_STATE: Dict[str, Dict] = {}
SPOT_STATE: Dict[str, Dict] = {}
QUOTE_ASSETS = ['USDT', 'USDC', 'USD', 'FDUSD', 'TUSD', 'BTC', 'ETH']
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
]


# --- 2. Вспомогательные функции ---
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


async def create_aiohttp_session() -> aiohttp.ClientSession:
    """Создает сессию aiohttp с отключенной проверкой SSL."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector, json_serialize=orjson.dumps)


# --- 3. Воркеры для сбора данных ---

# --- СПОТ ---
async def spot_data_worker() -> None:
    """Подключается к потокам !miniTicker@arr и !ticker_1h@arr для спота."""
    spot_url = "wss://stream.binance.com:9443/stream?streams=!miniTicker@arr/!ticker_1h@arr"
    logger.info(f"[Spot Worker] Запуск воркера. URL: {spot_url}")

    while True:
        try:
            async with websockets.connect(spot_url) as websocket:
                logger.info("[Spot Worker] Успешно подключен к спотовым потокам Binance.")
                while True:
                    message = await websocket.recv()
                    wrapper = orjson.loads(message)

                    stream_name = wrapper.get('stream')
                    data_array = wrapper.get('data', [])

                    if stream_name == '!miniTicker@arr':  # Данные за 24ч
                        for ticker in data_array:
                            symbol = ticker.get('s')
                            if symbol:
                                SPOT_STATE.setdefault(symbol, {}).update({
                                    'price': float(ticker.get('c', 0)),
                                    'volume_24h': float(ticker.get('v', 0)),
                                    'quote_volume_24h': float(ticker.get('q', 0))
                                })
                    elif stream_name == '!ticker_1h@arr':  # Данные за 1ч
                        for ticker in data_array:
                            symbol = ticker.get('s')
                            if symbol:
                                SPOT_STATE.setdefault(symbol, {}).update({
                                    'volume_1h': float(ticker.get('v', 0)),
                                    'quote_volume_1h': float(ticker.get('q', 0))
                                })
        except Exception as e:
            logger.error(f"[Spot Worker] Ошибка: {e}. Переподключение через 10 сек...")
            await asyncio.sleep(10)


# --- ФЬЮЧЕРСЫ ---
async def binance_worker(pairs_to_track: List[str]) -> None:
    """WebSocket воркер для фьючерсов Binance."""
    logger.info(f"[Futures Binance] Запуск WebSocket воркера для {len(pairs_to_track)} пар.")
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async def handle_binance_chunk(pairs_chunk: List[str]) -> None:
        streams = [f"{p.lower()}@ticker" for p in pairs_chunk] + [f"{p.lower()}@markPrice@1s" for p in pairs_chunk]
        url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"

        while True:
            try:
                async with websockets.connect(url, ssl=ssl_context) as websocket:
                    logger.info(f"[Futures Binance Chunk] Подключен к {len(pairs_chunk)} парам.")
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
                logger.error(f"[Futures Binance Chunk] Ошибка: {e}. Переподключение через 10 сек...")
                await asyncio.sleep(10)

    chunk_size = 100
    tasks = [handle_binance_chunk(pairs_to_track[i:i + chunk_size]) for i in range(0, len(pairs_to_track), chunk_size)]
    await asyncio.gather(*tasks)


async def bybit_worker(pairs_to_track: List[str]) -> None:
    """WebSocket воркер для фьючерсов Bybit."""
    logger.info(f"[Futures Bybit] Запуск WebSocket воркера для {len(pairs_to_track)} пар.")
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
                logger.info(f"[Futures Bybit] Отправлены запросы на подписку для {len(topics)} тем.")

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
            logger.error(f"[Futures Bybit] Ошибка: {e}. Переподключение через 10 сек...")
            await asyncio.sleep(10)


async def parse_binance_oi(session: aiohttp.ClientSession, symbol: str) -> Tuple[str, bool, None]:
    """Получает и парсит OI для фьючерсов Binance."""
    url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}"
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json(loads=orjson.loads)
                oi_value = float(data.get('openInterest', 0))
                MARKET_STATE.setdefault(f"BINANCE:{symbol}", {})['open_interest'] = oi_value
                return symbol, True, None
            else:
                logger.warning(f"[OI - Binance] HTTP {response.status} для {symbol}")
                return symbol, False, None
    except Exception as e:
        logger.error(f"[OI - Binance] Ошибка для {symbol}: {e}")
        return symbol, False, None


async def parse_bybit_oi(session: aiohttp.ClientSession, symbol: str) -> Tuple[str, bool, None]:
    """
    Получает и парсит OI для фьючерсов Bybit, используя основной и запасной эндпоинты.
    """
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: Восстановлена логика с запасным эндпоинтом ---
    try:
        # Попытка 1: Основной эндпоинт /open-interest
        url = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}"
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json(loads=orjson.loads)
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    oi_list = data['result']['list']
                    if oi_list:
                        oi_value = float(oi_list[0].get('openInterest', 0))
                        if oi_value > 0:
                            MARKET_STATE.setdefault(f"BYBIT:{symbol}", {})['open_interest'] = oi_value
                            return symbol, True, None

        # Попытка 2: Запасной эндпоинт /tickers (если первая не удалась)
        logger.debug(f"[OI - Bybit] Для {symbol} нет данных на /open-interest, пробую /tickers.")
        tickers_url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        async with session.get(tickers_url, timeout=10) as response:
            if response.status == 200:
                data = await response.json(loads=orjson.loads)
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    ticker_data = data['result']['list'][0]
                    oi_value = float(ticker_data.get('openInterestValue', 0))
                    if oi_value > 0:
                        MARKET_STATE.setdefault(f"BYBIT:{symbol}", {})['open_interest'] = oi_value
                        return symbol, True, None

        logger.warning(f"[OI - Bybit] Не удалось получить OI для {symbol} всеми способами.")
        return symbol, False, None

    except Exception as e:
        logger.error(f"[OI - Bybit] Критическая ошибка для {symbol}: {e}")
        return symbol, False, None


async def oi_collector(exchange_name: str, pairs: List[str], oi_parser: Callable) -> None:
    """Универсальный, отказоустойчивый сборщик OI для фьючерсов."""
    logger.info(f"[OI Collector - {exchange_name}] Запущен для {len(pairs)} пар.")
    session = await create_aiohttp_session()
    try:
        while True:
            start_time = datetime.now(timezone.utc)
            tasks = [oi_parser(session, symbol) for symbol in pairs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for r in results if isinstance(r, tuple) and r[1])
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            logger.info(
                f"[{end_time.strftime('%H:%M:%S')}] OI Collector - {exchange_name}: "
                f"Цикл завершен за {duration:.1f} сек. Успешно: {success_count}/{len(pairs)}"
            )

            next_cycle_delay = max(120 - duration, 5)
            await asyncio.sleep(next_cycle_delay)
    finally:
        await session.close()
        logger.info(f"[OI Collector - {exchange_name}] Сессия закрыта.")


# --- 4. Сохранение данных в БД ---

async def spot_db_saver(db_pool: asyncpg.Pool, spot_pairs_from_db: Dict[int, Dict]) -> None:
    """Сохраняет спотовые данные в таблицу spot_data."""
    logger.info("[Spot DB Saver] Запущен.")
    required_keys = ['price', 'volume_1h', 'quote_volume_1h', 'volume_24h', 'quote_volume_24h']

    while True:
        now = datetime.now(timezone.utc)
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        sleep_seconds = (next_minute - now).total_seconds()

        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)

        capture_time = next_minute
        logger.info(f"[{capture_time.strftime('%H:%M:%S')}] Spot DB Saver: Начало сессии сбора данных.")

        records_to_save_this_minute = {}
        pairs_needing_data = set(spot_pairs_from_db.keys())

        for _ in range(58):
            if not pairs_needing_data:
                logger.info("[Spot DB Saver] Все спотовые данные собраны досрочно.")
                break

            for pair_id in list(pairs_needing_data):
                pair_symbol = spot_pairs_from_db[pair_id]['pair_symbol']
                state = SPOT_STATE.get(pair_symbol)

                if state and all(key in state for key in required_keys):
                    records_to_save_this_minute[pair_id] = state.copy()
                    pairs_needing_data.remove(pair_id)
            await asyncio.sleep(1)

        if not records_to_save_this_minute:
            logger.warning("[Spot DB Saver] Нет полностью собранных спотовых данных для сохранения.")
            continue

        records_for_executemany = []
        for pair_id, state in records_to_save_this_minute.items():
            records_for_executemany.append((
                pair_id, capture_time, state['price'],
                state['volume_1h'], state['quote_volume_1h'],
                state['volume_24h'], state['quote_volume_24h']
            ))

        try:
            async with db_pool.acquire() as conn:
                await conn.executemany("""
                                       INSERT INTO spot_data (trading_pair_id, capture_time, price,
                                                              volume_1h, quote_volume_1h, volume_24h, quote_volume_24h)
                                       VALUES ($1, $2, $3, $4, $5, $6,
                                               $7) ON CONFLICT (trading_pair_id, capture_time) DO NOTHING;
                                       """, records_for_executemany)

            logger.info(f"[Spot DB Saver] УСПЕШНО СОХРАНЕНО {len(records_for_executemany)} записей в 'spot_data'.")
        except Exception as e:
            logger.error(f"[Spot DB Saver] DB_ERROR: {e}")


async def db_saver(db_pool: asyncpg.Pool, pairs_from_db: Dict[int, Dict]) -> None:
    """Сохраняет фьючерсные данные в таблицу market_data."""
    logger.info("[Futures DB Saver] Запущен.")
    required_keys_from_ws = ['mark_price', 'index_price', 'funding_rate', 'volume_base_24h', 'volume_quote_24h']
    exchange_map = {1: "BINANCE", 2: "BYBIT"}

    while True:
        now = datetime.now(timezone.utc)
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        sleep_seconds = (next_minute - now).total_seconds()

        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)

        capture_time = next_minute
        logger.info(f"[{capture_time.strftime('%H:%M:%S')}] Futures DB Saver: Начало сессии сбора данных.")

        records_to_save_this_minute = {}
        pairs_needing_data = set(pairs_from_db.keys())

        for _ in range(58):
            if not pairs_needing_data:
                logger.info("[Futures DB Saver] Все фьючерсные данные собраны досрочно.")
                break

            for pair_id in list(pairs_needing_data):
                pair_info = pairs_from_db[pair_id]
                market_key = f"{exchange_map.get(pair_info['exchange_id'])}:{pair_info['pair_symbol']}"
                state = MARKET_STATE.get(market_key)

                if state and all(key in state for key in required_keys_from_ws):
                    records_to_save_this_minute[pair_id] = state.copy()
                    pairs_needing_data.remove(pair_id)
            await asyncio.sleep(1)

        if pairs_needing_data:
            failed_info = [f"{exchange_map.get(pairs_from_db[pid]['exchange_id'])}:{pairs_from_db[pid]['pair_symbol']}"
                           for pid in list(pairs_needing_data)[:10]]
            logger.warning(
                f"[Futures DB Saver] Не удалось собрать данные для {len(pairs_needing_data)} пар. Примеры: {failed_info}")

        if not records_to_save_this_minute:
            logger.warning("[Futures DB Saver] Нет данных для сохранения.")
            continue

        records_for_executemany = []
        for pair_id, state in records_to_save_this_minute.items():
            pair_info = pairs_from_db[pair_id]
            base_asset, quote_asset = parse_symbol(pair_info['pair_symbol'])
            open_interest = state.get('open_interest', 0.0)

            records_for_executemany.append((
                pair_id, capture_time, pair_info['pair_symbol'], base_asset, quote_asset,
                state['mark_price'], state['index_price'], state['funding_rate'],
                state['volume_base_24h'], state['volume_quote_24h'], open_interest
            ))

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

            logger.info(f"[Futures DB Saver] УСПЕШНО СОХРАНЕНО {len(records_for_executemany)} записей в 'market_data'.")
        except Exception as e:
            logger.error(f"[Futures DB Saver] DB_ERROR: {e}")


# --- 5. Главная функция ---
async def main():
    """Главная функция-оркестратор."""
    db_pool = None
    try:
        db_pool = await asyncpg.create_pool(
            user=os.getenv("POSTGRES_USER"), password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
            database=os.getenv("POSTGRES_DB")
        )
        logger.info("Успешное подключение к PostgreSQL.")

        async with db_pool.acquire() as conn:
            sql_query = "SELECT id, pair_symbol, exchange_id, contract_type_id FROM trading_pairs"
            rows = await conn.fetch(sql_query)

            if not rows:
                logger.error("Таблица trading_pairs пуста. Завершение работы.")
                return

            all_pairs_from_db = {row['id']: dict(row) for row in rows}

            futures_pairs_from_db = {pid: pinfo for pid, pinfo in all_pairs_from_db.items() if
                                     pinfo['contract_type_id'] == 1}
            spot_pairs_from_db = {pid: pinfo for pid, pinfo in all_pairs_from_db.items() if
                                  pinfo['contract_type_id'] == 2}

            binance_futures_pairs = [p['pair_symbol'] for p in futures_pairs_from_db.values() if p['exchange_id'] == 1]
            bybit_futures_pairs = [p['pair_symbol'] for p in futures_pairs_from_db.values() if p['exchange_id'] == 2]

        logger.info(
            f"Загружено {len(rows)} пар: {len(futures_pairs_from_db)} фьючерсных, {len(spot_pairs_from_db)} спотовых.")

        tasks = []

        # Запуск воркеров для ФЬЮЧЕРСОВ
        if binance_futures_pairs:
            tasks.append(asyncio.create_task(binance_worker(binance_futures_pairs)))
            tasks.append(asyncio.create_task(oi_collector("Binance", binance_futures_pairs, parse_binance_oi)))

        if bybit_futures_pairs:
            tasks.append(asyncio.create_task(bybit_worker(bybit_futures_pairs)))
            tasks.append(asyncio.create_task(oi_collector("Bybit", bybit_futures_pairs, parse_bybit_oi)))

        # Запуск воркера для СПОТА
        if spot_pairs_from_db:
            tasks.append(asyncio.create_task(spot_data_worker()))

        if not tasks:
            logger.warning("Нет пар для отслеживания. Завершение работы.")
            return

        logger.info("Начальная задержка 30 секунд для сбора первоначальных данных...")
        await asyncio.sleep(30)

        # Запуск обоих сохраняторов
        if futures_pairs_from_db:
            tasks.append(asyncio.create_task(db_saver(db_pool, futures_pairs_from_db)))
        if spot_pairs_from_db:
            tasks.append(asyncio.create_task(spot_db_saver(db_pool, spot_pairs_from_db)))

        await asyncio.gather(*tasks)

    except Exception as e:
        logger.critical(f"Критическая ошибка в main: {e}", exc_info=True)
    finally:
        if db_pool:
            await db_pool.close()
            logger.info("Пул соединений к БД закрыт.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем.")