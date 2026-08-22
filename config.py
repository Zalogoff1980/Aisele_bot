import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AI_MODEL = os.getenv("AI_MODEL", "gpt-5.6")
MEMORY_MODEL = os.getenv("MEMORY_MODEL", AI_MODEL)

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not configured")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not configured")
