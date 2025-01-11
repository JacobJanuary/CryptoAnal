import os
import json
import math
import MySQLdb
from dotenv import load_dotenv
from openai import OpenAI

# Считываем переменные окружения из .env
load_dotenv()

# ==================================================================
# Настройки MySQL - замените на свои (или используйте свой способ подключения)
# ==================================================================
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
DB_NAME = os.getenv("MYSQL_DATABASE", "crypto_db")

# ==================================================================
# Настройки OpenAI
# ==================================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "o1-preview"

PROMPT_SUFFIX = """
Check all coins from this prompt one by one. 
If it's related to Ai project, add it to list 1, 
if to meme coins - add to list 2, 
if to real-word assets project - to list 3.
Answer - only 3 lists of AI-tokens, meme coins and real-world assets.

Like 
{'AI': ['coin1', 'coin2', 'coin3']};
{'MEME': ['coin4', 'coin5', 'coin6']};
{'REAL': ['coin7', 'coin8', 'coin9']};
"""


def fetch_all_cryptocurrency_names():
    """
    Забираем список всех криптовалют из таблицы 'cryptocurrencies'
    (допустим, нас интересует колонка 'name').
    """
    db = MySQLdb.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASSWORD,
        db=DB_NAME
    )
    cursor = db.cursor()
    cursor.execute("SELECT name FROM cryptocurrencies")
    rows = cursor.fetchall()

    names = [row[0] for row in rows]  # [(name1,), (name2,), ...] -> [name1, name2, ...]

    cursor.close()
    db.close()
    return names


def chunkify(lst, chunk_size=100):
    """
    Разбивает список монет на чанки по 'chunk_size' штук.
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i: i + chunk_size]


def call_chatgpt_for_coins(client, coins_chunk):
    """
    Отправляем в ChatGPT список монет (до 100 штук).
    Выводим в консоль сформированный запрос (content_data) и ответ от API (response).
    Возвращаем текстовый ответ ChatGPT.
    """
    # Склеиваем монеты в одну строку
    coins_str = ",".join(coins_chunk)

    # Формируем контент (в массиве "content")
    content_data = [
        {
            "type": "text",
            "text": f"{coins_str}\n\n{PROMPT_SUFFIX}"
        }
    ]

    # Выводим в консоль часть запроса для отладки
    print("[DEBUG] Prompt content_data:", content_data)

    # Делаем запрос к API
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": content_data
            }
        ]
    )

    # Выводим весь объект ответа в консоль
    print("[DEBUG] Full API response:", response)

    # Возвращаем содержимое ответа
    return response.choices[0].message.content


def parse_chatgpt_response(response_text):
    """
    Пытаемся вытащить три списка:
        {'AI': [...], 'MEME': [...], 'REAL': [...]}
    из ответа ChatGPT, который может выглядеть так:
        {'AI': ['coin1', 'coin2']};
        {'MEME': ['coin3', 'coin4']};
        {'REAL': ['coin5']}

    Для простоты:
      1) Заменяем переводы строк на пробелы.
      2) Разбиваем по "};".
      3) Меняем одинарные кавычки на двойные.
      4) Парсим JSON и добавляем монеты в общий словарь.
    """
    text_clean = response_text.replace("\n", " ")
    parts = text_clean.split("};")

    result = {
        "AI": [],
        "MEME": [],
        "REAL": []
    }

    for part in parts:
        fragment = part.strip()
        if not fragment.endswith("}"):
            fragment += "}"

        # Меняем одинарные кавычки на двойные
        json_like = fragment.replace("'", "\"")

        try:
            parsed_obj = json.loads(json_like)
            # parsed_obj -> {"AI": [...]} или {"MEME": [...]} или {"REAL": [...]}
            if "AI" in parsed_obj:
                result["AI"].extend(parsed_obj["AI"])
            if "MEME" in parsed_obj:
                result["MEME"].extend(parsed_obj["MEME"])
            if "REAL" in parsed_obj:
                result["REAL"].extend(parsed_obj["REAL"])
        except Exception as e:
            print(f"Не удалось распарсить кусок: {json_like}\nОшибка: {e}")

    return result


def main():
    # Инициализируем клиент OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Получаем все имена монет
    all_names = fetch_all_cryptocurrency_names()
    print(f"[INFO] Всего монет в таблице: {len(all_names)}")

    # Итоговые списки
    final_ai = []
    final_meme = []
    final_real = []

    # Идём по чанкам
    for chunk in chunkify(all_names, 100):
        print(f"[INFO] Обрабатываем chunk из {len(chunk)} монет, например: {chunk[:5]} ...")

        # Запрашиваем у ChatGPT
        chatgpt_response = call_chatgpt_for_coins(client, chunk)

        # Парсим ответ
        parsed = parse_chatgpt_response(chatgpt_response)

        # Добавляем к общим спискам
        final_ai.extend(parsed["AI"])
        final_meme.extend(parsed["MEME"])
        final_real.extend(parsed["REAL"])

    # Вывод результата
    print("\n====== РЕЗУЛЬТАТ ======")
    print("AI-токены:")
    print(final_ai)
    print("\nMeme-токены:")
    print(final_meme)
    print("\nReal-world assets:")
    print(final_real)


if __name__ == "__main__":
    main()