from app import app # Предполагается, что ваш главный файл app.py, и в нем есть переменная app = Flask(__name__)

if __name__ == "__main__":
    app.run()