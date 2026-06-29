"""
services/formatter.py
Helpers for Telegram MarkdownV2 formatting.
MarkdownV2 requires escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
"""

import re

_ESCAPE_CHARS = r"\_*[]()~`>#+-=|{}.!"
_ESCAPE_RE = re.compile(r"([" + re.escape(_ESCAPE_CHARS) + r"])")


def escape(text: str) -> str:
    """Escape a plain string for MarkdownV2."""
    if not text:
        return ""
    return _ESCAPE_RE.sub(r"\\\1", text)


def bold(text: str) -> str:
    return f"*{escape(text)}*"


def italic(text: str) -> str:
    return f"_{escape(text)}_"


def code(text: str) -> str:
    return f"`{escape(text)}`"


def format_answer(question_row) -> str:
    """
    Format a questions table row into a nicely structured MarkdownV2 message.
    Accepts an aiosqlite.Row or dict-like object.
    """
    def section(emoji: str, title: str, content: str) -> str:
        if not content or not content.strip():
            return ""
        lines = [f"{emoji} *{escape(title)}*"]
        for line in content.strip().split("\n"):
            lines.append(escape(line))
        return "\n".join(lines)

    parts = [
        f"📋 *{escape(question_row['question_text'])}*",
        "",
    ]

    sections = [
        ("📖", "Definition",           question_row["answer_definition"]),
        ("💡", "Introduction",          question_row["answer_intro"]),
        ("🔬", "Explanation",           question_row["answer_explanation"]),
        ("⚙️",  "Mechanism",            question_row["answer_mechanism"]),
        ("🔄", "Flowchart",             question_row["answer_flowchart"]),
        ("🏥", "Clinical Correlation",  question_row["answer_clinical"]),
        ("⭐", "High Yield",            question_row["answer_high_yield"]),
        ("🎤", "Common Viva Questions", question_row["answer_viva"]),
    ]

    for emoji, title, content in sections:
        block = section(emoji, title, content)
        if block:
            parts.append(block)
            parts.append("")

    if question_row["guyton_chapter"]:
        parts.append(f"📘 *Guyton Reference:* {escape(question_row['guyton_chapter'])}")

    return "\n".join(parts).strip()


def format_progress(stats: dict, first_name: str) -> str:
    """Format progress stats into a readable MarkdownV2 message."""
    accuracy = 0
    if stats["mcq_attempted"] > 0:
        accuracy = int((stats["mcq_correct"] / stats["mcq_attempted"]) * 100)

    def bar(pct: int, width: int = 10) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

    streak_emoji = "🔥" if stats["streak"] > 2 else "📅"

    lines = [
        f"📊 *{escape(first_name)}'s Progress*",
        "",
        f"📖 Questions Read: *{stats['questions_viewed']}*",
        f"🧠 MCQ Sessions: *{stats['mcq_sessions']}*",
        "",
        f"MCQ Accuracy: `{bar(accuracy)} {accuracy}%`",
        f"Correct: *{stats['mcq_correct']}* / *{stats['mcq_attempted']}* attempted",
        "",
        f"⭐ Bookmarks: *{stats['bookmarks']}*",
        f"{streak_emoji} Current Streak: *{stats['streak']} day{'s' if stats['streak'] != 1 else ''}*",
    ]
    return "\n".join(escape(l) if not l.startswith("*") and not l.startswith("`") and not l.startswith("📊") else l for l in lines)


def format_search_results(results: list) -> str:
    """Format search results list."""
    if not results:
        return escape("No results found. Try a different keyword.")

    type_emoji = {"term": "📚", "card": "🗂️", "item": "📄", "question": "❓"}
    lines = ["🔍 *Search Results*", ""]
    for r in results:
        emoji = type_emoji.get(r["entity_type"], "•")
        lines.append(f"{emoji} {escape(r['keyword'])} \\({escape(r['entity_type'])}\\)")
    return "\n".join(lines)
