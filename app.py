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

        # Выводим в консоль весь ответ от API
        print("[get_grok_analytics] Полный ответ от API:", response)

        if response and isinstance(response.content, str):
            print("[get_grok_analytics] Содержимое ответа:", response.content)
            return {"content": response.content}
        else:
            error_msg = "Unexpected response from API"
            print("[get_grok_analytics]", error_msg)
            return {"error": error_msg}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# Получение информации об инвестициях
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

        # Выводим в консоль весь ответ от API
        print("[get_grok_invest] Полный ответ от API:", response)

        if response and isinstance(response.content, str):
            print("[get_grok_invest] Содержимое ответа:", response.content)
            return {"content": response.content}
        else:
            error_msg = "Unexpected response from API"
            print("[get_grok_invest]", error_msg)
            return {"error": error_msg}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# Основной маршрут
@app.route("/", methods=["GET", "POST"])
def index():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, symbol, cryptorank FROM cryptocurrencies")
        cryptos = cur.fetchall()

        crypto_data_to_display = []
        time_difference_global = None

        for coin in cryptos:
            coin_id = coin[0]
            cur.execute('''
                SELECT datetime, volume, price
                FROM coins_volume_stats
                WHERE coin_id = %s
                ORDER BY datetime DESC
                LIMIT 6
            ''', (coin_id,))
            volume_data = cur.fetchall()

            if len(volume_data) >= 2:
                periods_of_growth = 0
                time_of_growth = timedelta(0)
                total_volume_increase_percentage = 0

                for i in range(1, len(volume_data)):
                    prev_volume, prev_datetime = volume_data[i][1], volume_data[i][0]
                    curr_volume, curr_datetime = volume_data[i - 1][1], volume_data[i - 1][0]

                    # Проверяем, что даты не None
                    if prev_datetime and curr_datetime:
                        time_diff = datetime.fromisoformat(str(curr_datetime)) - datetime.fromisoformat(
                            str(prev_datetime))
                    else:
                        time_diff = timedelta(0)

                    if prev_volume and curr_volume and curr_volume > prev_volume:
                        periods_of_growth += 1
                        time_of_growth += time_diff

                        increase_percentage = ((curr_volume - prev_volume) / prev_volume) * 100
                        total_volume_increase_percentage += increase_percentage

                average_volume_increase_percentage = (
                    total_volume_increase_percentage / periods_of_growth if periods_of_growth > 0 else 0
                )

                if volume_data and len(volume_data) >= 2:
                    # Если значения уже datetime:
                    time_difference_global = volume_data[0][0] - volume_data[1][0]
                else:
                    time_difference_global = timedelta(0)

                latest_volume, latest_price = volume_data[0][1], volume_data[0][2]
                previous_volume, previous_price = volume_data[1][1], volume_data[1][2]

                if all(v is not None for v in (previous_volume, latest_volume, latest_price)):
                    volume_increase = ((latest_volume - previous_volume) / previous_volume) * 100
                    price_change = ((latest_price - previous_price) / previous_price) * 100

                    if volume_increase >= 20 and abs(price_change) <= 10:
                        crypto_data_to_display.append({
                            "name": coin[1],
                            "symbol": coin[2],
                            "rank": coin[3],
                            "current_volume": format_volume(latest_volume),
                            "volume_increase": volume_increase,
                            "current_price": format_price(latest_price),
                            "price_change": price_change,
                            "periods_of_growth": min(periods_of_growth, 5),
                            "time_of_growth": time_of_growth,
                            "average_volume_increase_percentage": average_volume_increase_percentage
                        })

        if request.method == "POST":
            name = request.form.get("name")
            symbol = request.form.get("symbol")

            if not name or not symbol:
                error_msg = "Не переданы name или symbol"
                print("[index] Ошибка:", error_msg)
                return jsonify({"error": error_msg}), 400

            # Проверяем, есть ли уже сохранённый AI_text в БД
            cur.execute("SELECT AI_text FROM cryptocurrencies WHERE name = %s AND symbol = %s", (name, symbol))
            row = cur.fetchone()

            if row and row[0]:
                print("[index] AI_text уже есть в БД, возвращаем сохранённый текст.")
                return jsonify({"content": row[0]})

            # Получаем свежую аналитику
            analytics = get_grok_analytics(name, symbol)
            if "error" in analytics:
                print("[index] Ошибка при получении аналитики:", analytics["error"])
                return jsonify(analytics), 400

            ai_text = analytics.get("content")
            print("[index] Полученный AI_text:", ai_text)

            cur.execute("""
                UPDATE cryptocurrencies SET AI_text = %s WHERE name = %s AND symbol = %s
            """, (ai_text, name, symbol))
            mysql.connection.commit()

            # Получаем информацию по инвестициям
            #invest = get_grok_invest(name, symbol)
            #if "error" in invest:
            #    print("[index] Ошибка при получении данных об инвестициях:", invest["error"])
            #    return jsonify(invest), 400

            #ai_invest = invest.get("content")
            #print("[index] Полученный AI_invest:", ai_invest)

            #cur.execute("""
            #    UPDATE cryptocurrencies SET AI_invest = %s WHERE name = %s AND symbol = %s
            #""", (ai_invest, name, symbol))
            # mysql.connection.commit()

            return jsonify({"content": ai_text})

        return render_template("index.html", crypto_data=crypto_data_to_display, time_difference=time_difference_global)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Ошибка: {e}"})


if __name__ == "__main__":
    # Включаем debug для более подробного вывода ошибок в консоль
    app.run(debug=True)