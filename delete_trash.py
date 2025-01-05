import sqlite3

try:
    conn = sqlite3.connect('cryptocurrencies.db')
    cursor = conn.cursor()


    cursor.execute('''
        DELETE FROM coins_volume_stats
            WHERE datetime > NOW() - INTERVAL 1 HOUR;
            ''')


    conn.commit()

except sqlite3.Error as e:
    print(f"Ошибка базы данных: {e}")
finally:
    if conn:
        conn.close()

#new test