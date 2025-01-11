# what_project_do.py

import os
import openai
import json
import math
import MySQLdb

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
openai.api_key = os.getenv("OPENAI_API_KEY")  # Или присвойте напрямую
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
    (допустим, нас интересует колонка 'name')
    """
    db = MySQLdb.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASSWORD, db=DB_NAME)
    cursor = db.cursor()

    # В зависимости от вашей структуры таблицы поправьте SELECT
    cursor.execute("SELECT name FROM cryptocurrencies")
    rows = cursor.fetchall()

    # rows будет списком кортежей [(name1,), (name2,), ...]
    names = [row[0] for row in rows]

    cursor.close()
    db.close()
    return names


def chunkify(lst, chunk_size=100):
    """
    Разбивает список монет на чанки по 'chunk_size' штук
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i: i + chunk_size]


def call_chatgpt_for_coins(coins_chunk):
    """
    Отправляем в ChatGPT список монет (до 100 штук).
    Возвращаем текстовый ответ ChatGPT.
    """
    # Формируем строку со списком монет
    coins_str = ", ".join(coins_chunk)

    # Создаём полный prompt
    prompt = PROMPT_TEMPLATE + f"\nCoins: {coins_str}\n"

    # Запрос к ChatGPT (используем модель gpt-3.5-turbo, можно менять на другую)
    response = openai.ChatCompletion.create(
        model="o1-preview",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    # Парсим ответ (берём самый первый choice)
    return response["choices"][0]["message"]["content"]


def parse_chatgpt_response(response_text):
    """
    Пытаемся вытащить три списка:
        {'AI': [...], 'MEME': [...], 'REAL': [...]}
    из ответа ChatGPT, который выглядит как:
        {'AI': ['coin1', 'coin2']};
        {'MEME': ['coin3', 'coin4']};
        {'REAL': ['coin5']}
    Возможны вариации формата, поэтому придётся быть гибкими.
    """
    # Пробуем извлечь словари по очереди.
    # Часто ChatGPT выдаёт в виде нескольких отдельных JSON-объектов/строк,
    # или одним JSON-блоком.
    # Простой способ — заменить `};` на `},` и обернуть в общие фигурные скобки
    # с ключами AI, MEME, REAL. Но точные регулярки могут понадобиться, если ответ
    # непредсказуем.

    # Шаг 1: Удалим все переводы строк, чтоб было удобнее парсить
    text_clean = response_text.replace("\n", " ")

    # Шаг 2: Часто ChatGPT возвращает формат типа:
    #   {'AI': ['coin1', 'coin2']}; {'MEME': [...]}; {'REAL': [...]}
    # Превратим это в JSON-валидную структуру:
    #   {"AI": ["coin1", "coin2"], "MEME": [...], "REAL": [...]}
    # Для этого найдём все фрагменты вида {...}; и соберём их в один словарь.

    # Грубый способ: разбить по ';' и затем парсить как JSON.
    parts = text_clean.split("};")

    result = {
        "AI": [],
        "MEME": [],
        "REAL": []
    }

    for part in parts:
        fragment = part.strip()
        # Удаляем лишние символы в конце (например, если не было ";")
        if fragment.endswith("}"):
            pass
        else:
            fragment += "}"

        # Пробуем распарсить как JSON-подобный словарь: {'AI': ['coin1',...]}
        # Python не умеет в одинарные кавычки по умолчанию,
        # нужно заменить их на двойные.
        json_like = fragment.replace("'", "\"")

        # Пробуем загрузить как JSON
        try:
            parsed_obj = json.loads(json_like)
            # parsed_obj будет чем-то вроде {"AI": ["coin1", "coin2"]}
            if "AI" in parsed_obj:
                result["AI"].extend(parsed_obj["AI"])
            if "MEME" in parsed_obj:
                result["MEME"].extend(parsed_obj["MEME"])
            if "REAL" in parsed_obj:
                result["REAL"].extend(parsed_obj["REAL"])
        except Exception as e:
            # Если не получается распарсить, пропускаем
            print(f"Не удалось распарсить кусок: {json_like}, ошибка: {e}")

    return result


def main():
    all_names = fetch_all_cryptocurrency_names()
    print(f"[INFO] Всего монет в таблице: {len(all_names)}")

    # Итоговые списки для всех чанков
    final_ai = []
    final_meme = []
    final_real = []

    for chunk in chunkify(all_names, chunk_size=100):
        print(f"[INFO] Обрабатываем chunk из {len(chunk)} монет, например: {chunk[:5]} ...")

        # 1) вызов ChatGPT
        chatgpt_response = call_chatgpt_for_coins(chunk)

        # 2) парсим ответ
        parsed = parse_chatgpt_response(chatgpt_response)

        # 3) Расширяем наши итоговые списки
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