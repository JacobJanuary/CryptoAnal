#cron раз в неделю
import requests
import os
import time
import datetime
import statistics
import mysql.connector
import pandas as pd
from dotenv import load_dotenv
from collections import deque
from threading import Timer

# Загрузка переменных окружения
load_dotenv()

# Конфигурация API
API_KEY = os.getenv('CMC_API_KEY')
if not API_KEY:
    raise ValueError("API ключ не найден. Пожалуйста, установите переменную CMC_API_KEY в файле .env")

# Конфигурация базы данных
DB_TYPE = os.getenv('DB_TYPE', 'mysql')
DB_NAME = os.getenv('DB_NAME', 'crypto_db')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')


# Класс для управления ограничением запросов к API
class RateLimiter:
    def __init__(self, max_calls, period=60):
        self.max_calls = max_calls  # Максимальное количество запросов
        self.period = period  # Период в секундах
        self.calls = deque()  # Очередь с временными метками запросов

    def wait_if_needed(self):
        """Ожидание, если превышен лимит запросов"""
        now = time.time()

        # Удаляем устаревшие записи
        while self.calls and now - self.calls[0] > self.period:
            self.calls.popleft()

        # Если очередь полна, ждем до освобождения места
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                print(f"Превышен лимит запросов. Ожидание {sleep_time:.2f} секунд...")
                time.sleep(sleep_time)

        # Добавляем текущее время в очередь
        self.calls.append(time.time())


# Конфигурация базы данных
DB_TYPE = os.getenv('DB_TYPE', 'mysql')
DB_NAME = os.getenv('DB_NAME', 'crypto_db')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')


def create_database_connection():
    """
    Создание подключения к базе данных MySQL
    """
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=int(DB_PORT)
        )
        print("Подключение к базе данных успешно установлено")
        return conn
    except mysql.connector.Error as err:
        print(f"Ошибка подключения к базе данных: {err}")
        raise


def fetch_cryptocurrencies_from_db(conn):
    """
    Получение списка криптовалют с ненулевым объемом торгов из базы данных
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
    SELECT id, name, symbol 
    FROM cmc_crypto 
    WHERE volume_24h > 0
    ORDER BY cmc_rank 
    """)

    cryptocurrencies = cursor.fetchall()
    print(f"Получено {len(cryptocurrencies)} криптовалют с ненулевым объемом из базы данных")
    return cryptocurrencies


