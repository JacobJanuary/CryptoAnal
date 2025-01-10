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
                LIMIT 7
            ''', (coin_id,))
            volume_data = cur.fetchall()

            # Если вообще нет записей — пропускаем
            if not volume_data:
                continue

            # ---------------------------------------------------
            # 1) Функция поиска "объёма N часов назад" (fallback 6->5->4->3->2->1)
            #    Аналогично сделаем и для цены.
            # ---------------------------------------------------
            def get_old_value(data, idx=1):
                """
                Ищем "старое" значение volume/price n часов назад,
                при этом пытаемся взять 6, потом 5, 4 и т.д. если не хватает строк.
                Если нет данных даже на 1 час, вернётся None.

                Параметр idx=1 говорит: "пытаемся взять 6" (т. е. data[6]),
                но если len(data) <= 6, пробуем 5, 4... 1.
                """
                for hours_back in range(6, 0, -1):
                    if len(data) > hours_back:
                        return data[hours_back][idx]  # volume или price
                return None

            # ---------------------------------------------------
            # 2) Расчёт объёмного роста за 6 часов (fallback)
            # ---------------------------------------------------
            latest_volume = volume_data[0][1]  # свежий volume
            old_volume_6h = get_old_value(volume_data, idx=1)  # volume X часов назад

            if old_volume_6h is not None and old_volume_6h != 0:
                volume_increase_6h = ((latest_volume - old_volume_6h) / old_volume_6h) * 100
            else:
                volume_increase_6h = None

            # ---------------------------------------------------
            # 3) Расчёт объёмного роста за 1 час
            #    (тут нет fallback: нужен хотя бы 1 предыдущий час — data[1])
            # ---------------------------------------------------
            if len(volume_data) > 1:
                one_hour_volume = volume_data[1][1]
                if one_hour_volume and one_hour_volume != 0:
                    volume_increase_1h = ((latest_volume - one_hour_volume) / one_hour_volume) * 100
                else:
                    volume_increase_1h = None
            else:
                volume_increase_1h = None

            # ---------------------------------------------------
            # 4) Расчёт изменения цены за 6 часов (по тому же принципу fallback)
            # ---------------------------------------------------
            latest_price = volume_data[0][2]
            old_price_6h = get_old_value(volume_data, idx=2)

            if old_price_6h is not None and old_price_6h != 0:
                price_change_6h = ((latest_price - old_price_6h) / old_price_6h) * 100
            else:
                price_change_6h = None

            # ---------------------------------------------------
            # 5) Проверяем условия отбора:
            #    (A) 6h volume >= 50% ИЛИ 1h volume >= 50%
            #    И 6h price change <= 10% (по модулю)
            # ---------------------------------------------------
            #  -- Если не можем посчитать price_change_6h, считаем что монету пропускаем,
            #     т.к. неизвестна цена, нет смысла выводить (ведь "и при этом" часть невыполнима).
            #  -- Аналогично, если нет volume_increase_6h и нет volume_increase_1h,
            #     то тоже пропускаем.
            # ---------------------------------------------------
            if price_change_6h is None:
                continue  # нет цены 6 часов назад — пропускаем

            abs_price_change_6h = abs(price_change_6h)

            # Логика по объёму: нужно, чтобы хотя бы одно из значений >= 50
            condition_volume = False

            if volume_increase_6h is not None and volume_increase_6h >= 50:
                condition_volume = True
            if volume_increase_1h is not None and volume_increase_1h >= 50:
                condition_volume = True

            # Логика по цене: цена менялась не более чем на 10% за 6ч
            condition_price = (abs_price_change_6h <= 10)

            if condition_volume and condition_price:
                crypto_data_to_display.append({
                    "name": coin[1],
                    "symbol": coin[2],
                    "rank": coin[3],
                    "current_volume": format_volume(latest_volume),
                    "volume_increase_6h": volume_increase_6h if volume_increase_6h is not None else 0,
                    "volume_increase_1h": volume_increase_1h if volume_increase_1h is not None else 0,
                    "current_price": format_price(latest_price),
                    "price_change_6h": price_change_6h,
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
            invest = get_grok_invest(name, symbol)
            if "error" in invest:
                print("[index] Ошибка при получении данных об инвестициях:", invest["error"])
                return jsonify(invest), 400

            ai_invest = invest.get("content")
            print("[index] Полученный AI_invest:", ai_invest)

            cur.execute("""
                UPDATE cryptocurrencies SET AI_invest = %s WHERE name = %s AND symbol = %s
            """, (ai_invest, name, symbol))
            mysql.connection.commit()

            return jsonify({"content": ai_text})

        return render_template("index.html", crypto_data=crypto_data_to_display, time_difference=time_difference_global)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Ошибка: {e}"})


if __name__ == "__main__":
    # Включаем debug для более подробного вывода ошибок в консоль
    app.run(debug=True)