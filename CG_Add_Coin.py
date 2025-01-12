import requests
import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime
import json

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем API-ключ CoinGecko (если требуется)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Конфигурация подключения к MySQL
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}


def fetch_coin_details(coin_id):
    """
    Запрашивает данные монеты по coin_id через API CoinGecko
    и возвращает полученный JSON-словарь.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": COINGECKO_API_KEY
    }
    params = {
        "localization": "false",  # не возвращать переводы
        "tickers": "false",  # не возвращать тикеры
        "market_data": "true",  # возвращать рыночные данные
        "community_data": "true",  # возвращать данные сообщества
        "developer_data": "false",
        "sparkline": "false"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        coin_data = response.json()
        return coin_data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API: {e}")
        return None


def parse_datetime(dt_str):
    """
    Преобразует ISO-8601 строку в объект datetime.
    Если преобразование не удается, возвращает None.
    """
    try:
        return datetime.fromisoformat(dt_str.rstrip("Z"))
    except Exception:
        return None


def print_coin_data(data):
    """
    Выводит на экран некоторые основные данные монеты.
    """
    if data is None:
        print("Нет данных для отображения.")
        return

    print("=== Детали монеты ===")
    print(f"ID: {data.get('id')}")
    print(f"Name: {data.get('name')}")
    print(f"Symbol: {data.get('symbol')}")

    categories = data.get("categories", [])
    print(f"Categories: {', '.join(categories) if categories else 'N/A'}")

    description = data.get("description", {}).get("en", "")
    print("\n--- Описание (англ.) ---")
    print(description.strip()[:300] + "...")

    sentiment_up = data.get("sentiment_votes_up_percentage")
    sentiment_down = data.get("sentiment_votes_down_percentage")
    print("\n--- Sentiment ---")
    print(f"Votes up: {sentiment_up}")
    print(f"Votes down: {sentiment_down}")

    market_cap_rank = data.get("market_cap_rank")
    print("\n--- Market Cap ---")
    print(f"Market Cap Rank: {market_cap_rank}")

    market_data = data.get("market_data", {})
    current_price = market_data.get("current_price", {}).get("usd")
    ath = market_data.get("ath", {}).get("usd")
    ath_change_percentage = market_data.get("ath_change_percentage", {}).get("usd")
    ath_date = parse_datetime(market_data.get("ath_date", {}).get("usd") or "")
    atl = market_data.get("atl", {}).get("usd")
    atl_change_percentage = market_data.get("atl_change_percentage", {}).get("usd")
    atl_date = parse_datetime(market_data.get("atl_date", {}).get("usd") or "")
    market_cap = market_data.get("market_cap", {}).get("usd")
    total_volume = market_data.get("total_volume", {}).get("usd")

    print("\n--- Market Data (USD) ---")
    print(f"Current Price: {current_price}")
    print(f"ATH: {ath} (Change: {ath_change_percentage}%, Date: {ath_date})")
    print(f"ATL: {atl} (Change: {atl_change_percentage}%, Date: {atl_date})")
    print(f"Market Cap: {market_cap}")
    print(f"Total Volume: {total_volume}")

    community_data = data.get("community_data", {})
    facebook_likes = community_data.get("facebook_likes")
    twitter_followers = community_data.get("twitter_followers")
    reddit_subscribers = community_data.get("reddit_subscribers")
    telegram_count = community_data.get("telegram_channel_user_count")
    print("\n--- Community Data ---")
    print(f"Facebook Likes: {facebook_likes}")
    print(f"Twitter Followers: {twitter_followers}")
    print(f"Reddit Subscribers: {reddit_subscribers}")
    print(f"Telegram Channel Users: {telegram_count}")

    watchlist_users = data.get("watchlist_portfolio_users")
    print("\n--- Watchlist ---")
    print(f"Watchlist Portfolio Users: {watchlist_users}")


def update_coin_in_db(data):
    """
    Обновляет запись в таблице coin_gesco_coins по данным, полученным из API.
    Также обновляет связи в таблице coin_category_relation, основываясь на field
    'categories', которые являются массивом строк.
    """
    coin_id = data.get("id")
    if not coin_id:
        print("Отсутствует coin_id в данных.")
        return

    # Извлекаем поля для обновления из полученных данных (пример – можно расширить)
    name = data.get("name")
    symbol = data.get("symbol")
    description_en = data.get("description", {}).get("en", "")
    sentiment_votes_up_percentage = data.get("sentiment_votes_up_percentage")
    sentiment_votes_down_percentage = data.get("sentiment_votes_down_percentage")
    market_cap_rank = data.get("market_cap_rank")

    market_data = data.get("market_data", {})
    current_price_usd = market_data.get("current_price", {}).get("usd")
    ath_usd = market_data.get("ath", {}).get("usd")
    ath_change_percentage_usd = market_data.get("ath_change_percentage", {}).get("usd")
    ath_date_str = market_data.get("ath_date", {}).get("usd")
    atl_usd = market_data.get("atl", {}).get("usd")
    atl_change_percentage_usd = market_data.get("atl_change_percentage", {}).get("usd")
    atl_date_str = market_data.get("atl_date", {}).get("usd")
    market_cap_usd = market_data.get("market_cap", {}).get("usd")
    total_volume_usd = market_data.get("total_volume", {}).get("usd")
    # Дополнительно можно добавить другие поля по необходимости

    # Преобразуем даты (если строки предоставлены)
    ath_date_usd = parse_datetime(ath_date_str) if ath_date_str else None
    atl_date_usd = parse_datetime(atl_date_str) if atl_date_str else None

    community_data = data.get("community_data", {})
    facebook_likes = community_data.get("facebook_likes")
    twitter_followers = community_data.get("twitter_followers")
    reddit_subscribers = community_data.get("reddit_subscribers")
    telegram_channel_user_count = community_data.get("telegram_channel_user_count")

    watchlist_portfolio_users = data.get("watchlist_portfolio_users")

    # Формируем запрос для обновления
    update_query = """
        UPDATE coin_gesco_coins SET
            name = %s,
            symbol = %s,
            description_en = %s,
            sentiment_votes_up_percentage = %s,
            sentiment_votes_down_percentage = %s,
            market_cap_rank = %s,
            current_price_usd = %s,
            ath_usd = %s,
            ath_change_percentage_usd = %s,
            ath_date_usd = %s,
            atl_usd = %s,
            atl_change_percentage_usd = %s,
            atl_date_usd = %s,
            market_cap_usd = %s,
            total_volume_usd = %s,
            facebook_likes = %s,
            twitter_followers = %s,
            reddit_subscribers = %s,
            telegram_channel_user_count = %s,
            watchlist_portfolio_users = %s
        WHERE id = %s
    """
    values = (
        name, symbol, description_en, sentiment_votes_up_percentage,
        sentiment_votes_down_percentage, market_cap_rank, current_price_usd,
        ath_usd, ath_change_percentage_usd, ath_date_usd, atl_usd,
        atl_change_percentage_usd, atl_date_usd, market_cap_usd, total_volume_usd,
        facebook_likes, twitter_followers, reddit_subscribers, telegram_channel_user_count,
        watchlist_portfolio_users, coin_id
    )

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(update_query, values)
        conn.commit()
        print(f"Запись монеты {coin_id} в таблице coin_gesco_coins успешно обновлена.")
    except mysql.connector.Error as e:
        print(f"Ошибка обновления монеты {coin_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_coin_categories(data):
    """
    Обновляет связи монеты с категориями.
    Для данной монеты удаляет старые связи в таблице coin_category_relation,
    затем для каждого элемента из data['categories']:
       - ищет в таблице CG_Categories запись, где name соответствует категории
       - если найдена, вставляет связь (coin_id, category_id) в coin_category_relation
    """
    coin_id = data.get("id")
    if not coin_id:
        print("Нет coin_id для обновления категорий.")
        return

    categories = data.get("categories", [])
    if not categories:
        print("Для монеты нет категорий для обновления.")
        return

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Удаляем старые связи для данной монеты
        delete_query = "DELETE FROM coin_category_relation WHERE coin_id = %s"
        cursor.execute(delete_query, (coin_id,))

        # Для каждой категории ищем category_id в CG_Categories по совпадению имени
        select_query = "SELECT category_id FROM CG_Categories WHERE name = %s"
        insert_query = "INSERT INTO coin_category_relation (coin_id, category_id) VALUES (%s, %s)"

        for cat in categories:
            cursor.execute(select_query, (cat,))
            row = cursor.fetchone()
            if row:
                category_id = row[0]
                cursor.execute(insert_query, (coin_id, category_id))
                print(f"Добавлена связь: монета {coin_id} ↔ категория {category_id} ({cat})")
            else:
                print(f"Не найдена категория с именем: {cat}")

        conn.commit()
    except mysql.connector.Error as e:
        print(f"Ошибка обновления категорий для монеты {coin_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def main():
    coin_id_input = input("Введите coin_id (например, bitcoin): ").strip()
    coin_data = fetch_coin_details(coin_id_input)
    if coin_data:
        # Выводим данные монеты на экран
        print_coin_data(coin_data)
        # Обновляем запись в таблице coin_gesco_coins
        update_coin_in_db(coin_data)
        # Обновляем связи монеты с категориями в таблице coin_category_relation
        update_coin_categories(coin_data)
    else:
        print("Не удалось получить данные монеты.")


if __name__ == "__main__":
    main()