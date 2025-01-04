import requests
from datetime import datetime, timedelta, timezone

# Ваш API-ключ для доступа к Coinalyze API
API_KEY = "71d8da0e-108e-48a8-a367-07ce4c54ab76"
BASE_URL = "https://api.coinalyze.net/v1"

def get_unix_timestamp(dt):
    return int(dt.timestamp())

def get_supported_future_markets():
    endpoint = f"{BASE_URL}/future-markets"
    params = {
        "api_key": API_KEY
    }
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка: {response.status_code}, {response.text}")
        return None

def filter_eth_symbols(markets):
    eth_symbols = [market["symbol"] for market in markets if market["base_asset"] == "ETH"]
    return eth_symbols

def get_open_interest(symbols):
    endpoint = f"{BASE_URL}/open-interest"
    params = {
        "symbols": ",".join(symbols),
        "api_key": API_KEY
    }
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка: {response.status_code}, {response.text}")
        return None

def aggregate_open_interest(data):
    total_open_interest = sum(item["value"] for item in data)
    return total_open_interest

def main():
    # Получаем список всех поддерживаемых фьючерсных рынков
    markets = get_supported_future_markets()
    if not markets:
        print("Не удалось получить список рынков.")
        return

    # Фильтруем символы, связанные с ETH
    eth_symbols = filter_eth_symbols(markets)
    if not eth_symbols:
        print("Не удалось найти символы, связанные с ETH.")
        return

    # Получаем текущий открытый интерес для всех ETH-символов
    open_interest_data = get_open_interest(eth_symbols)
    if not open_interest_data:
        print("Не удалось получить данные об открытом интересе.")
        return

    # Агрегируем открытый интерес
    total_open_interest = aggregate_open_interest(open_interest_data)
    print(f"Агрегированный открытый интерес для ETH: {total_open_interest}")

if __name__ == "__main__":
    main()