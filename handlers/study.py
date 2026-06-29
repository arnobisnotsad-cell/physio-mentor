"""
handlers/study.py
Study Cards flow: Term → Card → Item → Question → Answer
All data from SQLite, no AI calls.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from database import db
from services.formatter import format_answer, escape
from config import ITEMS_PER_PAGE

logger = logging.getLogger(__name__)

HOME_BTN = InlineKeyboardButton("🏠 Home", callback_data="menu:home")
BACK_TO_TERMS_BTN = InlineKeyboardButton("◀ Terms", callback_data="study:terms")


def _paginate(items: list, page: int) -> tuple[list, bool, bool]:
    """Return (page_items, has_prev, has_next)."""
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    return items[start:end], page > 0, end < len(items)


async def show_terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    page = int(context.user_data.get("study_term_page", 0))
    # parse page from callback if present
    if query.data.startswith("study:terms:"):
        page = int(query.data.split(":")[-1])
    context.user_data["study_term_page"] = page

    try:
        terms = await db.get_all_terms()
    except Exception as e:
        logger.error("DB error fetching terms: %s", e)
        await query.edit_message_text("⚠️ Database error. Please try /start again.")
        return

    if not terms:
        await query.edit_message_text(
            "No terms found\\. Please run seed\\.py first\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
        )
        return

    page_items, has_prev, has_next = _paginate(list(terms), page)
    buttons = [
        [InlineKeyboardButton(t["name"], callback_data=f"study:cards:{t['id']}")]
        for t in page_items
    ]
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"study:terms:{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"study:terms:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([HOME_BTN])

    await query.edit_message_text(
        "📚 *Study Cards*\n\nChoose a topic:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    term_id = int(query.data.split(":")[-1])
    context.user_data["current_term_id"] = term_id

    try:
        term = await db.get_term(term_id)
        cards = await db.get_cards(term_id)
    except Exception as e:
        logger.error("DB error: %s", e)
        await query.edit_message_text("⚠️ Database error.")
        return

    if not cards:
        await query.edit_message_text(
            "No cards found for this term\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[BACK_TO_TERMS_BTN], [HOME_BTN]]),
        )
        return

    buttons = [
        [InlineKeyboardButton(c["title"], callback_data=f"study:items:{c['id']}")]
        for c in cards
    ]
    buttons.append([BACK_TO_TERMS_BTN, HOME_BTN])

    term_name = escape(term["name"]) if term else "Term"
    await query.edit_message_text(
        f"📚 *{term_name}*\n\nChoose a card:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    card_id = int(query.data.split(":")[-1])
    context.user_data["current_card_id"] = card_id

    try:
        card = await db.get_card(card_id)
        items = await db.get_items(card_id)
    except Exception as e:
        logger.error("DB error: %s", e)
        await query.edit_message_text("⚠️ Database error.")
        return

    if not items:
        await query.edit_message_text(
            "No items found for this card\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
        )
        return

    term_id = card["term_id"] if card else context.user_data.get("current_term_id", 0)
    back_btn = InlineKeyboardButton("◀ Cards", callback_data=f"study:cards:{term_id}")

    buttons = [
        [InlineKeyboardButton(i["title"], callback_data=f"study:questions:{i['id']}")]
        for i in items
    ]
    buttons.append([back_btn, HOME_BTN])

    card_title = escape(card["title"]) if card else "Card"
    await query.edit_message_text(
        f"🗂️ *{card_title}*\n\nChoose an item:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.split(":")[-1])
    context.user_data["current_item_id"] = item_id

    try:
        item = await db.get_item(item_id)
        questions = await db.get_questions(item_id)
    except Exception as e:
        logger.error("DB error: %s", e)
        await query.edit_message_text("⚠️ Database error.")
        return

    if not questions:
        await query.edit_message_text(
            "No questions found for this item\\.\n\nThis item hasn't been seeded with questions yet\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
        )
        return

    card_id = item["card_id"] if item else context.user_data.get("current_card_id", 0)
    back_btn = InlineKeyboardButton("◀ Items", callback_data=f"study:items:{card_id}")

    buttons = [
        [InlineKeyboardButton(
            f"Q{i+1}: {q['question_text'][:45]}{'…' if len(q['question_text']) > 45 else ''}",
            callback_data=f"study:answer:{q['id']}"
        )]
        for i, q in enumerate(questions)
    ]
    buttons.append([back_btn, HOME_BTN])

    item_title = escape(item["title"]) if item else "Item"
    await query.edit_message_text(
        f"📄 *{item_title}*\n\nChoose a question:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    question_id = int(parts[-1])
    # Handle bookmark toggle
    if "bookmark" in query.data:
        return await toggle_bookmark(update, context)

    context.user_data["current_question_id"] = question_id

    try:
        question = await db.get_question(question_id)
    except Exception as e:
        logger.error("DB error: %s", e)
        await query.edit_message_text("⚠️ Database error.")
        return

    if not question:
        await query.edit_message_text("Question not found\\.", parse_mode="MarkdownV2")
        return

    # Record view
    try:
        await db.record_question_view(query.from_user.id, question_id)
    except Exception:
        pass

    answer_text = format_answer(question)
    item_id = question["item_id"]
    back_btn = InlineKeyboardButton("◀ Questions", callback_data=f"study:questions:{item_id}")
    bookmark_btn = InlineKeyboardButton("⭐ Bookmark", callback_data=f"study:bookmark:{question_id}")

    buttons = [[bookmark_btn], [back_btn, HOME_BTN]]

    # Telegram message limit is 4096 chars; truncate if needed
    if len(answer_text) > 4000:
        answer_text = answer_text[:3990] + "\n\n\\.\\.\\. \\(truncated\\)"

    try:
        await query.edit_message_text(
            answer_text,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except Exception as e:
        logger.error("Message edit failed: %s", e)
        # Fallback: send as plain text
        await query.message.reply_text(
            "⚠️ Formatting error. Try /start and navigate again."
        )


async def toggle_bookmark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    question_id = int(query.data.split(":")[-1])
    user_id = query.from_user.id

    try:
        added = await db.toggle_bookmark(user_id, question_id)
        msg = "⭐ Bookmarked!" if added else "🗑️ Bookmark removed"
        await query.answer(msg, show_alert=False)
    except Exception as e:
        logger.error("Bookmark error: %s", e)
        await query.answer("Failed to update bookmark.", show_alert=True)


def register(app) -> None:
    app.add_handler(CallbackQueryHandler(show_terms,     pattern="^study:terms"))
    app.add_handler(CallbackQueryHandler(show_cards,     pattern="^study:cards:\\d+$"))
    app.add_handler(CallbackQueryHandler(show_items,     pattern="^study:items:\\d+$"))
    app.add_handler(CallbackQueryHandler(show_questions, pattern="^study:questions:\\d+$"))
    app.add_handler(CallbackQueryHandler(show_answer,    pattern="^study:answer:\\d+$"))
    app.add_handler(CallbackQueryHandler(toggle_bookmark, pattern="^study:bookmark:\\d+$"))
    # Entry from main menu
    app.add_handler(CallbackQueryHandler(show_terms,     pattern="^menu:study$"))
