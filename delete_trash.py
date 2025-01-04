import sqlite3

try:
    conn = sqlite3.connect('cryptocurrencies.db')
    cursor = conn.cursor()

    # Получаем ID, name и rank криптовалют с объемом торгов менее 100000
    cursor.execute('''
        SELECT c.id, c.name, c.rank
        FROM cryptocurrencies c
        INNER JOIN (
            SELECT coin_id, MAX(datetime) as max_datetime
            FROM coins_volume_stats
            GROUP BY coin_id
        ) AS latest_stats ON c.id = latest_stats.coin_id
        INNER JOIN coins_volume_stats cvs ON latest_stats.coin_id = cvs.coin_id AND latest_stats.max_datetime = cvs.datetime
        WHERE cvs.volume < 100000
    ''')
    coins_to_delete = cursor.fetchall()

    deleted_count_volume_stats = 0
    deleted_count_cryptocurrencies = 0

    if coins_to_delete:
        print("Криптовалюты, подлежащие удалению:")
        for coin_id, coin_name, coin_rank in coins_to_delete:
            print(f"ID: {coin_id}, Название: {coin_name}, Rank: {coin_rank}")

            # Удаляем записи из coins_volume_stats
            cursor.execute('''
                DELETE FROM coins_volume_stats
                WHERE coin_id = ?
            ''', (coin_id,))
            deleted_count_volume_stats += cursor.rowcount

            # Удаляем записи из cryptocurrencies
            cursor.execute('''
                DELETE FROM cryptocurrencies
                WHERE id = ?
            ''', (coin_id,))
            deleted_count_cryptocurrencies += cursor.rowcount

        conn.commit()
        print("-" * 20)
        print(f"Удалено {deleted_count_volume_stats} записей из таблицы coins_volume_stats.")
        print(f"Удалено {deleted_count_cryptocurrencies} записей из таблицы cryptocurrencies.")
    else:
        print("Криптовалют с объемом торгов менее 100000 не найдено.")

except sqlite3.Error as e:
    print(f"Ошибка базы данных: {e}")
finally:
    if conn:
        conn.close()