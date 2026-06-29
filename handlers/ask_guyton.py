"""
handlers/ask_guyton.py
Ask Guyton AI flow — multi-turn conversation with follow-up buttons.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, MessageHandler,
    ConversationHandler, filters, CommandHandler,
)

from services.gemini import gemini
from services.formatter import escape

logger = logging.getLogger(__name__)

# States
WAITING_QUESTION = 1
HOME_BTN = InlineKeyboardButton("🏠 Home", callback_data="menu:home")

FOLLOWUP_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔄 Explain Simpler",   callback_data="guyton:simpler"),
        InlineKeyboardButton("📝 Exam Version",       callback_data="guyton:exam"),
    ],
    [
        InlineKeyboardButton("🏥 Clinical Only",      callback_data="guyton:clinical"),
        InlineKeyboardButton("⭐ High Yield Only",    callback_data="guyton:highyield"),
    ],
    [
        InlineKeyboardButton("❓ Ask Another",        callback_data="guyton:again"),
        HOME_BTN,
    ],
])

FOLLOWUP_PROMPTS = {
    "simpler":   "Explain this in very simple terms, as if teaching a first-year student. Use analogies.",
    "exam":      "Give me an exam-oriented concise version with key points only. Max 5 sentences.",
    "clinical":  "Focus only on the clinical correlations and bedside applications of this topic.",
    "highyield": "List only the high-yield exam points as a numbered list. Nothing else.",
}


async def entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("guyton_last_question", None)
    context.user_data.pop("guyton_last_answer", None)

    await query.edit_message_text(
        "🤖 *Ask Guyton*\n\n"
        "Type your Physiology question and I'll answer it in a structured, exam\\-oriented format\\.\n\n"
        "_Example: What is the Frank\\-Starling mechanism?_",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
    )
    return WAITING_QUESTION


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question = update.message.text.strip()
    if not question:
        await update.message.reply_text("Please type a question.")
        return WAITING_QUESTION

    context.user_data["guyton_last_question"] = question
    thinking_msg = await update.message.reply_text("🤔 Professor Guyton is thinking…")

    try:
        answer = await gemini.ask_guyton(question)
        context.user_data["guyton_last_answer"] = answer
    except Exception as e:
        logger.error("Gemini error: %s", e)
        answer = "⚠️ AI is currently busy. Please try again in a few minutes."

    await thinking_msg.delete()

    # Truncate if too long
    if len(answer) > 4000:
        answer = answer[:3990] + "\n\n_\\.\\.\\. truncated_"

    await update.message.reply_text(
        answer,
        parse_mode="MarkdownV2",
        reply_markup=FOLLOWUP_KEYBOARD,
    )
    return WAITING_QUESTION


async def followup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    action = query.data.split(":")[-1]
    await query.answer()

    if action == "again":
        await query.edit_message_text(
            "❓ *Ask another question:*\n\nType your next Physiology question\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
        )
        context.user_data.pop("guyton_last_question", None)
        return WAITING_QUESTION

    last_q = context.user_data.get("guyton_last_question", "")
    last_a = context.user_data.get("guyton_last_answer", "")

    if not last_q:
        await query.answer("No previous question found.", show_alert=True)
        return WAITING_QUESTION

    followup_instruction = FOLLOWUP_PROMPTS.get(action, "")
    combined_prompt = (
        f"Previous question: {last_q}\n\n"
        f"Previous answer summary: {last_a[:500]}\n\n"
        f"Now: {followup_instruction}"
    )

    await query.edit_message_text("🤔 Thinking…", reply_markup=None)

    try:
        answer = await gemini.ask_guyton(combined_prompt)
    except Exception as e:
        logger.error("Gemini followup error: %s", e)
        answer = "⚠️ AI is currently busy."

    if len(answer) > 4000:
        answer = answer[:3990] + "\n\n_\\.\\.\\. truncated_"

    await query.edit_message_text(
        answer,
        parse_mode="MarkdownV2",
        reply_markup=FOLLOWUP_KEYBOARD,
    )
    return WAITING_QUESTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Returning to main menu. Use /start.")
    return ConversationHandler.END


def register(app) -> None:
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(entry_callback, pattern="^menu:guyton$")],
        states={
            WAITING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question),
                CallbackQueryHandler(followup_callback, pattern="^guyton:(simpler|exam|clinical|highyield|again)$"),
            ],
        },
        fallbacks=[CommandHandler("start", cancel)],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
    app.add_handler(conv)
