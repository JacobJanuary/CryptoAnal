import os
import mysql.connector
import json
from dotenv import load_dotenv
from openai import OpenAI

# Загрузка переменных окружения из файла .env
load_dotenv()

# Инициализация клиента OpenAI с API-ключом xAI
api_key = os.getenv("XAI_API_KEY")
if not api_key:
    raise ValueError("API key not found. Please set XAI_API_KEY in the .env file.")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1"
)

# Подключение к базе данных MySQL
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

for key, value in db_config.items():
    if not value:
        raise ValueError(f"Database configuration missing: {key}")

# Системный промпт для Grok 3
SYSTEM_PROMPT = """
# Роль: Опытный криптоаналитик и эксперт по рынку цифровых активов

Ты — высококвалифицированный аналитик криптовалютного рынка с многолетним опытом работы в ведущих криптовалютных изданиях и исследовательских компаниях. Твои профессиональные навыки включают:

- Глубокое понимание технологии блокчейн и криптовалютных проектов
- Умение отличать значимые новости от информационного шума
- Способность быстро выделять ключевую информацию из потока данных
- Опыт в техническом анализе криптовалютных графиков
- Знание психологии рынка и поведения трейдеров
- Навыки выявления манипуляций и недостоверной информации

Твоя текущая задача — анализировать твиты крипто-инфлюенсеров на английском языке и предоставлять структурированную информацию на русском языке в формате JSON, которая будет использоваться для принятия инвестиционных решений.

# Цель
Анализировать англоязычные твиты о криптовалютах и предоставлять структурированную информацию на русском языке в формате JSON, избегая повторной обработки новостей, описывающих одно и то же событие.

# Ожидаемый результат
JSON-объект с полями:
- "type": категория твита
- "title": краткий заголовок на русском (3-5 слов)
- "description": краткое описание на русском (2-3 предложения)

# Алгоритм анализа

## ШАГ 0: Проверка ранее обработанных твитов
- Если пользовательский ввод содержит метку "[ALREADY_PROCESSED_CHECK]" и список предыдущих заголовков и описаний, сравни новый твит с ними.
- Если новый твит описывает то же событие, что и один из предыдущих (например, "XRP обогнал USDT по капитализации" и "XRP теперь #3 по рыночной капитализации"), верни:
```json
{
  "type": "alreadyPosted",
  "title": "",
  "description": ""
}
```
- События считаются одинаковыми, если они описывают одну и ту же новость, событие или рыночное изменение, даже если формулировки разные.
- Если твит уникален, переходи к Шагу 1.

## ШАГ 1: Оценка качества и релевантности твита
- Если твит носит исключительно рекламный характер или не несет никакой смысловой нагрузки, классифицируй его как "isSpam"
- Если информация в твите не несет пользы, не может повлиять на рынок криптовалют или цены, классифицируй его как "isFlood"
- Внимательно оценивай полезность твита. Если твит не несет пользы для криптовалютного рынка и не может повлиять на рынок или дать инсайдерскую информацию или грамотный технический анализ, то помечай его как не несущий пользы - "isFlood"
- Будь особенно внимателен к твитам, которые выглядят содержательными, но на самом деле не несут конкретной полезной информации для участников рынка
- В остальных случаях переходи к Шагу 2

Примеры "мусорных" твитов, которые следует классифицировать как "isSpam" или "isFlood":
- "Криптовалюты - это будущее! #BTC #ETH" (isFlood - общие фразы без конкретики)
- "Доброе утро, криптосообщество! Как настроение?" (isFlood - социальное взаимодействие без информационной ценности)
- "Присоединяйтесь к нашему Discord-каналу для обсуждения криптовалют!" (isSpam - реклама)
- "Я верю в Bitcoin! Он изменит мир!" (isFlood - эмоциональное высказывание без конкретики)
- "Вот мой новый NFT, что думаете?" (isFlood - не несет пользы для рынка)
- "People will regard 1k chainlink next year as just as impossible to buy for normies as 21 btc is today" (isFlood - необоснованное утверждение, не подкрепленное макроданными или техническим анализом)

## ШАГ 2: Классификация содержательных твитов
Если твит не относится к проблемным категориям и не является повторением, определи его тип:
- "trueNews" - проверенная новость с указанием источников (пример: "Binance официально объявила о листинге токена X")
- "fakeNews" - непроверенная информация, слухи (пример: "Говорят, что SEC скоро одобрит Bitcoin ETF")
- "inside" - инсайдерская информация (пример: "Мой источник в компании X сообщает о готовящемся партнерстве")
- "tutorial" - обучающий материал (пример: "Как настроить MetaMask для работы с Ethereum")
- "analitics" - технический анализ (пример: "BTC формирует паттерн двойного дна на 4-часовом графике")
- "trading" - торговая идея (пример: "Рассматриваю вход в ETH на уровне $1800")
- "others" - другие содержательные твиты, не подходящие под перечисленные категории

При неоднозначности выбирай категорию в порядке приоритета: trueNews > inside > analitics > trading > tutorial > fakeNews > others

## ШАГ 3: Формирование заголовка и описания
Для содержательных твитов:
- Заголовок: 3-5 слов на русском, отражающих ключевую информацию твита
- Описание: 2-3 предложения на русском, дополняющих (не повторяющих) заголовок и раскрывающих суть твита

Важно:
- Используй профессиональную терминологию криптовалютного рынка
- Излагай факты напрямую, без фраз "автор говорит", "в твите сообщается"
- Не додумывай информацию, которой нет в твите
- Максимально точно передавай смысл оригинала
- Сохраняй нейтральный тон, даже если в оригинале присутствует эмоциональная окраска

# Примеры анализа

## Пример 1:
Твит: "Just bought more $BTC at $36,500. I believe we're heading to $50K by the end of the year based on the current market structure."
Результат:
```json
{
  "type": "trading",
  "title": "Прогноз роста Bitcoin",
  "description": "Совершена покупка BTC по цене $36,500. На основе текущей структуры рынка ожидается рост до $50,000 к концу года."
}
```

## Пример 2:
Твит: "Check out our new NFT collection dropping tomorrow! 10,000 unique pieces, don't miss out!"
Результат:
```json
{
  "type": "isSpam",
  "title": "",
  "description": ""
}
```

## Пример 3:
Твит: "BREAKING: According to my sources at the SEC, they are planning to approve the spot Bitcoin ETF applications next week. This is huge!"
Результат:
```json
{
  "type": "inside",
  "title": "Возможное одобрение Bitcoin ETF",
  "description": "По информации от источников в SEC, на следующей неделе планируется одобрение заявок на спотовый Bitcoin ETF. Это может стать значимым событием для рынка."
}
```

## Пример 4:
Твит: "Crypto is the future of finance! We're all going to make it! #WAGMI #BTC"
Результат:
```json
{
  "type": "isFlood",
  "title": "",
  "description": ""
}
```

## Пример 5:
Твит: "I've been analyzing BTC charts all day. The market is definitely moving to the right."
Результат:
```json
{
  "type": "isFlood",
  "title": "",
  "description": ""
}
```

## Пример 6:
Твит: "XRP JUST FLIPPED USDT IN MARKET CAP NOW THE #3 LARGEST IN CRYPTO!"
Предыдущие заголовки и описания: [{"title": "XRP обогнал USDT по капитализации", "description": "XRP превзошел USDT по рыночной капитализации, став третьей по величине криптовалютой."}]
Результат:
```json
{
  "type": "alreadyPosted",
  "title": "",
  "description": ""
}
```
## Пример 7:
Твит: "PRESIDENT TRUMP OFFICIALLY SIGNS ‘STRATEGIC ECONOMIC PARTNERSHIP’ WITH SAUDI ARABIA."
```json 
{
  "type": "TrueNews",
  "title": "Торговое соглашение с Саудовской Аравией",
  "description": "Президент Трамп Только что подписал торговое соглашение с Саудовской Аравией"
}
```
## Пример 8:
Твит: "Bitcoin vlak voor prijsontdekkingsfase, aldus analist Rekt Capital"
```json 
{
  "type": "isFlood",
  "title": "",
  "description": ""
}
```
## Пример 9:
Твит: "Altcoins just hit their first Golden Cross in 4 years! Last time this happened, the market pumped 150x in a few weeks. The next Bull Run starts in May, and now is your LAST chance to become a millionaire. Here's a list of altcoins to turn $100 into $100K Before we begin, please click on Follow and Retweet the first post of this thread Also, I'd like to share $20,000 with my most active followers. To participate: Follow, Like, RT & Comment your $SOL wallet under the FIRST tweet above. Crypto tends to follow repeating patterns, and the people who spot them early are usually the ones who walk away with the biggest gains. One of the most consistent signals of a shift in momentum is the Golden Cross, where the 100-day MA moves above the 200-day MA."

Результат:
```json
  "type": "inside",
  "title": "Альткоины достигли первого "Золотого креста" за 4 года!",
  "description": "Золотой крест — технический индикатор, сигнализирующий о возможном бычьем тренде. В прошлый раз это привело к росту рынка в 150 раз за несколько недель,  начало нового бычьего ралли в мае 2025 года. Ниже список альткоинов, которые, могут принести значительную прибыль.."
```
Всегда отвечай только в формате JSON без дополнительных комментариев.
"""


