import os
import time
import traceback
from datetime import datetime
import mysql.connector as mc
from dotenv import load_dotenv

# 1) Загружаем переменные окружения из .env-файла,
#    как это делается в вашем Flask-проекте.
load_dotenv()

# 2) Читаем настройки для подключения к базе данных (тоже как в Flask)
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "crypto_db")

# 3) Формируем db_config — используем тот же подход, что и во Flask-приложении:
db_config = {
    'host': MYSQL_HOST,
    'user': MYSQL_USER,
    'password': MYSQL_PASSWORD,
    'database': MYSQL_DB
}

# -----------------------------
# ПАРАМЕТРЫ МОНИТОРИНГА
# -----------------------------
CHECK_INTERVAL = 6       # Сколько секунд ждать между проверками таблицы coin_volume_history
VOLUME_MIN = 10000        # Минимальный объем, при котором начинаем проверять изменение
GROWTH_THRESHOLD = 10.0   # Если прирост объема (в %) выше этого значения, выводим уведомление

def main():
    """
    Основная функция скрипта:
      - Хранит в переменной last_dt отметку времени последней обработанной записи.
      - В бесконечном цикле каждые CHECK_INTERVAL секунд:
         * Подключается к базе
         * Ищет записи с history_date_time > last_dt
         * Для каждой новой записи, если volume>VOLUME_MIN, ищет предыдущую запись и считает прирост
         * Если прирост >GROWTH_THRESHOLD, печатает уведомление
         * Поднимает last_dt до максимального history_date_time из новых строк
    """

    # При первом запуске считаем, что мы не обрабатывали вообще никакие записи.
    # Если в таблице уже много строк, вы можете вместо 1970-01-01
    # подставить datetime.now(), чтобы сразу брать только самые свежие.
    last_dt = datetime(1970, 1, 1)

    print(f"[INFO] Старт мониторинга coin_volume_history. Параметры:\n"
          f"  CHECK_INTERVAL={CHECK_INTERVAL}с, VOLUME_MIN={VOLUME_MIN}, GROWTH_THRESHOLD={GROWTH_THRESHOLD}%\n"
          f"  Начальная last_dt = {last_dt}\n"
          f"Подключаемся к базе: {db_config}\n")

    while True:
        try:
            # Подключаемся к базе через mysql.connector
            # Выводим комментарий, что мы делаем
            print("[INFO] Открываем соединение к базе...")
            conn = mc.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            print("[INFO] Соединение успешно открыто.")

            # Запрашиваем все записи, появившиеся после last_dt
            # ORDER BY ... ASC, чтобы шли по хронологическому порядку
            query_new = """
                SELECT coin_id, volume, price, history_date_time
                FROM coin_volume_history
                WHERE history_date_time > %s
                ORDER BY history_date_time ASC
            """
            cursor.execute(query_new, (last_dt,))
            new_rows = cursor.fetchall()

            if new_rows:
                print(f"[INFO] Найдено {len(new_rows)} новых записей (после {last_dt}). Начинаем обработку.")
            else:
                print(f"[INFO] Нет новых записей (после {last_dt}).")

            # Перебираем каждую новую строку
            for row in new_rows:
                coin_id = row["coin_id"]
                new_volume = row["volume"]
                new_dt = row["history_date_time"]

                # Выводим в консоль, какую строку обрабатываем
                print(f"  [DEBUG] Обработка записи для монеты={coin_id}, volume={new_volume}, time={new_dt}")

                # Если объем > VOLUME_MIN, то проверяем прирост
                if new_volume and new_volume > VOLUME_MIN:
                    # Ищем предыдущую запись
                    prev_query = """
                        SELECT volume
                        FROM coin_volume_history
                        WHERE coin_id = %s
                          AND history_date_time < %s
                        ORDER BY history_date_time DESC
                        LIMIT 1
                    """
                    cursor.execute(prev_query, (coin_id, new_dt))
                    prev_row = cursor.fetchone()
                    if prev_row:
                        old_volume = prev_row["volume"]
                        if old_volume and old_volume > 0:
                            # Считаем % изменения
                            change_pct = ((new_volume - old_volume) / old_volume) * 100
                            if change_pct > GROWTH_THRESHOLD:
                                print(f"[ALERT] Монета {coin_id} — объём вырос на {change_pct:.2f}% "
                                      f"(старый={old_volume}, новый={new_volume})")
                        else:
                            print(f"  [DEBUG] Предыдущий объем={old_volume}, нулевой или отсутствует. Пропускаем расчёт.")
                    else:
                        print(f"  [DEBUG] Нет предыдущей записи для монеты {coin_id} (для time<{new_dt}).")

                # Обновляем last_dt, если текущее время записи больше
                if new_dt > last_dt:
                    last_dt = new_dt

            # Закрываем курсор и соединение
            cursor.close()
            conn.close()
            print("[INFO] Соединение к базе закрыто.")

        except Exception as exc:
            print("[ERROR] Ошибка при обработке:", traceback.format_exc())

        # Ждем перед следующим циклом
        print(f"[INFO] Переходим в сон на {CHECK_INTERVAL} секунд...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()