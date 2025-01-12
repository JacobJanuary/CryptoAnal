import requests
import mysql.connector
import os
import time
from dotenv import load_dotenv
from datetime import datetime
import json

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем API-ключ CoinGecko (если требуется)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Конфигурация подключения к базе данных
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}


def fetch_coin_details(coin_id):
    """
    Запрашивает данные монеты по coin_id через API CoinGecko и возвращает JSON-словарь.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": COINGECKO_API_KEY
    }
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "true",
        "developer_data": "false",
        "sparkline": "false"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        coin_data = response.json()
        return coin_data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API для монеты {coin_id}: {e}")
        return None


def parse_datetime(dt_str):
    """
    Преобразует строку формата ISO-8601 в объект datetime.
    Если преобразование не удаётся – возвращает None.
    """
    try:
        return datetime.fromisoformat(dt_str.rstrip("Z"))
    except Exception:
        return None


def print_coin_data(data):
    """
    Выводит на экран выбранные данные монеты.
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
    high_24h = market_data.get("high_24h", {}).get("usd")
    low_24h = market_data.get("low_24h", {}).get("usd")
    price_change_24h = market_data.get("price_change_24h")
    price_change_percentage_24h = market_data.get("price_change_percentage_24h")

    print("\n--- Market Data (USD) ---")
    print(f"Current Price: {current_price}")
    print(f"ATH: {ath} (Change: {ath_change_percentage}% on {ath_date})")
    print(f"ATL: {atl} (Change: {atl_change_percentage}% on {atl_date})")
    print(f"Market Cap: {market_cap}")
    print(f"Total Volume: {total_volume}")
    print("\n--- 24h Data ---")
    print(f"24h High: {high_24h}")
    print(f"24h Low: {low_24h}")
    print(f"24h Price Change: {price_change_24h}")
    print(f"24h Price Change Percentage: {price_change_percentage_24h}")

    community_data = data.get("community_data", {})
    facebook_likes = community_data.get("facebook_likes")
    twitter_followers = community_data.get("twitter_followers")
    reddit_subscribers = community_data.get("reddit_subscribers")
    telegram_channel_user_count = community_data.get("telegram_channel_user_count")
    print("\n--- Community Data ---")
    print(f"Facebook Likes: {facebook_likes}")
    print(f"Twitter Followers: {twitter_followers}")
    print(f"Reddit Subscribers: {reddit_subscribers}")
    print(f"Telegram Channel Users: {telegram_channel_user_count}")

    watchlist_users = data.get("watchlist_portfolio_users")
    print("\n--- Watchlist ---")
    print(f"Watchlist Portfolio Users: {watchlist_users}")


def update_coin_in_db(data):
    """
    Обновляет запись монеты в таблице coin_gesco_coins.
    Обновляются поля: name, symbol, description_en,
    sentiment_votes_up_percentage, sentiment_votes_down_percentage, market_cap_rank,
    current_price_usd, ath_usd, ath_change_percentage_usd, ath_date_usd,
    atl_usd, atl_change_percentage_usd, atl_date_usd, market_cap_usd, total_volume_usd,
    high_24h_usd, low_24h_usd, price_change_24h_usd, price_change_percentage_24h,
    facebook_likes, twitter_followers, reddit_subscribers, telegram_channel_user_count,
    watchlist_portfolio_users.
    """
    coin_id = data.get("id")
    if not coin_id:
        print("Отсутствует coin_id в данных.")
        return

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
    high_24h_usd = market_data.get("high_24h", {}).get("usd")
    low_24h_usd = market_data.get("low_24h", {}).get("usd")
    price_change_24h_usd = market_data.get("price_change_24h")
    price_change_percentage_24h = market_data.get("price_change_percentage_24h")

    ath_date_usd = parse_datetime(ath_date_str) if ath_date_str else None
    atl_date_usd = parse_datetime(atl_date_str) if atl_date_str else None

    community_data = data.get("community_data", {})
    facebook_likes = community_data.get("facebook_likes")
    twitter_followers = community_data.get("twitter_followers")
    reddit_subscribers = community_data.get("reddit_subscribers")
    telegram_channel_user_count = community_data.get("telegram_channel_user_count")

    watchlist_portfolio_users = data.get("watchlist_portfolio_users")

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
            high_24h_usd = %s,
            low_24h_usd = %s,
            price_change_24h_usd = %s,
            price_change_percentage_24h = %s,
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
        ath_usd, ath_change_percentage_usd, ath_date_usd,
        atl_usd, atl_change_percentage_usd, atl_date_usd,
        market_cap_usd, total_volume_usd, high_24h_usd, low_24h_usd,
        price_change_24h_usd, price_change_percentage_24h,
        facebook_likes, twitter_followers, reddit_subscribers, telegram_channel_user_count,
        watchlist_portfolio_users, coin_id
    )

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(update_query, values)
        conn.commit()
        print(f"Запись монеты {coin_id} успешно обновлена в таблице coin_gesco_coins.")
    except mysql.connector.Error as e:
        print(f"Ошибка обновления монеты {coin_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_coin_categories(data):
    """
    Обновляет связи монеты с категориями в таблице coin_category_relation.
    Для данной монеты:
      - Удаляет старые связи,
      - Затем для каждого элемента из data['categories']:
            ищет в таблице CG_Categories запись по совпадению имени,
            если найдена, вставляет новую связь (coin_id, category_id).
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

        # Для каждой категории, ищем category_id в CG_Categories по совпадению имени
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


def get_coin_ids_for_update():
    """
    Возвращает список coin_id из таблицы coin_gesco_coins, у которых поле description_en не пустое или не NULL.
    """
    coin_ids = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        # Выбираем все записи, где description_en не NULL и не пустое (после обрезки пробелов)
        query = "SELECT id FROM coin_gesco_coins WHERE description_en IS NOT NULL AND TRIM(description_en) != ''"
        cursor.execute(query)
        rows = cursor.fetchall()
        coin_ids = [row[0] for row in rows]
    except mysql.connector.Error as e:
        print(f"Ошибка при выборке coin_id для обновления: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return coin_ids


def main():
    # Получаем список coin_id для обновления
    coin_ids = get_coin_ids_for_update()
    print(f"Найдено {len(coin_ids)} монет для обновления.")

    # Для ограничения API до 30 запросов в минуту устанавливаем задержку 2 секунды между запросами
    for coin_id in coin_ids:
        print(f"\nОбработка монеты {coin_id}...")
        coin_data = fetch_coin_details(coin_id)
        if coin_data:
            print_coin_data(coin_data)
            update_coin_in_db(coin_data)
            update_coin_categories(coin_data)
        else:
            print(f"Не удалось получить данные для монеты {coin_id}.")
        # Задержка в 2 секунды для соблюдения лимита 30 запросов в минуту
        time.sleep(2)


if __name__ == "__main__":
    main()