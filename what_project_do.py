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
# Настройки OpenAI (ключ может быть взят из переменных окружения либо прописан напрямую)
# ==================================================================
openai.api_key = os.getenv("OPENAI_API_KEY")  # Или присвойте напрямую (не рекомендуется хранить ключ в коде)

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

    # В зависимости от вашей структуры таблицы скорректируйте SELECT
    cursor.execute("SELECT name FROM cryptocurrencies")
    rows = cursor.fetchall()

    # rows будет списком кортежей [(name1,), (name2,), ...]
    names = [row[0] for row in rows]

    cursor.close()
    db.close()
    return names


def chunkify(lst, chunk_size=100):
    """
    Разбивает список монет на чанки по 'chunk_size' штук.
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i: i + chunk_size]


def call_chatgpt_for_coins(coins_chunk):
    """
    Отправляем в ChatGPT список монет (до 100 штук).
    Возвращаем текстовый ответ ChatGPT, используя новое API (>=1.0.0).
    """
    # Формируем строку со списком монет
    coins_str = ", ".join(coins_chunk)

    # Создаём полный prompt
    prompt = PROMPT_TEMPLATE + f"\nCoins: {coins_str}\n"

    # Запрос к ChatGPT (используем модель gpt-3.5-turbo, можно менять на другую)
    response = openai.chat_completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    # В новом API результат находится в response.choices[0].message.content
    return response.choices[0].message.content


def parse_chatgpt_response(response_text):
    """
    Пытаемся вытащить три списка:
        {'AI': [...], 'MEME': [...], 'REAL': [...]}
    из ответа ChatGPT, который может выглядеть как:
        {'AI': ['coin1', 'coin2']};
        {'MEME': ['coin3', 'coin4']};
        {'REAL': ['coin5']}

    Из-за того, что ChatGPT может вернуть разные форматы, используем простой
    текстовый парсинг: разбиваем по '};', приводим одинарные кавычки к двойным,
    и пытаемся загрузить как JSON.
    """
    # Удалим все переводы строк для удобства
    text_clean = response_text.replace("\n", " ")

    # Разбиваем по "};" (каждый кусок должен содержать словарь вида {'AI': [...]} )
    parts = text_clean.split("};")

    # Итоговая структура
    result = {
        "AI": [],
        "MEME": [],
        "REAL": []
    }

    for part in parts:
        fragment = part.strip()
        # Удаляем лишние символы в конце (если не было '}' - добавляем)
        if not fragment.endswith("}"):
            fragment += "}"

        # Заменяем одинарные кавычки на двойные, чтобы можно было распарсить JSON
        json_like = fragment.replace("'", "\"")

        try:
            parsed_obj = json.loads(json_like)

            # parsed_obj может выглядеть как {"AI": ["coin1", "coin2"]}
            if "AI" in parsed_obj:
                result["AI"].extend(parsed_obj["AI"])
            if "MEME" in parsed_obj:
                result["MEME"].extend(parsed_obj["MEME"])
            if "REAL" in parsed_obj:
                result["REAL"].extend(parsed_obj["REAL"])
        except Exception as e:
            # Если не получается распарсить - просто пропускаем
            print(f"Не удалось распарсить кусок: {json_like}\nОшибка: {e}")

    return result


def main():
    # 1) Получаем все имена монет
    all_names = fetch_all_cryptocurrency_names()
    print(f"[INFO] Всего монет в таблице: {len(all_names)}")

    # Итоговые списки для всех чанков
    final_ai = []
    final_meme = []
    final_real = []

    # 2) Обрабатываем списки по 100 штук
    for chunk in chunkify(all_names, chunk_size=100):
        print(f"[INFO] Обрабатываем chunk из {len(chunk)} монет, например: {chunk[:5]} ...")

        # Вызываем ChatGPT
        chatgpt_response = call_chatgpt_for_coins(chunk)

        # Парсим ответ
        parsed = parse_chatgpt_response(chatgpt_response)

        # Расширяем наши итоговые списки
        final_ai.extend(parsed["AI"])
        final_meme.extend(parsed["MEME"])
        final_real.extend(parsed["REAL"])

    # 3) После обработки всех чанков выводим суммарные результаты
    print("\n====== РЕЗУЛЬТАТ ======")
    print("AI-токены:")
    print(final_ai)
    print("\nMeme-токены:")
    print(final_meme)
    print("\nReal-world Assets:")
    print(final_real)


if __name__ == "__main__":
    main()