import os
import MySQLdb
from dotenv import load_dotenv


def main():
    # Подгружаем переменные окружения из .env
    load_dotenv()

    # ===== Настройки подключения к БД =====
    DB_HOST = os.getenv("MYSQL_HOST", "localhost")
    DB_USER = os.getenv("MYSQL_USER", "root")
    DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
    DB_NAME = os.getenv("MYSQL_DATABASE", "crypto_db")

    # Подключаемся к MySQL
    db = MySQLdb.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASSWORD,
        db=DB_NAME
    )
    cursor = db.cursor()

    # Запрашиваем у пользователя списки монет
    ai_input = input("Введите список AI-монет (через запятую): ")
    meme_input = input("Введите список MEME-монет (через запятую): ")
    real_input = input("Введите список REAL-монет (через запятую): ")

    # Преобразуем каждую строку в список названий (убираем лишние пробелы)
    ai_coins = [coin.strip() for coin in ai_input.split(",") if coin.strip()]
    meme_coins = [coin.strip() for coin in meme_input.split(",") if coin.strip()]
    real_coins = [coin.strip() for coin in real_input.split(",") if coin.strip()]

    # Обновляем SectorID для каждого списка
    # 1) AI -> SectorID = '1'
    for coin_name in ai_coins:
        try:
            cursor.execute(
                "UPDATE cryptocurrencies SET SectorID = '1' WHERE name = %s",
                (coin_name,)
            )
            print(f"[INFO] AI-монета '{coin_name}' → SectorID=1")
        except Exception as e:
            print(f"[ERROR] Не удалось обновить AI-монету '{coin_name}': {e}")

    # 2) MEME -> SectorID = '2'
    for coin_name in meme_coins:
        try:
            cursor.execute(
                "UPDATE cryptocurrencies SET SectorID = '2' WHERE name = %s",
                (coin_name,)
            )
            print(f"[INFO] MEME-монета '{coin_name}' → SectorID=2")
        except Exception as e:
            print(f"[ERROR] Не удалось обновить MEME-монету '{coin_name}': {e}")

    # 3) REAL -> SectorID = '3'
    for coin_name in real_coins:
        try:
            cursor.execute(
                "UPDATE cryptocurrencies SET SectorID = '3' WHERE name = %s",
                (coin_name,)
            )
            print(f"[INFO] REAL-монета '{coin_name}' → SectorID=3")
        except Exception as e:
            print(f"[ERROR] Не удалось обновить REAL-монету '{coin_name}': {e}")

    # Сохраняем изменения
    db.commit()

    # Закрываем соединение
    cursor.close()
    db.close()

    print("\n[INFO] Обновление SectorID завершено.")


if __name__ == "__main__":
    main()