import os
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv
from anthropic import Anthropic
from flask import Flask, render_template, request, jsonify
from flask_caching import Cache
from flask_mysqldb import MySQL

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Конфигурация MySQL для Flask-MySQLdb
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST", "localhost")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER", "root")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD", "password")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DATABASE", "crypto_db")

mysql = MySQL(app)

# Вспомогательные функции
def format_volume(volume):
    return f"{volume / 1_000_000:.2f} млн" if volume else "N/A"


def format_price(price):
    return f"{price:.2f}" if price else "N/A"


# Получение аналитики с помощью API Grok
def get_grok_analytics(name, symbol):
    if not XAI_API_KEY:
        error_msg = "API ключ не установлен. Установите переменную окружения XAI_API_KEY."
        print(error_msg)
        return {"error": error_msg}
    try:
        client = Anthropic(api_key=XAI_API_KEY, base_url="https://api.x.ai")
        prompt = (
            f"Дай подробную информацию о проекте {name} ({symbol}). "
            f"Что он делает, когда создан, кто в команде, какие перспективы, развитие, социальная активность. "
            f"Заходили ли в проект умные деньги, какие твои прогнозы по курсу токена на 2025 год."
        )
        print(f"[get_grok_analytics] Prompt:\n{prompt}")
        response = client.messages.create(
            model="grok-2-1212",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        print("[get_grok_analytics] Полный ответ от API:", response)
        if response and isinstance(response.content[0].text, str):
            print("[get_grok_analytics] Содержимое ответа:", response.content[0].text)
            return {"content": response.content[0].text}
        else:
            error_msg = "Unexpected response from API"
            print("[get_grok_analytics]", error_msg)
            return {"error": error_msg}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


def get_grok_invest(name, symbol):
    if not XAI_API_KEY:
        error_msg = "API ключ не установлен. Установите переменную окружения XAI_API_KEY."
        print(error_msg)
        return {"error": error_msg}
    try:
        client = Anthropic(api_key=XAI_API_KEY, base_url="https://api.x.ai")
        prompt = f"Найди информацию какие фонды или Smart money инвестировали в проект {name} ({symbol})."
        print(f"[get_grok_invest] Prompt:\n{prompt}")
        response = client.messages.create(
            model="grok-beta",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        print("[get_grok_invest] Полный ответ от API:", response)
        if response and isinstance(response.content[0].text, str):
            print("[get_grok_invest] Содержимое ответа:", response.content[0].text)
            return {"content": response.content[0].text}
        else:
            error_msg = "Unexpected response from API"
            print("[get_grok_invest]", error_msg)
            return {"error": error_msg}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        # По умолчанию используем параметры:
        # p_vol_min=10000, p_growth6h=100, p_growth1h=100, p_price_change_max=10, p_price_change_min=0, p_market_cap_rank=NULL
        p_vol_min = 10000
        p_growth6h = 100
        p_growth1h = 100
        p_price_change_max = 10
        p_price_change_min = 0
        p_market_cap_rank = None  # Если параметр равен NULL, фильтр не применяется

        if request.method == "POST":
            # Ожидаем, что POST-запрос приходит в формате JSON с нужными параметрами
            data = request.get_json() or {}
            # Если параметр отсутствует или равен пустой строке, оставляем значение по умолчанию (или NULL)
            try:
                p_vol_min = float(data.get("volMin", p_vol_min))
            except:
                pass
            try:
                p_growth6h = float(data.get("growth6h", p_growth6h))
            except:
                pass
            try:
                p_growth1h = float(data.get("growth1h", p_growth1h))
            except:
                pass
            try:
                p_price_change_max = float(data.get("priceChangeMax", p_price_change_max))
            except:
                pass
            try:
                p_price_change_min = float(data.get("priceChangeMin", p_price_change_min))
            except:
                pass
            try:
                # Если параметр не задан, оставляем NULL
                market_cap_rank_val = data.get("marketCapRank")
                if market_cap_rank_val is not None and market_cap_rank_val != "":
                    p_market_cap_rank = int(market_cap_rank_val)
                else:
                    p_market_cap_rank = None
            except:
                p_market_cap_rank = None

        # Формируем запрос к хранимой функции/процедуре cg_GetFilteredCoins с нужными параметрами.
        # Если ваша функция/процедура возвращает результирующий набор, используем CALL:
        query = "CALL cg_GetFilteredCoins(%s, %s, %s, %s, %s, %s)"
        # Для p_market_cap_rank, если значение None, передаём SQL NULL (можно использовать None напрямую)
        params = (p_vol_min, p_growth6h, p_growth1h, p_price_change_max, p_price_change_min, p_market_cap_rank)

        cur = mysql.connection.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        crypto_data = [dict(zip(col_names, row)) for row in rows]
        cur.close()


        # Если POST-запрос для аналитики и инвестиций
        if request.method == "POST":
            name = request.form.get("name")
            symbol = request.form.get("symbol")
            if not name or not symbol:
                error_msg = "Не переданы name или symbol"
                print("[index] Ошибка:", error_msg)
                return jsonify({"error": error_msg}), 400

            # Проверяем, есть ли уже сохранённый AI_text в БД
            cur = mysql.connection.cursor()
            cur.execute("SELECT AI_text FROM coin_gesco_coins WHERE name = %s AND symbol = %s", (name, symbol))
            row = cur.fetchone()
            if row and row[0]:
                print("[index] AI_text уже есть в БД, возвращаем сохранённый текст.")
                return jsonify({"content": row[0]})

            analytics = get_grok_analytics(name, symbol)
            if "error" in analytics:
                print("[index] Ошибка при получении аналитики:", analytics["error"])
                return jsonify(analytics), 400

            ai_text = analytics.get("content")
            print("[index] Полученный AI_text:", ai_text)

            cur.execute("UPDATE coin_gesco_coins SET AI_text = %s WHERE name = %s AND symbol = %s",
                        (ai_text, name, symbol))
            mysql.connection.commit()

            invest = get_grok_invest(name, symbol)
            if "error" in invest:
                print("[index] Ошибка при получении данных об инвестициях:", invest["error"])
                return jsonify(invest), 400

            ai_invest = invest.get("content")
            print("[index] Полученный AI_invest:", ai_invest)

            cur.execute("UPDATE coin_gesco_coins SET AI_invest = %s WHERE name = %s AND symbol = %s",
                        (ai_invest, name, symbol))
            mysql.connection.commit()
            cur.close()

            return jsonify({"content": ai_text})

        return render_template("coingecko.html", crypto_data=crypto_data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Ошибка: {e}"})


# Обработчик для переключения избранного (toggle_favourite)
@app.route("/toggle_favourite", methods=["POST"])
def toggle_favourite():
    try:
        data = request.get_json()
        coin_id = data.get("id")
        new_val = data.get("isFavourites")  # True или False

        if coin_id is None or new_val is None:
            return jsonify({"error": "Не переданы необходимые данные"}), 400

        bool_val = 1 if new_val else 0

        cur = mysql.connection.cursor()
        cur.execute("UPDATE coin_gesco_coins SET isFavourites = %s WHERE id = %s", (bool_val, coin_id))
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)