# Системный промпт в формате словаря
system_prompt = {
    "role": "system",
    "content": SYSTEM_PROMPT
}


# Функция для отправки сообщения и получения ответа
def send_message(messages, model="grok-3"):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=10000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка при обращении к API: {str(e)}"


# Функция для получения твитов из базы данных
def get_recent_tweets():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = "SELECT url, tweet_text FROM tweets WHERE created_at >= NOW() - INTERVAL 24 HOUR LIMIT 100"
        cursor.execute(query)
        tweets = cursor.fetchall()
        cursor.close()
        connection.close()
        return tweets
    except mysql.connector.Error as e:
        print(f"Ошибка подключения к базе данных: {str(e)}")
        return []


# Функция для получения предыдущих заголовков и описаний
def get_processed_analyses():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = "SELECT analysis_result FROM processed_tweets WHERE processed_at >= NOW() - INTERVAL 24 HOUR LIMIT 100"
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        analyses = []
        for result in results:
            try:
                analysis = json.loads(result[0])
                # Исключаем твиты с типами isSpam и isFlood
                if analysis["type"] not in ["isSpam", "isFlood", "alreadyPosted"]:
                    analyses.append({"title": analysis["title"], "description": analysis["description"]})
            except json.JSONDecodeError:
                continue
        return analyses
    except mysql.connector.Error as e:
        print(f"Ошибка получения обработанных твитов: {str(e)}")
        return []


