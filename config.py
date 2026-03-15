"""Конфигурация из переменных окружения."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# AiTunnel (OpenAI-совместимый API)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.aitunnel.ru/v1/")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o")

# Временные файлы
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

