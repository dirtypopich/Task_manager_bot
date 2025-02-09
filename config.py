import os
from dotenv import load_dotenv

load_dotenv()  # Загружаем переменные окружения
TOKEN = os.getenv("BOT_TOKEN")
