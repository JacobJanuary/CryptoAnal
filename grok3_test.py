import os
import json
import mysql.connector
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
import telegram
import asyncio

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

# Telegram настройки
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_channel_id = os.getenv("TELEGRAM_CHANNEL_ID")

if not telegram_bot_token or not telegram_channel_id:
    raise ValueError("Telegram configuration missing: TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID")

# Инициализация Telegram бота
bot = telegram.Bot(token=telegram_bot_token)

# Системный промпт для Grok
crypto_prompt = """
Role:
You are a highly experienced crypto market analyst with a proven track record in leading crypto media and research firms. Your expertise includes:
- Deep understanding of blockchain technology and crypto projects
- Ability to distinguish significant news from noise
- Skill in extracting key information from data streams
- Experience in technical analysis of crypto charts
- Knowledge of market psychology and trader behavior
- Ability to detect manipulation and misinformation

Task:
Analyze English-language tweets from crypto influencers and provide structured information in Russian for investment decision-making.

INPUT FORMAT
A JSON array of raw, unprocessed tweets:
[{"text": "tweet_text1"}, {"text": "tweet_text2"}, ...]

OUTPUT FORMAT
A JSON array where each object corresponds to one tweet and contains:
- "type": tweet category
- "title": concise Russian headline (3–5 words)
- "description": brief Russian summary (2–3 sentences)

ANALYSIS ALGORITHM

STEP 0: Duplicate Check
- For each tweet, check if it describes the same event as any previous tweet in the array (e.g., both mention XRP surpassing USDT in market cap).
- If so, return:
{"type": "alreadyPosted", "title": "", "description": ""}
- Do not analyze further.

STEP 1: Quality and Relevance Filter
- If the tweet is purely promotional, spam, or lacks meaningful content (see detailed criteria below), return:
{"type": "isSpam", "title": "", "description": ""}
- Criteria for spam/irrelevance:
    - Contains advertising, referral, or promotional material; calls to retweet, like, follow, join chats, giveaways, airdrops, quick profit promises, NFT/token launches, or similar.
    - Lacks concrete information — only emotions, memes, greetings, thanks, off-topic chatter, or generic reactions ("to the moon!", "HODL", "soon", etc.).
    - Is just a link, a news headline, clickbait, rhetorical question, or personal conversation without facts, analysis, or new information.
    - Merely repeats or rephrases media headlines without meaningful details, facts, or context.
    - Does not provide new data, analysis, forecast, educational, or market-related value.
    - Duplicates the meaning of other tweets (merge similar news/events into a single entry).
    - Cannot impact the crypto market or provide insider information or sound technical analysis.

STEP 2: Informational Value Check
- Proceed only if the tweet contains at least one of the following:
    - Actual, market-moving news: launches, listings, hacks, partnerships, bans/permissions, regulatory decisions, major reports/lawsuits, policy changes, official investigations, etc.
    - Authoritative opinions or forecasts with specifics (well-reasoned, with data or context).
    - Market or fundamental analysis: stats, fund flows, trend analysis, institutional activity, liquidation levels, etc.
    - Technical analysis with explanation: levels, indicators, patterns, market signals — only if accompanied by reasoning.
    - Important insider information confirmed by data or trustworthy sources.
    - Valuable educational content about crypto markets, tools, or strategies (guides, explanations, step-by-step instructions).
- If none apply, return:
{"type": "isFlood", "title": "", "description": ""}

STEP 3: Content Classification
- Assign one of the following types:
    - "trueNews": verified news with sources (e.g., "Binance officially announces token X listing")
    - "fakeNews": unverified info, rumors (e.g., "Rumor: SEC to approve Bitcoin ETF soon")
    - "inside": insider information (e.g., "My source at company X reports upcoming partnership")
    - "tutorial": educational material (e.g., "How to set up MetaMask for Ethereum")
    - "analitics": technical analysis (e.g., "BTC forms double bottom on 4H chart")
    - "trading": trading idea (e.g., "Considering ETH entry at $1800")
    - "others": other valuable tweets not fitting above categories
- If ambiguous, prioritize: trueNews > inside > analitics > trading > tutorial > fakeNews > others

STEP 4: Title and Description Generation
- For valuable tweets:
    - Title: 2–3 words in Russian, reflecting the tweet’s key info
    - Description: 2 sentences in Russian, expanding on the title and clearly conveying the tweet’s essence (15 words maximum)
- Important:
    - Use professional crypto market terminology
    - State facts directly, without phrases like "the author says" or "the tweet reports"
    - Do not invent or infer information not present in the tweet
    - Convey the original meaning as accurately as possible

EXAMPLES

Spam/Flood Examples (should return isSpam or isFlood):
- "Just bought more $BTC at $36,500. I believe we're heading to $50K by the end of the year based on the current market structure." (isFlood — no confirmation, insider info, or analysis)
- "Check out our new NFT collection dropping tomorrow! 10,000 unique pieces, don't miss out!" (isSpam)
- "Crypto is the future of finance! We're all going to make it! #WAGMI #BTC" (isFlood)
- "I've been analyzing BTC charts all day. The market is definitely moving to the right." (isFlood)
- "Доброе утро, криптосообщество! Как настроение?" (isFlood)
- "Присоединяйтесь к нашему Discord-каналу для обсуждения криптовалют!" (isSpam)
- "People will regard 1k chainlink next year as just as impossible to buy for normies as 21 btc is today" (isFlood — unsubstantiated claim)
"""

