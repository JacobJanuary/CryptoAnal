#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Crypto Analysis Script

This script extracts cryptocurrency data from a MySQL database,
sends requests to Claude 3.7 API for analytical information,
and saves the responses back to the database.

Author: Python Expert
Date: 2023-07-01
"""

import os
import time
import json
import logging
import mysql.connector
import anthropic
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crypto_analysis.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def parse_analysis_response(response_text: str) -> Dict[str, Any]:
    """
    Парсит ответ от Claude API и извлекает структурированные данные.

    Args:
        response_text (str): Текст ответа от Claude API

    Returns:
        Dict[str, Any]: Словарь с извлеченными данными
    """
    result = {
        "project_review": "",
        "top5_good": "",
        "top5_bad": "",
        "social_metrics": "",
        "bullrun_roi": "",
        "project_final_recomend": "",
        "rull_run_x": "",
        "grade": ""
    }

    # Разбиваем текст на секции по заголовкам
    sections = {}
    current_section = None
    lines = response_text.split('\n')

    for line in lines:
        if line.startswith('## '):
            current_section = line.strip('# \n')
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    # Извлекаем данные из секций
    if 'Обзор проекта' in sections:
        result["project_review"] = '\n'.join(sections['Обзор проекта']).strip()

    if '5 сильных метрик проекта' in sections:
        result["top5_good"] = '\n'.join(sections['5 сильных метрик проекта']).strip()

    if '5 слабых метрик проекта' in sections:
        result["top5_bad"] = '\n'.join(sections['5 слабых метрик проекта']).strip()

    # Ищем секцию с социальными метриками (может быть разное название)
    social_section_keys = [k for k in sections.keys() if 'Социальные метрики' in k or 'социальные метрики' in k.lower()]
    if social_section_keys:
        result["social_metrics"] = '\n'.join(sections[social_section_keys[0]]).strip()

    # Ищем секцию с потенциалом на буллране (может быть разное название)
    bullrun_section_keys = [k for k in sections.keys() if
                            'Потенциал проекта на буллране' in k or 'буллран' in k.lower()]
    if bullrun_section_keys:
        result["bullrun_roi"] = '\n'.join(sections[bullrun_section_keys[0]]).strip()

    # Ищем секцию с заключением (может быть разное название)
    conclusion_section_keys = [k for k in sections.keys() if 'Заключение' in k]
    if conclusion_section_keys:
        result["project_final_recomend"] = '\n'.join(sections[conclusion_section_keys[0]]).strip()

    # Ищем секцию с потенциальными X (может быть разное название)
    x_section_keys = [k for k in sections.keys() if 'Потенциальные Х' in k or 'потенциальные x' in k.lower()]
    if x_section_keys:
        x_section = '\n'.join(sections[x_section_keys[0]]).strip()

        # Извлекаем числовое значение X
        import re
        x_match = re.search(r'(\d+(?:\.\d+)?)\s*%', x_section)
        if x_match:
            result["rull_run_x"] = x_match.group(1)

    # Ищем оценку проекта
    grade_section_keys = [k for k in sections.keys() if 'Оценка проекта' in k]
    if grade_section_keys:
        grade_section = '\n'.join(sections[grade_section_keys[0]]).strip()

        # Извлекаем числовое значение оценки
        grade_match = re.search(r'(\d+)(?:\s*\/\s*100)?', grade_section)
        if grade_match:
            result["grade"] = grade_match.group(1)

    # Также ищем JSON блок, если он есть
    json_block = None
    in_json_block = False
    json_lines = []

    for line in lines:
        if line.strip() == '```json' or line.strip() == '{':
            in_json_block = True
            if line.strip() == '{':
                json_lines.append(line)
        elif line.strip() == '```' and in_json_block:
            in_json_block = False
        elif in_json_block:
            json_lines.append(line)

    if json_lines:
        try:
            json_text = '\n'.join(json_lines)
            # Если JSON начинается с { и не заканчивается }, добавляем }
            if json_text.strip().startswith('{') and not json_text.strip().endswith('}'):
                json_text += '\n}'
            json_data = json.loads(json_text)

            if 'rull_run_x' in json_data and not result["rull_run_x"]:
                result["rull_run_x"] = str(json_data['rull_run_x']).replace('%', '')

            if 'grade' in json_data and not result["grade"]:
                result["grade"] = str(json_data['grade'])
        except json.JSONDecodeError:
            # Если не удалось распарсить JSON, пробуем найти значения через регулярные выражения
            rull_run_match = re.search(r'"rull_run_x"\s*:\s*"?(\d+(?:\.\d+)?)"?', json_text)
            if rull_run_match and not result["rull_run_x"]:
                result["rull_run_x"] = rull_run_match.group(1)

            grade_match = re.search(r'"grade"\s*:\s*"?(\d+)"?', json_text)
            if grade_match and not result["grade"]:
                result["grade"] = grade_match.group(1)

    return result

class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self):
        """Initialize database connection parameters from environment variables."""
        self.host = os.getenv("MYSQL_HOST")
        self.user = os.getenv("MYSQL_USER")
        self.password = os.getenv("MYSQL_PASSWORD")
        self.database = os.getenv("MYSQL_DATABASE")
        self.connection = None
        self.cursor = None

    def connect(self) -> bool:
        """
        Establish connection to the MySQL database.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.cursor = self.connection.cursor(dictionary=True)
            logger.info("Successfully connected to the database")
            return True
        except mysql.connector.Error as err:
            logger.error(f"Database connection error: {err}")
            return False

    def disconnect(self) -> None:
        """Close database connection and cursor."""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            logger.info("Database connection closed")
        except mysql.connector.Error as err:
            logger.error(f"Error closing database connection: {err}")

    def get_favorite_cryptocurrencies(self) -> List[Dict[str, Any]]:
        """
        Retrieve favorite cryptocurrencies from the database.

        Returns:
            List[Dict[str, Any]]: List of dictionaries containing cryptocurrency data
        """
        cryptocurrencies = []
        try:
            query = """
                    SELECT id, name, symbol
                    FROM cmc_crypto
                    WHERE id IN (SELECT coin_id FROM cmc_favorites) AND project_review is NULL \
                    """
            self.cursor.execute(query)
            cryptocurrencies = self.cursor.fetchall()
            logger.info(f"Retrieved {len(cryptocurrencies)} favorite cryptocurrencies")
        except mysql.connector.Error as err:
            logger.error(f"Error retrieving favorite cryptocurrencies: {err}")

        return cryptocurrencies

    def update_crypto_analysis(self, crypto_id: int, analysis: str) -> bool:
        """
        Update the analysis fields for a cryptocurrency.

        Args:
            crypto_id (int): The ID of the cryptocurrency
            analysis (str): The analysis text from Claude 3.7

        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            # Парсим ответ для извлечения структурированных данных
            parsed_data = parse_analysis_response(analysis)

            # Обновляем все поля в базе данных
            query = """
                    UPDATE cmc_crypto
                    SET gemini_invest          = %s,
                        project_review         = %s,
                        top5_good              = %s,
                        top5_bad               = %s,
                        social_metrics         = %s,
                        bullrun_roi            = %s,
                        project_final_recomend = %s,
                        rull_run_x             = %s,
                        grade                  = %s
                    WHERE id = %s \
                    """

            self.cursor.execute(query, (
                analysis,
                parsed_data["project_review"],
                parsed_data["top5_good"],
                parsed_data["top5_bad"],
                parsed_data["social_metrics"],
                parsed_data["bullrun_roi"],
                parsed_data["project_final_recomend"],
                parsed_data["rull_run_x"],
                parsed_data["grade"] if parsed_data["grade"] else None,
                crypto_id
            ))

            self.connection.commit()
            logger.info(f"Updated analysis for cryptocurrency ID {crypto_id}")

            # Логируем извлеченные данные
            logger.info(f"Extracted data for {crypto_id}:")
            logger.info(f"rull_run_x: {parsed_data['rull_run_x']}")
            logger.info(f"grade: {parsed_data['grade']}")

            return True
        except mysql.connector.Error as err:
            logger.error(f"Error updating analysis for cryptocurrency ID {crypto_id}: {err}")
            return False
        except Exception as e:
            logger.error(f"Error parsing analysis for cryptocurrency ID {crypto_id}: {e}")
            return False


class ClaudeClient:
    """Manages interactions with the Claude 3.7 API."""

    def __init__(self):
        """Initialize Claude API client with API key from environment variables."""
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-3-7-sonnet-20250219"
        # Для отслеживания времени между запросами
        self.last_request_time = 0
        # Минимальный интервал между запросами (в секундах)
        self.request_interval = 10
        # Максимальное количество попыток при ошибке превышения лимита
        self.max_retries = 10
        # Время ожидания между повторными попытками (в секундах)
        self.retry_wait_time = 60

    def wait_for_rate_limit(self) -> None:
        """
        Обеспечивает минимальный интервал между запросами к API.
        """
        current_time = time.time()
        elapsed_time = current_time - self.last_request_time

        if elapsed_time < self.request_interval:
            wait_time = self.request_interval - elapsed_time
            logger.info(f"Rate limiting: waiting {wait_time:.2f} seconds before next request")
            time.sleep(wait_time)

    def extract_final_response(self, message) -> str:
        """
        Извлекает финальный ответ из сообщения Claude API, начиная с блока,
        содержащего фразу "## Обзор проекта".

        Args:
            message: Ответ от Claude API

        Returns:
            str: Финальный текст ответа
        """
        if not message.content or len(message.content) == 0:
            return "Не удалось получить ответ от API"

        # Ищем блок, содержащий "## Обзор проекта"
        overview_block_index = None
        for i, content_block in enumerate(message.content):
            if (content_block.type == "text" and
                    "## Обзор проекта" in content_block.text):
                overview_block_index = i
                break

        # Если нашли блок с обзором проекта
        if overview_block_index is not None:
            # Извлекаем текст из этого блока, начиная с "## Обзор проекта"
            overview_text = message.content[overview_block_index].text
            start_index = overview_text.find("## Обзор проекта")
            overview_text = overview_text[start_index:]

            # Собираем все последующие текстовые блоки
            result = [overview_text]
            for i in range(overview_block_index + 1, len(message.content)):
                if message.content[i].type == "text":
                    result.append(message.content[i].text)

            return "\n\n".join(result)

        # Если не нашли блок с обзором проекта, ищем блок с "# Анализ"
        analysis_block_index = None
        for i, content_block in enumerate(message.content):
            if (content_block.type == "text" and
                    "# Анализ" in content_block.text):
                analysis_block_index = i
                break

        # Если нашли блок с анализом
        if analysis_block_index is not None:
            # Собираем все текстовые блоки, начиная с блока анализа
            result = []
            for i in range(analysis_block_index, len(message.content)):
                if message.content[i].type == "text":
                    result.append(message.content[i].text)

            return "\n\n".join(result)

        # Если не нашли ни обзор проекта, ни анализ, возвращаем последний текстовый блок
        for content_block in reversed(message.content):
            if content_block.type == "text" and content_block.text.strip():
                return content_block.text

        # Если ничего не нашли, возвращаем текст первого блока
        return message.content[0].text

    def analyze_cryptocurrency(self, name: str, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Send a request to Claude 3.7 to analyze a cryptocurrency.

        Args:
            name (str): The name of the cryptocurrency
            symbol (str): The symbol of the cryptocurrency

        Returns:
            Tuple[bool, Optional[str]]: Success status and analysis text if successful
        """
        # Ожидаем необходимое время между запросами
        self.wait_for_rate_limit()

        prompt = f"\nРоль: Ты ведущий аналитик криптовалютного направления в BlackRock, чья экспертиза определяет судьбу цифровых активов в портфелях крупнейшего инвестиционного фонда мира. Моя работа — безошибочно оценивать риски и потенциал блокчейн-проектов, выявляя среди тысяч криптовалют те редкие жемчужины, способные принести 100-1000-кратную доходность. Благодаря уникальной методологии анализа рынка, я безупречно идентифицирую тренды, оцениваю риски и нахожу возможности, которые другие упускают, обеспечивая нашим клиентам доступ к самым перспективным проектам на ранних стадиях.Add to Conversation\n\nЗадание: Проанализируйте предоставленный мной криптовалютный проект, сосредоточившись на его ключевых инвестиционных аспектах и рисках. Я хочу понять его потенциал и ограничения.\n\nКонтекст: любая свежая критическая информация о проекте, которую вы можете найти в интернете на сайтах cryptorank.io, dropstab.com, coinmarketcap.com или других.\n Обязательно проведи поиск в интернете негативных и позитивных новостей относительно данного проекта или его СЕО.\n\nИнструкции: Следуйте этой схеме, расставляя приоритеты по наиболее важным аспектам:\n\n## 1. Обзор проекта (важно)\n- Какую проблему решает проект и для кого?\n- Кратко опишите основную технологию и подход\n- Текущая стадия развития (идея, тестнет, мейннет, устоявшийся)\n- Дата основания и основные достигнутые результаты\n\n## 2. Критические факторы инвестирования\n- Текущая рыночная капитализация и полностью разводненная оценка\n- Полезность токенов и механизмы начисления стоимости\n- Опыт ключевых членов команды (без указания конкретных имен, если нет уверенности)\n- Заметные спонсоры (типы венчурных фондов/инвесторов, а не конкретные имена, если нет уверенности)\n- Фактические показатели принятия (пользователи, TVL, транзакции - только если они поддаются проверке)\n- Основные конкуренты и дифференциация\n\n## 3. Оценка рисков\n- Определите 3-5 наиболее значимых рисков (регуляторные, технические, рыночные и т. д.).\n- Отметьте любые ограничения в вашем анализе, связанные с доступностью информации\n- Выделите области, в которых рекомендуется провести дополнительные исследования.\n\n## 4. Инвестиционная перспектива\n- Текущий ценовой контекст относительно исторических показателей\n- Ключевые катализаторы потенциального будущего роста\n- Общая позиция на рынке (ранняя стадия, фаза роста, устоявшаяся)\n- Соответствующая инвестиционная категория (спекулятивная, растущая, устоявшаяся).\n\nФормат: Все ответы должны быть на русском языке. Выведи:\n- Обзор проекта (3 предложения)\n- 5 сильных метрик проекта\n- 5 слабых метрик проекта\n- социальные метрики.  Активность и настроения в интернете. Краткая сводка на 3-4 предложения\n- потенциал проекта на булране (3-5 предложений)\n- заключение: рекомендация, возможный профит. не более 5 предложений\n- потенциальные Х в процентах. Без объяснений, предположение\n- оценка проекта от 1 до 100. На основе полученных данных и аналитики. Без объяснений\n\n+ JSON эти 2 параметра. \n- потенциальные Х в процентах. Без объяснений, предположение. Имя - rull_run_x\n- оценка проекта от 1 до 100. На основе полученных данных и аналитики. Без объяснений. Имя - grade\nОграничения:\nЕсли вы не уверены в конкретных данных, признайте их ограниченность, а не стройте догадки. Отдавайте предпочтение проверенной информации, а не прогнозам.\n\nДля любых расчетов или конкретных показателей:\n- Четко укажите источники или предположения.\n- Указывайте, когда данные могут быть устаревшими\n- При необходимости используйте диапазоны, а не точные цифры.\n\nПроект для анализа: {name} ({symbol})"

        retries = 0
        while retries <= self.max_retries:
            start_time = time.time()
            try:
                logger.info(f"Sending request to Claude 3.7 for {name} ({symbol})")

                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=64000,
                    temperature=0.1,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    tools=[
                        {
                            "type": "web_search_20250305",
                            "name": "web_search"
                        }
                    ],
                    system="You are a helpful assistant that provides accurate information about cryptocurrencies."
                )

                self.last_request_time = time.time()
                elapsed_time = self.last_request_time - start_time
                logger.info(f"Received response from Claude 3.7 for {name} ({symbol}) in {elapsed_time:.2f} seconds")

                # Извлекаем финальный ответ
                final_response = self.extract_final_response(message)

                # Выводим полученный ответ в консоль для отладки
                # Выводим полученный ответ в консоль для отладки
                print("\n" + "=" * 80)
                print(f"RESPONSE FOR {name} ({symbol}):")
                print("CONTENT BLOCKS:")
                for i, content in enumerate(message.content):
                    print(f"Block {i}: Type={content.type}")
                    if content.type == "text":
                        # Проверяем, содержит ли блок ключевые фразы
                        contains_overview = "## Обзор проекта" in content.text
                        contains_analysis = "# Анализ" in content.text
                        markers = []
                        if contains_overview:
                            markers.append("CONTAINS OVERVIEW")
                        if contains_analysis:
                            markers.append("CONTAINS ANALYSIS")

                        marker_text = f" [{', '.join(markers)}]" if markers else ""
                        preview = content.text[:200] + "..." if len(content.text) > 200 else content.text
                        print(f"Preview{marker_text}: {preview}")
                print("\nFINAL RESPONSE PREVIEW:")
                print(final_response[:500] + "..." if len(final_response) > 500 else final_response)
                print("=" * 80 + "\n")

                return True, final_response

            except anthropic.RateLimitError as e:
                retries += 1
                logger.warning(f"Rate limit exceeded for {name} ({symbol}). Retry {retries}/{self.max_retries}")

                if retries <= self.max_retries:
                    wait_time = self.retry_wait_time * retries  # Увеличиваем время ожидания с каждой попыткой
                    logger.info(f"Waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries exceeded for {name} ({symbol}). Giving up.")
                    return False, None

            except Exception as e:
                logger.error(f"Error analyzing cryptocurrency {name} ({symbol}): {e}")
                return False, None

        return False, None