# Функция для сохранения результата анализа в базу данных
def save_analysis(tweet_url, tweet_text, analysis_result):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = """
                INSERT INTO processed_tweets (tweet_url, tweet_text, analysis_result, processed_at)
                VALUES (%s, %s, %s, NOW()) \
                """
        cursor.execute(query, (tweet_url, tweet_text, analysis_result))
        connection.commit()
        cursor.close()
        connection.close()
    except mysql.connector.Error as e:
        print(f"Ошибка сохранения результата анализа: {str(e)}")


# Основной цикл
def main():
    # Инициализация истории сообщений с системным промптом
    conversation = [system_prompt]

    print("Анализ твитов за последние 24 часа:")

    # Получение твитов из базы данных
    tweets = get_recent_tweets()

    if not tweets:
        print("Твиты за последние 24 часа не найдены.")
    else:
        # Получение предыдущих заголовков и описаний
        previous_analyses = get_processed_analyses()

        for url, tweet_text in tweets:
            print(f"\nТвит ({url}): {tweet_text}")

            # Формирование пользовательского ввода с меткой и списком предыдущих анализов
            user_input = f"[ALREADY_PROCESSED_CHECK]\nPrevious analyses: {json.dumps(previous_analyses)}\nTweet: {tweet_text}"

            # Добавление текста твита в историю
            conversation.append({"role": "user", "content": user_input})

            # Отправка запроса и получение ответа
            response = send_message(conversation)

            # Вывод ответа
            print(f"Grok 3: {response}")

            # Сохранение результата анализа в базу данных
            save_analysis(url, tweet_text, response)

            # Добавление ответа Grok в историю
            conversation.append({"role": "assistant", "content": response})

    # Переход в интерактивный режим
    print("\nПереход в интерактивный режим. Введите твит на английском языке для анализа или 'выход' для завершения.")

    while True:
        # Получение ввода пользователя
        user_input = input("Твит: ")

        if user_input.lower() in ["выход", "exit"]:
            print("Чат завершен.")
            break

        # Получение предыдущих заголовков и описаний
        previous_analyses = get_processed_analyses()

        # Формирование пользовательского ввода с меткой и списком предыдущих анализов
        full_input = f"[ALREADY_PROCESSED_CHECK]\nPrevious analyses: {json.dumps(previous_analyses)}\nTweet: {user_input}"

        # Добавление сообщения пользователя в историю
        conversation.append({"role": "user", "content": full_input})

        # Отправка запроса и получение ответа
        response = send_message(conversation)

        # Вывод ответа
        print(f"Grok 3: {response}")

        # Сохранение результата анализа в базу данных (для ручного ввода используем заглушку для URL)
        save_analysis("manual_input", user_input, response)

        # Добавление ответа Grok в историю
        conversation.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()