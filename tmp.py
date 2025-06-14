import os
import mysql.connector
import requests
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate
import gspread
from google.oauth2.service_account import Credentials
# from gspread.models import CellFormat, Color # Removed this import
from gspread.utils import ValueInputOption

# Загружаем переменные окружения
load_dotenv()


class CryptoPriceAnalyzer:
    def __init__(self):
        self.db_connection = None
        self.cmc_api_key = os.getenv('CMC_API_KEY')
        self.cmc_base_url = 'https://pro-api.coinmarketcap.com'
        self.google_sheets_enabled = False
        self.setup_google_sheets()
        self.date_april_7 = "2025-04-07"
        self.date_may_23 = "2025-05-23"

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

    def get_historical_prices_batch(self, coin_ids, date_str):
        """Получение исторических цен для пакета валют на указанную дату"""
        headers = {
            'X-CMC_PRO_API_KEY': self.cmc_api_key,
            'Accept': 'application/json'
        }

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        timestamp = int(date_obj.timestamp())

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

            print(f"   Fetching historical prices for {date_str}, batch {i // batch_size + 1}...")
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                if 'data' in data and data['data']:  # Check if data['data'] is not None or empty
                    for coin_id_str, coin_data_entry in data['data'].items():
                        coin_id = int(coin_id_str)
                        actual_coin_data = coin_data_entry[0] if isinstance(coin_data_entry,
                                                                            list) and coin_data_entry else coin_data_entry

                        if actual_coin_data and 'quotes' in actual_coin_data and actual_coin_data['quotes']:
                            quote_list = actual_coin_data['quotes']
                            if isinstance(quote_list, list) and quote_list:
                                price_info = quote_list[0].get('quote', {}).get('USD', {})
                                price = price_info.get('price')
                                if price is not None:
                                    all_prices[coin_id] = price
                                else:
                                    print(
                                        f"     ⚠️  Price is None for coin ID {coin_id} on {date_str}. Quote: {price_info}")
                            else:
                                print(
                                    f"     ⚠️  'quotes' list is empty or not a list for coin ID {coin_id} on {date_str}. Quotes: {quote_list}")
                        else:
                            print(
                                f"     ⚠️  No 'quotes' in data for coin ID {coin_id} on {date_str}. Data: {str(actual_coin_data)[:200]}")
                else:
                    print(
                        f"   ❌ No 'data' field or empty 'data' in API response for historical prices ({date_str}). Status: {data.get('status')}")

            except requests.exceptions.HTTPError as http_err:
                print(f"   ❌ HTTP ошибка API (исторические {date_str}): {http_err} - {response.text}")
            except Exception as e:
                print(f"   ❌ Ошибка получения исторических цен для {date_str}: {e}")

        return all_prices

    def get_current_prices_batch(self, coin_ids):
        """Получение текущих цен для пакета валют"""
        headers = {
            'X-CMC_PRO_API_KEY': self.cmc_api_key,
            'Accept': 'application/json'
        }

        batch_size = 1000
        all_prices = {}

        for i in range(0, len(coin_ids), batch_size):
            batch_ids = coin_ids[i:i + batch_size]
            ids_str = ','.join(map(str, batch_ids))

            url = f"{self.cmc_base_url}/v1/cryptocurrency/quotes/latest"
            params = {'id': ids_str}
            print(f"   Fetching current prices, batch {i // batch_size + 1}...")
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                if 'data' in data and data['data']:
                    for coin_id_str, coin_data_entry in data['data'].items():
                        coin_id = int(coin_id_str)
                        # CMC API for latest quotes has a slightly different structure for 'data' items
                        if coin_data_entry and 'quote' in coin_data_entry and 'USD' in coin_data_entry['quote']:
                            price = coin_data_entry['quote']['USD'].get('price')
                            if price is not None:
                                all_prices[coin_id] = price
                            else:
                                print(
                                    f"     ⚠️  Price is None for coin ID {coin_id} (current). Quote: {coin_data_entry['quote']['USD']}")
                        else:
                            print(
                                f"     ⚠️  Unexpected data structure for coin ID {coin_id} (current). Data: {str(coin_data_entry)[:200]}")
                else:
                    print(
                        f"   ❌ No 'data' field or empty 'data' in API response for current prices. Status: {data.get('status')}")
            except requests.exceptions.HTTPError as http_err:
                print(f"   ❌ HTTP ошибка API (текущие): {http_err} - {response.text}")
            except Exception as e:
                print(f"   ❌ Ошибка получения текущих цен: {e}")

        return all_prices

    def calculate_price_change(self, old_price, new_price):
        """Вычисление процентного изменения цены"""
        if old_price is not None and new_price is not None and old_price > 0:
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

        coin_ids = [coin[0] for coin in coins]
        coin_dict = {coin[0]: {'name': coin[1], 'symbol': coin[2]} for coin in coins}

        print(f"\n🔄 Получение исторических цен ({self.date_april_7}) для {len(coin_ids)} валют...")
        prices_april_7 = self.get_historical_prices_batch(coin_ids, self.date_april_7)

        print(f"\n🔄 Получение исторических цен ({self.date_may_23}) для {len(coin_ids)} валют...")
        prices_may_23 = self.get_historical_prices_batch(coin_ids, self.date_may_23)

        print(f"\n🔄 Получение текущих цен для {len(coin_ids)} валют...")
        current_prices = self.get_current_prices_batch(coin_ids)

        results = []
        print("\n📊 Обработка данных...")
        for coin_id in coin_ids:
            coin_info = coin_dict[coin_id]
            price_d1 = prices_april_7.get(coin_id)
            price_d2 = prices_may_23.get(coin_id)
            current_price = current_prices.get(coin_id)

            change_d1_to_d2 = self.calculate_price_change(price_d1, price_d2)
            change_d2_to_current = self.calculate_price_change(price_d2, current_price)

            if price_d1 is not None or price_d2 is not None or current_price is not None:
                results.append({
                    'name': coin_info['name'],
                    'symbol': coin_info['symbol'],
                    'price_april_7': price_d1,
                    'price_may_23': price_d2,
                    'current_price': current_price,
                    'change_d1_d2_percent': change_d1_to_d2,
                    'change_d2_current_percent': change_d2_to_current
                })
            else:
                print(f"   ⚠️  Нет данных для {coin_info['symbol']} (ID: {coin_id}) по всем запрашиваемым датам.")

        results.sort(
            key=lambda x: x['change_d1_d2_percent'] if x['change_d1_d2_percent'] is not None else float('-inf'),
            reverse=True)

        self.display_results(results)

        historical_batches_d1 = (len(coin_ids) + 99) // 100
        historical_batches_d2 = (len(coin_ids) + 99) // 100
        current_batches = (len(coin_ids) + 999) // 1000
        total_requests = historical_batches_d1 + historical_batches_d2 + current_batches
        requests_without_batching = len(coin_ids) * 3

        print(f"\n💡 Экономия API токенов:")
        print(f"   Без пакетной обработки: {requests_without_batching} запросов")
        print(f"   С пакетной обработкой: {total_requests} запросов")
        print(f"   Экономия: {requests_without_batching - total_requests} запросов")

        if self.db_connection:
            self.db_connection.close()

    def format_percentage_change(self, change_percent, for_sheets=False):
        """Форматирует строку изменения процента с эмодзи"""
        if change_percent is None:
            return "N/A"

        change_str = f"{change_percent:.2f}%"
        # For sheets, emojis are fine. For console, some terminals might handle them better.
        if change_percent > 0:
            return f"🟢 +{change_str}"
        elif change_percent < 0:
            return f"🔴 {change_str}"
        else:
            return f"⚪️ {change_str}"

    def display_results(self, results):
        """Вывод результатов в виде таблицы"""
        if not results:
            print("❌ Нет данных для отображения")
            return

        print("\n" + "=" * 120)
        print("📊 АНАЛИЗ ИЗМЕНЕНИЯ ЦЕН КРИПТОВАЛЮТ")
        print("=" * 120)

        table_data = []
        for result in results:
            table_data.append([
                result['name'],
                result['symbol'],
                f"${result['current_price']:.4f}" if result['current_price'] is not None else "N/A",
                f"${result['price_may_23']:.4f}" if result['price_may_23'] is not None else "N/A",
                f"${result['price_april_7']:.4f}" if result['price_april_7'] is not None else "N/A",
                self.format_percentage_change(result['change_d1_d2_percent']),
                self.format_percentage_change(result['change_d2_current_percent'])
            ])

        date_d1_short_display = f'{self.date_april_7.split("-")[2]}.{self.date_april_7.split("-")[1]}'
        date_d2_short_display = f'{self.date_may_23.split("-")[2]}.{self.date_may_23.split("-")[1]}'

        headers = ['Проект', 'Символ', 'Текущая цена',
                   f'Цена {date_d2_short_display}',
                   f'Цена {date_d1_short_display}',
                   f'Рост {date_d1_short_display}-{date_d2_short_display} %',
                   f'Рост {date_d2_short_display}-Тек. %']

        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        print(f"\n📈 Всего проанализировано: {len(results)} валют")

        if self.google_sheets_enabled:
            self.export_to_google_sheets(results)

    def export_to_google_sheets(self, results):
        """Экспорт данных в Google Таблицу"""
        try:
            spreadsheet_name = os.getenv('GOOGLE_SPREADSHEET_NAME', 'Crypto Price Analysis')
            try:
                spreadsheet = self.gc.open(spreadsheet_name)
                print(f"📋 Открыта существующая таблица: {spreadsheet_name}")
            except gspread.SpreadsheetNotFound:
                spreadsheet = self.gc.create(spreadsheet_name)
                print(f"📋 Создана новая таблица: {spreadsheet_name}")
                editor_email = os.getenv('GOOGLE_SHEET_EDITOR_EMAIL')
                if editor_email:
                    try:
                        spreadsheet.share(editor_email, perm_type='user', role='writer')
                        print(f"✓ Таблица расшарена для {editor_email}")
                    except Exception as share_err:
                        print(f"⚠️ Ошибка расшаривания таблицы: {share_err}")

            try:
                worksheet = spreadsheet.sheet1
            except:
                worksheet = spreadsheet.add_worksheet(title="Analysis", rows="1000", cols="30")

            worksheet.clear()

            timestamp_str = datetime.now().strftime("%d.%m.%Y %H:%M")
            date_d1_short = f'{self.date_april_7.split("-")[2]}.{self.date_april_7.split("-")[1]}'
            date_d2_short = f'{self.date_may_23.split("-")[2]}.{self.date_may_23.split("-")[1]}'

            gs_headers = ['Проект', 'Символ', 'Текущая цена',
                          f'Цена {date_d2_short}',
                          f'Цена {date_d1_short}',
                          f'Рост {date_d1_short}-{date_d2_short} %',
                          f'Рост {date_d2_short}-Тек. %']

            num_cols = len(gs_headers)
            title_header_sheet = [f'Анализ криптовалют - {timestamp_str}'] + [''] * (num_cols - 1)
            worksheet.update('A1', [title_header_sheet], value_input_option=ValueInputOption.user_entered)
            worksheet.update('A3', [gs_headers], value_input_option=ValueInputOption.user_entered)

            rows_data = []
            for result in results:
                current_price_gs = result['current_price'] if result['current_price'] is not None else "N/A"
                price_may_23_gs = result['price_may_23'] if result['price_may_23'] is not None else "N/A"
                price_april_7_gs = result['price_april_7'] if result['price_april_7'] is not None else "N/A"

                rows_data.append([
                    result['name'],
                    result['symbol'],
                    current_price_gs,
                    price_may_23_gs,
                    price_april_7_gs,
                    self.format_percentage_change(result['change_d1_d2_percent'], for_sheets=True),
                    self.format_percentage_change(result['change_d2_current_percent'], for_sheets=True)
                ])

            if rows_data:
                worksheet.update(f'A4:{chr(64 + num_cols)}{3 + len(rows_data)}', rows_data,
                                 value_input_option=ValueInputOption.user_entered)

            self.format_google_sheet(worksheet, len(rows_data), num_cols)

            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
            print(f"✅ Данные экспортированы в Google Таблицу: {spreadsheet_url}")

        except Exception as e:
            print(f"❌ Ошибка экспорта в Google Sheets: {e}")

    def format_google_sheet(self, worksheet, data_rows, num_cols):
        """Форматирование Google таблицы с улучшенной визуализацией"""
        try:
            # Общий заголовок листа
            worksheet.merge_cells(f'A1:{chr(64 + num_cols)}1', merge_type='MERGE_ALL')
            worksheet.format('A1', {
                "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9},
                "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                               "bold": True, "fontSize": 14},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            })

            # Заголовки колонок таблицы
            header_range_gs = f'A3:{chr(64 + num_cols)}3'
            worksheet.format(header_range_gs, {
                "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85},
                "textFormat": {"bold": True, "fontSize": 10},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
                "borders": {
                    "top": {"style": "SOLID_MEDIUM"}, "bottom": {"style": "SOLID_MEDIUM"},
                    "left": {"style": "SOLID_THIN"}, "right": {"style": "SOLID_THIN"}
                }
            })

            if data_rows > 0:
                data_range_str_gs = f'A4:{chr(64 + num_cols)}{3 + data_rows}'
                worksheet.format(data_range_str_gs, {
                    "borders": {
                        "top": {"style": "SOLID_THIN"}, "bottom": {"style": "SOLID_THIN"},
                        "left": {"style": "SOLID_THIN"}, "right": {"style": "SOLID_THIN"}
                    }
                })

                # Формат для цен (колонки C, D, E - индексы 2, 3, 4)
                # Используем словарь напрямую для cell_format
                price_format_dict = {
                    'numberFormat': {'type': 'NUMBER', 'pattern': '$#,##0.0000'},
                    'horizontalAlignment': 'RIGHT'
                }
                worksheet.format(f'C4:E{3 + data_rows}', price_format_dict)

                percent_text_format_dict = {
                    'horizontalAlignment': 'RIGHT',
                }
                worksheet.format(f'F4:G{3 + data_rows}', percent_text_format_dict)

                light_grey_bg = {"red": 0.95, "green": 0.95, "blue": 0.95}  # Светло-серый
                requests_for_formatting = []
                for i in range(data_rows):
                    current_row_in_sheet = 4 + i
                    if i % 2 == 1:
                        requests_for_formatting.append({
                            'range': f'A{current_row_in_sheet}:{chr(64 + num_cols)}{current_row_in_sheet}',
                            'format': {'backgroundColor': light_grey_bg}
                        })
                if requests_for_formatting:
                    worksheet.batch_format(requests_for_formatting)

            if hasattr(worksheet, 'columns_auto_resize'):
                for col_idx in range(num_cols):
                    worksheet.columns_auto_resize(col_idx, col_idx)
            else:
                print("⚠️  Автоподбор ширины колонок может потребовать gspread v6+ или ручной настройки.")

        except Exception as e:
            print(f"⚠️  Ошибка форматирования Google Sheets: {e}")


def main():
    analyzer = CryptoPriceAnalyzer()
    analyzer.analyze_coins()


if __name__ == "__main__":
    main()