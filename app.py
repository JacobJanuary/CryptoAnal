import os
import traceback
from anthropic import Anthropic
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_caching import Cache
from flask_mysqldb import MySQL
import mysql.connector as mc

# Импорты для работы с CMC API и управления портфелями
import json
import time
import requests
# Добавляем timedelta к импорту
from datetime import datetime, timedelta


app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")
# Получение ключа API для CoinMarketCap
CMC_API_KEY = os.getenv("CMC_API_KEY", "")

# MySQL configuration for Flask-MySQLdb
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST", "localhost")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER", "root")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD", "password")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DATABASE", "crypto_db")

# Initialize MySQL from flask_mysqldb
mysql = MySQL(app)

# Configuration for mysql.connector
db_config = {
    'host': app.config['MYSQL_HOST'],
    'user': app.config['MYSQL_USER'],
    'password': app.config['MYSQL_PASSWORD'],
    'database': app.config['MYSQL_DB']
}


def get_grok_analytics(name, symbol):
    if not XAI_API_KEY:
        error_msg = "API key not set. Set the XAI_API_KEY environment variable."
        print(error_msg)
        return {"error": error_msg}
    try:
        client = Anthropic(api_key=XAI_API_KEY, base_url="https://api.x.ai")
        prompt = (
            f"Give detailed information about the project {name} ({symbol}). "
            f"What does it do, when was it created, who is on the team, what are the prospects, "
            f"development, social activity. Did smart money invest in the project, "
            f"what are your token price forecasts for 2025."
        )
        print(f"[get_grok_analytics] Prompt:\n{prompt}")
        response = client.messages.create(
            model="grok-beta",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        print("[get_grok_analytics] Full API response:", response)
        if response and isinstance(response.content[0].text, str):
            print("[get_grok_analytics] Response content:", response.content[0].text)
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
        error_msg = "API key not set. Set the XAI_API_KEY environment variable."
        print(error_msg)
        return {"error": error_msg}
    try:
        client = Anthropic(api_key=XAI_API_KEY, base_url="https://api.x.ai")
        prompt = f"Find information about which funds or Smart money invested in the project {name} ({symbol})."
        print(f"[get_grok_invest] Prompt:\n{prompt}")
        response = client.messages.create(
            model="grok-beta",
            max_tokens=128000,
            messages=[{"role": "user", "content": prompt}]
        )
        print("[get_grok_invest] Full API response:", response)
        if response and isinstance(response.content[0].text, str):
            print("[get_grok_invest] Response content:", response.content[0].text)
            return {"content": response.content[0].text}
        else:
            error_msg = "Unexpected response from API"
            print("[get_grok_invest]", error_msg)
            return {"error": error_msg}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# Custom filter for formatting volume
@app.template_filter('format_volume')
def format_volume(value):
    if value:
        vol_str = f"${value / 1_000_000:.2f}".replace('.', ',')
        return f"{vol_str} mln"
    return "N/A"


@app.template_filter('safe_round')
def safe_round(value, precision=2):
    if value is None:
        return "N/A"
    try:
        return round(float(value), precision)
    except:
        return "N/A"


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        # Default to "Made in America" category
        category_id = request.args.get('category', '678ded1251eda549b5afd3fe')

        # Get sort parameters from request
        sort_by = request.args.get('sort_by', 'market_cap_rank')
        order = request.args.get('order', 'asc')

        # Get filter parameter
        is_filtered = request.args.get('filtered') == 'true'

        # Get all categories with isTop=1
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name FROM categories WHERE isTop = 1 ORDER BY name")
        top_categories = [dict(zip(['id', 'name'], row)) for row in cur.fetchall()]

        # Validate sort parameters
        valid_sort_fields = {
            'name': 'c.name',
            'market_cap_rank': 'c.cmc_rank',
            'price_change_percentage_24h': 'c.percent_change_24h',
            'market_cap': 'c.market_cap',
            'volume_24h': 'c.volume_24h',
            'big_volume_rank': '(c.high_volume_days / c.total_days * 100)'  # Добавляем новый параметр сортировки
        }

        if sort_by not in valid_sort_fields:
            sort_by = 'market_cap_rank'

        if order not in ['asc', 'desc']:
            order = 'asc'

        # Create ORDER BY clause
        order_by_clause = f"ORDER BY {valid_sort_fields[sort_by]} {order.upper()}"

        # Handle POST request for AI analytics
        if request.method == "POST":
            name = request.form.get("name")
            symbol = request.form.get("symbol")
            if not name or not symbol:
                error_msg = "Name or symbol not provided"
                print("[index] Error:", error_msg)
                return jsonify({"error": error_msg}), 400

            # Check if we already have AI text
            cur = mysql.connection.cursor()
            cur.execute("SELECT grok2_text FROM cmc_crypto WHERE name = %s AND symbol = %s", (name, symbol))
            row = cur.fetchone()
            if row and row[0]:
                print("[index] AI_text already exists in DB, returning saved text.")
                return jsonify({"content": row[0]})

            # Get AI analytics
            analytics = get_grok_analytics(name, symbol)
            if "error" in analytics:
                print("[index] Error getting analytics:", analytics["error"])
                return jsonify(analytics), 400

            ai_text = analytics.get("content")
            print("[index] Received AI_text:", ai_text)

            # Save AI analytics
            cur.execute("UPDATE cmc_crypto SET grok2_text = %s WHERE name = %s AND symbol = %s",
                        (ai_text, name, symbol))
            mysql.connection.commit()

            # Get investment data
            invest = get_grok_invest(name, symbol)
            if "error" in invest:
                print("[index] Error getting investment data:", invest["error"])
                return jsonify(invest), 400

            ai_invest = invest.get("content")
            print("[index] Received AI_invest:", ai_invest)

            # Save investment data
            cur.execute("UPDATE cmc_crypto SET grok2_invest = %s WHERE name = %s AND symbol = %s",
                        (ai_invest, name, symbol))
            mysql.connection.commit()
            cur.close()

            return jsonify({"content": ai_text})

        # Get coins from selected category with sorting
        base_query = """
            SELECT 
                c.id as coin_id,
                c.name,
                c.symbol,
                c.cmc_rank as market_cap_rank,
                c.market_cap,
                c.volume_24h as total_volume_usd,
                c.percent_change_24h as price_change_percentage_24h,
                c.price_usd as current_price_usd,
                c.min_365d_price,
                c.max_365d_price,
                c.high_volume_days,
                c.total_days,
                (SELECT COUNT(*) > 0 FROM cmc_favorites WHERE coin_id = c.id) as isFavourites,
                (
                    SELECT cat.name
                    FROM cmc_category_relations ccr
                    JOIN categories cat ON ccr.category_id = cat.id
                    WHERE ccr.coin_id = c.id
                    ORDER BY cat.isTop DESC
                    LIMIT 1
                ) AS main_category
            FROM cmc_crypto c
            JOIN cmc_category_relations r ON c.id = r.coin_id
            WHERE r.category_id = %s
        """

        # Apply filters if requested
        if is_filtered:
            filter_conditions = " AND c.market_cap >= 10000000 AND c.volume_24h >= 100000"
            query = base_query + filter_conditions + f" {order_by_clause}"
        else:
            query = base_query + f" {order_by_clause}"

        # Execute query
        cur.execute(query, (category_id,))
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        crypto_data = [dict(zip(col_names, row)) for row in rows]

        # Get category details
        cur.execute("SELECT name FROM categories WHERE id = %s", (category_id,))
        category_name_row = cur.fetchone()
        category_name = category_name_row[0] if category_name_row else "Made in America"

        # Get additional category info for each coin
        if crypto_data:
            coin_ids = [coin['coin_id'] for coin in crypto_data]
            if coin_ids:
                format_str = ','.join(['%s'] * len(coin_ids))
                cur.execute(f"""
                    SELECT ccr.coin_id, c.name
                    FROM cmc_category_relations ccr
                    JOIN categories c ON ccr.category_id = c.id
                    WHERE ccr.coin_id IN ({format_str})
                    ORDER BY c.isTop DESC
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

        cur.close()

        # Render template with all required data
        return render_template("cmc.html",
                               crypto_data=crypto_data,
                               top_categories=top_categories,
                               current_category_id=category_id,
                               current_category_name=category_name,
                               current_sort=sort_by,
                               current_order=order,
                               is_filtered=is_filtered,
                               opposite_order='desc' if order == 'asc' else 'asc')

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error: {e}"}), 500


@app.route("/toggle_favourite", methods=["POST"])
def toggle_favourite():
    try:
        data = request.get_json()
        print("Received data:", data)  # Debug output

        coin_id = data.get("id")
        new_val = data.get("isFavourites")  # True or False

        print(f"Toggling favorite: coin_id={coin_id}, new_val={new_val}, type={type(new_val)}")  # Debug output

        if coin_id is None or new_val is None:
            return jsonify({"error": "Required data not provided"}), 400

        # Ensure new_val is boolean
        if isinstance(new_val, str):
            new_val = new_val.lower() == 'true'
        elif isinstance(new_val, int):
            new_val = bool(new_val)

        print(f"After type conversion: new_val={new_val}, type={type(new_val)}")  # Debug output

        cur = mysql.connection.cursor()

        # First check if the favorite table exists
        try:
            cur.execute("SHOW TABLES LIKE 'cmc_favorites'")
            table_exists = cur.fetchone() is not None
            print(f"Table cmc_favorites exists: {table_exists}")  # Debug output

            if not table_exists:
                print("Creating table cmc_favorites")  # Debug output
                cur.execute("""
                    CREATE TABLE cmc_favorites (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        coin_id BIGINT NOT NULL,
                        UNIQUE KEY (coin_id)
                    )
                """)
                mysql.connection.commit()
        except Exception as table_error:
            print(f"Error checking/creating table: {table_error}")

        # Now handle the favorite action
        if new_val:
            # Check if record already exists before inserting
            cur.execute("SELECT id FROM cmc_favorites WHERE coin_id = %s", (coin_id,))
            exists = cur.fetchone() is not None

            if not exists:
                print(f"Adding coin {coin_id} to favorites")  # Debug output
                cur.execute("INSERT INTO cmc_favorites (coin_id) VALUES (%s)", (coin_id,))
            else:
                print(f"Coin {coin_id} already in favorites - nothing to do")  # Debug output
        else:
            print(f"Removing coin {coin_id} from favorites")  # Debug output
            cur.execute("DELETE FROM cmc_favorites WHERE coin_id = %s", (coin_id,))

        mysql.connection.commit()
        cur.close()

        print("Operation completed successfully")  # Debug output
        return jsonify({"success": True, "action": "added" if new_val else "removed"})
    except Exception as e:
        traceback.print_exc()
        print(f"Error in toggle_favourite: {str(e)}")  # Debug output
        return jsonify({"error": str(e)}), 500


# В файле app.py функция favourites нужно модифицировать запрос,
# чтобы он также получал категории для каждой монеты.
# Найдите функцию favourites и обновите запрос:

@app.route("/cmc_favourites")
def favourites():
    """
    Display page with favorite coins (from cmc_favorites table) with sorting options.
    """
    try:
        sort_by = request.args.get('sort_by', 'market_cap_rank')
        order = request.args.get('order', 'asc')

        valid_sort_fields = {
            'name': 'c.name',
            'market_cap_rank': 'c.cmc_rank',
            'price_change_percentage_24h': 'c.percent_change_24h',
            'market_cap': 'c.market_cap',
            'volume_24h': 'c.volume_24h',
            'big_volume_rank': '(c.high_volume_days / c.total_days * 100)',
            'percent_change_1h': 'c.percent_change_1h',
            'percent_change_7d': 'c.percent_change_7d',
            'percent_change_30d': 'c.percent_change_30d',
            'percent_change_60d': 'c.percent_change_60d',
            'percent_change_90d': 'c.percent_change_90d'
        }

        if sort_by not in valid_sort_fields:
            sort_by = 'market_cap_rank'

        if order not in ['asc', 'desc']:
            order = 'asc'

        order_by_clause = f"ORDER BY {valid_sort_fields[sort_by]} {order.upper()}"

        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Получаем список категорий с isTop=1
        categories_query = """
            SELECT id, name FROM categories 
            WHERE isTop = 1 
            ORDER BY name
        """
        cursor.execute(categories_query)
        top_categories = cursor.fetchall()

        # Для каждой категории считаем количество избранных монет
        for category in top_categories:
            count_query = """
                SELECT COUNT(DISTINCT f.coin_id) as count
                FROM cmc_favorites f
                JOIN cmc_category_relations cr ON f.coin_id = cr.coin_id
                WHERE cr.category_id = %s
            """
            cursor.execute(count_query, (category['id'],))
            count_result = cursor.fetchone()
            category['coins_count'] = count_result['count'] if count_result else 0

        # Основной запрос для получения избранных монет
        query = f"""
            SELECT c.id,
                   c.name,
                   c.symbol,
                   c.cmc_rank AS market_cap_rank,
                   c.price_usd AS current_price_usd,
                   c.percent_change_24h AS price_change_percentage_24h,
                   c.percent_change_1h,
                   c.percent_change_7d,
                   c.percent_change_30d,
                   c.percent_change_60d,
                   c.percent_change_90d,
                   c.market_cap,
                   c.volume_24h AS total_volume_usd,
                   c.high_volume_days,
                   c.total_days,
                   c.rull_run_x, 
                   c.grade,
                   (
                     SELECT cat.name
                     FROM cmc_category_relations ccr
                     JOIN categories cat ON ccr.category_id = cat.id
                     WHERE ccr.coin_id = c.id
                     ORDER BY cat.isTop DESC
                     LIMIT 1
                   ) AS main_category
            FROM cmc_crypto c
            JOIN cmc_favorites f ON c.id = f.coin_id
            {order_by_clause}
        """
        cursor.execute(query)
        coins = cursor.fetchall()

        # Получаем категории для каждой монеты
        if coins:
            coin_ids = [coin['id'] for coin in coins]
            if coin_ids:
                format_str = ','.join(['%s'] * len(coin_ids))
                cursor.execute(f"""
                    SELECT ccr.coin_id, c.id as category_id, c.name
                    FROM cmc_category_relations ccr
                    JOIN categories c ON ccr.category_id = c.id
                    WHERE ccr.coin_id IN ({format_str})
                    ORDER BY c.isTop DESC
                """, tuple(coin_ids))
                rows = cursor.fetchall()

                from collections import defaultdict
                cat_map = defaultdict(list)
                cat_id_map = defaultdict(list)

                for r in rows:
                    c_id = r['coin_id']
                    cat_id = r['category_id']
                    cat_name = r['name']
                    cat_map[c_id].append(cat_name)
                    cat_id_map[c_id].append(str(cat_id))

                for coin in coins:
                    c_id = coin['id']
                    coin['categories_str'] = ", ".join(cat_map.get(c_id, []))
                    coin['category_ids'] = ",".join(cat_id_map.get(c_id, []))

        cursor.close()
        conn.close()

        # Определяем opposite_order для сортировки
        opposite_order = 'desc' if order == 'asc' else 'asc'

        # Передаем все необходимые переменные в шаблон
        return render_template("cmc_favourites.html",
                               coins=coins,  # Определяем переменную coins
                               current_sort=sort_by,
                               current_order=order,
                               opposite_order=opposite_order,  # Определяем переменную opposite_order
                               top_categories=top_categories)

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
                c.project_review, 
                c.top5_good, 
                c.top5_bad, 
                c.social_metrics, 
                c.bullrun_roi, 
                c.project_final_recomend,
                c.rull_run_x, 
                c.grade,
                c.market_cap,
                c.cmc_rank AS market_cap_rank,
                c.ath_usd, c.atl_usd,
                c.volume_24h AS total_volume_usd,
                c.price_usd AS current_price_usd,
                c.high_volume_days,
                c.total_days,
                c.min_365d_price,
                c.min_365d_date,
                c.max_365d_price,
                c.max_365d_date,
                c.percent_change_1h,
                c.percent_change_24h AS price_change_percentage_24h,
                c.percent_change_7d,
                c.percent_change_30d,
                c.percent_change_60d,
                c.percent_change_90d,
                c.date_added,
                c.circulating_supply,
                c.total_supply
            FROM cmc_crypto c
            WHERE c.id = %s
        """
        cursor.execute(query_main, (coin_id,))
        coin = cursor.fetchone()
        if not coin:
            return jsonify({"error": "Coin not found"}), 404

        # Calculate percentage from min to current and max to current
        if coin['min_365d_price'] and coin['current_price_usd']:
            coin['perc_change_min_to_current'] = ((coin['current_price_usd'] / coin['min_365d_price']) - 1) * 100
        else:
            coin['perc_change_min_to_current'] = None

        if coin['max_365d_price'] and coin['current_price_usd']:
            coin['perc_change_max_to_current'] = ((coin['current_price_usd'] / coin['max_365d_price']) - 1) * 100
        else:
            coin['perc_change_max_to_current'] = None

        cursor.close()
        conn.close()

        return jsonify(coin)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/update_prices", methods=["POST"])
def update_prices():
    try:
        # Получаем идентификаторы монет из избранного
        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Запрос для получения id и символов всех избранных монет
        query = """
            SELECT c.id, c.symbol
            FROM cmc_crypto c
            JOIN cmc_favorites f ON c.id = f.coin_id
        """
        cursor.execute(query)
        favorites = cursor.fetchall()

        if not favorites:
            return jsonify({"error": "Нет избранных монет"}), 400

        # Подготовка параметров для запроса к CoinMarketCap API
        symbols = ','.join([coin['symbol'] for coin in favorites])

        if not CMC_API_KEY:
            return jsonify({"error": "API ключ CoinMarketCap не настроен"}), 400

        # Запрос к API CoinMarketCap
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': symbols,
            'convert': 'USD'
        }
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': CMC_API_KEY,
        }

        response = requests.get(url, headers=headers, params=parameters)
        data = response.json()

        if 'status' not in data or data['status']['error_code'] != 0:
            error_msg = data.get('status', {}).get('error_message', 'Unknown error')
            return jsonify({"error": f"Ошибка API CoinMarketCap: {error_msg}"}), 400

        # Обновление цен в базе данных
        update_count = 0
        for coin in favorites:
            symbol = coin['symbol']
            if symbol in data['data']:
                coin_data = data['data'][symbol]
                price = coin_data['quote']['USD']['price']

                # Обновляем цену в базе данных
                update_query = """
                    UPDATE cmc_crypto
                    SET price_usd = %s, 
                        last_updated = NOW()
                    WHERE id = %s
                """
                cursor.execute(update_query, (price, coin['id']))
                update_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Обновлены цены для {update_count} монет",
            "updated_coins": update_count
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/get_portfolios", methods=["GET"])
def get_portfolios():
    try:
        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        query = "SELECT id, name, description FROM investment_portfolios ORDER BY id"
        cursor.execute(query)
        portfolios = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({"portfolios": portfolios})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/add_portfolio", methods=["POST"])
