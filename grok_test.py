from dotenv import load_dotenv
import os

load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")  # Безопасное использование ключа
# Querying chat models with xAI
from anthropic import Anthropic

client = Anthropic(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai",
)

prompt = (
            f"Найди информацию какие фонды или Smart money инвестировали в проект StormX (STMX)"
        )
message = client.messages.create(
    model="grok-beta",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
print(message.content)