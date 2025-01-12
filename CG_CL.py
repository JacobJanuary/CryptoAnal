import requests
import mysql.connector
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем API ключ из переменных окружения
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

# URL для получения списка монет через endpoint CoinGecko Markets
# (для примера, используем vs_currency=usd, можно менять по необходимости)
url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"

headers = {
    "accept": "application/json",
    "x-cg-demo-api-key": COINGECKO_API_KEY  # передаем API-ключ через заголовок
}


def fetch_coingecko_coins():
    """Получает список всех монет через API CoinGecko (endpoint markets)."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Проверка на HTTP ошибки
        # Документация endpoint markets:
        # ответ содержит множество полей, но нас интересуют: id, name, symbol.
        coins = response.json()
        return coins
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API: {e}")
        return []


def save_coins_to_db(coins):
    """Сохраняет список монет в таблицу coin_gesco_coins.
       Если таблица не существует — создаёт её.
       Не очищает таблицу, а добавляет только новые записи.
    """
    # Получаем параметры подключения к БД
    db_config = {
        'host': os.getenv("MYSQL_HOST", "localhost"),
        'user': os.getenv("MYSQL_USER", "root"),
        'password': os.getenv("MYSQL_PASSWORD", "password"),
        'database': os.getenv("MYSQL_DATABASE", "crypto_db")
    }

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Создаем таблицу, если она не существует
        create_table_query = """
            CREATE TABLE IF NOT EXISTS coin_gesco_coins (
                id VARCHAR(255) NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                symbol VARCHAR(50) NOT NULL
            );
        """
        cursor.execute(create_table_query)

        # Вставляем данные. Используем INSERT IGNORE чтобы не вставлять дубли.
        insert_query = """
            INSERT IGNORE INTO coin_gesco_coins (id, name, symbol)
            VALUES (%s, %s, %s);
        """

        for coin in coins:
            coin_id = coin.get("id")
            name = coin.get("name")
            symbol = coin.get("symbol")
            if coin_id and name and symbol:
                cursor.execute(insert_query, (coin_id, name, symbol))

        conn.commit()
        print("Данные успешно сохранены в таблицу coin_gesco_coins")

    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL: {e}")

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def main():
    coins = fetch_coingecko_coins()
    if coins:
        print(f"Получено {len(coins)} монет от CoinGecko")
        save_coins_to_db(coins)
    else:
        print("Нет данных для сохранения.")


if __name__ == "__main__":
    main()