import asyncio
import multiprocessing
import ssl
import certifi
import aiohttp
import orjson
import psutil
import os
import time
import websockets
from datetime import datetime
from dotenv import load_dotenv
import asyncpg

# --- 1. Настройки (без изменений) ---
MIN_USD_VALUE = 10000.0
MIN_24H_VOLUME_USDT = 1000000.0
COINBASE_SYMBOLS = [
    "00-USD", "1INCH-USD", "A8-USD", "AAVE-USD", "ABT-USD", "ACH-USD", "ACS-USD", "ACX-USD", "ADA-USD", "AERGO-USD",
    "AERO-USD", "AGLD-USD", "AIOZ-USD", "AKT-USD", "ALCX-USD", "ALEO-USD", "ALEPH-USD", "ALGO-USD", "ALICE-USD",
    "ALT-USD",
    "AMP-USD", "ANKR-USD", "APE-USD", "API3-USD", "APT-USD", "ARB-USD", "ARKM-USD", "ARPA-USD", "ASM-USD", "AST-USD",
    "ATH-USD", "ATOM-USD", "AUCTION-USD", "AUDIO-USD", "AURORA-USD", "AVAX-USD", "AVT-USD", "AXL-USD", "AXS-USD",
    "B3-USD",
    "BADGER-USD", "BAL-USD", "BAND-USD", "BAT-USD", "BCH-USD", "BERA-USD", "BICO-USD", "BIGTIME-USD", "BLAST-USD",
    "BLUR-USD",
    "BLZ-USD", "BNT-USD", "BOBA-USD", "BONK-USD", "BTC-USD", "BTRST-USD", "C98-USD", "CAKE-USD", "CBETH-USD",
    "CELR-USD",
    "CGLD-USD", "CHZ-USD", "CLANKER-USD", "CLV-USD", "COMP-USD", "COOKIE-USD", "CORECHAIN-USD", "COTI-USD", "COW-USD",
    "CRO-USD",
    "CRV-USD", "CTSI-USD", "CTX-USD", "CVC-USD", "CVX-USD", "DAI-USD", "DASH-USD", "DEGEN-USD", "DEXT-USD", "DIA-USD",
    "DIMO-USD", "DNT-USD", "DOGE-USD", "DOGINME-USD", "DOT-USD", "DRIFT-USD", "EDGE-USD", "EGLD-USD", "EIGEN-USD",
    "ELA-USD",
    "ENA-USD", "ENS-USD", "EOS-USD", "ERN-USD", "ETC-USD", "ETH-USD", "ETHFI-USD", "FAI-USD", "FARM-USD",
    "FARTCOIN-USD",
    "FET-USD", "FIDA-USD", "FIL-USD", "FIS-USD", "FLOKI-USD", "FLOW-USD", "FLR-USD", "FORT-USD", "FORTH-USD", "FOX-USD",
    "FX-USD", "G-USD", "GFI-USD", "GHST-USD", "GIGA-USD", "GLM-USD", "GMT-USD", "GNO-USD", "GODS-USD", "GRT-USD",
    "GST-USD", "GTC-USD", "HBAR-USD", "HFT-USD", "HIGH-USD", "HNT-USD", "HOME-USD", "HONEY-USD", "HOPR-USD", "ICP-USD",
    "IDEX-USD", "ILV-USD", "IMX-USD", "INDEX-USD", "INJ-USD", "INV-USD", "IO-USD", "IOTX-USD", "IP-USD", "JASMY-USD",
    "JTO-USD", "KAITO-USD", "KARRAT-USD", "KAVA-USD", "KERNEL-USD", "KEYCAT-USD", "KNC-USD", "KRL-USD", "KSM-USD",
    "L3-USD",
    "LA-USD", "LCX-USD", "LDO-USD", "LINK-USD", "LOKA-USD", "LPT-USD", "LQTY-USD", "LRC-USD", "LRDS-USD", "LSETH-USD",
    "LTC-USD", "MAGIC-USD", "MANA-USD", "MANTLE-USD", "MASK-USD", "MATH-USD", "MATIC-USD", "MDT-USD", "ME-USD",
    "METIS-USD",
    "MINA-USD", "MKR-USD", "MLN-USD", "MNDE-USD", "MOBILE-USD", "MOG-USD", "MOODENG-USD", "MORPHO-USD", "MSOL-USD",
    "MUSE-USD",
    "NCT-USD", "NEAR-USD", "NEON-USD", "NKN-USD", "NMR-USD", "OCEAN-USD", "OGN-USD", "OMNI-USD", "ONDO-USD", "OP-USD",
    "ORCA-USD", "OSMO-USD", "OXT-USD", "PAX-USD", "PAXG-USD", "PENDLE-USD", "PENGU-USD", "PEPE-USD", "PERP-USD",
    "PIRATE-USD",
    "PLU-USD", "PNG-USD", "PNUT-USD", "POL-USD", "POLS-USD", "POND-USD", "POPCAT-USD", "POWR-USD", "PRCL-USD",
    "PRIME-USD",
    "PRO-USD", "PROMPT-USD", "PUNDIX-USD", "PYR-USD", "PYTH-USD", "QI-USD", "QNT-USD", "RAD-USD", "RARE-USD",
    "RARI-USD",
    "RBN-USD", "RED-USD", "RENDER-USD", "REQ-USD", "REZ-USD", "RLC-USD", "RNDR-USD", "RONIN-USD", "ROSE-USD", "RPL-USD",
    "RSR-USD", "SAFE-USD", "SAND-USD", "SD-USD", "SEAM-USD", "SEI-USD", "SHDW-USD", "SHIB-USD", "SHPING-USD", "SKL-USD",
    "SNX-USD", "SOL-USD", "SPA-USD", "SPELL-USD", "SQD-USD", "STG-USD", "STORJ-USD", "STRK-USD", "STX-USD", "SUI-USD",
    "SUKU-USD", "SUPER-USD", "SUSHI-USD", "SWELL-USD", "SWFTC-USD", "SXT-USD", "SYN-USD", "SYRUP-USD", "T-USD",
    "TAO-USD",
    "TIA-USD", "TIME-USD", "TNSR-USD", "TOSHI-USD", "TRAC-USD", "TRB-USD", "TRU-USD", "TRUMP-USD", "TURBO-USD",
    "UMA-USD",
    "UNI-USD", "USDT-USD", "VARA-USD", "VELO-USD", "VET-USD", "VOXEL-USD", "VTHO-USD", "VVV-USD", "WAXL-USD",
    "WCFG-USD",
    "WELL-USD", "WIF-USD", "WLD-USD", "XCN-USD", "XLM-USD", "XRP-USD", "XTZ-USD", "XYO-USD", "YFI-USD", "ZEC-USD",
    "ZEN-USD", "ZETA-USD", "ZETACHAIN-USD", "ZK-USD", "ZORA-USD", "ZRO-USD", "ZRX-USD",
]
load_dotenv()

