import os
import traceback
from anthropic import Anthropic
from dotenv import load_dotenv
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

# Пользовательский фильтр для форматирования объема
@app.template_filter('format_volume')
def format_volume(value):
    if value:
        vol_str = f"${value / 1_000_000:.2f}".replace('.', ',')
        return f"{vol_str} млн"
    return "N/A"
@app.route("/", methods=["GET", "POST"])
def index():
    try:
        cur = mysql.connection.cursor()

        # Если GET, то читаем сохраненные фильтры и используем их,
        # если их нет, подставляем значения по умолчанию:
        default_filters = {
            "vol_min": 10000,
            "growth6h": 100,
            "growth1h": 100,
            "price_change_max": 10,
            "price_change_min": 0,
            "market_cap_rank": None
        }
        cur.execute("SELECT vol_min, growth6h, growth1h, price_change_max, price_change_min, market_cap_rank FROM filter_settings WHERE id = 1")
        row = cur.fetchone()
        if row:
            filters = {
                "vol_min": row[0],
                "growth6h": row[1],
                "growth1h": row[2],
                "price_change_max": row[3],
                "price_change_min": row[4],
                "market_cap_rank": row[5]
            }
        else:
            filters = default_filters

        # Формируем запрос к функции cg_GetFilteredCoins с нужными параметрами.
        query = "CALL cg_GetFilteredCoins(%s, %s, %s, %s, %s, %s)"
        params = (filters["vol_min"], filters["growth6h"], filters["growth1h"],
                  filters["price_change_max"], filters["price_change_min"], filters["market_cap_rank"])
        cur.execute(query, params)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        crypto_data = [dict(zip(col_names, row)) for row in rows]
        cur.close()

        # После того как получили crypto_data (массив словарей, содержащих coin_id и т.д.)
        if crypto_data:
            coin_ids = [coin['coin_id'] for coin in crypto_data]
            if coin_ids:
                format_str = ','.join(['%s'] * len(coin_ids))
                cur = mysql.connection.cursor()
                cur.execute(f"""
                    SELECT ccr.coin_id, cc.name
                    FROM coin_category_relation ccr
                    JOIN CG_Categories cc ON ccr.category_id = cc.category_id
                    WHERE ccr.coin_id IN ({format_str})
                    ORDER BY cc.Weight ASC
                """, tuple(coin_ids))
                rows = cur.fetchall()  # [(coin_id, category_name), ...]

                # Построим mapping coin_id -> [список категорий]
                from collections import defaultdict
                cat_map = defaultdict(list)
                for r in rows:
                    c_id = r[0]
                    cat_name = r[1]
                    cat_map[c_id].append(cat_name)

                # Для каждой монеты собираем строку категорий
                for coin in crypto_data:
                    c_id = coin['coin_id']
                    categories_list = cat_map.get(c_id, [])
                    # Сформируем строку "Cat1, Cat2, Cat3"
                    coin['categories_str'] = ", ".join(categories_list)

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


# Маршрут для сохранения настроек фильтров на сервере
@app.route("/save_filters", methods=["POST"])
def save_filters():
    try:
        data = request.get_json()
        # Получаем значения фильтров из входного JSON
        vol_min = data.get("volMin")
        growth6h = data.get("growth6h")
        growth1h = data.get("growth1h")
        price_change_max = data.get("priceChangeMax")
        price_change_min = data.get("priceChangeMin")
        market_cap_rank = data.get("marketCapRank")

        # Преобразуем значения к числовому типу и заменяем нули на None
        try:
            vol_min = float(vol_min) if vol_min is not None and float(vol_min) != 0 else None
        except:
            vol_min = None

        try:
            growth6h = float(growth6h) if growth6h is not None and float(growth6h) != 0 else None
        except:
            growth6h = None

        try:
            growth1h = float(growth1h) if growth1h is not None and float(growth1h) != 0 else None
        except:
            growth1h = None

        try:
            price_change_max = float(price_change_max) if price_change_max is not None and float(
                price_change_max) != 0 else None
        except:
            price_change_max = None

        try:
            price_change_min = float(price_change_min) if price_change_min is not None and float(
                price_change_min) != 0 else None
        except:
            price_change_min = None

        try:
            market_cap_rank = int(market_cap_rank) if market_cap_rank is not None and int(
                market_cap_rank) != 0 else None
        except:
            market_cap_rank = None

        cur = mysql.connection.cursor()
        # Если запись с id = 1 уже существует, обновляем её
        cur.execute("SELECT id FROM filter_settings WHERE id = 1")
        row = cur.fetchone()
        if row:
            query = """
                UPDATE filter_settings 
                SET vol_min=%s, growth6h=%s, growth1h=%s, price_change_max=%s, price_change_min=%s, market_cap_rank=%s
                WHERE id=1
            """
            cur.execute(query, (vol_min, growth6h, growth1h, price_change_max, price_change_min, market_cap_rank))
        else:
            query = """
                INSERT INTO filter_settings (id, vol_min, growth6h, growth1h, price_change_max, price_change_min, market_cap_rank)
                VALUES (1, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(query, (vol_min, growth6h, growth1h, price_change_max, price_change_min, market_cap_rank))
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
