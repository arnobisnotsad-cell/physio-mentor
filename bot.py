"""
bot.py — PhysioMentor AI
Entry point. Initialises DB, registers all handlers, starts bot.

Modes:
  - Webhook (production):  set WEBHOOK_URL in .env
  - Polling (development): leave WEBHOOK_URL empty
"""

import asyncio
import logging
import sys

from telegram.ext import Application, ApplicationBuilder

from config import BOT_TOKEN, WEBHOOK_URL, PORT
from database.db import init_db, populate_search_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    from handlers import ask_guyton, mcq, search
    ask_guyton.register(app)