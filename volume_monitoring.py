import os
import time
import traceback
from datetime import datetime
import requests
import mysql.connector as mc
from dotenv import load_dotenv

load_dotenv()

# Подключаемся, как в Flask
db_config = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", "password"),
    'database': os.getenv("MYSQL_DATABASE", "crypto_db")
}

# Параметры Telegram
BOT_TOKEN = os.getenv("MY_TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.getenv("MY_TELEGRAM_CHAT_ID", "0"))  # ваш id или id группы

def send_telegram_message(text):
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
    except Exception as e:
        print(f"[ERROR] Telegram сообщение не отправлено: {e}")


CHECK_INTERVAL = 60
VOLUME_MIN = 100000
GROWTH_THRESHOLD = 100.0

def main():
    last_dt = datetime(1970, 1, 1)

    while True:
        try:
            conn = mc.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            query_new = """
                SELECT coin_id, volume, price, history_date_time
                FROM coin_volume_history
                WHERE history_date_time > %s
                ORDER BY history_date_time ASC
            """
            cursor.execute(query_new, (last_dt,))
            new_rows = cursor.fetchall()

            if new_rows:
                print(f"[INFO] Найдено {len(new_rows)} новых записей (после {last_dt}).")

            for row in new_rows:
                coin_id = row["coin_id"]
                new_volume = row["volume"]
                new_dt = row["history_date_time"]

                if new_volume and new_volume > VOLUME_MIN:
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
                        if old_volume and old_volume>0:
                            change_pct = ((new_volume - old_volume)/old_volume)*100
                            if change_pct>GROWTH_THRESHOLD:
                                msg = (f"[ALERT] Монета {coin_id}: объём вырос на {change_pct:.2f}% "
                                       f"(старый={old_volume}, новый={new_volume})")
                                print(msg)
                                send_telegram_message(msg)

                if new_dt>last_dt:
                    last_dt = new_dt

            cursor.close()
            conn.close()

        except Exception as exc:
            print("[ERROR]", traceback.format_exc())

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()