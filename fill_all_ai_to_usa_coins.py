import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import mysql.connector
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "crypto_db")


def get_grok_analytics(name, symbol):
    if not XAI_API_KEY:
        return {"error": "API ключ не установлен."}
    try:
        client = Anthropic(api_key=XAI_API_KEY, base_url="https://api.x.ai")
        prompt = (
            f"Дай подробную информацию о проекте {name} ({symbol}). "
            f"Что он делает, когда создан, кто в команде, какие перспективы, развитие, социальная активность. "
            f"Заходили ли в проект умные деньги, какие твои прогнозы по курсу токена на 2025 год."
        )
        print(f"[get_grok_analytics] Отправляем запрос ИИ по монете {name} ({symbol})...")
        response = client.messages.create(
            model="grok-beta",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        if response and isinstance(response.content[0].text, str):
            print(f"[get_grok_analytics] Ответ ИИ получен по монете {name} ({symbol}).")
            return {"content": response.content[0].text}
        else:
            return {"error": "Unexpected response from API"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


def get_grok_invest(name, symbol):
    if not XAI_API_KEY:
        return {"error": "API ключ не установлен."}
    try:
        client = Anthropic(api_key=XAI_API_KEY, base_url="https://api.x.ai")
        prompt = f"Найди информацию какие фонды или Smart money инвестировали в проект {name} ({symbol})."
        print(f"[get_grok_invest] Отправляем запрос ИИ по фондам для монеты {name} ({symbol})...")
        response = client.messages.create(
            model="grok-beta",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        if response and isinstance(response.content[0].text, str):
            print(f"[get_grok_invest] Ответ ИИ по фондам получен по монете {name} ({symbol}).")
            return {"content": response.content[0].text}
        else:
            return {"error": "Unexpected response from API"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


def main():
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB
        )
        cursor = conn.cursor(dictionary=True)

        # 1) Получаем все coin_id из категории 'made-in-usa'
        cursor.execute("SELECT coin_id FROM coin_category_relation WHERE category_id = 'made-in-usa'")
        rows = cursor.fetchall()
        if not rows:
            print("Нет монет в категории 'made-in-usa'.")
            return

        coin_ids = [r["coin_id"] for r in rows]

        # 2) Загружаем данные (name, symbol, AI_text, AI_invest) из coin_gesco_coins
        format_str = ",".join(["%s"] * len(coin_ids))
        query = f"""
            SELECT id AS coin_id, name, symbol, AI_text, AI_invest
            FROM coin_gesco_coins
            WHERE id IN ({format_str})
        """
        cursor.execute(query, tuple(coin_ids))
        coins = cursor.fetchall()
        cursor.close()

        if not coins:
            print("В таблице coin_gesco_coins нет записей, соответствующих монетам 'made-in-usa'.")
            return

        # 3) Отбираем монеты, у которых AI_text или AI_invest не заполнены
        tasks = []
        for c in coins:
            cid = c["coin_id"]
            name = c["name"]
            symbol = c["symbol"]
            ai_text = c.get("AI_text")
            ai_invest = c.get("AI_invest")

            if not ai_text or not ai_invest:
                tasks.append(c)

        need_count = len(tasks)
        if need_count == 0:
            print("Все монеты из 'made-in-usa' уже имеют AI_text и AI_invest.")
            return

        print(f"Нужно обработать {need_count} монет категории 'made-in-usa', у которых нет AI_text или AI_invest.")

        # 4) Параллельная обработка
        def process_coin(coin):
            coin_id = coin["coin_id"]
            name = coin["name"]
            symbol = coin["symbol"]
            ai_text = coin.get("AI_text")
            ai_invest = coin.get("AI_invest")
            error_log = []

            # Если нет AI_text, запрашиваем аналитику
            if not ai_text:
                ana_result = get_grok_analytics(name, symbol)
                if "error" in ana_result:
                    error_log.append("Analytics error: " + ana_result["error"])
                else:
                    ai_text = ana_result["content"]

            # Если нет AI_invest, запрашиваем информацию о фондах
            if not ai_invest:
                invest_result = get_grok_invest(name, symbol)
                if "error" in invest_result:
                    error_log.append("Invest error: " + invest_result["error"])
                else:
                    ai_invest = invest_result["content"]

            return (coin_id, ai_text, ai_invest, error_log)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_coin = {executor.submit(process_coin, c): c for c in tasks}
            for future in as_completed(future_to_coin):
                coin_data = future_to_coin[future]
                cid = coin_data["coin_id"]
                try:
                    coin_id, new_ai_text, new_ai_invest, err_log = future.result()
                    results.append((coin_id, new_ai_text, new_ai_invest, err_log))
                    print(f"[process_coin] Завершено для монеты {cid}.")
                except Exception as e:
                    print(f"[process_coin] Ошибка для монеты {cid}: {e}")
                    traceback.print_exc()

        # 5) Записываем обновления в базу
        upd_cursor = conn.cursor()
        upd_sql = "UPDATE coin_gesco_coins SET AI_text = %s, AI_invest = %s WHERE id = %s"
        cnt_updates = 0
        for (cid, ai_text, ai_invest, err_log) in results:
            # Если хотя бы одно из полей заполнено, обновляем запись
            if ai_text or ai_invest:
                upd_cursor.execute(upd_sql, (ai_text, ai_invest, cid))
                cnt_updates += 1
                if err_log:
                    print(f"[coin_id={cid}] Были ошибки: {err_log}")
                else:
                    print(f"[coin_id={cid}] Данные AI_text и AI_invest успешно обновлены.")

        conn.commit()
        upd_cursor.close()

        print(f"Обработано (параллельно) {len(results)} монет. Из них обновлено {cnt_updates}.")
    except Exception as e:
        traceback.print_exc()
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()