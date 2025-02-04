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
        response = client.messages.create(
            model="grok-beta",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        if response and isinstance(response.content[0].text, str):
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
        response = client.messages.create(
            model="grok-beta",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        if response and isinstance(response.content[0].text, str):
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

        # 1) Считываем текущие настройки фильтра
        cursor.execute(
            "SELECT vol_min, growth6h, growth1h, price_change_max, price_change_min, market_cap_rank FROM filter_settings WHERE id = 1")
        row = cursor.fetchone()
        filters = {
            "vol_min": row["vol_min"] if row and row["vol_min"] else 10000,
            "growth6h": row["growth6h"] if row and row["growth6h"] else 100,
            "growth1h": row["growth1h"] if row and row["growth1h"] else 100,
            "price_change_max": row["price_change_max"] if row and row["price_change_max"] else 10,
            "price_change_min": row["price_change_min"] if row and row["price_change_min"] else 0,
            "market_cap_rank": row["market_cap_rank"] if row and row["market_cap_rank"] else None
        }

        # 2) Получаем монеты из cg_GetFilteredCoins
        call_sql = "CALL AI_GetFilteredCoins(%s, %s, %s, %s, %s, %s)"
        params = (
            filters["vol_min"],
            filters["growth6h"],
            filters["growth1h"],
            filters["price_change_max"],
            filters["price_change_min"],
            filters["market_cap_rank"]
        )
        cursor.execute(call_sql, params)
        coins = cursor.fetchall()

        # Пытаемся освободить остальные result set, если вдруг они есть.
        # Но если процедура возвращает только 1 result set, это может вызвать 2053.
        try:
            cursor.nextset()  # всего один вызов
        except mysql.connector.InterfaceError:
            pass  # игнорируем ошибку 2053: "Attempt to read a row while there is no result set"

        cursor.close()
        if not coins:
            print("Нет монет, удовлетворяющих текущим фильтрам.")
            return

        # 3) Определяем, какие монеты из этого списка трендовые
        coin_ids = [c["coin_id"] for c in coins]  # предполагая, что поле называется 'id'
        format_str = ','.join(['%s'] * len(coin_ids))
        trend_map = {}

        if coin_ids:
            trend_cursor = conn.cursor()
            trend_sql = f"""
                SELECT ccr.coin_id, MIN(cc.about_what) AS min_about
                FROM coin_category_relation ccr
                JOIN CG_Categories cc ON ccr.category_id = cc.category_id
                WHERE ccr.coin_id IN ({format_str})
                  AND cc.about_what <> 0
                GROUP BY ccr.coin_id
            """
            trend_cursor.execute(trend_sql, tuple(coin_ids))
            rows2 = trend_cursor.fetchall()
            trend_cursor.close()
            for r in rows2:
                c_id, min_val = r[0], r[1]
                trend_map[c_id] = min_val

        # 4) Составляем список «трендовых» монет, у которых AI_text или AI_invest пусты
        tasks = []
        for c in coins:
            cid = c["coin_id"]
            name = c["name"]
            symbol = c["symbol"]
            ai_text = c.get("AI_text")
            ai_invest = c.get("AI_invest")
            min_about = trend_map.get(cid, 0)
            isFavourites = c.get('isFavourites')

            # не трендовая - пропускаем
            if min_about == 0 and not isFavourites:
                continue

            # нужно ли обновить
            if not ai_text or not ai_invest:
                tasks.append(c)

        need_count = len(tasks)
        if need_count == 0:
            print("Все трендовые монеты уже имеют AI_text и AI_invest.")
            return

        print(f"Нужно обработать {need_count} трендовых монет, у которых нет AI_text или AI_invest.")

        # 5) Спросим у пользователя, продолжать ли

        # 6) Параллельная обработка
        def process_coin(coin):
            coin_id = coin["coin_id"]
            name = coin["name"]
            symbol = coin["symbol"]
            ai_text = coin.get("AI_text")
            ai_invest = coin.get("AI_invest")
            error_log = []

            if not ai_text:
                res_ana = get_grok_analytics(name, symbol)
                if "error" in res_ana:
                    error_log.append("Analytics error: " + res_ana["error"])
                else:
                    ai_text = res_ana["content"]
            if not ai_invest:
                res_inv = get_grok_invest(name, symbol)
                if "error" in res_inv:
                    error_log.append("Invest error: " + res_inv["error"])
                else:
                    ai_invest = res_inv["content"]
            return (coin_id, ai_text, ai_invest, error_log)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_coin = {executor.submit(process_coin, c): c for c in tasks}
            for future in as_completed(future_to_coin):
                cdata = future_to_coin[future]
                try:
                    coin_id, new_ai_text, new_ai_invest, err_log = future.result()
                    results.append((coin_id, new_ai_text, new_ai_invest, err_log))
                except Exception as e:
                    traceback.print_exc()

        # 7) Запись в базу
        upd_cursor = conn.cursor()
        upd_sql = "UPDATE coin_gesco_coins SET AI_text = %s, AI_invest = %s WHERE id = %s"
        cnt_updates = 0
        for (cid, ai_text, ai_invest, err_log) in results:
            if ai_text or ai_invest:
                upd_cursor.execute(upd_sql, (ai_text, ai_invest, cid))
                cnt_updates += 1
                if err_log:
                    print(f"[coin_id={cid}] Были ошибки: {err_log}")
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