import os
import sqlite3
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv
from anthropic import Anthropic
from flask import Flask, render_template, request, jsonify
from flask_caching import Cache

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")  # Безопасное использование ключа

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'cryptocurrencies.db')


# Вспомогательные функции
def format_volume(volume):
    return f"{volume / 1_000_000:.2f} млн" if volume else "N/A"


def format_price(price):
    return f"{price:.2f}" if price else "N/A"


# Получение аналитики с помощью API Grok
def get_grok_analytics(name, symbol):
    if not XAI_API_KEY:
        return {"error": "API ключ не установлен. Установите переменную окружения XAI_API_KEY."}

    try:
        client = Anthropic(api_key=XAI_API_KEY, base_url="https://api.x.ai")
        prompt = (
            f"Дай подробную информацию о проекте {name} ({symbol}). "
            f"Что он делает, когда создан, кто в команде, какие перспективы, развитие, социальная активность. "
            f"Заходили ли в проект умные деньги, какие твои прогнозы по курсу токена на 2025 год"
        )

        message = client.messages.create(
            model="grok-2-1212",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )

        if message and hasattr(message, 'content') and isinstance(message.content,
                                                                  list):  # проверяем что message.content именно список
            text_blocks = message.content
            full_text = ""
            for block in text_blocks:
                if hasattr(block, 'text'):
                    full_text += block.text
            return {"content": full_text}
        elif message and hasattr(message, 'content') and hasattr(message.content,
                                                                 'text'):  # если это не список, а сразу TextBlock
            content = message.content.text
            return {"content": content}
        else:
            print(f"Unexpected response structure: {message}")
            return {"error": "Unexpected response from API"}

    except Exception as e:
        print(f"Ошибка при запросе к API Grok: {e}")
        traceback.print_exc()
        return {"error": str(e)}


# Основной маршрут
@app.route("/", methods=["GET", "POST"])
@cache.cached(timeout=300)
def index():
    conn = None  # Инициализация переменной conn
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, symbol, rank FROM cryptocurrencies")
        cryptos = cursor.fetchall()

        crypto_data_to_display = []
        time_difference_global = None

        for coin_id, coin_name, coin_symbol, current_rank in cryptos:
            cursor.execute('''
                SELECT datetime, volume, price
                FROM coins_volume_stats
                WHERE coin_id = ?
                ORDER BY datetime DESC
                LIMIT 6
            ''', (coin_id,))
            volume_data = cursor.fetchall()

            if len(volume_data) >= 2:
                periods_of_growth = 0
                time_of_growth = timedelta(0)
                total_volume_increase_percentage = 0

                for i in range(1, len(volume_data)):
                    prev_volume, prev_datetime = volume_data[i][1], volume_data[i][0]
                    curr_volume, curr_datetime = volume_data[i - 1][1], volume_data[i - 1][0]

                    if prev_volume and curr_volume and curr_volume > prev_volume:
                        periods_of_growth += 1
                        time_diff = datetime.fromisoformat(curr_datetime) - datetime.fromisoformat(prev_datetime)
                        time_of_growth += time_diff

                        increase_percentage = ((curr_volume - prev_volume) / prev_volume) * 100
                        total_volume_increase_percentage += increase_percentage

                average_volume_increase_percentage = (
                    total_volume_increase_percentage / periods_of_growth if periods_of_growth > 0 else 0
                )

                if time_difference_global is None and len(volume_data) >= 2:
                    time_difference_global = datetime.fromisoformat(volume_data[0][0]) - datetime.fromisoformat(
                        volume_data[1][0])

                latest_volume, latest_price = volume_data[0][1], volume_data[0][2]
                previous_volume, previous_price = volume_data[1][1], volume_data[1][2]

                if all(v is not None for v in (previous_volume, latest_volume, latest_price)):
                    volume_increase = ((latest_volume - previous_volume) / previous_volume) * 100
                    price_change = ((latest_price - previous_price) / previous_price) * 100

                    if volume_increase >= 20 and abs(price_change) <= 10:
                        crypto_data_to_display.append({
                            "name": coin_name,
                            "symbol": coin_symbol,
                            "rank": current_rank,
                            "current_volume": format_volume(latest_volume),
                            "volume_increase": volume_increase,
                            "current_price": format_price(latest_price),
                            "price_change": price_change,
                            "periods_of_growth": min(periods_of_growth, 5),
                            "time_of_growth": time_of_growth,
                            "average_volume_increase_percentage": average_volume_increase_percentage
                        })

        if request.method == "POST":
            print(request.form)  # Логируем входящие данные
            name = request.form.get("name")
            symbol = request.form.get("symbol")
            if name and symbol:
                analytics = get_grok_analytics(name, symbol)
                return jsonify(analytics)
            else:
                return jsonify({"error": "Не переданы name или symbol"}), 400

        return render_template("index.html", crypto_data=crypto_data_to_display, time_difference=time_difference_global)

    except sqlite3.Error as e:
        return jsonify({"error": f"Ошибка базы данных: {e}"})
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    app.run(debug=True)