def confirm_operation(cryptocurrencies: List[Dict[str, Any]]) -> bool:
    """
    Ask for user confirmation before proceeding with the analysis.

    Args:
        cryptocurrencies (List[Dict[str, Any]]): List of cryptocurrencies to analyze

    Returns:
        bool: True if user confirms, False otherwise
    """
    print(f"\nFound {len(cryptocurrencies)} cryptocurrencies to analyze:")
    for i, crypto in enumerate(cryptocurrencies, 1):
        print(f"{i}. {crypto['name']} ({crypto['symbol']})")

    confirmation = input("\nDo you want to proceed with the analysis? (y/n): ").strip().lower()
    return confirmation == 'y'


def main():
    """Main function to orchestrate the cryptocurrency analysis process."""
    logger.info("Starting cryptocurrency analysis script")

    # Initialize database manager and connect to the database
    db_manager = DatabaseManager()
    if not db_manager.connect():
        logger.error("Failed to connect to the database. Exiting.")
        return

    try:
        # Get favorite cryptocurrencies
        cryptocurrencies = db_manager.get_favorite_cryptocurrencies()

        if not cryptocurrencies:
            logger.warning("No favorite cryptocurrencies found. Exiting.")
            return

        # Ask for user confirmation
        if not confirm_operation(cryptocurrencies):
            logger.info("Operation cancelled by user. Exiting.")
            return

        # Initialize Claude client
        claude_client = ClaudeClient()

        # Process each cryptocurrency
        for crypto in cryptocurrencies:
            crypto_id = crypto['id']
            name = crypto['name']
            symbol = crypto['symbol']

            logger.info(f"Processing cryptocurrency: {name} ({symbol})")

            # Get analysis from Claude 3.7
            success, analysis = claude_client.analyze_cryptocurrency(name, symbol)

            if success and analysis:
                # Update database with the analysis
                update_success = db_manager.update_crypto_analysis(crypto_id, analysis)
                if update_success:
                    logger.info(f"Successfully updated analysis for {name} ({symbol})")
                else:
                    logger.error(f"Failed to update analysis for {name} ({symbol})")
            else:
                logger.error(f"Failed to get analysis for {name} ({symbol})")

        logger.info("Cryptocurrency analysis completed successfully")

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

    finally:
        # Ensure database connection is closed
        db_manager.disconnect()


if __name__ == "__main__":
    main()