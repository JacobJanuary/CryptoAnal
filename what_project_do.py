import os
import json
import re
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
    Универсальный парсер для ответов ChatGPT, в которых ожидаются структуры вида:
      {'AI': [...], 'MEME': [...], 'REAL': [...]}
    либо несколько таких объектов, разделённых `};`, либо один JSON, либо
    что-то внутри кодовых блоков.

    Возвращает словарь:
      {
        "AI": [...],
        "MEME": [...],
        "REAL": [...]
      }

    Где все найденные значения объединяются (extend).
    """
    # Результирующий агрегатор
    result = {
        "AI": [],
        "MEME": [],
        "REAL": []
    }

    # 1) Удалим из ответа все блоки с тройными бэктиками (```...```)
    #    вместе с содержимым. Часто ChatGPT возвращает код/JSON именно так.
    text_no_codeblocks = re.sub(r'```.*?```', '', response_text, flags=re.DOTALL)

    # 2) С помощью регулярного выражения найдём все блоки в фигурных скобках,
    #    которые не содержат вложенных фигурных скобок.
    #    То есть ищем последовательность: { ... } (жадный, но без вложенных {})
    #    Эта «небольшая» регулярка может ложиться, если внутри фигурных скобок есть другие.
    #    Для более сложных случаев нужно более хитрое решение.
    blocks = re.findall(r'\{[^{}]*\}', text_no_codeblocks)

    # 3) Перебираем каждый фрагмент, пытаемся загрузить его как JSON (после замены ' на ").
    for block in blocks:
        # Для начала убираем пробелы по краям
        block_clean = block.strip()
        # Заменим одинарные кавычки на двойные (часто ChatGPT возвращает '...': '...')
        block_clean = block_clean.replace("'", "\"")

        # Попробуем распарсить
        try:
            parsed_obj = json.loads(block_clean)

            # Если это полноценный словарь, возможно, содержит "AI", "MEME", "REAL"
            if isinstance(parsed_obj, dict):
                # Если ключи "AI"/"MEME"/"REAL" действительно есть
                if "AI" in parsed_obj and isinstance(parsed_obj["AI"], list):
                    result["AI"].extend(parsed_obj["AI"])
                if "MEME" in parsed_obj and isinstance(parsed_obj["MEME"], list):
                    result["MEME"].extend(parsed_obj["MEME"])
                if "REAL" in parsed_obj and isinstance(parsed_obj["REAL"], list):
                    result["REAL"].extend(parsed_obj["REAL"])

        except json.JSONDecodeError:
            # Если не вышло распарсить как JSON — пропускаем
            pass

    # 4) Если регулярка ничего не нашла (blocks=[]), но ChatGPT вернул объекты через `};`,
    #    можно добавить fallback-парсер — как вы делали ранее (split("};") и т.п.).
    #    Однако часто findall() уже найдёт эти объекты.

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