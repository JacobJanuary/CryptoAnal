import os
import time
import traceback
from datetime import datetime
import requests
import mysql.connector as mc
from dotenv import load_dotenv

# 1) Загружаем переменные окружения
load_dotenv()

# 2) Конфиги БД
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "crypto_db")

db_config = {
    'host': MYSQL_HOST,
    'user': MYSQL_USER,
    'password': MYSQL_PASSWORD,
    'database': MYSQL_DB
}

# Параметры Telegram
BOT_TOKEN = os.getenv("MY_TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.getenv("MY_TELEGRAM_CHAT_ID", "0"))  # например, 123456789

def send_telegram_message(text: str) -> None:
    """Отправляет сообщение text в Telegram-чат CHAT_ID, используя BOT_TOKEN."""
    if not BOT_TOKEN or CHAT_ID == 0:
        print("[WARN] Не задан токен бота или chat_id, пропускаем отправку.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": text
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        print(f"[INFO] Сообщение отправлено в Telegram: {text}")
    except Exception as e:
        print(f"[ERROR] Telegram сообщение не отправлено: {e}")

# 3) Параметры мониторинга
CHECK_INTERVAL = 60        # интервал между проверками
VOLUME_MIN = 100000        # объём, начиная с которого проверяем прирост
GROWTH_THRESHOLD = 100.0   # прирост (в %) для уведомления

def main():
    # Храним время последней обработанной записи
    last_dt = datetime(1970, 1, 1)
    # Флаг, чтобы отправить уведомление об успешном подключении только один раз
    first_connection = True

    while True:
        try:
            # Сообщаем, что пытаемся подключиться
            print("[INFO] Пытаемся подключиться к базе...")
            conn = mc.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            print("[INFO] Успешно подключились к базе.")

            # Отправляем уведомление в Telegram (только при первом подключении)
            if first_connection:
                send_telegram_message("Успешное подключение к базе данных! Начинаем мониторинг объёма.")
                first_connection = False

            # Достаём новые записи (history_date_time > last_dt)
            query_new = """
                SELECT coin_id, volume, price, history_date_time
                FROM coin_volume_history
                WHERE history_date_time > %s
                ORDER BY history_date_time ASC
            """
            cursor.execute(query_new, (last_dt,))
            new_rows = cursor.fetchall()

            if new_rows:
                print(f"[INFO] Найдено {len(new_rows)} новых записей после {last_dt}.")

            for row in new_rows:
                coin_id = row["coin_id"]
                new_volume = row["volume"]
                new_dt = row["history_date_time"]

                # Если объём > VOLUME_MIN, сравниваем с предыдущим
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
                            change_pct = ((new_volume - old_volume) / old_volume) * 100
                            if change_pct > GROWTH_THRESHOLD:
                                msg = (f"[ALERT] Монета {coin_id}: объём вырос на {change_pct:.2f}% "
                                       f"(старый={old_volume}, новый={new_volume})")
                                print(msg)
                                send_telegram_message(msg)

                # Обновляем last_dt (берём самую свежую)
                if new_dt > last_dt:
                    last_dt = new_dt

            cursor.close()
            conn.close()

        except Exception as exc:
            print("[ERROR] Ошибка в скрипте мониторинга:", traceback.format_exc())
            # Если при подключении ошибка — при следующей итерации скрипт попробует снова.
            # Можно отправить Telegram, но рискуем заспамить, если БД недоступна.

        print(f"[INFO] Ждем {CHECK_INTERVAL} секунд до следующей проверки.\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()