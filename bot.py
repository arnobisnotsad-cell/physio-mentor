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
    mcq.register(app)
    search.register(app)

    from handlers import menu, study, progress
    menu.register(app)
    study.register(app)
    progress.register(app)

    return app


async def _seed_database() -> None:
    """Idempotent — safe to run on every startup."""
    logger.info("Seeding database…")
    import seed
    await seed.main()


async def _run_webhook(app: Application) -> None:
    logger.info("Initialising database…")
    await init_db()
    await _seed_database()
    logger.info("Building search index…")
    await populate_search_index()
    logger.info("Bot ready ✓")

    logger.info("Starting in WEBHOOK mode: %s", WEBHOOK_URL)

    await app.initialize()
    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True,
    )
    logger.info("Bot is running (webhook). Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def _run_polling(app: Application) -> None:
    logger.info("Initialising database…")
    await init_db()
    await _seed_database()
    logger.info("Building search index…")
    await populate_search_index()
    logger.info("Bot ready ✓")

    logger.info("Starting in POLLING mode (development)")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot is running (polling). Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def main() -> None:
    print("MAIN STARTED", flush=True)
    app = build_app()
    print("APP BUILT", flush=True)

    if WEBHOOK_URL:
        print("ENTERING WEBHOOK MODE", flush=True)
        asyncio.run(_run_webhook(app))
    else:
        print("ENTERING POLLING MODE", flush=True)
        asyncio.run(_run_polling(app))


if __name__ == "__main__":
    print("SCRIPT STARTED", flush=True)
    main()