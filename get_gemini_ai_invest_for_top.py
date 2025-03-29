def wait_with_countdown(minutes):
    """
    Ожидание с обратным отсчетом
    """
    seconds = minutes * 60
    for remaining in range(seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        hours, mins = divmod(mins, 60)
        timer = f"{hours:02d}:{mins:02d}:{secs:02d}"
        print(f"Ожидание: {timer} до следующей попытки", end="\r")
        time.sleep(1)
    print("\nВремя ожидания истекло. Возобновление обработки...")

import os
import time
import mysql.connector
import google.generativeai as genai
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация базы данных
DB_TYPE = os.getenv('DB_TYPE', 'mysql')
DB_NAME = os.getenv('DB_NAME', 'crypto_db')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# Конфигурация Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("API ключ Gemini не найден. Пожалуйста, установите GEMINI_API_KEY в файле .env")

# Настройка клиента Gemini
genai.configure(api_key=GEMINI_API_KEY)


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


def fetch_top_cryptocurrencies(conn):
    """
    Получение криптовалют из категории isTop, у которых еще нет данных об инвестициях
    """
    cursor = conn.cursor(dictionary=True)

    # Получаем список id категорий с isTop=1
    cursor.execute("SELECT id FROM categories WHERE isTop = 1")
    category_ids = [row['id'] for row in cursor.fetchall()]

    if not category_ids:
        print("Не найдены категории с isTop=1")
        return []

    # Получаем список монет, относящихся к этим категориям,
    # у которых еще нет информации об инвестициях
    placeholders = ','.join(['%s'] * len(category_ids))
    query = f"""
    SELECT DISTINCT c.id, c.name, c.symbol, c.cmc_rank
    FROM cmc_crypto c
    JOIN cmc_category_relations r ON c.id = r.coin_id
    WHERE r.category_id IN ({placeholders})
    AND (c.gemini_invest IS NULL OR c.gemini_invest = '')
    ORDER BY c.cmc_rank
    """

    cursor.execute(query, category_ids)
    cryptos = cursor.fetchall()

    print(f"Получено {len(cryptos)} криптовалют из категории isTop, требующих обработки")
    return cryptos


def query_gemini_for_crypto(crypto_name, crypto_symbol):
    """
    Отправка запроса к Gemini для получения информации об инвестициях
    """
    # Шаблон запроса
    prompt = f"""Найди информацию об инвестициях в проект {crypto_name} ({crypto_symbol}), включая фонды, суммы инвестиций, даты и цены токенов. Если цены токенов для фондов неизвестны, найди общую сумму инвестиций и количество токенов, выделенных ранним инвесторам, и рассчитай среднюю стоимость токена для фондов.

(1) Найди информацию о раундах финансирования проекта {crypto_name} ({crypto_symbol}).
(2) Для каждого раунда финансирования определи названия инвестиционных фондов, участвовавших в нем.
(3) Узнай сумму инвестиций для каждого фонда в каждом раунде, если эта информация доступна.
(4) Определи дату каждого раунда финансирования.
(5) Найди цену токена {crypto_symbol} для каждого инвестиционного фонда в каждом раунде, если эта информация доступна.
(6) Если цена токена для какого-либо фонда неизвестна, найди общую сумму инвестиций, привлеченных проектом от ранних инвесторов.
(7) Найди общее количество токенов {crypto_symbol}, выделенных ранним инвесторам.
(8) Рассчитай среднюю стоимость токена {crypto_symbol} для ранних инвесторов, разделив общую сумму инвестиций (из пункта 6) на общее количество выделенных токенов (из пункта 7)."""

    try:
        # Создание модели Gemini
        model = genai.GenerativeModel(model_name="gemini-2.5-pro-exp-03-25")

        # Отправка запроса
        response = model.generate_content(prompt)

        # Извлечение и возврат текста ответа
        if hasattr(response, 'text'):
            return response.text
        else:
            return str(response)

    except Exception as e:
        error_str = str(e)
        # Проверяем, является ли ошибка превышением квоты (HTTP 429)
        if "429" in error_str:
            print(f"Ошибка при запросе к Gemini для {crypto_symbol}: превышена квота (429)")
            # Возвращаем специальный маркер для обработки превышения квоты
            return "QUOTA_EXCEEDED"
        else:
            print(f"Ошибка при запросе к Gemini для {crypto_symbol}: {error_str}")
            return f"Ошибка при запросе: {error_str}"


def save_invest_info_to_db(conn, crypto_id, invest_info):
    """
    Сохранение информации об инвестициях в базу данных
    """
    cursor = conn.cursor()

    update_sql = """
    UPDATE cmc_crypto
    SET gemini_invest = %s
    WHERE id = %s
    """

    cursor.execute(update_sql, (invest_info, crypto_id))
    conn.commit()

    return cursor.rowcount


def main():
    try:
        start_time = time.time()

        # Создание подключения к базе данных
        conn = create_database_connection()

        # Получение криптовалют из категории isTop
        cryptocurrencies = fetch_top_cryptocurrencies(conn)

        if not cryptocurrencies:
            print("Нет криптовалют для обработки")
            return

        processed_count = 0
        quota_exceeded_cryptos = []

        # Обработка каждой криптовалюты
        for crypto in cryptocurrencies:
            try:
                print(f"Обработка {crypto['symbol']} (ID: {crypto['id']})...")

                # Запрос к Gemini
                invest_info = query_gemini_for_crypto(crypto['name'], crypto['symbol'])

                # Проверяем, превышена ли квота
                if invest_info == "QUOTA_EXCEEDED":
                    print(f"Квота для запросов к Gemini превышена при обработке {crypto['symbol']}.")
                    print(f"Приостановка выполнения скрипта на 60 минут...")

                    # Добавляем текущую и все оставшиеся криптовалюты в список для последующей обработки
                    quota_exceeded_cryptos.append(crypto)
                    remaining_index = cryptocurrencies.index(crypto) + 1
                    quota_exceeded_cryptos.extend(cryptocurrencies[remaining_index:])

                    # Запускаем обратный отсчет на 60 минут
                    wait_with_countdown(60)

                    # Прерываем текущий цикл, переходим к обработке отложенных криптовалют
                    break

                elif invest_info:
                    # Сохранение результата в базу данных
                    updated = save_invest_info_to_db(conn, crypto['id'], invest_info)
                    if updated:
                        print(f"Информация об инвестициях для {crypto['symbol']} сохранена в базе данных")
                    else:
                        print(f"Не удалось сохранить информацию для {crypto['symbol']}")

                processed_count += 1
                print(f"Обработано {processed_count} из {len(cryptocurrencies)} криптовалют")

                # Задержка между запросами для соблюдения лимитов API
                time.sleep(2)

            except Exception as e:
                print(f"Ошибка при обработке {crypto['symbol']}: {str(e)}")
                continue

        # Обработка криптовалют, отложенных из-за превышения квоты
        if quota_exceeded_cryptos:
            print(f"\nНачало обработки {len(quota_exceeded_cryptos)} отложенных криптовалют...")
            retry_processed = 0

            for crypto in quota_exceeded_cryptos:
                try:
                    print(f"Обработка отложенной криптовалюты {crypto['symbol']} (ID: {crypto['id']})...")

                    # Запрос к Gemini
                    invest_info = query_gemini_for_crypto(crypto['name'], crypto['symbol'])

                    # Снова проверяем, превышена ли квота
                    if invest_info == "QUOTA_EXCEEDED":
                        print(f"Квота для Gemini всё ещё превышена при обработке {crypto['symbol']}.")
                        print(f"Приостановка выполнения скрипта ещё на 60 минут...")

                        # Добавляем оставшиеся криптовалюты в новый список
                        remaining_index = quota_exceeded_cryptos.index(crypto)
                        remaining_cryptos = quota_exceeded_cryptos[remaining_index:]

                        # Запускаем обратный отсчет на 60 минут
                        wait_with_countdown(60)

                        # Рекурсивно обрабатываем оставшиеся криптовалюты
                        # (можно реализовать более элегантное решение с использованием циклов)
                        for remaining_crypto in remaining_cryptos:
                            try:
                                print(
                                    f"Обработка оставшейся криптовалюты {remaining_crypto['symbol']} (ID: {remaining_crypto['id']})...")

                                remaining_info = query_gemini_for_crypto(remaining_crypto['name'],
                                                                         remaining_crypto['symbol'])

                                if remaining_info == "QUOTA_EXCEEDED":
                                    print(f"Квота всё ещё превышена. Пропускаем {remaining_crypto['symbol']}.")
                                elif remaining_info:
                                    updated = save_invest_info_to_db(conn, remaining_crypto['id'], remaining_info)
                                    if updated:
                                        print(f"Информация для {remaining_crypto['symbol']} сохранена после ожидания")
                                    else:
                                        print(f"Не удалось сохранить информацию для {remaining_crypto['symbol']}")

                                retry_processed += 1
                                print(
                                    f"Обработано {retry_processed} из {len(quota_exceeded_cryptos)} отложенных криптовалют")
                                time.sleep(2)
                            except Exception as e:
                                print(
                                    f"Ошибка при обработке оставшейся криптовалюты {remaining_crypto['symbol']}: {str(e)}")
                                continue

                        # Прерываем основной цикл, так как оставшиеся криптовалюты уже обработаны
                        break

                    elif invest_info:
                        # Сохранение результата в базу данных
                        updated = save_invest_info_to_db(conn, crypto['id'], invest_info)
                        if updated:
                            print(
                                f"Информация об инвестициях для {crypto['symbol']} сохранена в базе данных после ожидания")
                        else:
                            print(f"Не удалось сохранить информацию для {crypto['symbol']}")

                    retry_processed += 1
                    print(f"Обработано {retry_processed} из {len(quota_exceeded_cryptos)} отложенных криптовалют")

                    # Задержка между запросами
                    time.sleep(2)

                except Exception as e:
                    print(f"Ошибка при обработке отложенной криптовалюты {crypto['symbol']}: {str(e)}")
                    continue

        # Закрытие соединения с базой данных
        conn.close()

        total_time = time.time() - start_time
        print(f"Общее время выполнения: {total_time:.2f} секунд")
        print(f"Всего обработано {processed_count + len(quota_exceeded_cryptos)} криптовалют")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
    main()