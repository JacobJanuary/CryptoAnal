import os
import traceback
from anthropic import Anthropic
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_caching import Cache
from flask_mysqldb import MySQL
import mysql.connector as mc  # <-- используем mysql.connector под псевдонимом mc

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Конфигурация MySQL для Flask-MySQLdb
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST", "localhost")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER", "root")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD", "password")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DATABASE", "crypto_db")

# Инициализируем MySQL от flask_mysqldb (если нужно в других местах)
mysql = MySQL(app)

# Настройка для mysql.connector
db_config = {
    'host': app.config['MYSQL_HOST'],
    'user': app.config['MYSQL_USER'],
    'password': app.config['MYSQL_PASSWORD'],
    'database': app.config['MYSQL_DB']
}


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
            model="grok-beta",
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
        # Для работы с Flask-MySQLdb
        cur = mysql.connection.cursor()

        # Если GET, то читаем сохраненные фильтры
        default_filters = {
            "vol_min": 10000,
            "growth6h": 100,
            "growth1h": 100,
            "price_change_max": 10,
            "price_change_min": 0,
            "market_cap_rank": 9999
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

        # Формируем запрос к процедуре
        query = "CALL cg_GetFilteredCoins(%s, %s, %s, %s, %s, %s)"
        params = (filters["vol_min"], filters["growth6h"], filters["growth1h"],
                  filters["price_change_max"], filters["price_change_min"], filters["market_cap_rank"])
        cur.execute(query, params)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        crypto_data = [dict(zip(col_names, row)) for row in rows]
        cur.close()

        # Дополнительная логика работы с coin_ids
        if crypto_data:
            coin_ids = [coin['coin_id'] for coin in crypto_data]
            if coin_ids:
                format_str = ','.join(['%s'] * len(coin_ids))
                # Снова используем Flask-MySQLdb
                cur = mysql.connection.cursor()
                cur.execute(f"""
                    SELECT ccr.coin_id, cc.name
                    FROM coin_category_relation ccr
                    JOIN CG_Categories cc ON ccr.category_id = cc.category_id
                    WHERE ccr.coin_id IN ({format_str})
                    ORDER BY cc.Weight ASC
                """, tuple(coin_ids))
                rows = cur.fetchall()

                from collections import defaultdict
                cat_map = defaultdict(list)
                for r in rows:
                    c_id = r[0]
                    cat_name = r[1]
                    cat_map[c_id].append(cat_name)

                for coin in crypto_data:
                    c_id = coin['coin_id']
                    categories_list = cat_map.get(c_id, [])
                    coin['categories_str'] = ", ".join(categories_list)

                # rev1 - Получение min_about
                cur = mysql.connection.cursor()
                query = f"""
                    SELECT
                      ccr.coin_id,
                      MIN(cc.about_what) AS min_about
                    FROM coin_category_relation ccr
                    JOIN CG_Categories cc ON ccr.category_id = cc.category_id
                    WHERE ccr.coin_id IN ({format_str})
                      AND cc.about_what <> 0
                    GROUP BY ccr.coin_id
                """
                cur.execute(query, tuple(coin_ids))
                rows = cur.fetchall()
                cur.close()

                about_map = {}
                for r in rows:
                    c_id = r[0]
                    min_about = r[1]
                    about_map[c_id] = min_about

                for coin in crypto_data:
                    c_id = coin['coin_id']
                    coin['min_about'] = about_map.get(c_id, 0)

        if request.method == "POST":
            # POST-запрос для аналитики
            name = request.form.get("name")
            symbol = request.form.get("symbol")
            if not name or not symbol:
                error_msg = "Не переданы name или symbol"
                print("[index] Ошибка:", error_msg)
                return jsonify({"error": error_msg}), 400

            # Проверяем, есть ли уже AI_text
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


@app.route("/save_filters", methods=["POST"])
def save_filters():
    try:
        data = request.get_json()
        vol_min = data.get("volMin")
        growth6h = data.get("growth6h")
        growth1h = data.get("growth1h")
        price_change_max = data.get("priceChangeMax")
        price_change_min = data.get("priceChangeMin")
        market_cap_rank = data.get("marketCapRank")

        cur = mysql.connection.cursor()
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

@app.template_filter('safe_round')
def safe_round(value, precision=2):
    if value is None:
        return "N/A"
    return round(value, precision)

@app.route("/favourites")
def favourites():
    """
    Отображает страницу с избранными монетами (isFavourites=1) с возможностью сортировки.
    Поддерживаемые поля для сортировки: name, market_cap_rank, price_change_percentage_24h.
    Порядок сортировки: asc, desc.
    """
    try:
        sort_by = request.args.get('sort_by', 'market_cap_rank')
        order = request.args.get('order', 'asc')

        valid_sort_fields = {
            'name': 'c.name',
            'market_cap_rank': 'c.market_cap_rank',
            'price_change_percentage_24h': 'c.price_change_percentage_24h'
        }

        if sort_by not in valid_sort_fields:
            sort_by = 'market_cap_rank'

        if order not in ['asc', 'desc']:
            order = 'asc'

        order_by_clause = f"ORDER BY {valid_sort_fields[sort_by]} {order.upper()}"

        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT c.id,
                   c.name,
                   c.symbol,
                   c.market_cap_rank,
                   c.current_price_usd,
                   c.price_change_percentage_24h,
                   (
                     SELECT cc.name
                     FROM coin_category_relation ccr
                     JOIN CG_Categories cc ON ccr.category_id = cc.category_id
                     WHERE ccr.coin_id = c.id
                     ORDER BY cc.Weight ASC
                     LIMIT 1
                   ) AS main_category
            FROM coin_gesco_coins c
            WHERE c.isFavourites = 1
            {order_by_clause}
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        opposite_order = 'desc' if order == 'asc' else 'asc'

        return render_template("favourites.html", coins=rows, current_sort=sort_by, current_order=order,
                               opposite_order=opposite_order)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/coin_details/<coin_id>", methods=["GET"])
def coin_details(coin_id):
    try:
        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        query_main = """
            SELECT 
                c.id AS coin_id,
                c.name,
                c.symbol,
                c.AI_text,
                c.AI_invest,
                c.market_cap_usd,
                c.market_cap_rank,
                c.ath_usd, c.ath_change_percentage_usd, c.ath_date_usd,
                c.atl_usd, c.atl_change_percentage_usd, c.atl_date_usd,
                c.total_volume_usd,
                c.current_price_usd,
                c.high_24h_usd,
                c.low_24h_usd,
                c.watchlist_portfolio_users
            FROM coin_gesco_coins c
            WHERE c.id = %s
        """
        cursor.execute(query_main, (coin_id,))
        coin = cursor.fetchone()
        if not coin:
            return jsonify({"error": "Монета не найдена"}), 404

        query_hist = """
            SELECT
                min_price_oct23_mar25,
                min_date_oct23_mar25,
                max_price_oct23_mar25,
                max_date_oct23_mar25,
                perc_change_max_to_current,
                volume_spikes,
                anomalous_buybacks
            FROM coin_history_new365
            WHERE coin_id = %s
        """
        cursor.execute(query_hist, (coin_id,))
        row_hist = cursor.fetchone()

        if row_hist:
            coin.update(row_hist)
            if coin['min_price_oct23_mar25'] and coin['current_price_usd']:
                perc_change_min_to_current = ((coin['current_price_usd'] - coin['min_price_oct23_mar25']) / coin['min_price_oct23_mar25']) * 100
                coin['perc_change_min_to_current'] = perc_change_min_to_current
            else:
                coin['perc_change_min_to_current'] = None
        else:
            coin['min_price_oct23_mar25'] = None
            coin['max_price_oct23_mar25'] = None
            coin['min_date_oct23_mar25'] = None
            coin['max_date_oct23_mar25'] = None
            coin['perc_change_max_to_current'] = None
            coin['volume_spikes'] = '[]'
            coin['anomalous_buybacks'] = '[]'
            coin['perc_change_min_to_current'] = None

        cursor.close()
        conn.close()

        return jsonify(coin)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/made_in_usa")
def made_in_usa():
    try:
        sort_by = request.args.get('sort_by', 'market_cap_rank')
        order = request.args.get('order', 'asc')

        valid_sort_fields = {
            'name': 'c.name',
            'market_cap_rank': 'c.market_cap_rank',
            'price_change_percentage_24h': 'c.price_change_percentage_24h',
            'market_cap': 'c.market_cap_usd',
            'volume_24h': 'c.total_volume_usd'
        }

        if sort_by not in valid_sort_fields:
            sort_by = 'market_cap_rank'
        if order not in ['asc', 'desc']:
            order = 'asc'

        order_by_clause = f"ORDER BY {valid_sort_fields[sort_by]} {order.upper()}"

        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT c.id,
                   c.name,
                   c.symbol,
                   c.market_cap_rank,
                   c.current_price_usd,
                   c.price_change_percentage_24h,
                   c.market_cap_usd,
                   c.total_volume_usd,
                   h.min_price_oct23_mar25,
                   h.max_price_oct23_mar25,
                   (
                     SELECT cc.name
                     FROM coin_category_relation ccr
                     JOIN CG_Categories cc ON ccr.category_id = cc.category_id
                     WHERE ccr.coin_id = c.id
                     ORDER BY cc.Weight ASC
                     LIMIT 1
                   ) AS main_category
            FROM coin_gesco_coins c
            JOIN coin_category_relation r ON c.id = r.coin_id
            LEFT JOIN coin_history_new365 h ON c.id = h.coin_id
            WHERE r.category_id = 'made-in-usa' AND c.market_cap_usd>=10000000 and c.total_volume_usd>=100000
            {order_by_clause}
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        total_count = len(rows)
        opposite_order = 'desc' if order == 'asc' else 'asc'

        return render_template(
            "made_in_usa.html",
            coins=rows,
            current_sort=sort_by,
            current_order=order,
            opposite_order=opposite_order,
            total_count=total_count
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.template_filter('safe_round')
def safe_round(value, precision=2):
    """
    Преобразует None в 0 или делает проверку
    """
    if value is None:
        return "N/A"  # или 0, или "N/A"
    try:
        return round(value, precision)
    except:
        return "N/A"

if __name__ == "__main__":
    app.run(debug=True)