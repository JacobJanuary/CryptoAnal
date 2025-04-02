import os
import time
import mysql.connector
from google import genai
from google.genai import types
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
    cursor.execute("SELECT id FROM categories WHERE name = 'Made in America'")
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
    Отправка запроса к Gemini для получения информации о криптовалюте с использованием Google-поиска
    """
    try:
        # Создание клиента Gemini API с нашим ключом
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Формируем промт, заменяя Sui на имя запрашиваемой криптовалюты
        prompt_text = f"""Проведи детальный анализ криптовалюты {crypto_name}
Мне нужен глубокий анализ проекта с использованием всех возможностей искусственного интеллекта.
Что делает, какую проблему решает проект. Стадия готовности, кем используется и где.
Исследуй интерес крупного капитала (так называемые whale transactions):
- Каков интерес крупных держателей к проекту?
- Какой процент эмиссии держат киты?
- Наблюдалась ли тенденция к накоплению или продаже токенов китами в течение последнего года?
Проанализируй интерес и вложения в проект со стороны так называемых \"умных денег\" (Smart money):
- Какие фонды вложились в проект?
- Каковы суммы инвестиций фондов?
- По какой цене фонды приобретали токены?
- Разблокированы ли уже токены, принадлежащие фондам?
- Успели ли фонды продать свои токены и получить прибыль, превышающую 20-кратный размер их первоначальных инвестиций?
Изучи торговлю проектом на централизованных биржах:
- На каких централизованных биржах торгуется {crypto_name}?
- Каковы текущие объемы торгов?
- Наблюдались ли ощутимые всплески объема торгов? Если да, то как ты можешь это охарактеризовать?
Оцени мнение лидеров индустрии и лидеров мнений о проекте {crypto_name}.
Выясни дату выхода проекта:
- Когда был выпущен токен {crypto_name}?
- Когда состоялся листинг на биржах?
- Произошло ли это во время бычьего рынка 2021 года или позже/раньше?
- Какова была максимальная рыночная капитализация проекта?
Оцени текущую актуальность проекта:
- В тренде ли сейчас то, чем занимается проект?
- Насколько сильна команда проекта?
- К какой стране относится проект? Зарегистрирован ли он в США?
Проанализируй активность команды разработчиков:
- Какова активность команды в целом?
- Какова активность в репозиториях GitHub и других платформах для разработчиков?
Оцени перспективы проекта:
- Каковы общие перспективы развития проекта {crypto_name}?
- Сделай прогноз цены токена на ближайший альтсезон."""

        # Настраиваем конфигурацию для генерации с использованием Google Search
        response = client.models.generate_content(
            model="gemini-2.5-pro-exp-03-25",
            contents=prompt_text,
            config=types.GenerateContentConfig(
                tools=[types.Tool(
                    google_search=types.GoogleSearchRetrieval
                )]
            )
        )

        # Получаем и возвращаем текст ответа
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

                # Запрос к Gemini с Google-поиском
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
                        print(f"Информация для {crypto['symbol']} сохранена в базе данных")
                    else:
                        print(f"Не удалось сохранить информацию для {crypto['symbol']}")

                processed_count += 1
                print(f"Обработано {processed_count} из {len(cryptocurrencies)} криптовалют")

                # Задержка между запросами для соблюдения лимитов API
                time.sleep(5)  # Увеличиваем задержку для работы с Google-поиском

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

                    # Запрос к Gemini с Google-поиском
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
                                time.sleep(5)  # Увеличиваем задержку для работы с Google-поиском
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
                            print(f"Информация для {crypto['symbol']} сохранена в базе данных после ожидания")
                        else:
                            print(f"Не удалось сохранить информацию для {crypto['symbol']}")

                    retry_processed += 1
                    print(f"Обработано {retry_processed} из {len(quota_exceeded_cryptos)} отложенных криптовалют")

                    # Задержка между запросами
                    time.sleep(5)  # Увеличиваем задержку для работы с Google-поиском

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


# Функция для запуска анализа одной конкретной криптовалюты по имени
def analyze_single_crypto(crypto_name, crypto_symbol):
    """
    Анализ одной конкретной криптовалюты по имени и символу
    """
    try:
        print(f"Запуск анализа для {crypto_name} ({crypto_symbol})...")
        analysis_info = query_gemini_for_crypto(crypto_name, crypto_symbol)

        if analysis_info == "QUOTA_EXCEEDED":
            print("Квота для запросов к Gemini превышена. Попробуйте позже.")
            return None

        return analysis_info

    except Exception as e:
        print(f"Ошибка при анализе {crypto_name}: {str(e)}")
        return None


if __name__ == "__main__":
    # Проверяем наличие аргументов командной строки
    import sys

    if len(sys.argv) > 2:
        # Если переданы аргументы, анализируем конкретную криптовалюту
        crypto_name = sys.argv[1]
        crypto_symbol = sys.argv[2]
        result = analyze_single_crypto(crypto_name, crypto_symbol)

        if result:
            print("\nРезультат анализа:")
            print(result)

            # Опционально сохраняем в файл
            with open(f"{crypto_symbol}_analysis.txt", "w", encoding="utf-8") as f:
                f.write(result)
            print(f"Результат сохранен в файл {crypto_symbol}_analysis.txt")
    else:
        # Если аргументы не переданы, запускаем обработку всех криптовалют из БД
        main()