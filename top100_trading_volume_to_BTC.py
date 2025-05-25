import ccxt.async_support as ccxt
import requests
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
import time
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Log ccxt version for debugging
logger.info(f"Using ccxt version: {ccxt.__version__}")

# Load environment variables from .env file (for future extensibility)
load_dotenv()


@dataclass
class CoinData:
    """Data class to store coin information."""
    name: str
    symbol: str
    volume_24h_btc: float
    price_btc: float
    market_cap_btc: float
    exchange_volumes: Dict[str, float]  # Volume per exchange


class CoinGeckoClient:
    """Client for interacting with CoinGecko API to get top 100 coins."""

    BASE_URL = "https://api.coingecko.com/api/v3"
    REQUEST_DELAY = 2.0  # Delay between requests (seconds)

    def __init__(self):
        """Initialize CoinGecko API client."""
        self.headers = {'Accept': 'application/json'}
        self.session = requests.Session()

    def _make_request(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Dict:
        """
        Make HTTP request to CoinGecko API.

        Args:
            endpoint (str): API endpoint path.
            params (Dict[str, str], optional): Query parameters for the request.

        Returns:
            Dict: JSON response from the API.

        Raises:
            requests.exceptions.HTTPError: If the request fails with an HTTP error.
            ValueError: If the API response is invalid.
        """
        url = f"{self.BASE_URL}{endpoint}"
        try:
            logger.debug(f"Making request to {url} with params {params}")
            response = self.session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and 'error' in data:
                logger.error(f"API error: {data['error']}")
                raise ValueError(f"API Error: {data['error']}")

            return data
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    def get_top_100_coins(self) -> List[Dict]:
        """
        Fetch top 100 cryptocurrencies by market cap.

        Returns:
            List[Dict]: List of coin data dictionaries.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
            ValueError: If the API response is invalid.
        """
        endpoint = "/coins/markets"
        params = {
            'vs_currency': 'btc',
            'order': 'market_cap_desc',
            'per_page': '100',
            'page': '1',
            'sparkline': 'false'
        }
        logger.info("Fetching top 100 coins by market cap from CoinGecko API")
        time.sleep(self.REQUEST_DELAY)
        return self._make_request(endpoint, params)


class ExchangeClient:
    """Client for interacting with multiple exchanges via ccxt.async_support."""

    EXCHANGES = {
        'binance': ccxt.binance,
        'coinbase': ccxt.coinbase,
        'kraken': ccxt.kraken,
        'gate': ccxt.gate,
        'huobi': ccxt.huobi,
        'bybit': ccxt.bybit,
        'okx': ccxt.okx,
        'kucoin': ccxt.kucoin,
        'bitfinex': ccxt.bitfinex,
        'upbit': ccxt.upbit
    }

    def __init__(self):
        """
        Initialize exchange clients with rate limiting.
        """
        self.clients = {}
        for name, exchange_class in self.EXCHANGES.items():
            try:
                self.clients[name] = exchange_class({
                    'enableRateLimit': True,  # Respect exchange rate limits
                    'apiKey': None,  # Public endpoints only
                    'secret': None
                })
                logger.info(f"Initialized {name} client")
            except Exception as e:
                logger.warning(f"Failed to initialize {name}: {str(e)}")
                self.clients[name] = None

    async def get_btc_pair_volume(self, symbol: str) -> tuple[float, Dict[str, float]]:
        """
        Fetch 24h trading volume in BTC pairs across all exchanges asynchronously.

        Args:
            symbol (str): Coin symbol (e.g., 'ETH').

        Returns:
            tuple[float, Dict[str, float]]: Total volume in BTC and per-exchange volumes.
        """
        total_volume_btc = 0.0
        exchange_volumes = {name: 0.0 for name in self.EXCHANGES}
        pair_formats = [
            f"{symbol}/BTC", f"{symbol}-BTC", f"{symbol}BTC", f"BTC-{symbol}",
            f"X{symbol}XXBT", f"X{symbol}XBT"  # Kraken-specific formats
        ]

        async def fetch_volume(name: str, client):
            if client is None:
                return 0.0
            volume_btc = 0.0
            try:
                markets = await client.fetch_markets()
                btc_pairs = [market['symbol'] for market in markets
                             if market['symbol'] in pair_formats and market['active']]
                logger.debug(f"{name}: Found BTC pairs for {symbol}: {btc_pairs}")

                for pair in btc_pairs:
                    try:
                        ticker = await client.fetch_ticker(pair)
                        logger.debug(f"{name} ticker for {pair}: {ticker}")
                        # Try quoteVolume (in BTC) first, then baseVolume * last
                        if ticker.get('quoteVolume') is not None:
                            pair_volume = ticker['quoteVolume']
                        elif (ticker.get('baseVolume') is not None and
                              ticker.get('last') is not None):
                            pair_volume = ticker['baseVolume'] * ticker['last']
                        else:
                            logger.warning(f"Missing volume or price for {pair} on {name}")
                            pair_volume = 0.0
                        volume_btc += pair_volume
                        logger.debug(f"{name}: {pair} volume = {pair_volume:.2f} BTC")
                    except Exception as e:
                        logger.warning(f"Failed to fetch ticker for {pair} on {name}: {str(e)}")
            except Exception as e:
                logger.warning(f"Failed to fetch markets for {name}: {str(e)}")
            return volume_btc

        tasks = [fetch_volume(name, client) for name, client in self.clients.items()]
        volumes = await asyncio.gather(*tasks, return_exceptions=True)

        for name, volume in zip(self.EXCHANGES.keys(), volumes):
            if isinstance(volume, float):
                exchange_volumes[name] = volume
                total_volume_btc += volume

        return total_volume_btc, exchange_volumes

    async def close(self):
        """
        Close all exchange client connections.
        """
        for name, client in self.clients.items():
            if client:
                try:
                    await client.close()
                    logger.info(f"Closed {name} client")
                except Exception as e:
                    logger.warning(f"Failed to close {name} client: {str(e)}")


async def get_top_100_coins_by_btc_volume() -> List[CoinData]:
    """
    Fetch top 100 cryptocurrencies by 24h trading volume in BTC pairs from multiple exchanges.

    Returns:
        List[CoinData]: List of CoinData objects sorted by BTC pair volume.

    Raises:
        Exception: For errors during execution.
    """
    coingecko_client = CoinGeckoClient()
    exchange_client = ExchangeClient()

    # Get top 100 coins from CoinGecko
    coins = coingecko_client.get_top_100_coins()
    coin_volumes = []

    for coin in coins:
        symbol = coin.get('symbol', '').upper()
        if symbol == 'BTC':  # Skip BTC itself
            continue
        volume_btc, exchange_volumes = await exchange_client.get_btc_pair_volume(symbol)
        coin_data = CoinData(
            name=coin.get('name', ''),
            symbol=symbol,
            volume_24h_btc=volume_btc,
            price_btc=coin.get('current_price', 0.0),
            market_cap_btc=coin.get('market_cap', 0.0),
            exchange_volumes=exchange_volumes
        )
        coin_volumes.append(coin_data)
        logger.info(f"Processed {coin_data.name} ({coin_data.symbol}): {volume_btc:.2f} BTC volume")
        await asyncio.sleep(0.1)  # Small delay between coins to avoid overloading

    # Sort by volume in descending order
    coin_volumes.sort(key=lambda x: x.volume_24h_btc, reverse=True)

    # Close exchange clients
    await exchange_client.close()

    return coin_volumes[:100]


def format_coin_data(coins: List[CoinData]) -> str:
    """
    Format coin data into a readable string with per-exchange volumes.

    Args:
        coins (List[CoinData]): List of coin data to format.

    Returns:
        str: Formatted string representation of coin data.
    """
    output = ["Top 100 Cryptocurrencies by 24h Trading Volume in BTC Pairs (Multiple Exchanges):"]
    output.append("-" * 150)
    header = (
        f"{'Rank':<5} {'Name':<20} {'Symbol':<8} {'Total Vol (BTC)':>15} "
        f"{'Price (BTC)':>15} {'Market Cap (BTC)':>15} "
        f"{'Binance Vol':>15} {'Coinbase Vol':>15} {'Kraken Vol':>15} "
        f"{'Gate Vol':>15} {'HTX Vol':>15} {'Bybit Vol':>15} "
        f"{'OKX Vol':>15} {'KuCoin Vol':>15} {'Bitfinex Vol':>15} {'Upbit Vol':>15}"
    )
    output.append(header)
    output.append("-" * 150)

    for i, coin in enumerate(coins, 1):
        output.append(
            f"{i:<5} {coin.name:<20} {coin.symbol:<8} "
            f"{coin.volume_24h_btc:>15.2f} {coin.price_btc:>15.8f} {coin.market_cap_btc:>15.2f} "
            f"{coin.exchange_volumes['binance']:>15.2f} {coin.exchange_volumes['coinbase']:>15.2f} "
            f"{coin.exchange_volumes['kraken']:>15.2f} {coin.exchange_volumes['gate']:>15.2f} "
            f"{coin.exchange_volumes['huobi']:>15.2f} {coin.exchange_volumes['bybit']:>15.2f} "
            f"{coin.exchange_volumes['okx']:>15.2f} {coin.exchange_volumes['kucoin']:>15.2f} "
            f"{coin.exchange_volumes['bitfinex']:>15.2f} {coin.exchange_volumes['upbit']:>15.2f}"
        )

    return "\n".join(output)


async def main() -> None:
    """
    Main function to fetch and display top 100 coins by volume in BTC pairs.

    Raises:
        Exception: For errors during execution.
    """
    try:
        coins = await get_top_100_coins_by_btc_volume()
        formatted_output = format_coin_data(coins)
        print(formatted_output)
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())