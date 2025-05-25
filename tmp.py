import os
import mysql.connector
import requests
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate
import gspread
from google.oauth2.service_account import Credentials

# Загружаем переменные окружения
load_dotenv()


class CryptoPriceAnalyzer:
    def __init__(self):
        self.db_connection = None
        self.cmc_api_key = os.getenv('CMC_API_KEY')
        self.cmc_base_url = 'https://pro-api.coinmarketcap.com'
        self.google_sheets_enabled = False
        self.setup_google_sheets()

    def setup_google_sheets(self):
        """Настройка подключения к Google Sheets"""
        try:
            credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
            if not credentials_path or not os.path.exists(credentials_path):
                print("⚠️  Google Sheets отключены: файл credentials не найден")
                return

            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            credentials = Credentials.from_service_account_file(credentials_path, scopes=scope)
            self.gc = gspread.authorize(credentials)
            self.google_sheets_enabled = True
            print("✅ Google Sheets API подключен")

        except Exception as e:
            print(f"⚠️  Ошибка подключения Google Sheets: {e}")
            self.google_sheets_enabled = False

    def connect_db(self):
        """Подключение к MySQL базе данных"""
        try:
            self.db_connection = mysql.connector.connect(
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('MYSQL_DATABASE'),
                port=int(os.getenv('DB_PORT', 3306))
            )
            print("✅ Успешно подключен к базе данных")
            return True
        except mysql.connector.Error as err:
            print(f"❌ Ошибка подключения к БД: {err}")
            return False

    def get_favorite_coins(self):
        """Получение списка избранных валют"""
        try:
            cursor = self.db_connection.cursor()
            query = """
                    SELECT id, name, symbol
                    FROM cmc_crypto
                    WHERE id IN (SELECT coin_id FROM cmc_favorites)
                    """
            cursor.execute(query)
            coins = cursor.fetchall()
            cursor.close()

            print(f"📋 Найдено {len(coins)} избранных валют")
            return coins
        except mysql.connector.Error as err:
            print(f"❌ Ошибка запроса к БД: {err}")
            return []

    def get_historical_prices_batch(self, coin_ids, date_str="2025-04-07"):
        """Получение исторических цен для пакета валют"""
        headers = {
            'X-CMC_PRO_API_KEY': self.cmc_api_key,
            'Accept': 'application/json'
        }

        # Конвертируем дату в timestamp
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        timestamp = int(date_obj.timestamp())

        # CMC API принимает до 100 ID за раз
        batch_size = 100
        all_prices = {}

        for i in range(0, len(coin_ids), batch_size):
            batch_ids = coin_ids[i:i + batch_size]
            ids_str = ','.join(map(str, batch_ids))

            url = f"{self.cmc_base_url}/v1/cryptocurrency/quotes/historical"
            params = {
                'id': ids_str,
                'time_start': timestamp,
                'time_end': timestamp,
                'count': 1,
                'interval': 'daily'
            }

            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        for coin_id_str, coin_data in data['data'].items():
                            coin_id = int(coin_id_str)
                            if 'quotes' in coin_data and coin_data['quotes']:
                                price = coin_data['quotes'][0]['quote']['USD']['price']
                                all_prices[coin_id] = price
                else:
                    print(f"❌ Ошибка API (исторические): {response.status_code}")
            except Exception as e:
                print(f"❌ Ошибка получения исторических цен: {e}")

        return all_prices

    def get_current_prices_batch(self, coin_ids):
        """Получение текущих цен для пакета валют"""
        headers = {
            'X-CMC_PRO_API_KEY': self.cmc_api_key,
            'Accept': 'application/json'
        }

        # CMC API принимает до 5000 ID за раз для текущих цен
        batch_size = 1000
        all_prices = {}

        for i in range(0, len(coin_ids), batch_size):
            batch_ids = coin_ids[i:i + batch_size]
            ids_str = ','.join(map(str, batch_ids))

            url = f"{self.cmc_base_url}/v1/cryptocurrency/quotes/latest"
            params = {'id': ids_str}

            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        for coin_id_str, coin_data in data['data'].items():
                            coin_id = int(coin_id_str)
                            price = coin_data['quote']['USD']['price']
                            all_prices[coin_id] = price
                else:
                    print(f"❌ Ошибка API (текущие): {response.status_code}")
            except Exception as e:
                print(f"❌ Ошибка получения текущих цен: {e}")

        return all_prices

    def calculate_price_change(self, old_price, new_price):
        """Вычисление процентного изменения цены"""
        if old_price and new_price and old_price > 0:
            return ((new_price - old_price) / old_price) * 100
        return None

    def analyze_coins(self):
        """Основная функция анализа"""
        if not self.connect_db():
            return

        if not self.cmc_api_key:
            print("❌ API ключ Coinmarketcap не найден в .env файле")
            return

        coins = self.get_favorite_coins()
        if not coins:
            print("❌ Не найдено избранных валют")
            return

        # Извлекаем ID для пакетных запросов
        coin_ids = [coin[0] for coin in coins]
        coin_dict = {coin[0]: {'name': coin[1], 'symbol': coin[2]} for coin in coins}

        print(f"\n🔄 Получение исторических цен для {len(coin_ids)} валют...")
        historical_prices = self.get_historical_prices_batch(coin_ids)

        print(f"🔄 Получение текущих цен для {len(coin_ids)} валют...")
        current_prices = self.get_current_prices_batch(coin_ids)

        results = []

        print("\n📊 Обработка данных...")
        for coin_id in coin_ids:
            coin_info = coin_dict[coin_id]
            historical_price = historical_prices.get(coin_id)
            current_price = current_prices.get(coin_id)

            if historical_price and current_price:
                price_change = self.calculate_price_change(historical_price, current_price)

                results.append({
                    'name': coin_info['name'],
                    'symbol': coin_info['symbol'],
                    'price_april_7': historical_price,
                    'current_price': current_price,
                    'change_percent': price_change
                })
            else:
                print(f"   ⚠️  Нет данных для {coin_info['symbol']} (ID: {coin_id})")

        # Сортируем по изменению цены (по убыванию)
        results.sort(key=lambda x: x['change_percent'] if x['change_percent'] else float('-inf'), reverse=True)

        # Выводим таблицу
        self.display_results(results)

        # Статистика API запросов
        historical_batches = (len(coin_ids) + 99) // 100  # округляем вверх
        current_batches = (len(coin_ids) + 999) // 1000  # округляем вверх
        total_requests = historical_batches + current_batches

        print(f"\n💡 Экономия API токенов:")
        print(f"   Без пакетной обработки: {len(coin_ids) * 2} запросов")
        print(f"   С пакетной обработкой: {total_requests} запросов")
        print(f"   Экономия: {len(coin_ids) * 2 - total_requests} запросов")

        # Закрываем соединение с БД
        if self.db_connection:
            self.db_connection.close()

    def display_results(self, results):
        """Вывод результатов в виде таблицы"""
        if not results:
            print("❌ Нет данных для отображения")
            return

        print("\n" + "=" * 80)
        print("📊 АНАЛИЗ ИЗМЕНЕНИЯ ЦЕН КРИПТОВАЛЮТ")
        print("=" * 80)

        table_data = []
        for result in results:
            change_str = f"{result['change_percent']:.2f}%" if result['change_percent'] else "N/A"

            # Добавляем эмодзи для наглядности
            if result['change_percent']:
                if result['change_percent'] > 0:
                    change_str = f"🟢 +{change_str}"
                else:
                    change_str = f"🔴 {change_str}"

            table_data.append([
                result['name'],
                result['symbol'],
                f"${result['price_april_7']:.4f}" if result['price_april_7'] else "N/A",
                f"${result['current_price']:.4f}" if result['current_price'] else "N/A",
                change_str
            ])

        headers = ['Проект', 'Символ', 'Цена 07.04.2025', 'Текущая цена', 'Изменение %']

        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        print(f"\n📈 Всего проанализировано: {len(results)} валют")

        # Экспорт в Google Sheets
        if self.google_sheets_enabled:
            self.export_to_google_sheets(results)

    def export_to_google_sheets(self, results):
        """Экспорт данных в Google Таблицу"""
        try:
            spreadsheet_name = os.getenv('GOOGLE_SPREADSHEET_NAME', 'Crypto Price Analysis')

            # Пытаемся открыть существующую таблицу или создать новую
            try:
                spreadsheet = self.gc.open(spreadsheet_name)
                print(f"📋 Открыта существующая таблица: {spreadsheet_name}")
            except gspread.SpreadsheetNotFound:
                spreadsheet = self.gc.create(spreadsheet_name)
                print(f"📋 Создана новая таблица: {spreadsheet_name}")

                # Делаем таблицу доступной для редактирования (опционально)
                spreadsheet.share('', perm_type='anyone', role='writer')

            # Получаем первый лист или создаем новый
            try:
                worksheet = spreadsheet.sheet1
            except:
                worksheet = spreadsheet.add_worksheet(title="Analysis", rows="1000", cols="20")

            # Очищаем лист
            worksheet.clear()

            # Подготавливаем данные для записи
            headers = ['Проект', 'Символ', 'Цена 07.04.2025', 'Текущая цена', 'Изменение %', 'Изменение $']

            # Добавляем заголовок с датой и временем
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            worksheet.update('A1:F1', [[f'Анализ криптовалют - {timestamp}', '', '', '', '', '']])

            # Добавляем заголовки таблицы
            worksheet.update('A3:F3', [headers])

            # Подготавливаем данные
            rows_data = []
            for result in results:
                change_percent = f"{result['change_percent']:.2f}%" if result['change_percent'] else "N/A"
                change_dollar = ""

                if result['price_april_7'] and result['current_price']:
                    change_dollar = f"${result['current_price'] - result['price_april_7']:.4f}"

                rows_data.append([
                    result['name'],
                    result['symbol'],
                    f"${result['price_april_7']:.4f}" if result['price_april_7'] else "N/A",
                    f"${result['current_price']:.4f}" if result['current_price'] else "N/A",
                    change_percent,
                    change_dollar
                ])

            # Записываем данные
            if rows_data:
                range_name = f'A4:F{3 + len(rows_data)}'
                worksheet.update(range_name, rows_data)

            # Форматирование таблицы
            self.format_google_sheet(worksheet, len(rows_data))

            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
            print(f"✅ Данные экспортированы в Google Таблицу: {spreadsheet_url}")

        except Exception as e:
            print(f"❌ Ошибка экспорта в Google Sheets: {e}")

    def format_google_sheet(self, worksheet, data_rows):
        """Форматирование Google таблицы"""
        try:
            # Заголовок
            worksheet.format('A1:F1', {
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
                'textFormat': {'bold': True, 'fontSize': 14},
                'horizontalAlignment': 'CENTER'
            })

            # Заголовки колонок
            worksheet.format('A3:F3', {
                'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8},
                'textFormat': {'bold': True},
                'horizontalAlignment': 'CENTER',
                'borders': {
                    'top': {'style': 'SOLID'},
                    'bottom': {'style': 'SOLID'},
                    'left': {'style': 'SOLID'},
                    'right': {'style': 'SOLID'}
                }
            })

            # Данные
            if data_rows > 0:
                data_range = f'A4:F{3 + data_rows}'
                worksheet.format(data_range, {
                    'borders': {
                        'top': {'style': 'SOLID'},
                        'bottom': {'style': 'SOLID'},
                        'left': {'style': 'SOLID'},
                        'right': {'style': 'SOLID'}
                    }
                })

                # Выравнивание колонок с ценами по правому краю
                worksheet.format(f'C4:F{3 + data_rows}', {
                    'horizontalAlignment': 'RIGHT'
                })

            # Автоподбор ширины колонок
            worksheet.columns_auto_resize(0, 5)

        except Exception as e:
            print(f"⚠️  Ошибка форматирования: {e}")


def main():
    analyzer = CryptoPriceAnalyzer()
    analyzer.analyze_coins()


if __name__ == "__main__":
    main()