# --- 2. Вспомогательные функции (без изменений) ---
# ... (parse_symbol, format_db_message) ...
QUOTE_ASSETS = ['USDT', 'USDC', 'USD', 'FDUSD', 'TUSD', 'BTC', 'ETH']


def parse_symbol(symbol_str: str):
    for quote in QUOTE_ASSETS:
        if symbol_str.endswith(quote):
            base = symbol_str[:-len(quote)]
            return base, quote
    parts = symbol_str.split('-')
    if len(parts) == 2: return parts[0], parts[1]
    return symbol_str, "N/A"


def format_db_message(exchange, symbol, is_sell, price, quantity, value_usd):
    base, quote = parse_symbol(symbol)
    return {
        "exchange": exchange, "base_asset": base, "quote_asset": quote,
        "price": price, "quantity": quantity, "value_usd": value_usd,
        "is_sell": is_sell
    }


# --- 3. Логика Воркеров (с изменениями) ---

def binance_worker(db_queue):  # Убираем ssl_context из аргументов
    print("[Binance Worker] Запущен.")

    async def _run():
        # Создаем ssl_context ВНУТРИ воркера
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession() as session:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            async with session.get(url, ssl=ssl_context) as response:
                data = orjson.loads(await response.read())
                symbols = [p['symbol'].lower() for p in data if
                           p['symbol'].endswith('USDT') and float(p['quoteVolume']) >= MIN_24H_VOLUME_USDT]

            ws_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join([f'{s}@aggTrade' for s in symbols])}"
            async with websockets.connect(ws_url, ssl=ssl_context) as websocket:
                print(f"[Binance Worker] Подключен к {len(symbols)} парам.")
                while True:
                    # ... (логика обработки сообщений без изменений)
                    wrapper = orjson.loads(await websocket.recv())
                    data = wrapper['data']
                    price, quantity = float(data['p']), float(data['q'])
                    if (value := price * quantity) >= MIN_USD_VALUE:
                        db_queue.put(format_db_message("Binance", data['s'], data['m'], price, quantity, value))

    while True:
        try:
            asyncio.run(_run())
        except Exception as e:
            print(f"[Binance Worker] Ошибка: {e}. Перезапуск через 10 сек..."); time.sleep(10)


