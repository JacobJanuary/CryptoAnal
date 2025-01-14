import os
import traceback
from flask import Flask, render_template, request, jsonify
from flask_mysqldb import MySQL
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# Конфигурация MySQL
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST", "localhost")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER", "root")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD", "password")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DATABASE", "crypto_db")

mysql = MySQL(app)

@app.route("/", methods=["GET"])
def index():
    try:
        cur = mysql.connection.cursor()
        # Вызываем функцию cg_GetFilteredCoins с параметрами по умолчанию:
        -- p_vol_min: 10000, p_growth6h: 100, p_growth1h: 100, p_price_change_max: 10, p_price_change_min: 0, p_market_cap_rank: NULL
        query = "SELECT * FROM cg_GetFilteredCoins(10000, 100, 100, 10, 0, NULL)"
        cur.execute(query)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        crypto_data = [dict(zip(col_names, row)) for row in rows]
        cur.close()
        return render_template("coingecko.html", crypto_data=crypto_data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(debug=True)