# -*- coding: utf-8 -*-
import os
import sys # Для вывода ошибок
import traceback # Импортируем для вывода traceback

# --- Библиотека для .env ---
from dotenv import load_dotenv # Добавлено для загрузки .env

# --- Библиотеки для работы с БД ---
# Вам нужно установить драйвер: pip install mysql-connector-python
import mysql.connector # Используем MySQL

# --- Библиотеки Google ---
from google.oauth2 import service_account
from google.api_core import exceptions as google_exceptions
import google.generativeai as genai
from google.generativeai import types
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- Загрузка переменных окружения из .env файла ---
load_dotenv() # Загружаем переменные из .env

# --- Конфигурация ---

# Файл ключа сервисного аккаунта Google
# !!! ВАЖНО: Укажите здесь ПОЛНЫЙ путь к вашему файлу JSON с ключом сервисного аккаунта !!!
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gen-lang-client-0317567419-7bf2e0685088.json") # Пытаемся взять из env, иначе используем плейсхолдер

# Модель Gemini
MODEL_NAME = "gemini-2.5-pro-preview-03-25"

# Конфигурация базы данных (читается из .env или системных переменных)
DB_TYPE = os.getenv('DB_TYPE') # Убраны значения по умолчанию
DB_NAME = os.getenv('DB_NAME')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Проверка наличия обязательных переменных БД
if not all([DB_TYPE, DB_NAME, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD]):
    print("Ошибка: Не все переменные окружения для подключения к БД установлены.")
    print("Убедитесь, что DB_TYPE, DB_NAME, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD заданы в .env или системных переменных.")
    sys.exit(1) # Выход из скрипта, если конфигурация не полная

# Шаблон промпта (без изменений)
PROMPT_TEMPLATE = """You are a highly qualified expert combining the roles of cryptocurrency analyst, financial consultant, risk manager, and, when necessary, a programmer. Your task is to perform a thorough and structured analysis of the cryptocurrency token {token_name}.
You may use your own internal tools, scripts, or code to extract and process data from sources such as https://cryptorank.io/price/sui/team, https://cryptorank.io/ico/{symbol_lower}#funding-rounds, Binance Research (https://research.binance.com/en), ICO Drops (https://icodrops.com/), or similar sites if you cannot find enough structured information from open sources. Never display or mention any code, scripts, or technical retrieval processes to the user; these must be used internally only. The user must receive ONLY the final, structured analysis and explanation in Russian.
EVERY answer, explanation, summary, and calculation you provide MUST be in Russian.
Please structure your analysis according to the following sections and guidance:
1. Team
(Act as a cryptocurrency and team assessment expert.)
Analyze the core and extended team (founders, advisors): their professional background, track record, public profiles (LinkedIn, Twitter), media presence, industry reputation, credibility, and trust from the community.
If information is insufficient, use your internal tools/scripts to extract and aggregate data. Only present your finalized analysis in Russian, with no mention of the code or process.
2. Project History and Roadmap
(Act as an industry analyst.)
Specify the project’s founding date and token launch date. Compare achievements to the published roadmap and timeline, highlighting key milestones, successes, and any delays.
3. Tokenomics and Distribution
(Act as a financial consultant and crypto analyst.)
Provide a detailed breakdown of tokenomics including distribution percentages (team, investors, community, funds), vesting/lock-up conditions, risks related to unlocks, current free float, and market capitalization.
4. Real-World Utility and Partnerships
(Act as a crypto expert.)
Assess what problem the token tries to solve, its real-world utility and uniqueness, operating products/services, meaningful partnerships, and real integrations.
5. Investors, Funds, and Early Investor Pricing
(Act as a financial consultant.)
Analyze investors and funds involved, investment rounds, total raised, dates, and token price per round (e.g., seed/private rounds).
When analyzing and verifying funding rounds, always check and cross-reference information from:
CryptoRank (https://cryptorank.io/ico/{symbol_lower})
Binance Research (https://research.binance.com/en)
ICO Drops (https://icodrops.com/)
Any other relevant sources, if needed
If the price per token for early investors is NOT directly stated:
Make every possible effort to estimate it.
Find how many tokens were allocated to early investors in total.
Find how many tokens were allocated and how much was raised in each funding round.
For example: if $2,500,000 was raised in the seed round for 9,500,000 tokens, and $12,000,000 in the private round (with tokenomics specifying a total of 20,000,000 tokens to early investors), you can calculate:Seed round price = $2,500,000 / 9,500,000
Private round price = $12,000,000 / (20,000,000 - 9,500,000)
Show and explain these calculations in Russian in your summary, explicitly stating what numbers were used and the logic.
If data is missing and calculation is impossible, explain in Russian what is missing and why calculation cannot be completed.
6. Reputational and Legal Risks
(Act as a risk analyst.)
Review for any public controversies, hacks, scandals, lawsuits, negative community sentiment, or legal threats/disputes in major crypto communities or networks.
7. Expert Analytical Summary
(Act as a senior financial analyst.)
Summarize the main strengths and weaknesses, primary risks, and provide a reasoned, analytical overall assessment of the project’s outlook (do NOT give financial advice).
Additional Instructions:
Absolutely ALL output, explanations, comments, and calculations must be in Russian.
Always cite specific sources of information used (preferably in Russian if available).
If certain information is missing even after internal extraction attempts, specify in Russian what data is missing and why.
Never display any code, pseudo-code, or technical details of extraction or data processing to the user."""