def bybit_worker(db_queue):  # Убираем ssl_context из аргументов
    print("[Bybit Worker] Запущен.")

    async def _run():
        # Создаем ssl_context ВНУТРИ воркера
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession() as session:
            # ... (логика получения пар без изменений)
            url = "https://api.bybit.com/v5/market/tickers?category=spot"
            async with session.get(url, ssl=ssl_context) as response:
                data = orjson.loads(await response.read())
                symbols = [p['symbol'] for p in data['result']['list'] if
                           p['symbol'].endswith('USDT') and float(p['turnover24h']) >= MIN_24H_VOLUME_USDT]

            ws_url = "wss://stream.bybit.com/v5/public/spot"
            async with websockets.connect(ws_url, ssl=ssl_context) as websocket:
                # ... (логика подписки и обработки сообщений без изменений)
                chunk_size = 10
                for i in range(0, len(symbols), chunk_size):
                    chunk = symbols[i:i + chunk_size]
                    subscribe_message = {"op": "subscribe", "args": [f"publicTrade.{s}" for s in chunk]}
                    await websocket.send(orjson.dumps(subscribe_message))
                    await asyncio.sleep(0.1)
                print(f"[Bybit Worker] Отправлены запросы на подписку для {len(symbols)} пар.")
                while True:
                    data = orjson.loads(await websocket.recv())
                    if data.get('op') == 'ping':
                        await websocket.send(orjson.dumps({"op": "pong"}))
                    elif 'topic' in data and data['topic'].startswith('publicTrade'):
                        for trade in data['data']:
                            price, quantity = float(trade['p']), float(trade['v'])
                            if (value := price * quantity) >= MIN_USD_VALUE:
                                db_queue.put(
                                    format_db_message("Bybit", trade['s'], trade['S'] != 'Buy', price, quantity, value))

    while True:
        try:
            asyncio.run(_run())
        except Exception as e:
            print(f"[Bybit Worker] Ошибка: {e}. Перезапуск через 10 сек..."); time.sleep(10)


def coinbase_worker(db_queue, symbols_to_track):  # Убираем ssl_context из аргументов
    print("[Coinbase Worker] Запущен.")

    async def _run():
        # Создаем ssl_context ВНУТРИ воркера
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        if not symbols_to_track: return
        url = "wss://ws-feed.exchange.coinbase.com"
        subscribe_message = {"type": "subscribe", "product_ids": symbols_to_track, "channels": ["matches"]}
        async with websockets.connect(url, ssl=ssl_context) as websocket:
            await websocket.send(orjson.dumps(subscribe_message))
            print(f"[Coinbase Worker] Подключен к {len(symbols_to_track)} парам.")
            while True:
                # ... (логика обработки сообщений без изменений)
                data = orjson.loads(await websocket.recv())
                if data.get('type') == 'match':
                    price, quantity = float(data['price']), float(data['size'])
                    if (value := price * quantity) >= MIN_USD_VALUE:
                        normalized_symbol = data['product_id'].replace('-', '').replace('USD', 'USDT')
                        db_queue.put(
                            format_db_message("Coinbase", normalized_symbol, data['side'] == 'sell', price, quantity,
                                              value))

    while True:
        try:
            asyncio.run(_run())
        except Exception as e:
            print(f"[Coinbase Worker] Ошибка: {e}. Перезапуск через 10 сек..."); time.sleep(10)


