"""
handlers/search.py
Text search across terms, cards, items, questions.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, MessageHandler,
    ConversationHandler, CommandHandler, filters,
)

from database import db
from services.formatter import escape

logger = logging.getLogger(__name__)

WAITING_QUERY = 1
HOME_BTN = InlineKeyboardButton("🏠 Home", callback_data="menu:home")

TYPE_EMOJI = {"term": "📚", "card": "🗂️", "item": "📄", "question": "❓"}
TYPE_LABEL = {"term": "Topic", "card": "Card", "item": "Item", "question": "Question"}


async def entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔍 *Search*\n\nType any keyword to search across all topics, cards, items, and questions\\.\n\n"
        "_Examples: 'plasma', 'starling', 'oxygen curve', 'renal'_",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
    )
    return WAITING_QUERY


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text.strip()
    if len(query_text) < 2:
        await update.message.reply_text("Please type at least 2 characters.")
        return WAITING_QUERY

    try:
        results = await db.search_content(query_text, limit=12)
    except Exception as e:
        logger.error("Search error: %s", e)
        await update.message.reply_text("⚠️ Search failed. Please try again.")
        return WAITING_QUERY

    if not results:
        await update.message.reply_text(
            f"No results found for *{escape(query_text)}*\\.\n\nTry a different keyword\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
        )
        return WAITING_QUERY

    # Group by type
    grouped: dict[str, list] = {"term": [], "card": [], "item": [], "question": []}
    for r in results:
        t = r["entity_type"]
        if t in grouped:
            grouped[t].append(r)

    lines = [f"🔍 *Results for:* _{escape(query_text)}_\n"]
    buttons = []

    for entity_type, items in grouped.items():
        if not items:
            continue
        emoji = TYPE_EMOJI[entity_type]
        label = TYPE_LABEL[entity_type]
        lines.append(f"\n{emoji} *{label}s:*")

        for r in items[:4]:  # Max 4 per type
            keyword = r["keyword"]
            entity_id = r["entity_id"]
            lines.append(f"  • {escape(keyword[:60])}")

            # Add navigation button based on type
            if entity_type == "term":
                cb = f"study:cards:{entity_id}"
            elif entity_type == "card":
                cb = f"study:items:{entity_id}"
            elif entity_type == "item":
                cb = f"study:questions:{entity_id}"
            elif entity_type == "question":
                cb = f"study:answer:{entity_id}"
            else:
                continue

            buttons.append([InlineKeyboardButton(
                f"{emoji} {keyword[:45]}",
                callback_data=cb
            )])

    buttons.append([InlineKeyboardButton("🔍 Search Again", callback_data="menu:search")])
    buttons.append([HOME_BTN])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return WAITING_QUERY


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END


def register(app) -> None:
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(entry_callback, pattern="^menu:search$")],
        states={
            WAITING_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search),
            ],
        },
        fallbacks=[CommandHandler("start", cancel)],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
    app.add_handler(conv)
