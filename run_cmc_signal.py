#!/usr/bin/env python3
"""
Модуль для обработки криптовалютных сигналов.

Каждые 15 секунд:
1. Вызывает функцию create_raw_signals в БД
2. Если найдены новые сигналы, дополняет их данными с Binance и Bybit
3. Заполняет все необходимые поля для спотовых и фьючерсных данных
"""

import os
import sys
import time
import requests
import psycopg2
import schedule
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv()

# Конфигурация БД
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "port": os.getenv("POSTGRES_PORT", 5432)
}

# Константы
SPOT_CONTRACT_TYPE_ID = 2
BINANCE_EXCHANGE_ID = 1
BYBIT_EXCHANGE_ID = 2


@dataclass
class SpotMarketData:
    """Структура данных для спотового рынка."""
    capture_time: Optional[datetime] = None
    price: Optional[Decimal] = None
    vol_1h: Optional[Decimal] = None
    quote_vol_1h: Optional[Decimal] = None
    vol_24h: Optional[Decimal] = None
    quote_vol_24h: Optional[Decimal] = None


@dataclass
class PriceStats:
    """Структура для статистических данных по ценам."""
    price_min_1h: Optional[Decimal] = None
    price_max_1h: Optional[Decimal] = None
    price_min_24h: Optional[Decimal] = None
    price_max_24h: Optional[Decimal] = None
    price_min_7d: Optional[Decimal] = None
    price_max_7d: Optional[Decimal] = None
    price_min_30d: Optional[Decimal] = None
    price_max_30d: Optional[Decimal] = None
    percent_change_24h: Optional[Decimal] = None
    percent_change_7d: Optional[Decimal] = None
    percent_change_30d: Optional[Decimal] = None


@dataclass
class SignalData:
    """Полная структура данных для сигнала."""
    signal_id: int
    token_id: int
    token_symbol: str
    base_asset: str
    # Текущие данные
    spot_usdt_binance_now: Optional[SpotMarketData] = None
    spot_usdt_bybit_now: Optional[SpotMarketData] = None
    spot_btc_binance_now: Optional[SpotMarketData] = None
    spot_btc_bybit_now: Optional[SpotMarketData] = None
    # Предыдущие данные (10 минут назад)
    spot_usdt_binance_prev: Optional[SpotMarketData] = None
    spot_usdt_bybit_prev: Optional[SpotMarketData] = None
    spot_btc_binance_prev: Optional[SpotMarketData] = None
    spot_btc_bybit_prev: Optional[SpotMarketData] = None
    # Статистика
    price_stats: Optional[PriceStats] = None
    # Доступные торговые пары
    available_pairs: Set[Tuple[int, str]] = field(default_factory=set)


class BaseAPIClient:
    """Базовый класс для API клиентов."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Выполняет HTTP запрос к API.

        Args:
            endpoint: Конечная точка API
            params: Параметры запроса

        Returns:
            Ответ API в виде словаря или None при ошибке
        """
        url = self.base_url + endpoint
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                # Не логируем 400 ошибки подробно - это нормально для отсутствующих пар
                return None
            print(f"API HTTP error for {url}: {e}", file=sys.stderr)
            return None
        except requests.exceptions.RequestException as e:
            print(f"API request error for {url}: {e}", file=sys.stderr)
            return None


class BinanceSpotClient(BaseAPIClient):
    """Клиент для работы со спотовым API Binance."""

    def __init__(self):
        super().__init__('https://api.binance.com')

    def get_24hr_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получает 24-часовую статистику по символу.

        Args:
            symbol: Торговый символ (например, BTCUSDT)

        Returns:
            Словарь с данными тикера или None
        """
        data = self._make_request('/api/v3/ticker/24hr', {'symbol': symbol})
        if data and isinstance(data, dict) and 'lastPrice' in data:
            return data
        return None

    def get_klines(self, symbol: str, interval: str, limit: int = 500,
                   start_time: Optional[int] = None, end_time: Optional[int] = None) -> Optional[List]:
        """
        Получает данные свечей.

        Args:
            symbol: Торговый символ
            interval: Интервал свечей (1m, 1h, 1d и т.д.)
            limit: Количество свечей
            start_time: Начальное время в миллисекундах
            end_time: Конечное время в миллисекундах

        Returns:
            Список свечей или None
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time

        data = self._make_request('/api/v3/klines', params)
        return data if isinstance(data, list) else None


