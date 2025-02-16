import os
import time
import traceback
from datetime import datetime
import requests
import mysql.connector as mc
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация БД
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "crypto_db")

db_config = {
    "host": MYSQL_HOST,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "database": MYSQL_DB
}

# Параметры Telegram
BOT_TOKEN = os.getenv("MY_TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.getenv("MY_TELEGRAM_CHAT_ID", "0"))  # например, 123456789

def send_telegram_message(text: str) -> None:
    """Отправляет сообщение text в Telegram-чат CHAT_ID, используя BOT_TOKEN."""
    if not BOT_TOKEN or CHAT_ID == 0:
        print("[WARN] Не задан токен бота или chat_id — пропускаем отправку.")
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

# Параметры мониторинга
CHECK_INTERVAL = 6         # интервал между проверками (сек)
MARKET_CAP_RANK_MIN = 1
MARKET_CAP_RANK_MAX = 9999
VOLUME_MIN = 10000
GROWTH_THRESHOLD = 100.0

def main():
    # Храним время последней обработанной записи
    last_dt = datetime(1970, 1, 1)
    # Флаг, чтобы отправить уведомление об успешном подключении только один раз
    first_connection = True

    while True:
        try:
            conn = mc.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            if first_connection:
                print("[INFO] Успешно подключились к базе.")
                send_telegram_message("Успешное подключение к базе данных! Начинаем мониторинг объёма.")
                first_connection = False

            # Получаем новые записи по ограниченному market_cap_rank
            query_new = """
                SELECT ch.coin_id,
                       ch.volume AS new_volume,
                       ch.price,
                       ch.history_date_time,
                       cg.name AS coin_name,
                       cg.symbol AS coin_symbol,
                       cg.market_cap_rank
                FROM coin_volume_history AS ch
                JOIN coin_gesco_coins AS cg ON cg.id = ch.coin_id
                WHERE ch.history_date_time > %s
                  AND cg.market_cap_rank BETWEEN %s AND %s
                ORDER BY ch.history_date_time ASC
            """
            cursor.execute(query_new, (last_dt, MARKET_CAP_RANK_MIN, MARKET_CAP_RANK_MAX))
            new_rows = cursor.fetchall()

            for row in new_rows:
                coin_id = row["coin_id"]
                coin_name = row["coin_name"]
                coin_symbol = row["coin_symbol"]
                new_volume = row["new_volume"]
                new_dt = row["history_date_time"]

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
                        if old_volume and old_volume > VOLUME_MIN:
                            change_pct = ((new_volume - old_volume) / old_volume) * 100
                            if change_pct > GROWTH_THRESHOLD:
                                # Формируем ссылку на coingesco, подставляя coin_id
                                coin_url = f"https://coingecko.com/coins/{coin_id}"
                                # Формируем сообщение, добавляем значок «🚀»
                                msg = (
                                    f"🚀  {coin_name} ({coin_symbol}): объём вырос на "
                                    f"{change_pct:.2f}% (старый={old_volume}, новый={new_volume})\n"
                                    f"Ссылка: {coin_url}"
                                )
                                print(msg)
                                send_telegram_message(msg)

                # Обновляем last_dt
                if new_dt > last_dt:
                    last_dt = new_dt

            cursor.close()
            conn.close()

        except Exception:
            print("[ERROR] Ошибка в скрипте мониторинга:")
            print(traceback.format_exc())

        # Ждём до следующей проверки
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()