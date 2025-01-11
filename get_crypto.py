import requests
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("COINMARKETCAP_API_KEY")

if not API_KEY:
    raise ValueError("Необходимо установить переменную окружения COINMARKETCAP_API_KEY")

url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/map'
headers = {
  'Accepts': 'application/json',
  'X-CMC_PRO_API_KEY': API_KEY,
}

# Загружаем параметры конфигурации с проверкой
db_config = {
    'host': os.getenv("MYSQL_HOST"),
    'user': os.getenv("MYSQL_USER"),
    'password': os.getenv("MYSQL_PASSWORD"),
    'database': os.getenv("MYSQL_DATABASE")
}

# Проверяем, чтобы все параметры были заданы
missing_vars = [key for key, value in db_config.items() if not value]
if missing_vars:
    raise ValueError(f"Не заданы следующие переменные окружения: {', '.join(missing_vars)}")

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Проверка на ошибки HTTP (например, 400, 401, 500)
    data = response.json().get('data', [])

    # Подключение к базе данных MySQL
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    # Далее предполагается, что БД и таблица cryptocurrencies УЖЕ существуют
    # Если нужно, отдельно делайте CREATE DATABASE / CREATE TABLE

    # Вставка данных в базу данных (только новых записей)
    for currency in data:
        if currency.get('is_active') == 1:
            currency_id = currency['id']
            rank = currency.get('rank')
            name = currency['name']
            symbol = currency['symbol']

            # Проверяем, есть ли уже такая запись по ID
            cursor.execute("SELECT id FROM cryptocurrencies WHERE id = %s", (currency_id,))
            row = cursor.fetchone()

            # Если не нашли, вставляем новую запись
            if not row:
                cursor.execute('''
                    INSERT INTO cryptocurrencies (id, cryptorank, name, symbol)
                    VALUES (%s, %s, %s, %s)
                ''', (currency_id, rank, name, symbol))

    conn.commit()
    print("Данные успешно сохранены в базу данных MySQL (добавлены только новые записи).")

except requests.exceptions.RequestException as e:
    print(f"Ошибка при запросе к API: {e}")
except mysql.connector.Error as e:
    print(f"Ошибка базы данных MySQL: {e}")
except KeyError as e:
    print(f"Ошибка в структуре данных API (отсутствует ключ {e}): возможно, структура ответа API изменилась")
finally:
    if 'conn' in locals() and conn.is_connected():
        cursor.close()
        conn.close()