def add_portfolio():
    try:
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')

        if not name:
            return jsonify({"error": "Имя портфеля обязательно"}), 400

        conn = mc.connect(**db_config)
        cursor = conn.cursor()

        query = "INSERT INTO investment_portfolios (name, description) VALUES (%s, %s)"
        cursor.execute(query, (name, description))

        portfolio_id = cursor.lastrowid

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "portfolio_id": portfolio_id,
            "name": name
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/save_purchases", methods=["POST"])
def save_purchases():
    try:
        data = request.get_json()
        portfolio_id = data.get('portfolio_id')
        purchases = data.get('purchases', [])

        if not portfolio_id:
            return jsonify({"error": "ID портфеля обязателен"}), 400

        if not purchases:
            return jsonify({"error": "Нет данных о покупках"}), 400

        conn = mc.connect(**db_config)
        cursor = conn.cursor()

        # Подготовка запроса для множественной вставки
        query = """
            INSERT INTO purchase_transactions 
            (portfolio_id, coin_id, coin_symbol, coin_name, quantity, price_usd, total_amount, purchase_date) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = []
        for purchase in purchases:
            coin_id = purchase.get('coin_id')
            coin_symbol = purchase.get('coin_symbol')
            coin_name = purchase.get('coin_name')
            quantity = purchase.get('quantity')
            price_usd = purchase.get('price_usd')
            purchase_date = purchase.get('purchase_date')

            # Расчет общей суммы
            total_amount = float(quantity) * float(price_usd)

            values.append((
                portfolio_id,
                coin_id,
                coin_symbol,
                coin_name,
                quantity,
                price_usd,
                total_amount,
                purchase_date
            ))

        cursor.executemany(query, values)
        conn.commit()

        transaction_count = cursor.rowcount
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Сохранено {transaction_count} транзакций"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Добавить следующие маршруты в app.py

@app.route("/get_all_tokens", methods=["GET"])
def get_all_tokens():
    """
    Возвращает список всех доступных токенов для выбора.
    """
    try:
        search_term = request.args.get('search', '')

        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Запрос для получения токенов с фильтрацией по поисковому запросу (если указан)
        query = """
            SELECT id, name, symbol, cmc_rank, price_usd, volume_24h
            FROM cmc_crypto
            WHERE (name LIKE %s OR symbol LIKE %s)
            ORDER BY cmc_rank
            LIMIT 100
        """

        search_pattern = f"%{search_term}%" if search_term else "%"
        cursor.execute(query, (search_pattern, search_pattern))

        tokens = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({"tokens": tokens})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/add_to_favourites", methods=["POST"])
def add_to_favourites():
    """
    Добавляет выбранные токены в избранное.
    """
    try:
        data = request.get_json()
        token_ids = data.get('token_ids', [])

        if not token_ids:
            return jsonify({"error": "Не указаны токены для добавления"}), 400

        conn = mc.connect(**db_config)
        cursor = conn.cursor()

        # Проверка существования таблицы избранного
        cursor.execute("SHOW TABLES LIKE 'cmc_favorites'")
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            cursor.execute("""
                CREATE TABLE cmc_favorites (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    coin_id BIGINT NOT NULL,
                    UNIQUE KEY (coin_id)
                )
            """)
            conn.commit()

        # Вставка токенов в избранное
        added_count = 0
        for token_id in token_ids:
            try:
                # Проверяем, существует ли уже запись
                cursor.execute("SELECT id FROM cmc_favorites WHERE coin_id = %s", (token_id,))
                if cursor.fetchone() is None:
                    cursor.execute("INSERT INTO cmc_favorites (coin_id) VALUES (%s)", (token_id,))
                    added_count += 1
            except Exception as insert_error:
                print(f"Error adding token {token_id}: {insert_error}")

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Добавлено {added_count} токенов в избранное"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Добавьте эти маршруты в ваш файл app.py

# Страница со списком всех портфелей
@app.route("/portfolios")
def portfolios_list():
    """
    Отображает страницу со списком всех портфелей пользователя.
    """
    try:
        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Запрос для получения списка портфелей
        query = """
            SELECT 
                p.id, 
                p.name, 
                p.description,
                COUNT(DISTINCT pt.coin_id) as coins_count,
                SUM(pt.total_amount) as total_invested,
                p.created_at
            FROM investment_portfolios p
            LEFT JOIN purchase_transactions pt ON p.id = pt.portfolio_id
            GROUP BY p.id
            ORDER BY p.name
        """
        cursor.execute(query)
        portfolios = cursor.fetchall()

        # Для каждого портфеля получаем текущую стоимость
        for portfolio in portfolios:
            if portfolio['coins_count'] > 0:
                # Запрос для получения текущей стоимости портфеля
                current_value_query = """
                    SELECT 
                        SUM(pt.quantity * c.price_usd) as current_value
                    FROM purchase_transactions pt
                    JOIN cmc_crypto c ON pt.coin_id = c.id
                    WHERE pt.portfolio_id = %s
                """
                cursor.execute(current_value_query, (portfolio['id'],))
                result = cursor.fetchone()
                portfolio['current_value'] = result['current_value'] if result and result['current_value'] else 0

                # Расчет прибыли/убытка
                if portfolio['total_invested'] and portfolio['current_value']:
                    portfolio['profit_loss'] = portfolio['current_value'] - portfolio['total_invested']
                    portfolio['profit_loss_percent'] = (portfolio['profit_loss'] / portfolio['total_invested']) * 100
                else:
                    portfolio['profit_loss'] = 0
                    portfolio['profit_loss_percent'] = 0
            else:
                portfolio['current_value'] = 0
                portfolio['profit_loss'] = 0
                portfolio['profit_loss_percent'] = 0

        cursor.close()
        conn.close()

        return render_template("portfolios_list.html", portfolios=portfolios)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/portfolio/<int:portfolio_id>")
def portfolio_detail(portfolio_id):
    """
    Отображает детальную страницу конкретного портфеля.
    """
    try:
        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Получаем информацию о портфеле
        portfolio_query = """
            SELECT id, name, description, created_at
            FROM investment_portfolios
            WHERE id = %s
        """
        cursor.execute(portfolio_query, (portfolio_id,))
        portfolio = cursor.fetchone()

        if not portfolio:
            return jsonify({"error": "Портфель не найден"}), 404

        # Получаем все транзакции по портфелю, сгруппированные по монетам
        transactions_query = """
            SELECT 
                pt.coin_id,
                pt.coin_name,
                pt.coin_symbol,
                c.price_usd as current_price,
                SUM(pt.quantity) as total_quantity,
                SUM(pt.total_amount) as total_invested,
                AVG(pt.price_usd) as avg_buy_price,
                MAX(pt.purchase_date) as last_purchase_date,
                COUNT(pt.id) as transactions_count
            FROM purchase_transactions pt
            LEFT JOIN cmc_crypto c ON pt.coin_id = c.id
            WHERE pt.portfolio_id = %s
            GROUP BY pt.coin_id, pt.coin_symbol, pt.coin_name
            ORDER BY total_invested DESC
        """
        cursor.execute(transactions_query, (portfolio_id,))
        assets = cursor.fetchall()

        # Рассчитываем текущую стоимость и прибыль/убыток для каждой монеты
        total_current_value = 0
        total_invested = 0

        for asset in assets:
            if asset['current_price'] and asset['total_quantity']:
                asset['current_value'] = asset['current_price'] * asset['total_quantity']
                asset['profit_loss'] = asset['current_value'] - asset['total_invested']
                asset['profit_loss_percent'] = (asset['profit_loss'] / asset['total_invested']) * 100 if asset[
                    'total_invested'] else 0

                total_current_value += asset['current_value']
                total_invested += asset['total_invested']
            else:
                asset['current_value'] = 0
                asset['profit_loss'] = 0
                asset['profit_loss_percent'] = 0

        # Получаем полную историю транзакций для этого портфеля
        history_query = """
            SELECT 
                pt.id,
                pt.coin_id, 
                pt.coin_name, 
                pt.coin_symbol, 
                pt.quantity, 
                pt.price_usd, 
                pt.total_amount, 
                pt.purchase_date
            FROM purchase_transactions pt
            WHERE pt.portfolio_id = %s
            ORDER BY pt.purchase_date DESC
        """
        cursor.execute(history_query, (portfolio_id,))
        transaction_history = cursor.fetchall()

        # Общая статистика портфеля
        portfolio_stats = {
            'total_invested': total_invested,
            'current_value': total_current_value,
            'profit_loss': total_current_value - total_invested,
            'profit_loss_percent': (
                        (total_current_value - total_invested) / total_invested * 100) if total_invested else 0,
            'assets_count': len(assets),
            'transactions_count': len(transaction_history)
        }

        cursor.close()
        conn.close()

        return render_template(
            "portfolio_detail.html",
            portfolio=portfolio,
            assets=assets,
            transaction_history=transaction_history,
            stats=portfolio_stats
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio/<int:portfolio_id>/performance")
def portfolio_performance(portfolio_id):
    """
    API-маршрут для получения исторических данных о производительности портфеля.
    Используется для построения графиков.
    """
    try:
        # Получаем период из параметров запроса (7d, 30d, 90d, all)
        period = request.args.get('period', 'all')

        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Запрос для получения истории транзакций портфеля
        query = """
            SELECT 
                pt.purchase_date,
                pt.coin_id,
                pt.quantity,
                pt.price_usd,
                pt.total_amount
            FROM purchase_transactions pt
            WHERE pt.portfolio_id = %s
            ORDER BY pt.purchase_date
        """
        cursor.execute(query, (portfolio_id,))
        transactions = cursor.fetchall()

        # Получение исторических цен для монет в портфеле (в реальном проекте здесь должен быть
        # запрос к базе данных с историческими ценами, но для простоты примера используем текущие цены)
        coin_ids = list(set(t['coin_id'] for t in transactions))

        if coin_ids:
            format_str = ','.join(['%s'] * len(coin_ids))
            price_query = f"""
                SELECT id, price_usd
                FROM cmc_crypto
                WHERE id IN ({format_str})
            """
            cursor.execute(price_query, tuple(coin_ids))
            current_prices = {row['id']: row['price_usd'] for row in cursor.fetchall()}
        else:
            current_prices = {}

        cursor.close()
        conn.close()

        # Создаем временную шкалу в зависимости от выбранного периода
        now = datetime.now()
        if period == '7d':
            start_date = now - timedelta(days=7)
        elif period == '30d':
            start_date = now - timedelta(days=30)
        elif period == '90d':
            start_date = now - timedelta(days=90)
        else:  # 'all'
            start_date = min([t['purchase_date'] for t in transactions]) if transactions else now - timedelta(days=30)

        # Создаем массив дат для графика
        date_range = []
        current_date = start_date
        while current_date <= now:
            date_range.append(current_date)
            current_date += timedelta(days=1)

        # Расчет портфельных значений для каждой даты
        performance_data = []

        for date in date_range:
            # Фильтруем транзакции до текущей даты
            relevant_transactions = [t for t in transactions if t['purchase_date'].date() <= date.date()]

            # Группируем транзакции по монетам для расчета общего количества каждой монеты
            coin_quantities = {}
            invested_value = 0

            for t in relevant_transactions:
                coin_id = t['coin_id']
                if coin_id not in coin_quantities:
                    coin_quantities[coin_id] = 0
                coin_quantities[coin_id] += t['quantity']
                invested_value += t['total_amount']

            # Рассчитываем стоимость портфеля на дату
            portfolio_value = sum(
                coin_quantities.get(coin_id, 0) * current_prices.get(coin_id, 0)
                for coin_id in coin_quantities
            )

            performance_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'value': portfolio_value,
                'invested': invested_value
            })

        return jsonify({
            'performance': performance_data
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio/<int:portfolio_id>/composition")
def portfolio_composition(portfolio_id):
    """
    API-маршрут для получения данных о составе портфеля.
    Используется для построения круговой диаграммы.
    """
    try:
        # Добавим отладочный вывод
        print(f"Запрос состава портфеля {portfolio_id}")

        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Проверим, есть ли транзакции для этого портфеля
        check_query = "SELECT COUNT(*) as count FROM purchase_transactions WHERE portfolio_id = %s"
        cursor.execute(check_query, (portfolio_id,))
        count_result = cursor.fetchone()

        if not count_result or count_result['count'] == 0:
            print(f"Портфель {portfolio_id} не содержит транзакций")
            return jsonify({"composition": []})

        # Запрос для получения состава портфеля - исправленная версия
        query = """
            SELECT 
                pt.coin_id,
                ANY_VALUE(pt.coin_name) as coin_name,
                pt.coin_symbol,
                ANY_VALUE(c.price_usd) as current_price,
                SUM(pt.quantity) as total_quantity,
                SUM(pt.total_amount) as total_invested
            FROM purchase_transactions pt
            LEFT JOIN cmc_crypto c ON pt.coin_id = c.id
            WHERE pt.portfolio_id = %s
            GROUP BY pt.coin_id, pt.coin_symbol
            ORDER BY total_invested DESC
        """
        cursor.execute(query, (portfolio_id,))
        assets = cursor.fetchall()

        print(f"Найдено активов: {len(assets)}")

        # Расчет текущей стоимости для каждого актива
        composition_data = []
        for asset in assets:
            print(f"Обработка актива: {asset['coin_symbol']} ({asset['coin_id']})")
            print(f"  - Текущая цена: {asset['current_price']}")
            print(f"  - Количество: {asset['total_quantity']}")

            if asset['current_price'] is not None and asset['total_quantity'] is not None:
                current_value = float(asset['current_price']) * float(asset['total_quantity'])
                print(f"  - Текущая стоимость: ${current_value}")

                composition_data.append({
                    'name': asset['coin_symbol'],
                    'full_name': asset['coin_name'],
                    'value': current_value
                })
            else:
                if asset['current_price'] is None:
                    print(f"  - ОШИБКА: Нет текущей цены для монеты {asset['coin_symbol']}")
                if asset['total_quantity'] is None:
                    print(f"  - ОШИБКА: Нет количества для монеты {asset['coin_symbol']}")

        cursor.close()
        conn.close()

        print(f"Отправка данных о составе портфеля: {composition_data}")
        return jsonify({"composition": composition_data})

    except Exception as e:
        traceback.print_exc()
        print(f"Ошибка в получении состава портфеля: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio/<int:portfolio_id>/update_prices", methods=["POST"])
def update_portfolio_prices(portfolio_id):
    """
    API-маршрут для обновления цен всех монет в портфеле.
    """
    try:
        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Получаем все уникальные монеты в портфеле
        query = """
            SELECT DISTINCT coin_id, coin_symbol
            FROM purchase_transactions
            WHERE portfolio_id = %s
        """
        cursor.execute(query, (portfolio_id,))
        portfolio_coins = cursor.fetchall()

        if not portfolio_coins:
            return jsonify({"error": "В портфеле нет монет"}), 400

        # Подготовка параметров для запроса к CoinMarketCap API
        symbols = ','.join([coin['coin_symbol'] for coin in portfolio_coins])

        if not CMC_API_KEY:
            return jsonify({"error": "API ключ CoinMarketCap не настроен"}), 400

        # Запрос к API CoinMarketCap
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': symbols,
            'convert': 'USD'
        }
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': CMC_API_KEY,
        }

        response = requests.get(url, headers=headers, params=parameters)
        data = response.json()

        if 'status' not in data or data['status']['error_code'] != 0:
            error_msg = data.get('status', {}).get('error_message', 'Unknown error')
            return jsonify({"error": f"Ошибка API CoinMarketCap: {error_msg}"}), 400

        # Обновление цен в базе данных
        update_count = 0
        for coin in portfolio_coins:
            symbol = coin['coin_symbol']
            if symbol in data['data']:
                coin_data = data['data'][symbol]
                price = coin_data['quote']['USD']['price']

                # Обновляем цену в базе данных
                update_query = """
                    UPDATE cmc_crypto
                    SET price_usd = %s, 
                        last_updated = NOW()
                    WHERE id = %s
                """
                cursor.execute(update_query, (price, coin['coin_id']))
                update_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Обновлены цены для {update_count} монет",
            "updated_coins": update_count
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio/<int:portfolio_id>/delete_transaction", methods=["POST"])
def delete_transaction(portfolio_id):
    """
    API-маршрут для удаления транзакции.
    """
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')

        if not transaction_id:
            return jsonify({"error": "ID транзакции не указан"}), 400

        conn = mc.connect(**db_config)
        cursor = conn.cursor()

        # Проверяем, существует ли транзакция и принадлежит ли она указанному портфелю
        check_query = """
            SELECT id FROM purchase_transactions
            WHERE id = %s AND portfolio_id = %s
        """
        cursor.execute(check_query, (transaction_id, portfolio_id))
        exists = cursor.fetchone() is not None

        if not exists:
            cursor.close()
            conn.close()
            return jsonify({"error": "Транзакция не найдена или не принадлежит указанному портфелю"}), 404

        # Удаляем транзакцию
        delete_query = """
            DELETE FROM purchase_transactions
            WHERE id = %s
        """
        cursor.execute(delete_query, (transaction_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Транзакция успешно удалена"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/update_favourite_tokens", methods=["POST"])
def update_favourite_tokens():
    try:
        # Получаем список всех монет из избранного
        conn = mc.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Запрос для получения символов всех избранных монет
        query = """
            SELECT c.symbol 
            FROM cmc_crypto c
            JOIN cmc_favorites f ON c.id = f.coin_id
        """
        cursor.execute(query)
        favorites = cursor.fetchall()

        if not favorites:
            return jsonify({"error": "Нет избранных монет"}), 400

        # Подготовка параметров для запроса к CoinMarketCap API
        symbols = ','.join([coin['symbol'] for coin in favorites])

        if not CMC_API_KEY:
            return jsonify({"error": "API ключ CoinMarketCap не настроен"}), 400

        # Запрос к API CoinMarketCap
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': symbols,
            'convert': 'USD'
        }
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': CMC_API_KEY,
        }

        response = requests.get(url, headers=headers, params=parameters)
        data = response.json()

        if 'status' not in data or data['status']['error_code'] != 0:
            error_msg = data.get('status', {}).get('error_message', 'Unknown error')
            return jsonify({"error": f"Ошибка API CoinMarketCap: {error_msg}"}), 400

        # Обновление данных в базе данных
        update_count = 0

        for symbol in data['data']:
            coin_data = data['data'][symbol]

            # Получаем основные данные для обновления
            coin_id = coin_data['id']
            price = coin_data['quote']['USD']['price']
            percent_change_1h = coin_data['quote']['USD']['percent_change_1h']
            percent_change_24h = coin_data['quote']['USD']['percent_change_24h']
            percent_change_7d = coin_data['quote']['USD']['percent_change_7d']
            percent_change_30d = coin_data['quote']['USD'].get('percent_change_30d')
            percent_change_60d = coin_data['quote']['USD'].get('percent_change_60d')
            percent_change_90d = coin_data['quote']['USD'].get('percent_change_90d')
            market_cap = coin_data['quote']['USD']['market_cap']
            volume_24h = coin_data['quote']['USD']['volume_24h']

            # Обновляем данные в таблице cmc_crypto
            update_query = """
                UPDATE cmc_crypto
                SET price_usd = %s,
                    percent_change_1h = %s,
                    percent_change_24h = %s,
                    percent_change_7d = %s,
                    percent_change_30d = %s,
                    percent_change_60d = %s,
                    percent_change_90d = %s,
                    market_cap = %s,
                    volume_24h = %s,
                    last_updated = NOW()
                WHERE id = %s
            """

            cursor.execute(update_query, (
                price,
                percent_change_1h,
                percent_change_24h,
                percent_change_7d,
                percent_change_30d,
                percent_change_60d,
                percent_change_90d,
                market_cap,
                volume_24h,
                coin_id
            ))

            update_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Данные обновлены для {update_count} монет",
            "updated_count": update_count
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)