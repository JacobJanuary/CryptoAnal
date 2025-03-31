import os
import traceback
from anthropic import Anthropic
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_caching import Cache
from flask_mysqldb import MySQL
import mysql.connector as mc

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")

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
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        opposite_order = 'desc' if order == 'asc' else 'asc'

        return render_template("cmc_favourites.html", coins=rows, current_sort=sort_by, current_order=order,
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
                c.grok2_text AS AI_text,
                c.grok2_invest AS AI_invest,
                c.gemini_invest,
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


if __name__ == "__main__":
    app.run(debug=True)