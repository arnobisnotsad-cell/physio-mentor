"""
handlers/menu.py
/start command and main menu rendering.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from database.db import upsert_user, update_streak

logger = logging.getLogger(__name__)

MAIN_MENU_TEXT = (
    "👋 *Welcome to PhysioMentor AI\\!*\n\n"
    "Your AI\\-powered Physiology study companion\\.\n"
    "Choose a feature to get started:"
)

MAIN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📚 Study Cards",        callback_data="menu:study")],
    [InlineKeyboardButton("🤖 Ask Guyton",         callback_data="menu:guyton")],
    [InlineKeyboardButton("📝 Practice MCQ",       callback_data="menu:mcq")],
    [InlineKeyboardButton("🔍 Search",             callback_data="menu:search")],
    [InlineKeyboardButton("📊 My Progress",        callback_data="menu:progress")],
])


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send or edit to main menu. Works from both commands and callbacks."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            MAIN_MENU_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            MAIN_MENU_TEXT,
            parse_mode="MarkdownV2",
            reply_markup=MAIN_KEYBOARD,
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        await upsert_user(user.id, user.username, user.first_name)
        await update_streak(user.id)
    except Exception as e:
        logger.error("DB error on /start: %s", e)
    await send_main_menu(update, context)


async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_main_menu(update, context)


def register(app) -> None:
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(home_callback, pattern="^menu:home$"))
