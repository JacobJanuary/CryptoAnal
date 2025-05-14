import os
import json
import mysql.connector
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

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
Роль: Опытный криптоаналитик и эксперт по рынку цифровых активов

Ты — высококвалифицированный аналитик криптовалютного рынка с многолетним опытом работы в ведущих криптовалютных изданиях и исследовательских компаниях. Твои профессиональные навыки включают:

- Глубокое понимание технологии блокчейн и криптовалютных проектов
- Умение отличать значимые новости от информационного шума
- Способность быстро выделять ключевую информацию из потока данных
- Опыт в техническом анализе криптовалютных графиков
- Знание психологии рынка и поведения трейдеров
- Навыки выявления манипуляций и недостоверной информации

Твоя текущая задача — анализировать твиты крипто-инфлюенсеров на английском языке и предоставлять структурированную информацию на русском языке, которая будет использоваться для принятия инвестиционных решений.

# Цель
Анализировать массив англоязычных твитов о криптовалютах и предоставлять структурированную информацию на русском языке в формате JSON.

# Ожидаемый результат
Массив JSON-объектов, где каждый объект соответствует одному твиту и содержит поля:
- "type": категория твита
- "title": краткий заголовок на русском (3-5 слов)
- "description": краткое описание на русском (2-3 предложения)

# Формат входных данных
Два массива JSON-объектов:
1. Первый массив - новые необработанные твиты:
```json
[
  {
    "text": "текст_твита1"
  },
  {
    "text": "текст_твита2"
  },
  ...
]
```

2. Второй массив - ранее обработанные твиты:
```json
[
  {
    "text": "текст_ранее_обработанного_твита1"
  },
  {
    "text": "текст_ранее_обработанного_твита2"
  },
  ...
]
```

# Алгоритм анализа для каждого твита из первого массива

## ШАГ 0: Проверка на дублирование информации
- Проверь, описывает ли текущий твит то же событие, что и один из предыдущих твитов в первом массиве ИЛИ любой твит из второго массива (ранее обработанные)
- Если текущий твит описывает то же событие, что и один из ранее обработанных твитов (например, уже был твит "XRP обогнал USDT по капитализации", а новый твит - "XRP теперь #3 по рыночной капитализации"), классифицируй его как "alreadyPosted"
- В случае обнаружения дубликата, не анализируй его содержание дальше и верни:

```json
{
  "type": "alreadyPosted",
  "title": "",
  "description": ""
}
```

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
Если твит не относится к проблемным категориям, определи его тип:
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
Твит: "US inflation fell to 2.3% in April, lower than initially expected in light of economic uncertainty. Inflation slowed during the month Trump introduced Liberation Day tariffs. Guys these things take time to fully kick in. Stop being so fiscally immature and acting like because we're going to see the end result 18 business hours after x y and z changes were made. Stop this. Glad to see inflation is down, but we need more action from the government to make sure prices stay low and everyone can afford basic needs. Exciting news! US inflation fell to 2.3% in April, showing that Trump's economic policies are starting to work. Let's continue supporting him and his efforts to make America great again. The first four days of the Trump Administration have been packed with news. That's why I'm excited to launch: , a daily (M-F) newsletter delivered at ~noon that highlights the story of the day from the 47th President."
Результат:
```json 
{
  "type": "TrueNews",
  "title": "Инфляция в США в апреле снизилась до 2,3%",
  "description": "что свидетельствует о том, что экономическая политика Трампа начинает работать"
}
```

