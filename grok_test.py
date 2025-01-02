import os

XAI_API_KEY = os.getenv("XAI_API_KEY")  # Безопасное использование ключа
# Querying chat models with xAI
from anthropic import Anthropic

client = Anthropic(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai",
)

message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello, Claude"}]
)
print(message.content)