# Настройки безопасности Gemini (без изменений)
safety_settings_config = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
}

# Конфигурация генерации Gemini (без изменений)
GENERATION_CONFIG = types.GenerationConfig(
    temperature = 0.1,
    top_p = 0.95,
    max_output_tokens = 8192,
)

# --- Функции для работы с БД ---

def connect_db():
    """Устанавливает соединение с базой данных MySQL."""
    try:
        # Проверка DB_TYPE (хотя читаем из env, подставляем явно mysql)
        if DB_TYPE != 'mysql':
             print(f"Ошибка: Скрипт настроен только для MySQL (DB_TYPE='mysql'), обнаружен: {DB_TYPE}")
             return None

        print(f"Подключение к MySQL: host={DB_HOST}, port={DB_PORT}, user={DB_USER}, db={DB_NAME}")
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print("Подключение к MySQL успешно.")
        return conn
    except mysql.connector.Error as err: # Ловим специфичные ошибки MySQL
        print(f"Ошибка подключения к MySQL: {err}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"Неожиданная ошибка подключения к базе данных: {e}")
        traceback.print_exc()
        return None


def fetch_tokens_to_analyze(cursor):
    """Извлекает токены из БД MySQL, для которых нужно получить анализ."""
    try:
        query = """
        SELECT id, name, symbol
        FROM cmc_crypto
        WHERE gemini_invest IS NULL
          AND id IN (SELECT coin_id FROM cmc_favorites)
        """
        print(f"\nВыполнение запроса для получения токенов:\n{query}")
        cursor.execute(query)
        tokens = cursor.fetchall()
        print(f"Найдено {len(tokens)} токенов для анализа.")
        # Преобразуем результат в список словарей для удобства
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in tokens]
    except mysql.connector.Error as err:
        print(f"Ошибка MySQL при извлечении токенов: {err}")
        traceback.print_exc()
        return []
    except Exception as e:
        print(f"Неожиданная ошибка при извлечении токенов: {e}")
        traceback.print_exc()
        return []

def update_token_analysis(cursor, conn, token_id, analysis_text):
    """Обновляет поле gemini_invest для указанного токена в БД MySQL."""
    try:
        # Используем плейсхолдеры %s для MySQL
        query = """
        UPDATE cmc_crypto
        SET gemini_invest = %s
        WHERE id = %s
        """
        print(f"\nОбновление анализа для токена ID: {token_id}...")
        cursor.execute(query, (analysis_text, token_id))
        conn.commit() # Фиксируем изменения
        print(f"Анализ для токена ID {token_id} успешно обновлен.")
        return True
    except mysql.connector.Error as err:
        print(f"Ошибка MySQL при обновлении анализа для токена ID {token_id}: {err}")
        conn.rollback() # Откатываем изменения в случае ошибки
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"Неожиданная ошибка при обновлении анализа для токена ID {token_id}: {e}")
        conn.rollback() # Откатываем изменения в случае ошибки
        traceback.print_exc()
        return False

# --- Функция для вызова Gemini ---
def get_gemini_analysis(model, prompt, config, safety_settings, tools):
    """Выполняет запрос к API Gemini и возвращает полный текст ответа."""
    full_response = ""
    try:
        print(f"Отправка запроса к модели {model.model_name}...")
        stream = model.generate_content(
            contents=[{'role': 'user', 'parts': [prompt]}],
            generation_config=config,
            safety_settings=safety_settings,
            tools=tools,
            stream=True,
        )

        print("\n--- Ответ модели (потоковый) ---")
        for chunk in stream:
            try:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    full_response += chunk.text
            except AttributeError:
                 if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                      part = chunk.candidates[0].content.parts[0]
                      if hasattr(part, 'text') and part.text:
                           print(part.text, end="", flush=True)
                           full_response += part.text
            # Обработка вызова функций (если нужно)
            try:
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                     part = chunk.candidates[0].content.parts[0]
                     if hasattr(part, 'function_call') and part.function_call:
                         print(f"\n[Модель запрашивает вызов функции: {part.function_call.name}]", flush=True)
            except Exception:
                 pass
        print("\n--- Потоковая генерация завершена ---")

    except google_exceptions.InvalidArgument as e:
        print(f"\nОшибка неверного аргумента при вызове Gemini: {e}")
        print("Проверьте конфигурацию запроса.")
        full_response = f"Ошибка Gemini: InvalidArgument - {e}"
    except Exception as e:
        print(f"\nНепредвиденная ошибка при вызове Gemini: {e}")
        traceback.print_exc()
        full_response = f"Ошибка Gemini: Exception - {e}"

    return full_response