# Системный промпт в формате словаря
system_prompt = {
    "role": "system",
    "content": crypto_prompt
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
        print(f"Ошибка при обращении к API: {str(e)}")
        return None

# Функция для получения твитов из базы данных
def get_recent_tweets():
    print("Запуск get_recent_tweets...")
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        # Получаем твиты за последние 8 часов с isGrok IS NULL
        print("Выполняем запрос для новых твитов...")
        query = "SELECT id, url, tweet_text FROM tweets WHERE created_at >= NOW() - INTERVAL 8 HOUR AND isGrok IS NULL"
        cursor.execute(query)
        tweets = cursor.fetchall()
        print(f"Получено {len(tweets)} новых твитов")

        # Проверяем, достаточно ли твитов
        if len(tweets) < 100:
            print("Менее 100 твитов за последние 8 часа.")
            cursor.close()
            connection.close()
            return [], []

        # Формируем JSON-объект из первых 30 твитов
        tweet_data = []
        tweet_info = []
        for tweet_id, url, tweet_text in tweets[:100]:
            tweet_data.append({"text": tweet_text})
            tweet_info.append({"id": tweet_id, "url": url, "text": tweet_text})
        print(f"Сформировано {len(tweet_data)} новых твитов для анализа")

        # Обновляем isGrok для обработанных твитов
        update_query = "UPDATE tweets SET isGrok = TRUE WHERE id = %s"
        for tweet in tweet_info:
            cursor.execute(update_query, (tweet["id"],))
        print("Обновлены флаги isGrok для новых твитов")

        connection.commit()
        cursor.close()
        connection.close()
        print("get_recent_tweets завершена успешно")
        return tweet_data, tweet_info
    except mysql.connector.Error as e:
        print(f"Ошибка подключения к базе данных: {str(e)}")
        return [], []

# Функция для сохранения результатов анализа в базу данных
def save_analysis_results(tweet_info, analysis_results):
    print("Сохранение результатов анализа...")
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
        print("Результаты анализа успешно сохранены")
    except mysql.connector.Error as e:
        print(f"Ошибка сохранения результатов в базу данных: {str(e)}")

# Функция для вывода и отправки отсортированных результатов в Telegram
async def print_sorted_analysis(tweet_info, analysis_results):
    print("\nФорматированный вывод для Telegram:")

    # Словарь эмодзи по типам новостей и контексту
    emojis = {
        # Общие категории
        "Новости": "📢",
        "Слухи": "❓",
        "инсайды": "🔍",
        "технический анализ": "📊",
        "торговые идеи": "💰",
        "прогнозы": "🔮",
        "обучение": "📚",
        # Контекстные эмодзи
        "рост": "📈",
        "падение": "📉",
        "биткоин": "₿",
        "btc": "₿",
        "bitcoin": "₿",
        "ethereum": "Ξ",
        "eth": "Ξ",
        "партнерство": "🤝",
        "запуск": "🚀",
        "листинг": "📋",
        "регулирование": "⚖️",
        "взлом": "🔓",
        "безопасность": "🔒",
        "закон": "📜",
        "суд": "⚖️",
        "предупреждение": "⚠️",
        "опасность": "🚨",
        "инвестиции": "💵",
        "доход": "💸",
        "кошелек": "👛",
        "новая функция": "✨",
        "обновление": "🔄",
        "успех": "✅",
        "провал": "❌",
        "внимание": "👀",
        "важно": "‼️",
        "инновации": "💡",
        "платежи": "💳",
        "nft": "🖼️",
        "defi": "🏦",
        "майнинг": "⛏️",
        "staking": "🥩",
        "комиссия": "💲",
        "халвинг": "✂️",
        "токен": "🪙",
        "ликвидность": "💧",
        "волатильность": "🎢"
    }

    # Определяем категории, эмодзи и их соответствие типам
    categories = [
        ("📰 Новости", ["trueNews"], "Новости"),
        ("🗣️ Слухи", ["fakeNews"], "Слухи"),
        ("🔍 Инсайд", ["inside"], "Инсайды"),
        ("📚 Учеба", ["tutorial"], "обучение"),
        ("📊 Аналитика и трейдинг", ["analitics", "trading"], "Трейдинг"),
        ("🌐 Другое", ["others"], "Другое")
    ]

    # Зарезервированные символы Markdown V2, которые нужно экранировать
    markdown_v2_reserved_chars = r'_*[]()~`>#-+=|{.}!'

    # Функция для экранирования зарезервированных символов
    def escape_markdown_v2(text):
        for char in markdown_v2_reserved_chars:
            text = text.replace(char, f'\\{char}')
        return text

    # Формируем сообщение в формате Markdown V2
    output = ["*Криптоанализ твитов* 🌟\n"]
    messages_to_send = []

    for category_name, category_types, category_emoji_key in categories:
        # Фильтруем твиты, соответствующие текущей категории
        relevant_tweets = [
            (tweet, analysis) for tweet, analysis in zip(tweet_info, analysis_results)
            if analysis["type"] in category_types and analysis["title"] and analysis["description"]
        ]

        if relevant_tweets:
            output.append(f"*{category_name}*\n")
            for tweet, analysis in relevant_tweets:
                # Экранируем специальные символы для Markdown V2
                title = escape_markdown_v2(analysis["title"])
                description = escape_markdown_v2(analysis["description"])
                url = escape_markdown_v2(tweet["url"])

                # Определяем эмодзи для твита
                emoji = emojis.get(category_emoji_key, "📢")
                # Ищем контекстные эмодзи в title и description
                combined_text = (analysis["title"] + " " + analysis["description"]).lower()
                for key, value in emojis.items():
                    if key in combined_text and key not in ["Новости", "Слухи", "инсайды", "технический анализ",
                                                          "торговые идеи", "прогнозы", "обучение"]:
                        emoji = value
                        break
                # Добавляем твит в вывод
                output.append(f"*{title} {emoji}*\n{description}\n[Источник]({url})\n")
            output.append("\n")

    # Объединяем строки для полного сообщения
    full_output = "".join(output)
    print(full_output)

    # Разбиваем сообщение на части, если оно слишком длинное
    MAX_MESSAGE_LENGTH = 4096
    current_message = ["*Криптоанализ твитов* 🌟\n"]
    current_length = len(current_message[0])

    for line in output[1:]:
        line_length = len(line)
        # Если добавление строки превысит лимит, отправляем текущую часть
        if current_length + line_length > MAX_MESSAGE_LENGTH:
            messages_to_send.append("".join(current_message))
            current_message = []
            current_length = 0
            # Если строка — это заголовок категории, начинаем с него
            if line.startswith("*") and not line.startswith("*Криптоанализ"):
                current_message.append(line)
                current_length = line_length
            else:
                # Если это твит, начинаем с предыдущего заголовка категории
                last_category = next((cat[0] for cat in categories if cat[0] in "".join(output[:output.index(line)])),
                                     None)
                if last_category:
                    current_message.append(f"*{last_category}*\n")
                    current_length = len(current_message[-1])
                current_message.append(line)
                current_length += line_length
        else:
            current_message.append(line)
            current_length += line_length

    # Добавляем последнюю часть, если она не пуста
    if current_message:
        messages_to_send.append("".join(current_message))

    # Отправляем каждую часть в Telegram-канал
    for i, message in enumerate(messages_to_send, 1):
        try:
            await bot.send_message(
                chat_id=telegram_channel_id,
                text=message,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
            print(f"Часть {i} сообщения успешно отправлена в Telegram-канал {telegram_channel_id}")
        except telegram.error.TelegramError as e:
            print(f"Ошибка отправки части {i} сообщения в Telegram: {str(e)}")

# Основной цикл
async def main():
    print("Запуск основного цикла...")
    # Получение твитов из базы данных
    tweet_data, tweet_info = get_recent_tweets()
    print(f"get_recent_tweets вернул: {len(tweet_data)} твитов")

    if not tweet_data:
        print("Завершение работы: недостаточно новых твитов.")
        return

    print(f"Найдено {len(tweet_data)} новых твитов за последние 8 часов. Начинается анализ...")

    # Формируем JSON для отправки в Grok
    tweets_json = json.dumps(tweet_data, ensure_ascii=False)
    print("JSON для Grok сформирован")

    # Инициализация истории сообщений с системным промптом
    conversation = [system_prompt, {"role": "user", "content": tweets_json}]

    # Отправка запроса и получение ответа
    print("Отправка запроса в Grok...")
    response = send_message(conversation)
    if not response:
        print("Не удалось получить ответ от Grok")
        return

    try:
        # Проверяем, является ли ответ валидным JSON
        print("Проверка ответа Grok на валидность JSON...")
        response_json = json.loads(response)
        if not isinstance(response_json, list):
            print("Ошибка: Ответ Grok не является массивом JSON")
            return

        # Выводим и отправляем отсортированные результаты
        await print_sorted_analysis(tweet_info, response_json)

        # Сохраняем результаты анализа в базу данных
        save_analysis_results(tweet_info, response_json)

    except json.JSONDecodeError:
        print(f"Ошибка: Неверный формат ответа от Grok: {response}")
        return

if __name__ == "__main__":
    asyncio.run(main())