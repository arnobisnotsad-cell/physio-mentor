"""
handlers/mcq.py
MCQ Practice flow:
Select Term → Card → Item → Difficulty → Count → Quiz (button-based, one at a time)
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, ConversationHandler,
    CommandHandler,
)

from database import db
from services.gemini import gemini
from services.formatter import escape

logger = logging.getLogger(__name__)

# States
SELECT_TERM = 1
SELECT_CARD = 2
SELECT_ITEM = 3
SELECT_DIFFICULTY = 4
SELECT_COUNT = 5
IN_QUIZ = 6

HOME_BTN = InlineKeyboardButton("🏠 Home", callback_data="menu:home")
DIFFICULTIES = ["Easy", "Medium", "Hard"]
COUNTS = [5, 10, 20]


async def entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("mcq", None)

    terms = await db.get_all_terms()
    if not terms:
        await query.edit_message_text("No content found. Please run seed.py first.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(t["name"], callback_data=f"mcq:term:{t['id']}")]
        for t in terms
    ]
    buttons.append([HOME_BTN])

    await query.edit_message_text(
        "📝 *Practice MCQ*\n\nStep 1/4 — Choose a topic:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SELECT_TERM


async def select_term(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    term_id = int(query.data.split(":")[-1])
    context.user_data["mcq"] = {"term_id": term_id}

    cards = await db.get_cards(term_id)
    if not cards:
        await query.answer("No cards found for this term.", show_alert=True)
        return SELECT_TERM

    buttons = [
        [InlineKeyboardButton(c["title"], callback_data=f"mcq:card:{c['id']}")]
        for c in cards
    ]
    buttons.append([HOME_BTN])

    await query.edit_message_text(
        "📝 *Practice MCQ*\n\nStep 2/4 — Choose a card:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SELECT_CARD


async def select_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    card_id = int(query.data.split(":")[-1])
    context.user_data["mcq"]["card_id"] = card_id

    items = await db.get_items(card_id)
    if not items:
        await query.answer("No items found for this card.", show_alert=True)
        return SELECT_CARD

    buttons = [
        [InlineKeyboardButton(i["title"], callback_data=f"mcq:item:{i['id']}:{i['title'][:30]}")]
        for i in items
    ]
    buttons.append([HOME_BTN])

    await query.edit_message_text(
        "📝 *Practice MCQ*\n\nStep 3/4 — Choose an item:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SELECT_ITEM


async def select_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    item_id = int(parts[2])
    item_title = ":".join(parts[3:])  # restore title (may contain colons)

    # Fetch full title from DB
    item = await db.get_item(item_id)
    full_title = item["title"] if item else item_title

    context.user_data["mcq"]["item_id"] = item_id
    context.user_data["mcq"]["item_title"] = full_title

    buttons = [
        [InlineKeyboardButton(d, callback_data=f"mcq:diff:{d}")]
        for d in DIFFICULTIES
    ]
    buttons.append([HOME_BTN])

    await query.edit_message_text(
        f"📝 *Practice MCQ*\n\nStep 4/4 — Choose difficulty:\n\n"
        f"Topic: _{escape(full_title)}_",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SELECT_DIFFICULTY


async def select_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    difficulty = query.data.split(":")[-1]
    context.user_data["mcq"]["difficulty"] = difficulty

    buttons = [
        [InlineKeyboardButton(f"{c} Questions", callback_data=f"mcq:count:{c}")]
        for c in COUNTS
    ]
    buttons.append([HOME_BTN])

    await query.edit_message_text(
        f"📝 *Practice MCQ*\n\nDifficulty: *{escape(difficulty)}*\n\nHow many questions?",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SELECT_COUNT


async def select_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    count = int(query.data.split(":")[-1])
    mcq_ctx = context.user_data["mcq"]
    mcq_ctx["count"] = count
    mcq_ctx["current"] = 0
    mcq_ctx["score"] = 0
    mcq_ctx["questions"] = []

    await query.edit_message_text(
        f"🧠 Generating *{count} {escape(mcq_ctx['difficulty'])}* MCQs on "
        f"*{escape(mcq_ctx['item_title'])}*\\.\n\n⏳ Please wait\\.\\.\\.",
        parse_mode="MarkdownV2",
    )

    try:
        questions = await gemini.generate_mcqs(
            item_title=mcq_ctx["item_title"],
            difficulty=mcq_ctx["difficulty"],
            count=count,
        )
    except Exception as e:
        logger.error("MCQ generation error: %s", e)
        questions = []

    if not questions:
        await query.message.reply_text(
            "⚠️ Failed to generate MCQs. AI may be busy. Please try again.",
            reply_markup=InlineKeyboardMarkup([[HOME_BTN]]),
        )
        return ConversationHandler.END

    mcq_ctx["questions"] = questions
    await _send_question(query.message, context, edit=False)
    return IN_QUIZ


async def _send_question(message, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    mcq_ctx = context.user_data["mcq"]
    idx = mcq_ctx["current"]
    questions = mcq_ctx["questions"]

    if idx >= len(questions):
        await _show_result(message, context)
        return

    q = questions[idx]
    total = len(questions)
    progress = f"Question {idx + 1}/{total}"

    q_text = escape(q.get("q", "Question text missing"))
    options = q.get("options", [])

    lines = [
        f"📝 *{escape(progress)}*",
        "",
        q_text,
        "",
    ]
    text = "\n".join(lines)

    option_labels = ["A", "B", "C", "D"]
    buttons = [
        [InlineKeyboardButton(
            f"{label}. {opt[3:] if opt.startswith(f'{label}. ') else opt}",
            callback_data=f"mcq:ans:{i}"
        )]
        for i, (label, opt) in enumerate(zip(option_labels, options))
    ]

    markup = InlineKeyboardMarkup(buttons)
    if edit:
        await message.edit_text(text, parse_mode="MarkdownV2", reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chosen = int(query.data.split(":")[-1])
    mcq_ctx = context.user_data["mcq"]
    idx = mcq_ctx["current"]
    q = mcq_ctx["questions"][idx]
    correct = q.get("correct", 0)

    is_correct = chosen == correct
    if is_correct:
        mcq_ctx["score"] += 1

    options = q.get("options", [])
    option_labels = ["A", "B", "C", "D"]

    result_emoji = "✅" if is_correct else "❌"
    correct_label = option_labels[correct] if correct < len(option_labels) else "?"
    chosen_label  = option_labels[chosen]  if chosen  < len(option_labels) else "?"

    exp = escape(q.get("explanation", ""))
    why = escape(q.get("why_wrong", ""))

    lines = [
        f"{result_emoji} *{'Correct\\!' if is_correct else 'Wrong'}*",
        "",
        f"Your answer: *{chosen_label}*",
        f"Correct answer: *{correct_label}*",
        "",
        f"📖 *Explanation:*\n{exp}",
    ]
    if why and not is_correct:
        lines += ["", f"ℹ️ *Why others are wrong:*\n{why}"]

    next_btn = InlineKeyboardButton(
        "Next ➡" if idx + 1 < len(mcq_ctx["questions"]) else "See Results 📊",
        callback_data="mcq:next"
    )
    markup = InlineKeyboardMarkup([[next_btn], [HOME_BTN]])

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        reply_markup=markup,
    )
    return IN_QUIZ


async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["mcq"]["current"] += 1

    if context.user_data["mcq"]["current"] >= len(context.user_data["mcq"]["questions"]):
        await _show_result(query.message, context, edit=True)
        return ConversationHandler.END

    await _send_question(query.message, context, edit=True)
    return IN_QUIZ


async def _show_result(message, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    mcq_ctx = context.user_data["mcq"]
    score = mcq_ctx["score"]
    total = len(mcq_ctx["questions"])
    accuracy = int((score / total) * 100) if total else 0

    def bar(pct: int, width: int = 10) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

    grade = "🏆 Excellent!" if accuracy >= 80 else "👍 Good!" if accuracy >= 60 else "📚 Keep studying!"

    text = (
        f"📊 *Quiz Complete\\!*\n\n"
        f"Score: *{score}/{total}*\n"
        f"Accuracy: `{bar(accuracy)} {accuracy}%`\n\n"
        f"{escape(grade)}"
    )

    # Save to DB
    try:
        user_id = message.chat_id
        await db.save_mcq_result(
            user_id=user_id,
            item_id=mcq_ctx.get("item_id", 0),
            difficulty=mcq_ctx.get("difficulty", ""),
            score=score,
            total=total,
        )
    except Exception as e:
        logger.error("Failed to save MCQ result: %s", e)

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Retry Same Topic", callback_data="menu:mcq")],
        [HOME_BTN],
    ])

    if edit:
        await message.edit_text(text, parse_mode="MarkdownV2", reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END


def register(app) -> None:
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(entry_callback, pattern="^menu:mcq$")],
        states={
            SELECT_TERM:       [CallbackQueryHandler(select_term,       pattern="^mcq:term:\\d+$")],
            SELECT_CARD:       [CallbackQueryHandler(select_card,       pattern="^mcq:card:\\d+$")],
            SELECT_ITEM:       [CallbackQueryHandler(select_item,       pattern="^mcq:item:\\d+:")],
            SELECT_DIFFICULTY: [CallbackQueryHandler(select_difficulty, pattern="^mcq:diff:")],
            SELECT_COUNT:      [CallbackQueryHandler(select_count,      pattern="^mcq:count:\\d+$")],
            IN_QUIZ: [
                CallbackQueryHandler(handle_answer,  pattern="^mcq:ans:\\d+$"),
                CallbackQueryHandler(next_question,  pattern="^mcq:next$"),
            ],
        },
        fallbacks=[CommandHandler("start", cancel)],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
    app.add_handler(conv)