# --- Основная функция ---

def main_process():
    """Основной процесс: подключение к БД, получение токенов, анализ, обновление БД."""

    # 1. Проверка файла ключа Google
    # Используем SERVICE_ACCOUNT_FILE, который теперь пытается читать из env
    if SERVICE_ACCOUNT_FILE == "ПУТЬ/К/ВАШЕМУ/ФАЙЛУ/keyfile.json" or not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"Ошибка: Путь к файлу ключа сервисного аккаунта Google не найден.")
        print(f"Проверьте переменную окружения GOOGLE_APPLICATION_CREDENTIALS или укажите путь в SERVICE_ACCOUNT_FILE.")
        print(f"Текущее значение SERVICE_ACCOUNT_FILE: {SERVICE_ACCOUNT_FILE}")
        return

    # 2. Настройка аутентификации Google
    try:
        print(f"Загрузка учетных данных Google из файла: {SERVICE_ACCOUNT_FILE}...")
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        print("Учетные данные Google успешно загружены.")
        print("Настройка аутентификации Generative AI...")
        genai.configure(credentials=credentials)
        print("Аутентификация Google настроена.")
    except Exception as e:
        print(f"Ошибка при настройке аутентификации Google: {e}")
        traceback.print_exc()
        return

    # 3. Инициализация модели Gemini
    try:
        print(f"Создание экземпляра модели: {MODEL_NAME}...")
        model = genai.GenerativeModel(MODEL_NAME)
        print("Экземпляр модели Gemini создан.")
    except Exception as e:
        print(f"Ошибка при создании экземпляра модели Gemini: {e}")
        traceback.print_exc()
        return

    # 4. Определение инструментов Gemini (веб-поиск)
    tools = None
    try:
         tools = [types.Tool(google_search=types.GoogleSearch())]
         print("Веб-поиск (Google Search) активирован.")
    except AttributeError as e:
         print(f"Ошибка при определении инструментов: {e}. Возможно, структура Tool/GoogleSearch изменилась.")
         print("Запуск без инструментов.")

    # 5. Подключение к БД
    conn = connect_db()
    if not conn:
        return # Ошибка подключения уже выведена

    cursor = None
    try:
        cursor = conn.cursor()

        # 6. Получение списка токенов для анализа
        tokens_to_process = fetch_tokens_to_analyze(cursor)

        if not tokens_to_process:
            print("Нет токенов для анализа или произошла ошибка при их получении.")
            return

        # 7. Обработка каждого токена
        for token in tokens_to_process:
            token_id = token['id']
            token_name = token['name']
            token_symbol = token['symbol']
            symbol_lower = token_symbol.lower() if token_symbol else ''

            print("-" * 40)
            print(f"Обработка токена: ID={token_id}, Name='{token_name}', Symbol='{token_symbol}'")

            # Формируем название для промпта
            token_display_name = f"{token_name} ({token_symbol})" if token_symbol else token_name

            # Формируем промпт
            formatted_prompt = PROMPT_TEMPLATE.format(token_name=token_display_name, symbol_lower=symbol_lower)

            # Получаем анализ от Gemini
            analysis_result = get_gemini_analysis(
                model,
                formatted_prompt,
                GENERATION_CONFIG,
                safety_settings_config,
                tools
            )

            # Обновляем запись в БД
            if analysis_result:
                update_token_analysis(cursor, conn, token_id, analysis_result)
            else:
                print(f"Не получен результат анализа для токена ID {token_id}, запись не обновлена.")

            print("-" * 40)

    except Exception as e:
        print(f"Произошла ошибка во время основного процесса: {e}")
        traceback.print_exc()
    finally:
        # 8. Закрытие соединения с БД
        if cursor:
            cursor.close()
            print("Курсор БД закрыт.")
        if conn and conn.is_connected(): # Проверяем, что соединение еще активно
            conn.close()
            print("Соединение с БД закрыто.")

if __name__ == "__main__":
    main_process()