# --- 4. Главный процесс-Менеджер ---
async def db_writer(queue: multiprocessing.Queue, db_pool):
    # ... (код этой функции без изменений)
    exchange_ids_cache = {}
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, exchange_name FROM exchanges")
        exchange_ids_cache = {row['exchange_name']: row['id'] for row in rows}
    print(f"ID бирж загружены в кэш: {exchange_ids_cache}")
    while True:
        try:
            trade_data = await asyncio.to_thread(queue.get)
            if trade_data is None: break
            exchange_id = exchange_ids_cache.get(trade_data["exchange"])
            if not exchange_id: continue
            async with db_pool.acquire() as conn:
                await conn.execute("""
                                   INSERT INTO large_trades (exchange_id, base_asset, quote_asset, price, quantity,
                                                             value_usd, is_sell)
                                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                                   """, exchange_id, trade_data['base_asset'], trade_data['quote_asset'],
                                   trade_data['price'],
                                   trade_data['quantity'], trade_data['value_usd'], trade_data['is_sell'])
            print(
                f"DB LOG: [{trade_data['exchange']}] {trade_data['base_asset']}/{trade_data['quote_asset']} | ${trade_data['value_usd']:,.2f}")
        except Exception as e:
            print(f"DB WRITER ERROR: Не удалось записать сделку. Ошибка: {e}")


async def main_manager(db_queue):
    # ... (логика менеджера без изменений)
    db_pool = None
    try:
        db_pool = await asyncpg.create_pool(user=os.getenv("POSTGRES_USER"), password=os.getenv("POSTGRES_PASSWORD"),
                                            host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
                                            database=os.getenv("POSTGRES_DB"))
        db_writer_task = asyncio.create_task(db_writer(db_queue, db_pool))
        print("\n--- Монитор запущен. Данные записываются в PostgreSQL... ---")
        process = psutil.Process(os.getpid())
        while not db_writer_task.done():
            await asyncio.sleep(60)
            cpu_usage = process.cpu_percent(interval=None)
            memory_usage_mb = process.memory_info().rss / (1024 * 1024)
            print("=" * 60)
            print(f"МОНИТОРИНГ: CPU (менеджер): {cpu_usage:.2f}% | RAM (менеджер): {memory_usage_mb:.2f} MB")
            print("=" * 60)
    finally:
        if db_pool:
            await db_pool.close()
            print("Пул соединений с БД закрыт.")


if __name__ == "__main__":
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass

    db_queue = multiprocessing.Queue()

    # Убираем создание ssl_context из главного процесса
    workers = [
        multiprocessing.Process(target=binance_worker, args=(db_queue,), daemon=True),
        multiprocessing.Process(target=bybit_worker, args=(db_queue,), daemon=True),
        multiprocessing.Process(target=coinbase_worker, args=(db_queue, COINBASE_SYMBOLS), daemon=True),
    ]

    for w in workers:
        w.start()

    # Главный процесс теперь запускает только db_writer и мониторинг
    try:
        asyncio.run(main_manager(db_queue))
    except KeyboardInterrupt:
        print("\nПолучен сигнал завершения. Остановка...")
    finally:
        # Корректное завершение
        db_queue.put(None)
        time.sleep(2)
        for w in workers:
            if w.is_alive():
                w.terminate()
                w.join()
        print("Все воркеры остановлены. Выход.")