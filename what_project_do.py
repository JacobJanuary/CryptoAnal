import os
import json
import math
import MySQLdb
import re
from dotenv import load_dotenv
from openai import OpenAI

# Считываем переменные окружения из .env
load_dotenv()

# ==================================================================
# Настройки MySQL
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


def fetch_all_cryptocurrency_names_with_sector0():
    """
    Забираем список всех криптовалют, у которых SectorID = '0'
    """
    db = MySQLdb.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASSWORD,
        db=DB_NAME
    )
    cursor = db.cursor()
    # Получаем только те, у кого SectorID = '0'
    cursor.execute("SELECT name FROM cryptocurrencies WHERE SectorID = '0'")
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
    Возвращаем текстовый ответ ChatGPT.
    """
    coins_str = ",".join(coins_chunk)
    content_data = [
        {
            "type": "text",
            "text": f"{coins_str}\n\n{PROMPT_SUFFIX}"
        }
    ]

    print("[DEBUG] Prompt content_data:", content_data)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": content_data
            }
        ]
    )

    print("[DEBUG] Full API response:", response)
    return response.choices[0].message.content


def parse_chatgpt_response(response_text):
    """
    Универсальный парсер для извлечения AI/MEME/REAL.
    Возвращает словарь {"AI": [...], "MEME": [...], "REAL": [...]}
    с объединёнными списками, если в ответе несколько блоков.
    """
    # Итоговый результат
    result = {
        "AI": [],
        "MEME": [],
        "REAL": []
    }

    # 1) Удалим блоки кода (```...```)
    text_no_codeblocks = re.sub(r'```.*?```', '', response_text, flags=re.DOTALL)

    # 2) Ищем все фрагменты в фигурных скобках (без вложенных {})
    blocks = re.findall(r'\{[^{}]*\}', text_no_codeblocks)

    for block in blocks:
        block_clean = block.strip()
        # если не оканчивается на '}'
        if not block_clean.endswith("}"):
            block_clean += "}"

        block_clean = block_clean.replace("'", "\"")  # заменяем одинарные кавычки
        try:
            parsed_obj = json.loads(block_clean)
            if isinstance(parsed_obj, dict):
                # Проверяем, есть ли ключи AI, MEME, REAL
                if "AI" in parsed_obj and isinstance(parsed_obj["AI"], list):
                    result["AI"].extend(parsed_obj["AI"])
                if "MEME" in parsed_obj and isinstance(parsed_obj["MEME"], list):
                    result["MEME"].extend(parsed_obj["MEME"])
                if "REAL" in parsed_obj and isinstance(parsed_obj["REAL"], list):
                    result["REAL"].extend(parsed_obj["REAL"])
        except json.JSONDecodeError:
            pass

    return result


def main():
    # Инициализируем клиент OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    # 1) Получаем все имена монет с SectorID = '0'
    all_names_sector0 = fetch_all_cryptocurrency_names_with_sector0()
    print(f"[INFO] Всего монет в таблице с SectorID=0: {len(all_names_sector0)}")

    # Подключаемся к БД на время обработки
    db = MySQLdb.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASSWORD,
        db=DB_NAME
    )
    cursor = db.cursor()

    # 2) Обрабатываем списки по 100 штук
    for chunk in chunkify(all_names_sector0, 100):
        print(f"[INFO] Обрабатываем chunk из {len(chunk)} монет, например: {chunk[:5]} ...")

        # Вызываем ChatGPT
        chatgpt_response = call_chatgpt_for_coins(client, chunk)

        # Парсим ответ
        parsed = parse_chatgpt_response(chatgpt_response)

        # Результирующие списки
        ai_list = set(parsed["AI"])  # множество для быстрого поиска
        meme_list = set(parsed["MEME"])
        real_list = set(parsed["REAL"])

        # 3) Проставляем сектор ID каждой монете из чанка
        for name in chunk:
            # Смотрим, к какому сектору отнесена монета
            if name in ai_list:
                new_sector = '1'
            elif name in meme_list:
                new_sector = '2'
            elif name in real_list:
                new_sector = '3'
            else:
                # Если не попало ни в один список — ставим '9'
                new_sector = '9'

            try:
                cursor.execute(
                    "UPDATE cryptocurrencies SET SectorID = %s WHERE name = %s",
                    (new_sector, name)
                )
            except Exception as e:
                print(f"[ERROR] Не удалось обновить монету {name}: {e}")

        # После обработки чанка — коммитим
        db.commit()

    # Закрываем соединение
    cursor.close()
    db.close()

    print("[INFO] Скрипт завершён.")


if __name__ == "__main__":
    main()