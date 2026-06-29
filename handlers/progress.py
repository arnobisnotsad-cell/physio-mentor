"""
handlers/progress.py
Progress display from SQLite stats.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from database.db import get_progress_stats
from services.formatter import escape

logger = logging.getLogger(__name__)

HOME_BTN = InlineKeyboardButton("🏠 Home", callback_data="menu:home")


def _bar(pct: int, width: int = 10) -> str:
    filled = int(min(pct, 100) / 100 * width)
    return "█" * filled + "░" * (width - filled)


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    try:
        stats = await get_progress_stats(user.id)
    except Exception as e:
        logger.error("Progress DB error: %s", e)
        await query.edit_message_text("⚠️ Could not load progress. Try /start.")
        return

    accuracy = 0
    if stats["mcq_attempted"] > 0:
        accuracy = int((stats["mcq_correct"] / stats["mcq_attempted"]) * 100)

    streak_emoji = "🔥" if stats["streak"] > 2 else "📅"
    name = escape(user.first_name or "Student")

    lines = [
        f"📊 *{name}'s Progress*",
        "",
        f"📖 Questions Read: *{stats['questions_viewed']}*",
        f"🧠 MCQ Sessions Played: *{stats['mcq_sessions']}*",
        "",
        "MCQ Accuracy:",
        f"`{_bar(accuracy)} {accuracy}%`",
        f"Correct: *{stats['mcq_correct']}* / *{stats['mcq_attempted']}* answered",
        "",
        f"⭐ Bookmarks Saved: *{stats['bookmarks']}*",
        f"{streak_emoji} Study Streak: *{stats['streak']} day{'s' if stats['streak'] != 1 else ''}*",
        "",
        "_Keep studying — consistency is the key to success\\!_",
    ]

    # Build safe MarkdownV2 text
    text = "\n".join(lines)

    await query.edit_message_text(
        text,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
    )


def register(app) -> None:
    app.add_handler(CallbackQueryHandler(show_progress, pattern="^menu:progress$"))