def fetch_historical_data(crypto_id, days=365, interval='daily', rate_limiter=None):
    """
    Получение исторических данных о криптовалюте через API CoinMarketCap
    """
    # Применяем ограничение скорости запросов, если указано
    if rate_limiter:
        rate_limiter.wait_if_needed()

    url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/historical'

    # Расчет временных интервалов
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)

    # Форматирование дат для API
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    headers = {
        'X-CMC_PRO_API_KEY': API_KEY,
        'Accept': 'application/json'
    }

    # Параметры для запроса
    params = {
        'id': crypto_id,
        'time_start': start_date_str,
        'time_end': end_date_str,
        'interval': interval,
        'convert': 'USD'
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при запросе исторических данных для ID {crypto_id}: {response.status_code}")
        print(response.text)
        return None


def analyze_volume_data(crypto, historical_data):
    """
    Анализ объемов торгов и подсчет дней с высоким объемом,
    а также нахождение минимальной и максимальной цены за период
    """
    if not historical_data or 'data' not in historical_data:
        print(f"Нет данных для анализа для {crypto['symbol']}")
        return None

    quotes = historical_data['data']['quotes']

    if not quotes:
        print(f"Нет котировок для анализа для {crypto['symbol']}")
        return None

    # Собираем данные по объемам и ценам в списки
    volumes = []
    prices = []
    timestamps = []

    for quote in quotes:
        if 'quote' in quote and 'USD' in quote['quote']:
            volume = quote['quote']['USD'].get('volume_24h')
            price = quote['quote']['USD'].get('price')

            if volume is not None:
                volumes.append(float(volume))

            if price is not None:
                prices.append(float(price))
                timestamps.append(quote['timestamp'])

    if not volumes or not prices:
        print(f"Нет данных о ценах или объемах для {crypto['symbol']}")
        return None

    # Создаем DataFrame для удобства анализа
    df = pd.DataFrame({
        'timestamp': timestamps,
        'price': prices,
        'volume_24h': volumes[:len(timestamps)] if len(volumes) >= len(timestamps) else volumes + [None] * (
                    len(timestamps) - len(volumes))
    })

    # Конвертируем timestamp в datetime для удобства
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Рассчитываем среднее значение объема
    avg_volume = statistics.mean(volumes)

    # Считаем количество дней с объемом в 2+ раза выше среднего
    if len(df) == len(volumes):
        high_volume_days = len(df[df['volume_24h'] >= 2 * avg_volume])
    else:
        # В случае, если длины списков не совпадают
        high_volume_days = sum(1 for v in volumes if v >= 2 * avg_volume)

    # Находим минимальную и максимальную цену
    min_price_idx = df['price'].idxmin()
    max_price_idx = df['price'].idxmax()

    min_price = df.loc[min_price_idx, 'price']
    min_price_date = df.loc[min_price_idx, 'timestamp'].strftime('%Y-%m-%d')

    max_price = df.loc[max_price_idx, 'price']
    max_price_date = df.loc[max_price_idx, 'timestamp'].strftime('%Y-%m-%d')

    result = {
        'coin_id': crypto['id'],
        'coin_name': crypto['name'],
        'coin_symbol': crypto['symbol'],
        'avg_volume_24h': avg_volume,
        'high_volume_days': high_volume_days,
        'total_days': len(volumes),
        'min_price': min_price,
        'min_price_date': min_price_date,
        'max_price': max_price,
        'max_price_date': max_price_date
    }

    print(
        f"Анализ для {crypto['symbol']}: среднее={avg_volume:.2f}, дней с высоким объемом={high_volume_days} из {len(volumes)}")
    print(f"Мин. цена: ${min_price:.6f} ({min_price_date}), Макс. цена: ${max_price:.6f} ({max_price_date})")

    return result


def save_analysis_results(conn, results):
    """
    Сохранение результатов анализа в таблицу cmc_crypto
    """
    if not results:
        return 0

    cursor = conn.cursor()

    # Подготавливаем SQL запрос для обновления
    update_sql = '''
    UPDATE cmc_crypto
    SET high_volume_days = %s,
        total_days = %s,
        min_365d_price = %s,
        min_365d_date = %s,
        max_365d_price = %s,
        max_365d_date = %s
    WHERE id = %s
    '''

    values = [
        (
            result['high_volume_days'],
            result['total_days'],
            result['min_price'],
            result['min_price_date'],
            result['max_price'],
            result['max_price_date'],
            result['coin_id']
        )
        for result in results
    ]

    cursor.executemany(update_sql, values)
    conn.commit()

    return cursor.rowcount


def main():
    try:
        start_time = time.time()

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Получение списка всех активных криптовалют для анализа
        cryptocurrencies = fetch_cryptocurrencies_from_db(conn)

        # Можно добавить ограничение на количество криптовалют для тестирования
        # cryptocurrencies = cryptocurrencies[:50]  # Раскомментируйте для ограничения

        # Создаем ограничитель скорости запросов: 30 запросов в минуту
        rate_limiter = RateLimiter(max_calls=30, period=60)

        all_results = []
        processed_count = 0

        # Анализ каждой криптовалюты
        for crypto in cryptocurrencies:
            try:
                print(f"Анализ {crypto['symbol']} (ID: {crypto['id']})...")

                # Получение исторических данных с учетом ограничения скорости
                historical_data = fetch_historical_data(crypto['id'], rate_limiter=rate_limiter)

                if historical_data:
                    # Анализ данных по объемам
                    result = analyze_volume_data(crypto, historical_data)

                    if result:
                        all_results.append(result)

                # Сохраняем результаты в базу каждые 20 криптовалют или в конце обработки всех
                if len(all_results) >= 20:
                    saved_count = save_analysis_results(conn, all_results)
                    print(f"Промежуточное сохранение: обновлено {saved_count} записей в таблице cmc_crypto")
                    all_results = []

                processed_count += 1
                print(f"Обработано {processed_count} из {len(cryptocurrencies)} криптовалют")

            except Exception as e:
                print(f"Ошибка при обработке {crypto['symbol']}: {str(e)}")
                continue

        # Сохранение оставшихся результатов анализа в базу данных
        if all_results:
            saved_count = save_analysis_results(conn, all_results)
            print(f"Финальное сохранение: обновлено {saved_count} записей в таблице cmc_crypto")

        # Закрытие соединения с базой данных
        conn.close()

        total_time = time.time() - start_time
        print(f"Общее время выполнения: {total_time:.2f} секунд")
        print(f"Всего обработано {processed_count} криптовалют")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
    main()