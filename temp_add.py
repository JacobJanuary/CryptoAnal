import os
import re
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

    # --- Функция парсинга: извлекает все подстроки в одинарных кавычках ---
    def parse_coins_from_input(user_input: str):
        """
        Ищет все фрагменты вида 'что-то' в строке.
        Возвращает список найденных значений без кавычек.
        Пример:
            Ввод: "'KCAL', 'DIMO', 'Hivemapper'"
            Вывод: ["KCAL", "DIMO", "Hivemapper"]
        """
        return re.findall(r"'([^']*)'", user_input)

    # Запрашиваем у пользователя списки монет
    print("Введите список монет в формате: 'KCAL', 'DIMO', 'Hivemapper', ...")
    ai_input = input("Список AI-монет: ")
    meme_input = input("Список MEME-монет: ")
    real_input = input("Список REAL-монет: ")

    # Преобразуем ввод в списки:
    ai_coins = parse_coins_from_input(ai_input)
    meme_coins = parse_coins_from_input(meme_input)
    real_coins = parse_coins_from_input(real_input)

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