## Пример 7:
Твит: "PRESIDENT TRUMP OFFICIALLY SIGNS 'STRATEGIC ECONOMIC PARTNERSHIP' WITH SAUDI ARABIA."
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
{
  "type": "inside",
  "title": "Альткоины достигли первого 'Золотого креста' за 4 года!",
  "description": "Золотой крест — технический индикатор, сигнализирующий о возможном бычьем тренде. В прошлый раз это привело к росту рынка в 150 раз за несколько недель, начало нового бычьего ралли в мае 2025 года. Ниже список альткоинов, которые могут принести значительную прибыль."
}
```

## Пример 10: Проверка на дублирование
Если в первом или втором массиве уже был проанализирован твит "XRP обогнал USDT по капитализации", а новый твит гласит "XRP теперь #3 по рыночной капитализации", то:

```json
{
  "type": "alreadyPosted",
  "title": "",
  "description": ""
}
```

Проанализируй каждый твит из первого массива (новые твиты) и верни результат в виде массива JSON-объектов, где каждый объект соответствует анализу одного твита. Отвечай только в формате JSON без дополнительных комментариев.
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
            temperature=0.1,  # Настройка креативности ответа
            max_tokens=10000  # Максимальное количество токенов в ответе
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка при обращении к API: {str(e)}"

# Функция для получения твитов из базы данных
def get_recent_tweets():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        # Получаем твиты за последние 4 часа с isGrok IS NULL
        query = "SELECT id, url, tweet_text FROM tweets WHERE created_at >= NOW() - INTERVAL 4 HOUR AND isGrok IS NULL"
        cursor.execute(query)
        tweets = cursor.fetchall()

        # Проверяем, достаточно ли твитов
        if len(tweets) < 30:
            print("Менее 30 твитов за последние 4 часа.")
            cursor.close()
            connection.close()
            return [], [], []

        # Формируем JSON-объект из первых 30 твитов
        tweet_data = []
        tweet_info = []
        for tweet_id, url, tweet_text in tweets[:30]:
            tweet_data.append({"text": tweet_text})
            tweet_info.append({"id": tweet_id, "url": url})

        # Обновляем isGrok для обработанных твитов
        update_query = "UPDATE tweets SET isGrok = TRUE WHERE id = %s"
        for tweet in tweet_info:
            cursor.execute(update_query, (tweet["id"],))

        # Получаем ранее обработанные твиты из tweet_analysis
        analysis_query = """
        SELECT title, description 
        FROM tweet_analysis 
        WHERE type NOT IN ('alreadyPosted', 'isSpam', 'isFlood') 
        AND created_at >= NOW() - INTERVAL 10 HOUR
        """
        cursor.execute(analysis_query)
        analyzed_tweets = [
            {"text": f"{row[0]} {row[1]}" if row[0] and row[1] else ""}
            for row in cursor.fetchall()
        ]
        # Фильтруем пустые строки
        analyzed_tweets = [t for t in analyzed_tweets if t["text"]]

        connection.commit()
        cursor.close()
        connection.close()
        return tweet_data, tweet_info, analyzed_tweets
    except mysql.connector.Error as e:
        print(f"Ошибка подключения к базе данных: {str(e)}")
        return [], [], []

# Функция для сохранения результатов анализа в базу данных
def save_analysis_results(tweet_info, analysis_results):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO tweet_analysis (url, type, title, description, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        current_time = datetime.now()
        for tweet, analysis in zip(tweet_info, analysis_results):
            cursor.execute(insert_query, (
                tweet["url"],
                analysis["type"],
                analysis["title"],
                analysis["description"],
                current_time
            ))
        connection.commit()
        cursor.close()
        connection.close()
    except mysql.connector.Error as e:
        print(f"Ошибка сохранения результатов в базу данных: {str(e)}")

# Основной цикл
def main():
    # Получение твитов из базы данных
    new_tweets, tweet_info, analyzed_tweets = get_recent_tweets()

    if not new_tweets:
        print("Завершение работы: недостаточно новых твитов.")
        return

    print(f"Найдено {len(new_tweets)} новых твитов за последние 4 часа и {len(analyzed_tweets)} ранее обработанных твитов. Начинается анализ...")

    # Формируем JSON для отправки в Grok
    tweets_json = json.dumps({"new_tweets": new_tweets, "analyzed_tweets": analyzed_tweets}, ensure_ascii=False)

    # Инициализация истории сообщений с системным промптом
    conversation = [system_prompt, {"role": "user", "content": tweets_json}]

    # Отправка запроса и получение ответа
    response = send_message(conversation)

    try:
        # Проверяем, является ли ответ валидным JSON
        response_json = json.loads(response)
        if not isinstance(response_json, list):
            print("Ошибка: Ответ Grok не является массивом JSON")
            return

        # Выводим результат в консоль
        print("\nРезультат анализа твитов:")
        for tweet, analysis in zip(tweet_info, response_json):
            print(f"\nURL: {tweet['url']}")
            print(f"Тип: {analysis['type']}")
            print(f"Заголовок: {analysis['title']}")
            print(f"Описание: {analysis['description']}")

        # Сохраняем результаты анализа в базу данных
        save_analysis_results(tweet_info, response_json)

    except json.JSONDecodeError:
        print(f"Ошибка: Неверный формат ответа от Grok: {response}")
        return

if __name__ == "__main__":
    main()