"""
bot.py â€” PhysioMentor AI
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

# â”€â”€â”€ Logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # Register handlers â€” ORDER MATTERS
    # ConversationHandlers must be registered before generic CallbackQueryHandlers
    from handlers import ask_guyton, mcq, search  # ConversationHandlers first
    ask_guyton.register(app)
    mcq.register(app)
    search.register(app)

    # Then simple CallbackQueryHandlers
    from handlers import menu, study, progress
    menu.register(app)
    study.register(app)
    progress.register(app)

    return app


async def startup(app: Application) -> None:
    """Run once before the bot starts processing updates."""
    logger.info("Initialising databaseâ€¦")
    await init_db()
    logger.info("Building search indexâ€¦")
    await populate_search_index()
    logger.info("Bot ready âœ“")


def main() -> None:
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = build_app()
    if WEBHOOK_URL:
        # â”€â”€ Production: webhook â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        logger.info("Starting in WEBHOOK mode: %s", WEBHOOK_URL)
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            drop_pending_updates=True,
            close_loop=False,
        )
    else:
        # â”€â”€ Development: polling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        logger.info("Starting in POLLING mode (development)")

        async def _run():
            await startup(app)
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot is running. Press Ctrl+C to stop.")
            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()

        asyncio.run(_run())


if __name__ == "__main__":
    main()