class BybitSpotClient(BaseAPIClient):
    """Клиент для работы со спотовым API Bybit."""

    def __init__(self):
        super().__init__('https://api.bybit.com')

    def get_24hr_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получает 24-часовую статистику по символу.

        Args:
            symbol: Торговый символ

        Returns:
            Словарь с данными тикера или None
        """
        data = self._make_request('/v5/market/tickers', {
            'category': 'spot',
            'symbol': symbol
        })

        if data and data.get('retCode') == 0:
            tickers = data.get('result', {}).get('list', [])
            return tickers[0] if tickers else None
        return None

    def get_klines(self, symbol: str, interval: str, limit: int = 200,
                   start_time: Optional[int] = None, end_time: Optional[int] = None) -> Optional[List]:
        """
        Получает данные свечей.

        Args:
            symbol: Торговый символ
            interval: Интервал свечей
            limit: Количество свечей
            start_time: Начальное время в миллисекундах
            end_time: Конечное время в миллисекундах

        Returns:
            Список свечей или None
        """
        params = {
            'category': 'spot',
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if start_time:
            params['start'] = start_time
        if end_time:
            params['end'] = end_time

        data = self._make_request('/v5/market/kline', params)

        if data and data.get('retCode') == 0:
            klines = data.get('result', {}).get('list', [])
            # Bybit возвращает свечи в обратном порядке
            return list(reversed(klines)) if klines else None
        return None


class MarketDataProcessor:
    """Процессор для обработки рыночных данных."""

    def __init__(self):
        self.binance_client = BinanceSpotClient()
        self.bybit_client = BybitSpotClient()

    def get_spot_data_binance(self, symbol: str, prev_time: datetime) -> Tuple[
        Optional[SpotMarketData], Optional[SpotMarketData]]:
        """
        Получает текущие и предыдущие спотовые данные с Binance.

        Args:
            symbol: Торговый символ
            prev_time: Время для получения предыдущих данных

        Returns:
            Кортеж (текущие_данные, предыдущие_данные)
        """
        try:
            # Получаем текущие данные
            ticker = self.binance_client.get_24hr_ticker(symbol)
            if not ticker:
                return None, None

            # Получаем часовые свечи для расчета объемов
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)

            # Текущий часовой объем
            hour_klines = self.binance_client.get_klines(
                symbol, '1h', limit=1
            )

            current_data = SpotMarketData(
                capture_time=now,
                price=Decimal(ticker['lastPrice']),
                vol_1h=Decimal(hour_klines[0][5]) if hour_klines else None,  # Base volume
                quote_vol_1h=Decimal(hour_klines[0][7]) if hour_klines else None,  # Quote volume
                vol_24h=Decimal(ticker['volume']),
                quote_vol_24h=Decimal(ticker['quoteVolume'])
            )

            # Получаем данные на момент prev_time
            prev_timestamp = int(prev_time.timestamp() * 1000)
            prev_klines = self.binance_client.get_klines(
                symbol, '1m', limit=1,
                start_time=prev_timestamp,
                end_time=prev_timestamp + 60000
            )

            if not prev_klines:
                return current_data, None

            # Получаем часовой объем на момент prev_time
            prev_hour_start = prev_time - timedelta(hours=1)
            prev_hour_klines = self.binance_client.get_klines(
                symbol, '1h', limit=1,
                start_time=int(prev_hour_start.timestamp() * 1000)
            )

            # Получаем 24h объем на момент prev_time
            prev_24h_start = prev_time - timedelta(hours=24)
            prev_24h_klines = self.binance_client.get_klines(
                symbol, '1h', limit=24,
                start_time=int(prev_24h_start.timestamp() * 1000),
                end_time=prev_timestamp
            )

            prev_vol_24h = sum(Decimal(k[5]) for k in prev_24h_klines) if prev_24h_klines else None
            prev_quote_vol_24h = sum(Decimal(k[7]) for k in prev_24h_klines) if prev_24h_klines else None

            prev_data = SpotMarketData(
                capture_time=prev_time,
                price=Decimal(prev_klines[0][4]),  # Close price
                vol_1h=Decimal(prev_hour_klines[0][5]) if prev_hour_klines else None,
                quote_vol_1h=Decimal(prev_hour_klines[0][7]) if prev_hour_klines else None,
                vol_24h=prev_vol_24h,
                quote_vol_24h=prev_quote_vol_24h
            )

            return current_data, prev_data

        except Exception as e:
            print(f"Error getting Binance spot data for {symbol}: {e}", file=sys.stderr)
            return None, None

    def get_spot_data_bybit(self, symbol: str, prev_time: datetime) -> Tuple[
        Optional[SpotMarketData], Optional[SpotMarketData]]:
        """
        Получает текущие и предыдущие спотовые данные с Bybit.

        Args:
            symbol: Торговый символ
            prev_time: Время для получения предыдущих данных

        Returns:
            Кортеж (текущие_данные, предыдущие_данные)
        """
        try:
            # Получаем текущие данные
            ticker = self.bybit_client.get_24hr_ticker(symbol)
            if not ticker:
                return None, None

            now = datetime.now(timezone.utc)

            # Получаем часовые свечи для расчета объемов
            hour_klines = self.bybit_client.get_klines(
                symbol, '60', limit=1
            )

            current_data = SpotMarketData(
                capture_time=now,
                price=Decimal(ticker['lastPrice']),
                vol_1h=Decimal(hour_klines[-1][5]) if hour_klines else None,
                quote_vol_1h=Decimal(hour_klines[-1][6]) if hour_klines else None,
                vol_24h=Decimal(ticker['volume24h']),
                quote_vol_24h=Decimal(ticker['turnover24h'])
            )

            # Получаем данные на момент prev_time
            prev_timestamp = int(prev_time.timestamp() * 1000)
            prev_klines = self.bybit_client.get_klines(
                symbol, '1', limit=1,
                start_time=prev_timestamp,
                end_time=prev_timestamp + 60000
            )

            if not prev_klines:
                return current_data, None

            # Получаем объемы на момент prev_time
            prev_hour_start = prev_time - timedelta(hours=1)
            prev_hour_klines = self.bybit_client.get_klines(
                symbol, '60', limit=1,
                start_time=int(prev_hour_start.timestamp() * 1000)
            )

            # Для 24h объема суммируем часовые свечи
            prev_24h_start = prev_time - timedelta(hours=24)
            prev_24h_klines = self.bybit_client.get_klines(
                symbol, '60', limit=24,
                start_time=int(prev_24h_start.timestamp() * 1000),
                end_time=prev_timestamp
            )

            prev_vol_24h = sum(Decimal(k[5]) for k in prev_24h_klines) if prev_24h_klines else None
            prev_quote_vol_24h = sum(Decimal(k[6]) for k in prev_24h_klines) if prev_24h_klines else None

            prev_data = SpotMarketData(
                capture_time=prev_time,
                price=Decimal(prev_klines[-1][4]),
                vol_1h=Decimal(prev_hour_klines[-1][5]) if prev_hour_klines else None,
                quote_vol_1h=Decimal(prev_hour_klines[-1][6]) if prev_hour_klines else None,
                vol_24h=prev_vol_24h,
                quote_vol_24h=prev_quote_vol_24h
            )

            return current_data, prev_data

        except Exception as e:
            print(f"Error getting Bybit spot data for {symbol}: {e}", file=sys.stderr)
            return None, None

    def get_price_statistics(self, base_asset: str, quote_asset: str = 'USDT',
                             available_pairs: Set[Tuple[int, str]] = None) -> Optional[PriceStats]:
        """
        Получает статистику цен для пары.

        Args:
            base_asset: Базовый актив
            quote_asset: Котируемый актив
            available_pairs: Доступные торговые пары

        Returns:
            Объект PriceStats или None
        """
        symbol = f"{base_asset}{quote_asset}"

        # Проверяем доступность на биржах
        binance_available = available_pairs and (BINANCE_EXCHANGE_ID, symbol) in available_pairs
        bybit_available = available_pairs and (BYBIT_EXCHANGE_ID, symbol) in available_pairs

        # Сначала пробуем Binance, если пара доступна
        if binance_available:
            print(f"  Получение статистики с Binance для {symbol}...")
            stats = self._get_price_stats_binance(symbol)
            if stats:
                return stats

        # Если не получилось или не доступна на Binance, пробуем Bybit
        if bybit_available:
            print(f"  Получение статистики с Bybit для {symbol}...")
            return self._get_price_stats_bybit(symbol)

        print(f"  ⚠️ Пара {symbol} не доступна ни на одной бирже для получения статистики")
        return None

    def _get_price_stats_binance(self, symbol: str) -> Optional[PriceStats]:
        """Получает статистику цен с Binance."""
        try:
            now = datetime.now(timezone.utc)

            # Получаем свечи за разные периоды
            klines_1m = self.binance_client.get_klines(symbol, '1m', limit=60)  # 1 час
            klines_1h = self.binance_client.get_klines(symbol, '1h', limit=24)  # 24 часа
            klines_1d = self.binance_client.get_klines(symbol, '1d', limit=30)  # 30 дней

            if not all([klines_1m, klines_1h, klines_1d]):
                return None

            # Расчет минимумов и максимумов
            stats = PriceStats()

            # 1 час
            prices_1h = [Decimal(k[2]) for k in klines_1m]  # High prices
            lows_1h = [Decimal(k[3]) for k in klines_1m]  # Low prices
            stats.price_max_1h = max(prices_1h)
            stats.price_min_1h = min(lows_1h)

            # 24 часа
            prices_24h = [Decimal(k[2]) for k in klines_1h]
            lows_24h = [Decimal(k[3]) for k in klines_1h]
            stats.price_max_24h = max(prices_24h)
            stats.price_min_24h = min(lows_24h)

            # 7 дней
            klines_7d = klines_1d[-7:]
            prices_7d = [Decimal(k[2]) for k in klines_7d]
            lows_7d = [Decimal(k[3]) for k in klines_7d]
            stats.price_max_7d = max(prices_7d)
            stats.price_min_7d = min(lows_7d)

            # 30 дней
            prices_30d = [Decimal(k[2]) for k in klines_1d]
            lows_30d = [Decimal(k[3]) for k in klines_1d]
            stats.price_max_30d = max(prices_30d)
            stats.price_min_30d = min(lows_30d)

            # Расчет процентных изменений
            current_price = Decimal(klines_1m[-1][4])  # Последняя цена закрытия

            # 24h изменение
            price_24h_ago = Decimal(klines_1h[0][1])  # Цена открытия 24 часа назад
            stats.percent_change_24h = ((current_price - price_24h_ago) / price_24h_ago * 100).quantize(Decimal('0.01'))

            # 7d изменение
            price_7d_ago = Decimal(klines_7d[0][1])
            stats.percent_change_7d = ((current_price - price_7d_ago) / price_7d_ago * 100).quantize(Decimal('0.01'))

            # 30d изменение
            price_30d_ago = Decimal(klines_1d[0][1])
            stats.percent_change_30d = ((current_price - price_30d_ago) / price_30d_ago * 100).quantize(Decimal('0.01'))

            return stats

        except Exception as e:
            print(f"Error getting price statistics from Binance for {symbol}: {e}", file=sys.stderr)
            return None

    def _get_price_stats_bybit(self, symbol: str) -> Optional[PriceStats]:
        """Получает статистику цен с Bybit."""
        try:
            now = datetime.now(timezone.utc)

            # Получаем свечи за разные периоды
            klines_1m = self.bybit_client.get_klines(symbol, '1', limit=60)  # 1 час
            klines_1h = self.bybit_client.get_klines(symbol, '60', limit=24)  # 24 часа
            klines_1d = self.bybit_client.get_klines(symbol, 'D', limit=30)  # 30 дней

            if not all([klines_1m, klines_1h, klines_1d]):
                return None

            # Расчет минимумов и максимумов
            stats = PriceStats()

            # 1 час
            prices_1h = [Decimal(k[2]) for k in klines_1m]
            lows_1h = [Decimal(k[3]) for k in klines_1m]
            stats.price_max_1h = max(prices_1h)
            stats.price_min_1h = min(lows_1h)

            # 24 часа
            prices_24h = [Decimal(k[2]) for k in klines_1h]
            lows_24h = [Decimal(k[3]) for k in klines_1h]
            stats.price_max_24h = max(prices_24h)
            stats.price_min_24h = min(lows_24h)

            # 7 дней
            klines_7d = klines_1d[-7:]
            prices_7d = [Decimal(k[2]) for k in klines_7d]
            lows_7d = [Decimal(k[3]) for k in klines_7d]
            stats.price_max_7d = max(prices_7d)
            stats.price_min_7d = min(lows_7d)

            # 30 дней
            prices_30d = [Decimal(k[2]) for k in klines_1d]
            lows_30d = [Decimal(k[3]) for k in klines_1d]
            stats.price_max_30d = max(prices_30d)
            stats.price_min_30d = min(lows_30d)

            # Расчет процентных изменений
            current_price = Decimal(klines_1m[-1][4])

            # 24h изменение
            price_24h_ago = Decimal(klines_1h[0][1])
            stats.percent_change_24h = ((current_price - price_24h_ago) / price_24h_ago * 100).quantize(Decimal('0.01'))

            # 7d изменение
            price_7d_ago = Decimal(klines_7d[0][1])
            stats.percent_change_7d = ((current_price - price_7d_ago) / price_7d_ago * 100).quantize(Decimal('0.01'))

            # 30d изменение
            price_30d_ago = Decimal(klines_1d[0][1])
            stats.percent_change_30d = ((current_price - price_30d_ago) / price_30d_ago * 100).quantize(Decimal('0.01'))

            return stats

        except Exception as e:
            print(f"Error getting price statistics from Bybit for {symbol}: {e}", file=sys.stderr)
            return None


class DatabaseManager:
    """Менеджер для работы с базой данных."""

    @staticmethod
    def get_connection() -> Optional[psycopg2.extensions.connection]:
        """
        Создает и возвращает соединение с БД.

        Returns:
            Объект соединения или None при ошибке
        """
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
        except psycopg2.OperationalError as e:
            print(f"Database connection error: {e}", file=sys.stderr)
            return None

    @staticmethod
    def get_available_trading_pairs(cursor, token_id: int) -> Set[Tuple[int, str]]:
        """
        Получает доступные торговые пары для токена.

        Args:
            cursor: Курсор БД
            token_id: ID токена

        Returns:
            Множество кортежей (exchange_id, pair_symbol)
        """
        query = """
            SELECT exchange_id, pair_symbol
            FROM trading_pairs
            WHERE token_id = %s AND contract_type_id = %s
        """
        cursor.execute(query, (token_id, SPOT_CONTRACT_TYPE_ID))
        return set(cursor.fetchall())

    @staticmethod
    def get_new_signals(cursor) -> List[Tuple[int, int, str, str]]:
        """
        Получает новые сигналы для обработки.

        Args:
            cursor: Курсор БД

        Returns:
            Список кортежей (signal_id, token_id, token_symbol, base_asset)
        """
        # Получаем сигналы, где не заполнены спотовые данные
        query = """
            SELECT id, token_id, token_symbol, base_asset
            FROM signals_10min
            WHERE signal_time > NOW() - INTERVAL '10 minutes'
              AND spot_usdt_binance_price_now IS NULL
        """
        cursor.execute(query)
        return cursor.fetchall()

    @staticmethod
    def update_signal(cursor, signal_data: SignalData) -> bool:
        """
        Обновляет данные сигнала в БД.

        Args:
            cursor: Курсор БД
            signal_data: Данные сигнала

        Returns:
            True при успешном обновлении
        """
        try:
            update_parts = []
            params = {'signal_id': signal_data.signal_id}

            # Обновляем данные Binance USDT
            if signal_data.spot_usdt_binance_now:
                update_parts.extend([
                    "spot_usdt_binance_capture_time_now = %(spot_usdt_binance_capture_time_now)s",
                    "spot_usdt_binance_price_now = %(spot_usdt_binance_price_now)s",
                    "spot_usdt_binance_vol_1h_now = %(spot_usdt_binance_vol_1h_now)s",
                    "spot_usdt_binance_quote_vol_1h_now = %(spot_usdt_binance_quote_vol_1h_now)s",
                    "spot_usdt_binance_vol_24h_now = %(spot_usdt_binance_vol_24h_now)s",
                    "spot_usdt_binance_quote_vol_24h_now = %(spot_usdt_binance_quote_vol_24h_now)s"
                ])
                params.update({
                    'spot_usdt_binance_capture_time_now': signal_data.spot_usdt_binance_now.capture_time,
                    'spot_usdt_binance_price_now': signal_data.spot_usdt_binance_now.price,
                    'spot_usdt_binance_vol_1h_now': signal_data.spot_usdt_binance_now.vol_1h,
                    'spot_usdt_binance_quote_vol_1h_now': signal_data.spot_usdt_binance_now.quote_vol_1h,
                    'spot_usdt_binance_vol_24h_now': signal_data.spot_usdt_binance_now.vol_24h,
                    'spot_usdt_binance_quote_vol_24h_now': signal_data.spot_usdt_binance_now.quote_vol_24h
                })

            if signal_data.spot_usdt_binance_prev:
                update_parts.extend([
                    "spot_usdt_binance_capture_time_prev = %(spot_usdt_binance_capture_time_prev)s",
                    "spot_usdt_binance_price_prev = %(spot_usdt_binance_price_prev)s",
                    "spot_usdt_binance_vol_1h_prev = %(spot_usdt_binance_vol_1h_prev)s",
                    "spot_usdt_binance_quote_vol_1h_prev = %(spot_usdt_binance_quote_vol_1h_prev)s",
                    "spot_usdt_binance_vol_24h_prev = %(spot_usdt_binance_vol_24h_prev)s",
                    "spot_usdt_binance_quote_vol_24h_prev = %(spot_usdt_binance_quote_vol_24h_prev)s"
                ])
                params.update({
                    'spot_usdt_binance_capture_time_prev': signal_data.spot_usdt_binance_prev.capture_time,
                    'spot_usdt_binance_price_prev': signal_data.spot_usdt_binance_prev.price,
                    'spot_usdt_binance_vol_1h_prev': signal_data.spot_usdt_binance_prev.vol_1h,
                    'spot_usdt_binance_quote_vol_1h_prev': signal_data.spot_usdt_binance_prev.quote_vol_1h,
                    'spot_usdt_binance_vol_24h_prev': signal_data.spot_usdt_binance_prev.vol_24h,
                    'spot_usdt_binance_quote_vol_24h_prev': signal_data.spot_usdt_binance_prev.quote_vol_24h
                })

            # Обновляем данные Bybit USDT
            if signal_data.spot_usdt_bybit_now:
                update_parts.extend([
                    "spot_usdt_bybit_capture_time_now = %(spot_usdt_bybit_capture_time_now)s",
                    "spot_usdt_bybit_price_now = %(spot_usdt_bybit_price_now)s",
                    "spot_usdt_bybit_vol_1h_now = %(spot_usdt_bybit_vol_1h_now)s",
                    "spot_usdt_bybit_quote_vol_1h_now = %(spot_usdt_bybit_quote_vol_1h_now)s",
                    "spot_usdt_bybit_vol_24h_now = %(spot_usdt_bybit_vol_24h_now)s",
                    "spot_usdt_bybit_quote_vol_24h_now = %(spot_usdt_bybit_quote_vol_24h_now)s"
                ])
                params.update({
                    'spot_usdt_bybit_capture_time_now': signal_data.spot_usdt_bybit_now.capture_time,
                    'spot_usdt_bybit_price_now': signal_data.spot_usdt_bybit_now.price,
                    'spot_usdt_bybit_vol_1h_now': signal_data.spot_usdt_bybit_now.vol_1h,
                    'spot_usdt_bybit_quote_vol_1h_now': signal_data.spot_usdt_bybit_now.quote_vol_1h,
                    'spot_usdt_bybit_vol_24h_now': signal_data.spot_usdt_bybit_now.vol_24h,
                    'spot_usdt_bybit_quote_vol_24h_now': signal_data.spot_usdt_bybit_now.quote_vol_24h
                })

            if signal_data.spot_usdt_bybit_prev:
                update_parts.extend([
                    "spot_usdt_bybit_capture_time_prev = %(spot_usdt_bybit_capture_time_prev)s",
                    "spot_usdt_bybit_price_prev = %(spot_usdt_bybit_price_prev)s",
                    "spot_usdt_bybit_vol_1h_prev = %(spot_usdt_bybit_vol_1h_prev)s",
                    "spot_usdt_bybit_quote_vol_1h_prev = %(spot_usdt_bybit_quote_vol_1h_prev)s",
                    "spot_usdt_bybit_vol_24h_prev = %(spot_usdt_bybit_vol_24h_prev)s",
                    "spot_usdt_bybit_quote_vol_24h_prev = %(spot_usdt_bybit_quote_vol_24h_prev)s"
                ])
                params.update({
                    'spot_usdt_bybit_capture_time_prev': signal_data.spot_usdt_bybit_prev.capture_time,
                    'spot_usdt_bybit_price_prev': signal_data.spot_usdt_bybit_prev.price,
                    'spot_usdt_bybit_vol_1h_prev': signal_data.spot_usdt_bybit_prev.vol_1h,
                    'spot_usdt_bybit_quote_vol_1h_prev': signal_data.spot_usdt_bybit_prev.quote_vol_1h,
                    'spot_usdt_bybit_vol_24h_prev': signal_data.spot_usdt_bybit_prev.vol_24h,
                    'spot_usdt_bybit_quote_vol_24h_prev': signal_data.spot_usdt_bybit_prev.quote_vol_24h
                })

            # Обновляем данные Binance BTC
            if signal_data.spot_btc_binance_now:
                update_parts.extend([
                    "spot_btc_binance_capture_time_now = %(spot_btc_binance_capture_time_now)s",
                    "spot_btc_binance_price_now = %(spot_btc_binance_price_now)s",
                    "spot_btc_binance_vol_1h_now = %(spot_btc_binance_vol_1h_now)s",
                    "spot_btc_binance_quote_vol_1h_now = %(spot_btc_binance_quote_vol_1h_now)s",
                    "spot_btc_binance_vol_24h_now = %(spot_btc_binance_vol_24h_now)s",
                    "spot_btc_binance_quote_vol_24h_now = %(spot_btc_binance_quote_vol_24h_now)s"
                ])
                params.update({
                    'spot_btc_binance_capture_time_now': signal_data.spot_btc_binance_now.capture_time,
                    'spot_btc_binance_price_now': signal_data.spot_btc_binance_now.price,
                    'spot_btc_binance_vol_1h_now': signal_data.spot_btc_binance_now.vol_1h,
                    'spot_btc_binance_quote_vol_1h_now': signal_data.spot_btc_binance_now.quote_vol_1h,
                    'spot_btc_binance_vol_24h_now': signal_data.spot_btc_binance_now.vol_24h,
                    'spot_btc_binance_quote_vol_24h_now': signal_data.spot_btc_binance_now.quote_vol_24h
                })

            if signal_data.spot_btc_binance_prev:
                update_parts.extend([
                    "spot_btc_binance_capture_time_prev = %(spot_btc_binance_capture_time_prev)s",
                    "spot_btc_binance_price_prev = %(spot_btc_binance_price_prev)s",
                    "spot_btc_binance_vol_1h_prev = %(spot_btc_binance_vol_1h_prev)s",
                    "spot_btc_binance_quote_vol_1h_prev = %(spot_btc_binance_quote_vol_1h_prev)s",
                    "spot_btc_binance_vol_24h_prev = %(spot_btc_binance_vol_24h_prev)s",
                    "spot_btc_binance_quote_vol_24h_prev = %(spot_btc_binance_quote_vol_24h_prev)s"
                ])
                params.update({
                    'spot_btc_binance_capture_time_prev': signal_data.spot_btc_binance_prev.capture_time,
                    'spot_btc_binance_price_prev': signal_data.spot_btc_binance_prev.price,
                    'spot_btc_binance_vol_1h_prev': signal_data.spot_btc_binance_prev.vol_1h,
                    'spot_btc_binance_quote_vol_1h_prev': signal_data.spot_btc_binance_prev.quote_vol_1h,
                    'spot_btc_binance_vol_24h_prev': signal_data.spot_btc_binance_prev.vol_24h,
                    'spot_btc_binance_quote_vol_24h_prev': signal_data.spot_btc_binance_prev.quote_vol_24h
                })

            # Обновляем данные Bybit BTC
            if signal_data.spot_btc_bybit_now:
                update_parts.extend([
                    "spot_btc_bybit_capture_time_now = %(spot_btc_bybit_capture_time_now)s",
                    "spot_btc_bybit_price_now = %(spot_btc_bybit_price_now)s",
                    "spot_btc_bybit_vol_1h_now = %(spot_btc_bybit_vol_1h_now)s",
                    "spot_btc_bybit_quote_vol_1h_now = %(spot_btc_bybit_quote_vol_1h_now)s",
                    "spot_btc_bybit_vol_24h_now = %(spot_btc_bybit_vol_24h_now)s",
                    "spot_btc_bybit_quote_vol_24h_now = %(spot_btc_bybit_quote_vol_24h_now)s"
                ])
                params.update({
                    'spot_btc_bybit_capture_time_now': signal_data.spot_btc_bybit_now.capture_time,
                    'spot_btc_bybit_price_now': signal_data.spot_btc_bybit_now.price,
                    'spot_btc_bybit_vol_1h_now': signal_data.spot_btc_bybit_now.vol_1h,
                    'spot_btc_bybit_quote_vol_1h_now': signal_data.spot_btc_bybit_now.quote_vol_1h,
                    'spot_btc_bybit_vol_24h_now': signal_data.spot_btc_bybit_now.vol_24h,
                    'spot_btc_bybit_quote_vol_24h_now': signal_data.spot_btc_bybit_now.quote_vol_24h
                })

            if signal_data.spot_btc_bybit_prev:
                update_parts.extend([
                    "spot_btc_bybit_capture_time_prev = %(spot_btc_bybit_capture_time_prev)s",
                    "spot_btc_bybit_price_prev = %(spot_btc_bybit_price_prev)s",
                    "spot_btc_bybit_vol_1h_prev = %(spot_btc_bybit_vol_1h_prev)s",
                    "spot_btc_bybit_quote_vol_1h_prev = %(spot_btc_bybit_quote_vol_1h_prev)s",
                    "spot_btc_bybit_vol_24h_prev = %(spot_btc_bybit_vol_24h_prev)s",
                    "spot_btc_bybit_quote_vol_24h_prev = %(spot_btc_bybit_quote_vol_24h_prev)s"
                ])
                params.update({
                    'spot_btc_bybit_capture_time_prev': signal_data.spot_btc_bybit_prev.capture_time,
                    'spot_btc_bybit_price_prev': signal_data.spot_btc_bybit_prev.price,
                    'spot_btc_bybit_vol_1h_prev': signal_data.spot_btc_bybit_prev.vol_1h,
                    'spot_btc_bybit_quote_vol_1h_prev': signal_data.spot_btc_bybit_prev.quote_vol_1h,
                    'spot_btc_bybit_vol_24h_prev': signal_data.spot_btc_bybit_prev.vol_24h,
                    'spot_btc_bybit_quote_vol_24h_prev': signal_data.spot_btc_bybit_prev.quote_vol_24h
                })

            # Обновляем статистику цен
            if signal_data.price_stats:
                update_parts.extend([
                    "price_min_1h = %(price_min_1h)s",
                    "price_max_1h = %(price_max_1h)s",
                    "price_min_24h = %(price_min_24h)s",
                    "price_max_24h = %(price_max_24h)s",
                    "price_min_7d = %(price_min_7d)s",
                    "price_max_7d = %(price_max_7d)s",
                    "price_min_30d = %(price_min_30d)s",
                    "price_max_30d = %(price_max_30d)s",
                    "percent_change_24h = %(percent_change_24h)s",
                    "percent_change_7d = %(percent_change_7d)s",
                    "percent_change_30d = %(percent_change_30d)s"
                ])
                params.update({
                    'price_min_1h': signal_data.price_stats.price_min_1h,
                    'price_max_1h': signal_data.price_stats.price_max_1h,
                    'price_min_24h': signal_data.price_stats.price_min_24h,
                    'price_max_24h': signal_data.price_stats.price_max_24h,
                    'price_min_7d': signal_data.price_stats.price_min_7d,
                    'price_max_7d': signal_data.price_stats.price_max_7d,
                    'price_min_30d': signal_data.price_stats.price_min_30d,
                    'price_max_30d': signal_data.price_stats.price_max_30d,
                    'percent_change_24h': signal_data.price_stats.percent_change_24h,
                    'percent_change_7d': signal_data.price_stats.percent_change_7d,
                    'percent_change_30d': signal_data.price_stats.percent_change_30d
                })

            if not update_parts:
                print(f"No data to update for signal {signal_data.signal_id}")
                return False

            query = f"""
                UPDATE signals_10min 
                SET {', '.join(update_parts)}
                WHERE id = %(signal_id)s
            """

            cursor.execute(query, params)
            return True

        except Exception as e:
            print(f"Error updating signal {signal_data.signal_id}: {e}", file=sys.stderr)
            return False


class SignalProcessor:
    """Основной процессор сигналов."""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.market_processor = MarketDataProcessor()

    def process_signals(self) -> None:
        """
        Основной метод обработки сигналов.

        Выполняет следующие шаги:
        1. Вызывает функцию create_raw_signals в БД
        2. Получает новые сигналы
        3. Обогащает их данными с бирж
        4. Обновляет записи в БД
        """
        print(f"\n[{datetime.now()}] === Начало обработки сигналов ===")

        conn = self.db_manager.get_connection()
        if not conn:
            print("Failed to connect to database", file=sys.stderr)
            return

        try:
            with conn.cursor() as cursor:
                # Шаг 1: Вызываем функцию в БД
                print("Шаг 1: Вызов функции create_raw_signals...")
                cursor.execute("SELECT create_raw_signals();")
                new_signals_count = cursor.fetchone()[0]
                conn.commit()
                print(f"Функция вернула: {new_signals_count} новых сигналов")

                if new_signals_count == 0:
                    print("Новых сигналов не найдено")
                    return

                # Шаг 2: Получаем новые сигналы
                print("\nШаг 2: Получение новых сигналов для обработки...")
                signals = self.db_manager.get_new_signals(cursor)

                if not signals:
                    print("Не найдено сигналов для обработки")
                    return

                print(f"Найдено {len(signals)} сигналов для обработки")

                # Шаг 3: Обрабатываем каждый сигнал
                for signal_id, token_id, token_symbol, base_asset in signals:
                    print(f"\n--- Обработка сигнала ID: {signal_id}, токен: {token_symbol} ---")

                    # Создаем объект для хранения данных
                    signal_data = SignalData(
                        signal_id=signal_id,
                        token_id=token_id,
                        token_symbol=token_symbol,
                        base_asset=base_asset
                    )

                    # Получаем доступные торговые пары
                    signal_data.available_pairs = self.db_manager.get_available_trading_pairs(cursor, token_id)

                    # Время для получения предыдущих данных (10 минут назад)
                    prev_time = datetime.now(timezone.utc) - timedelta(minutes=10)

                    # Обрабатываем каждую пару
                    self._process_trading_pairs(signal_data, prev_time)

                    # Получаем статистику цен
                    print(f"Получение статистики цен для {base_asset}...")
                    signal_data.price_stats = self.market_processor.get_price_statistics(
                        base_asset,
                        available_pairs=signal_data.available_pairs
                    )

                    # Обновляем данные в БД
                    print(f"Обновление данных в БД для сигнала {signal_id}...")
                    if self.db_manager.update_signal(cursor, signal_data):
                        conn.commit()
                        print(f"✅ Сигнал {signal_id} успешно обновлен")
                    else:
                        conn.rollback()
                        print(f"❌ Ошибка обновления сигнала {signal_id}")

        except Exception as e:
            print(f"Critical error during signal processing: {e}", file=sys.stderr)
            if conn:
                conn.rollback()

        finally:
            if conn:
                conn.close()
            print(f"\n[{datetime.now()}] === Обработка сигналов завершена ===")

    def _process_trading_pairs(self, signal_data: SignalData, prev_time: datetime) -> None:
        """
        Обрабатывает торговые пары для сигнала.

        Args:
            signal_data: Данные сигнала
            prev_time: Время для получения предыдущих данных
        """
        base_asset = signal_data.base_asset

        # Проверяем доступность пар на биржах
        binance_usdt_available = (BINANCE_EXCHANGE_ID, f"{base_asset}USDT") in signal_data.available_pairs
        binance_btc_available = (BINANCE_EXCHANGE_ID, f"{base_asset}BTC") in signal_data.available_pairs
        bybit_usdt_available = (BYBIT_EXCHANGE_ID, f"{base_asset}USDT") in signal_data.available_pairs
        bybit_btc_available = (BYBIT_EXCHANGE_ID, f"{base_asset}BTC") in signal_data.available_pairs

        # Получаем данные USDT пар
        if binance_usdt_available:
            print(f"Получение данных {base_asset}USDT с Binance...")
            now_data, prev_data = self.market_processor.get_spot_data_binance(f"{base_asset}USDT", prev_time)
            signal_data.spot_usdt_binance_now = now_data
            signal_data.spot_usdt_binance_prev = prev_data

        if bybit_usdt_available:
            print(f"Получение данных {base_asset}USDT с Bybit...")
            now_data, prev_data = self.market_processor.get_spot_data_bybit(f"{base_asset}USDT", prev_time)
            signal_data.spot_usdt_bybit_now = now_data
            signal_data.spot_usdt_bybit_prev = prev_data

        # Получаем данные BTC пар
        if binance_btc_available:
            print(f"Получение данных {base_asset}BTC с Binance...")
            now_data, prev_data = self.market_processor.get_spot_data_binance(f"{base_asset}BTC", prev_time)
            signal_data.spot_btc_binance_now = now_data
            signal_data.spot_btc_binance_prev = prev_data

        if bybit_btc_available:
            print(f"Получение данных {base_asset}BTC с Bybit...")
            now_data, prev_data = self.market_processor.get_spot_data_bybit(f"{base_asset}BTC", prev_time)
            signal_data.spot_btc_bybit_now = now_data
            signal_data.spot_btc_bybit_prev = prev_data


def main():
    """Главная функция запуска планировщика."""
    print("=" * 60)
    print("Запуск планировщика обработки криптовалютных сигналов")
    print(f"Время запуска: {datetime.now()}")
    print(f"Интервал обработки: каждые 15 секунд")
    print("=" * 60)

    # Создаем процессор сигналов
    processor = SignalProcessor()

    # Настраиваем планировщик
    schedule.every(15).seconds.do(processor.process_signals)

    print("\nПланировщик запущен. Первая проверка через 15 секунд...")
    print("Для остановки нажмите Ctrl+C\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nПланировщик остановлен пользователем")
        print(f"Время остановки: {datetime.now()}")
    except Exception as e:
        print(f"\n\nКритическая ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()