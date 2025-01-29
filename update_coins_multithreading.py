import os
import traceback
import requests
import time
import threading
import psutil
from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import mysql.connector

# Загружаем переменные окружения
load_dotenv()

# Параметры подключения к базе данных
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

# API-ключ и URL для CoinGecko (упрощённый метод)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
COINGECKO_URL = "https://pro-api.coingecko.com/api/v3/simple/price"

# Максимальное количество потоков
MAX_WORKERS = 15

# Глобальная коллекция замеров загрузки CPU
cpu_samples = []
# Флаг для остановки потока измерения загрузки CPU
stop_cpu_sampling = threading.Event()


def remove_coin_from_db(coin_id):
    """
    Сначала удаляет все записи из coin_category_relation по данному coin_id,
    затем удаляет саму монету из coin_gesco_coins.
    Возвращает True, если действительно была удалена хотя бы 1 запись в coin_gesco_coins.
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 1) Удаляем связанные записи из coin_category_relation
        del_cats_query = "DELETE FROM coin_category_relation WHERE coin_id = %s"
        cursor.execute(del_cats_query, (coin_id,))

        # 2) Удаляем саму монету из coin_gesco_coins
        del_coin_query = "DELETE FROM coin_gesco_coins WHERE id = %s"
        cursor.execute(del_coin_query, (coin_id,))

        conn.commit()

        deleted_rows = cursor.rowcount  # кол-во удалённых строк в последнем DELETE
        return deleted_rows > 0
    except mysql.connector.Error as e:
        print(f"Ошибка при удалении монеты {coin_id}: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def cpu_sampling():
    """
    Функция для измерения загрузки CPU.
    Каждую секунду замеряет загрузку и сохраняет в глобальный список cpu_samples.
    Работает до установки события stop_cpu_sampling.
    """
    while not stop_cpu_sampling.is_set():
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


def fetch_simple_price(ids_batch):
    """
    Выполняет запрос к API CoinGecko /simple/price
    ?ids=...&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true
    Возвращает словарь, где ключ = coin_id, значение = dict(...) с нужными данными.
    """
    ids_str = ",".join(ids_batch)
    params = {
        "ids": ids_str,
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
        "include_last_updated_at": "false"
    }
    headers = {
        "accept": "application/json",
        "x-cg-pro-api-key": COINGECKO_API_KEY
    }
    try:
        response = requests.get(COINGECKO_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()  # Пример:  {"bitcoin": {"usd": 26800, "usd_market_cap": ..., ...}, "litecoin": {...}}
        return data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к /simple/price: {e}")
        return {}


def update_coin_in_db(coin_id, market_data):
    """
    Обновляет запись монеты в таблице coin_gesco_coins по её coin_id.
    Из market_data берем:
      - "usd" -> current_price_usd
      - "usd_market_cap" -> market_cap_usd
      - "usd_24h_vol" -> total_volume_usd
      - "usd_24h_change" -> price_change_percentage_24h
    Также обновляем lastupdate = NOW().
    Возвращает True, если обновление успешно, иначе False.
    """
    current_price = market_data.get("usd")
    market_cap = market_data.get("usd_market_cap")
    total_volume = market_data.get("usd_24h_vol")
    price_change_24h = market_data.get("usd_24h_change")  # проценты

    if not coin_id:
        return False

    update_query = """
        UPDATE coin_gesco_coins SET
            current_price_usd = %s,
            market_cap_usd = %s,
            total_volume_usd = %s,
            price_change_percentage_24h = %s,
            lastupdate = NOW()
        WHERE id = %s
    """
    values = (
        current_price,
        market_cap,
        total_volume,
        price_change_24h,
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


def insert_volume_history(coin_id, market_data):
    """
    Вставляет в таблицу coin_volume_history запись с:
      - coin_id
      - volume = usd_24h_vol
      - price = usd
      - history_date_time = NOW()
    Если для монеты не передаются данные по объемам или цене (нулевые значения),
    запись не вставляется и выводится сообщение.
    Возвращает True, если вставка успешна, иначе False.
    """
    volume = market_data.get("usd_24h_vol", 0)
    price = market_data.get("usd", 0)

    # Если цена или объем равны нулю или отсутствуют, не вставляем запись
    if not volume or volume == 0 or not price or price == 0:
        print(f"Для монеты {coin_id} объем={volume}, цена={price}")
        return False

    insert_query = """
         INSERT INTO coin_volume_history (coin_id, volume, price, history_date_time)
         VALUES (%s, %s, %s, NOW())
    """
    values = (coin_id, volume, price)
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(insert_query, values)
        conn.commit()
        return True
    except mysql.connector.Error as e:
        print(f"Ошибка вставки в coin_volume_history для монеты {coin_id}: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def process_batch(batch, batch_number):
    """
    Обрабатывает один батч монет:
      - запрашивает данные с нового упрощённого API CoinGecko
      - обновляет данные монет в БД
      - вставляет историю объемов
    Возвращает (updated_count, zero_count_local)
    """
    print(f"\nОбработка батча {batch_number} (монет в батче: {len(batch)})...")
    # Получаем словарь {coin_id: {...}, ...}
    coins_data = fetch_simple_price(batch)
    received_count = len(coins_data)
    print(f"Батч {batch_number}: получено данных для {received_count} монет (из {len(batch)})")

    batch_updated_count = 0
    zero_count_local = 0

    # coins_data выглядит как, например:
    # {
    #   "bitcoin": {
    #     "usd": 26800,
    #     "usd_market_cap": 5199999990,
    #     "usd_24h_vol": 9999999,
    #     "usd_24h_change": -0.45
    #   },
    #   ...
    # }

    for coin_id in batch:
        market_data = coins_data.get(coin_id.lower())
        if not market_data:
            # Нет данных => удаляем монету coin_id из coin_gesco_coins
            removed = remove_coin_from_db(coin_id)
            print(f"Батч {batch_number}: нет данных для {coin_id}, монета удалена: {removed}")
            continue
        # Обновляем основную таблицу
        if update_coin_in_db(coin_id, market_data):
            batch_updated_count += 1
            # Добавляем запись в coin_volume_history
            if not insert_volume_history(coin_id, market_data):
                zero_count_local += 1

    print(f"Батч {batch_number}: обновлено {batch_updated_count} монет.")
    return (batch_updated_count, zero_count_local)


def delete_old_records():
    """
    Удаляет из таблицы coin_volume_history записи, старше 7 часов.
    Выводит на экран количество удалённых записей.
    """
    delete_query = """
        DELETE FROM coin_volume_history
        WHERE history_date_time < DATE_SUB(NOW(), INTERVAL 7 HOUR)
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(delete_query)
        affected = cursor.rowcount
        conn.commit()
        print(f"\nУдалено {affected} записей из таблицы coin_volume_history (старше 7 часов).")
        return affected
    except mysql.connector.Error as e:
        print(f"Ошибка при удалении старых записей: {e}")
        return 0
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def alter_table_engine():
    """
    Выполняет запрос для изменения механизма таблицы coin_volume_history на INNODB.
    """
    alter_query = "ALTER TABLE coin_volume_history ENGINE=INNODB"
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(alter_query)
        conn.commit()
        print("ALTER TABLE выполнен: coin_volume_history теперь использует ENGINE=INNODB.")
    except mysql.connector.Error as e:
        print(f"Ошибка при выполнении ALTER TABLE: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


stop_cpu_sampling = threading.Event()
cpu_samples = []

def main():
    start_time = time.time()

    # Запускаем отдельный поток для замера загрузки CPU
    cpu_thread = threading.Thread(target=cpu_sampling)
    cpu_thread.start()

    coin_ids = get_all_coin_ids()
    total_ids = len(coin_ids)
    print(f"Найдено {total_ids} монет в таблице coin_gesco_coins.")

    overall_updated_count = 0
    overall_zero_count = 0

    # Разбиваем список id на батчи по BATCH_SIZE (100)
    BATCH_SIZE = 100
    batches = list(batch_list(coin_ids, BATCH_SIZE))
    total_batches = len(batches)
    print(f"Всего батчей: {total_batches}")

    from concurrent.futures import ThreadPoolExecutor, as_completed
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

    # Удаляем записи из coin_volume_history, старше 7 часов
    deleted_records = delete_old_records()

    # Выполняем ALTER TABLE
    alter_table_engine()

    # Останавливаем поток измерения загрузки CPU
    stop_cpu_sampling.set()
    cpu_thread.join()

    end_time = time.time()
    total_time = end_time - start_time

    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    print(f"\nСкрипт работал: {total_time:.2f} секунд.")
    print(f"Средняя загрузка CPU в процессе работы: {avg_cpu:.2f}%.")
    print(f"Общее количество удалённых записей: {deleted_records}")


if __name__ == "__main__":
    main()