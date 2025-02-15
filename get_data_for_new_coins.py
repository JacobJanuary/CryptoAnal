
import requests
import mysql.connector
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем API-ключ для CoinGecko из переменных окружения
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
if not COINGECKO_API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINGECKO_API_KEY")

# URL для получения списка всех монет
url = "https://pro-api.coingecko.com/api/v3/coins/list"

# Передаём API-ключ через заголовок (если требуется)
headers = {
    "accept": "application/json",
    "x-cg-pro-api-key": COINGECKO_API_KEY
}


def fetch_coingecko_coins():
    """Получает список всех монет через API CoinGecko (/coins/list)."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # выбрасываем исключение при HTTP ошибке
        coins = response.json()  # каждая монета имеет поля: id, symbol, name
        return coins
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к CoinGecko API: {e}")
        return []


def save_coins_to_db(coins):
    """
    Сохраняет список монет в таблицу coin_gesco_coins (создание таблицы, если её нет).
    Добавляются только новые записи (INSERT IGNORE).

    Возвращает кортеж статистики:
       (found_count, processed_count, error_count, list_ids_unprocessed, new_coins_count)

       found_count - общее количество монет, полученных от API
       processed_count - количество монет с полным набором необходимых данных
       error_count - количество монет, в которых отсутствуют необходимые данные
       list_ids_unprocessed - список id монет с отсутствующими данными
       new_coins_count - количество реально добавленных записей (новых монет)
    """
    # Параметры подключения к БД
    db_config = {
        'host': os.getenv("MYSQL_HOST", "localhost"),
        'user': os.getenv("MYSQL_USER", "root"),
        'password': os.getenv("MYSQL_PASSWORD", "password"),
        'database': os.getenv("MYSQL_DATABASE", "crypto_db")
    }

    new_coins_count = 0
    processed_count = 0
    error_count = 0
    ids_unprocessed = []

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

        # Запрос для вставки (INSERT IGNORE, чтобы не вставлять дубли)
        insert_query = """
            INSERT IGNORE INTO coin_gesco_coins (id, name, symbol)
            VALUES (%s, %s, %s);
        """

        for coin in coins:
            coin_id = coin.get("id")
            name = coin.get("name")
            symbol = coin.get("symbol")
            # Если все необходимые данные есть, пытаемся сохранить монету
            if coin_id and name and symbol:
                processed_count += 1
                cursor.execute(insert_query, (coin_id, name, symbol))
                # Если строка была вставлена (то есть rowcount равен 1), увеличиваем счетчик новых записей
                if cursor.rowcount == 1:
                    new_coins_count += 1
            else:
                error_count += 1
                # Если coin_id отсутствует, добавим строку "Без ID", иначе сам coin_id
                ids_unprocessed.append(coin_id if coin_id else "Без ID")

        conn.commit()
    except mysql.connector.Error as e:
        print(f"Ошибка базы данных MySQL: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

    found_count = len(coins)
    return found_count, processed_count, error_count, ids_unprocessed, new_coins_count

def main():
    coins = fetch_coingecko_coins()
    if coins:
        found_count, processed_count, error_count, ids_unprocessed, new_coins_count = save_coins_to_db(coins)
        print(f"Найдено записей: {found_count}")
        print(f"Обработано записей: {processed_count}")
        print(f"С ошибкой: {error_count}")
        print(f"ID необработанных: {', '.join(ids_unprocessed) if ids_unprocessed else 'Нет'}")
        print(f"Всего добавлено новых монет: {new_coins_count}")
    else:
        print("Нет данных для сохранения.")

if __name__ == "__main__":
    main()
