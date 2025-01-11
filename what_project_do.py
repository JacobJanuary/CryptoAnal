# what_project_do.py

import os
import json
import math
import MySQLdb

# Из новой версии библиотеки:
# см. https://github.com/openai/openai-python#usage
from openai import OpenAI

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # или пропишите напрямую
PROMPT_TEMPLATE = """Check all coins from this prompt one by one.
If it's related to Ai project, add it to list 1,
if to meme coins - add it to list 2,
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

    # rows -> [(name1,), (name2,), ...]
    names = [row[0] for row in rows]

    cursor.close()
    db.close()
    return names

def chunkify(lst, chunk_size=100):
    """
    Разбивает список монет на чанки по 'chunk_size' штук.
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]

def call_chatgpt_for_coins(client, coins_chunk):
    """
    Отправляем в ChatGPT список монет (до 100 штук).
    Используем клиентский подход:
        from openai import OpenAI
        client = OpenAI(api_key=...)
    Возвращаем текстовый ответ ChatGPT.
    """
    # Формируем строку со списком монет
    coins_str = ", ".join(coins_chunk)

    # Создаём полный prompt
    prompt = PROMPT_TEMPLATE + f"\nCoins: {coins_str}\n"

    # Выполняем запрос к ChatGPT (пример: модель "gpt-4o")
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "developer", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    # Возвращаем только контент из первого варианта
    return completion.choices[0].message["content"]

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

        # Заменяем одинарные кавычки на двойные, чтобы можно было распарсить JSON
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

    # Итоговые списки для всех чанков
    final_ai = []
    final_meme = []
    final_real = []

    # Обрабатываем списки по 100 штук
    for chunk in chunkify(all_names, chunk_size=100):
        print(f"[INFO] Обрабатываем chunk из {len(chunk)} монет, например: {chunk[:5]} ...")

        # Вызываем ChatGPT
        chatgpt_response = call_chatgpt_for_coins(client, chunk)

        # Парсим ответ
        parsed = parse_chatgpt_response(chatgpt_response)

        # Расширяем наши итоговые списки
        final_ai.extend(parsed["AI"])
        final_meme.extend(parsed["MEME"])
        final_real.extend(parsed["REAL"])

    # После обработки всех чанков выводим суммарные результаты
    print("\n====== РЕЗУЛЬТАТ ======")
    print("AI-токены:")
    print(final_ai)
    print("\nMeme-токены:")
    print(final_meme)
    print("\nReal-world Assets:")
    print(final_real)

if __name__ == "__main__":
    main()