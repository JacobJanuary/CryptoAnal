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

    # Создание базы данных, если она не существует
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
    cursor.execute(f"USE {db_config['database']}")

    # Создание таблицы, если она не существует
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cryptocurrencies (
            id INT PRIMARY KEY,
            rank INT,
            name VARCHAR(255),
            symbol VARCHAR(50)
        )
    ''')

    # Очистка таблицы перед добавлением новых данных (опционально, если нужно полное обновление)
    cursor.execute("TRUNCATE TABLE cryptocurrencies")

    # Вставка данных в базу данных
    for currency in data:
        if currency.get('is_active') == 1:
            cursor.execute('''
                INSERT INTO cryptocurrencies (id, rank, name, symbol)
                VALUES (%s, %s, %s, %s)
            ''', (currency['id'], currency.get('rank'), currency['name'], currency['symbol']))

    conn.commit()

    print("Данные успешно сохранены в базу данных MySQL")

except requests.exceptions.RequestException as e:
    print(f"Ошибка при запросе к API: {e}")
except mysql.connector.Error as e:
    print(f"Ошибка базы данных MySQL: {e}")
except KeyError as e:
    print(f"Ошибка в структуре данных API (отсутствует ключ {e}): возможно, структура ответа API изменилась")
finally:
    if conn.is_connected():
        cursor.close()
        conn.close()
