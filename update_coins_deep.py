import requests
import mysql.connector
import os
import time
import threading
import psutil
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Загружаем переменные окружения
load_dotenv()

# Параметры подключения к базе данных
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

# API-ключ для CoinGecko (если требуется)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Параметры API
MARKETS_URL = "https://pro-api.coingecko.com/api/v3/coins/markets"
VS_CURRENCY = "usd"
BATCH_SIZE = 100  # обрабатываем по 100 монет за один запрос

# Максимальное количество потоков
MAX_WORKERS = 5

# Глобальная коллекция замеров загрузки CPU
cpu_samples = []
# Флаг для остановки потока измерения загрузки CPU
stop_cpu_sampling = threading.Event()


def cpu_sampling():
    """
    Функция для измерения загрузки CPU.
    Каждую секунду замеряет загрузку и сохраняет в глобальный список cpu_samples.
    Работает до установки события stop_cpu_sampling.
    """
    while not stop_cpu_sampling.is_set():
        # Задаём интервал в 1 секунду для замера загрузки CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_samples.append(cpu_percent)


def get_all_coin_ids():
    """
    Извлекает список coin_id из таблицы coin_gesco_coins.
    Возвращает список строк.
    """
    coin_ids = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "SELECT id FROM coin_gesco_coins"
        cursor.execute(query)
        rows = cursor.fetchall()
        coin_ids = [row[0] for row in rows]
    except mysql.connector.Error as e:
        print(f"Ошибка при выборке coin_id: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return coin_ids


def batch_list(lst, batch_size):
    """Разбивает список lst на батчи по batch_size элементов."""
    for i in range(0, len(lst), batch_size):
        yield lst[i:i + batch_size]


def fetch_market_data_for_ids(ids_batch):
    """
    Выполняет запрос к API CoinGecko /coins/markets для батча идентификаторов.
    ids_batch – список идентификаторов монет.
    Возвращает список монет (JSON-объекты).
    """
    ids_str = ",".join(ids_batch)
    params = {
        "vs_currency": VS_CURRENCY,
        "ids": ids_str
    }
    headers = {
        "accept": "application/json",
        "x-cg-pro-api-key": COINGECKO_API_KEY
    }
    try:
        response = requests.get(MARKETS_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к /coins/markets: {e}")
        return []


def parse_datetime(dt_str):
    """Пытается преобразовать ISO-8601 дату в объект datetime; возвращает None, если не удается."""
    try:
        return datetime.fromisoformat(dt_str.rstrip("Z"))
    except Exception:
        return None


def update_coin_in_db(coin):
    """
    Обновляет запись монеты в таблице coin_gesco_coins по её id.
    Обновляются следующие поля:
      - current_price_usd
      - market_cap_rank
      - market_cap_usd
      - total_volume_usd
      - high_24h_usd
      - low_24h_usd
      - price_change_24h_usd
      - price_change_percentage_24h
      - ath_usd
      - ath_change_percentage_usd
      - ath_date_usd
      - atl_usd
      - atl_change_percentage_usd
      - atl_date_usd
      - lastupdate (NOW())
    Возвращает True, если обновление успешно, иначе False.
    """
    coin_id = coin.get("id")
    if not coin_id:
        return False

    current_price = coin.get("current_price")
    market_cap_rank = coin.get("market_cap_rank")
    market_cap = coin.get("market_cap")
    total_volume = coin.get("total_volume")
    high_24h = coin.get("high_24h")
    low_24h = coin.get("low_24h")
    price_change_24h = coin.get("price_change_24h")
    price_change_percentage_24h = coin.get("price_change_percentage_24h")
    ath = coin.get("ath")
    ath_change_percentage = coin.get("ath_change_percentage")
    ath_date_str = coin.get("ath_date")
    atl = coin.get("atl")
    atl_change_percentage = coin.get("atl_change_percentage")
    atl_date_str = coin.get("atl_date")

    ath_date = parse_datetime(ath_date_str) if ath_date_str else None
    atl_date = parse_datetime(atl_date_str) if atl_date_str else None

    update_query = """
        UPDATE coin_gesco_coins SET
            current_price_usd = %s,
            market_cap_rank = %s,
            market_cap_usd = %s,
            total_volume_usd = %s,
            high_24h_usd = %s,
            low_24h_usd = %s,
            price_change_24h_usd = %s,
            price_change_percentage_24h = %s,
            ath_usd = %s,
            ath_change_percentage_usd = %s,
            ath_date_usd = %s,
            atl_usd = %s,
            atl_change_percentage_usd = %s,
            atl_date_usd = %s,
            lastupdate = NOW()
        WHERE id = %s
    """
    values = (
        current_price,
        market_cap_rank,
        market_cap,
        total_volume,
        high_24h,
        low_24h,
        price_change_24h,
        price_change_percentage_24h,
        ath,
        ath_change_percentage,
        ath_date,
        atl,
        atl_change_percentage,
        atl_date,
        coin_id
    )
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(update_query, values)
        conn.commit()
        return True
    except mysql.connector.Error as e:
        print(f"Ошибка обновления монеты {coin_id}: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def process_batch(batch, batch_number):
    """
    Обрабатывает один батч монет:
      - запрашивает данные с API;
      - обновляет данные монет в БД;
      - вставляет историю объемов.
    Возвращает количество успешно обновленных монет в данном батче и число монет с нулевыми значениями.
    """
    print(f"\nОбработка батча {batch_number} (монет в батче: {len(batch)})...")
    coins_data = fetch_market_data_for_ids(batch)
    received_count = len(coins_data)
    print(f"Батч {batch_number}: получено данных: {received_count}")
    batch_updated_count = 0
    zero_count_local = 0

    if coins_data:
        for coin in coins_data:
            if update_coin_in_db(coin):
                batch_updated_count += 1

    print(f"Батч {batch_number}: обновлено {batch_updated_count} монет.")
    return batch_updated_count, zero_count_local

def main():
    # Запоминаем время старта обработки
    start_time = time.time()

    # Запускаем отдельный поток для замера CPU загрузки
    cpu_thread = threading.Thread(target=cpu_sampling)
    cpu_thread.start()

    coin_ids = get_all_coin_ids()
    total_ids = len(coin_ids)
    print(f"Найдено {total_ids} монет в таблице coin_gesco_coins.")

    overall_updated_count = 0
    overall_zero_count = 0

    # Разбиваем список id на батчи по BATCH_SIZE (100)
    batches = list(batch_list(coin_ids, BATCH_SIZE))
    total_batches = len(batches)
    print(f"Всего батчей: {total_batches}")

    # Используем пул потоков для обработки батчей
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_batch = {
            executor.submit(process_batch, batch, idx + 1): idx + 1
            for idx, batch in enumerate(batches)
        }
        for future in as_completed(future_to_batch):
            batch_number = future_to_batch[future]
            try:
                updated_count, zero_count = future.result()
                overall_updated_count += updated_count
                overall_zero_count += zero_count
            except Exception as exc:
                print(f"Батч {batch_number} сгенерировал исключение: {exc}")

    print(f"\nОбновлено записей всего: {overall_updated_count} из {total_ids}")
    print(f"Количество монет с нулевым объемом или ценой: {overall_zero_count}")

    # Останавливаем поток измерения загрузки CPU
    stop_cpu_sampling.set()
    cpu_thread.join()

    # Подсчет итогового времени работы
    end_time = time.time()
    total_time = end_time - start_time

    # Вычисляем среднюю загрузку CPU по всем замерам
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0

    # Выводим итоговую информацию
    print(f"\nСкрипт работал: {total_time:.2f} секунд.")
    print(f"Средняя загрузка CPU в процессе работы: {avg_cpu:.2f}%.")
    print(f"Общее количество удалённых записей: {deleted_records}")


if __name__ == "__main__":
    main()