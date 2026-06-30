"""
Async SQLite wrapper using aiosqlite.
All DB access goes through this module.
"""

import aiosqlite
import logging
from pathlib import Path
from config import DB_PATH

logger = logging.getLogger(__name__)

_DB_PATH = DB_PATH
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db() -> aiosqlite.Connection:
    """Return an aiosqlite connection context manager (not yet connected)."""
    return aiosqlite.connect(_DB_PATH)


async def _prep(db: aiosqlite.Connection) -> None:
    """Apply standard settings to a freshly opened connection."""
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("PRAGMA journal_mode = WAL")


async def init_db() -> None:
    """Create all tables from schema.sql if they don't exist."""
    schema = _SCHEMA_PATH.read_text()
    async with get_db() as db:
        await _prep(db)
        await db.executescript(schema)
        await db.commit()
    logger.info("Database initialised at %s", _DB_PATH)


# ─── Terms ────────────────────────────────────────────────────────────────────

async def get_all_terms(subject: str = "physiology") -> list[aiosqlite.Row]:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT id, name FROM terms WHERE subject = ? ORDER BY name", (subject,)
        )
        return await cur.fetchall()


async def get_term(term_id: int) -> aiosqlite.Row | None:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute("SELECT id, name FROM terms WHERE id = ?", (term_id,))
        return await cur.fetchone()


# ─── Cards ────────────────────────────────────────────────────────────────────

async def get_cards(term_id: int) -> list[aiosqlite.Row]:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT id, title FROM cards WHERE term_id = ? ORDER BY order_index, title",
            (term_id,),
        )
        return await cur.fetchall()


async def get_card(card_id: int) -> aiosqlite.Row | None:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute("SELECT id, title, term_id FROM cards WHERE id = ?", (card_id,))
        return await cur.fetchone()


# ─── Items ────────────────────────────────────────────────────────────────────

async def get_items(card_id: int) -> list[aiosqlite.Row]:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT id, title FROM items WHERE card_id = ? ORDER BY order_index, title",
            (card_id,),
        )
        return await cur.fetchall()


async def get_item(item_id: int) -> aiosqlite.Row | None:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute("SELECT id, title, card_id FROM items WHERE id = ?", (item_id,))
        return await cur.fetchone()


# ─── Questions ────────────────────────────────────────────────────────────────

async def get_questions(item_id: int) -> list[aiosqlite.Row]:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT id, question_text FROM questions WHERE item_id = ? ORDER BY id",
            (item_id,),
        )
        return await cur.fetchall()


async def get_question(question_id: int) -> aiosqlite.Row | None:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        )
        return await cur.fetchone()


# ─── Users ────────────────────────────────────────────────────────────────────

async def upsert_user(telegram_id: int, username: str | None, first_name: str) -> None:
    async with get_db() as db:
        await _prep(db)
        await db.execute(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (telegram_id, username, first_name),
        )
        await db.commit()


async def update_streak(telegram_id: int) -> int:
    """Update streak based on last_active date. Returns new streak."""
    from datetime import date, timedelta
    today = date.today()
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT streak, last_active FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cur.fetchone()
        if not row:
            return 0
        streak = row["streak"]
        last_active = row["last_active"]
        if last_active:
            last_date = date.fromisoformat(last_active)
            if last_date == today:
                return streak
            elif last_date == today - timedelta(days=1):
                streak += 1
            else:
                streak = 1
        else:
            streak = 1
        await db.execute(
            "UPDATE users SET streak = ?, last_active = ? WHERE telegram_id = ?",
            (streak, today.isoformat(), telegram_id),
        )
        await db.commit()
        return streak


# ─── Progress ─────────────────────────────────────────────────────────────────

async def record_question_view(user_id: int, question_id: int) -> None:
    async with get_db() as db:
        await _prep(db)
        await db.execute(
            "INSERT INTO progress (user_id, question_id) VALUES (?, ?)",
            (user_id, question_id),
        )
        await db.commit()


async def get_progress_stats(user_id: int) -> dict:
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT COUNT(DISTINCT question_id) as questions_viewed FROM progress WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        questions_viewed = row["questions_viewed"] if row else 0

        cur = await db.execute(
            """
            SELECT
                COUNT(*) as total_sessions,
                SUM(score) as total_correct,
                SUM(total) as total_attempted,
                MAX(played_at) as last_played
            FROM mcq_history WHERE user_id = ?
            """,
            (user_id,),
        )
        mcq = await cur.fetchone()

        cur = await db.execute(
            "SELECT COUNT(*) as bk FROM bookmarks WHERE user_id = ?", (user_id,)
        )
        bk = await cur.fetchone()

        cur = await db.execute(
            "SELECT streak FROM users WHERE telegram_id = ?", (user_id,)
        )
        u = await cur.fetchone()

        return {
            "questions_viewed": questions_viewed,
            "mcq_sessions": mcq["total_sessions"] if mcq else 0,
            "mcq_correct": mcq["total_correct"] or 0,
            "mcq_attempted": mcq["total_attempted"] or 0,
            "bookmarks": bk["bk"] if bk else 0,
            "streak": u["streak"] if u else 0,
        }


# ─── MCQ History ──────────────────────────────────────────────────────────────

async def save_mcq_result(user_id: int, item_id: int, difficulty: str, score: int, total: int) -> None:
    async with get_db() as db:
        await _prep(db)
        await db.execute(
            "INSERT INTO mcq_history (user_id, item_id, difficulty, score, total) VALUES (?,?,?,?,?)",
            (user_id, item_id, difficulty, score, total),
        )
        await db.commit()


# ─── Bookmarks ────────────────────────────────────────────────────────────────

async def toggle_bookmark(user_id: int, question_id: int) -> bool:
    """Returns True if added, False if removed."""
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            "SELECT id FROM bookmarks WHERE user_id = ? AND question_id = ?",
            (user_id, question_id),
        )
        existing = await cur.fetchone()
        if existing:
            await db.execute(
                "DELETE FROM bookmarks WHERE user_id = ? AND question_id = ?",
                (user_id, question_id),
            )
            await db.commit()
            return False
        else:
            await db.execute(
                "INSERT INTO bookmarks (user_id, question_id) VALUES (?, ?)",
                (user_id, question_id),
            )
            await db.commit()
            return True


# ─── Search ───────────────────────────────────────────────────────────────────

async def search_content(query: str, limit: int = 10) -> list[aiosqlite.Row]:
    pattern = f"%{query.lower()}%"
    async with get_db() as db:
        await _prep(db)
        cur = await db.execute(
            """
            SELECT DISTINCT entity_type, entity_id, keyword
            FROM search_index
            WHERE LOWER(keyword) LIKE ?
            LIMIT ?
            """,
            (pattern, limit),
        )
        return await cur.fetchall()


async def populate_search_index() -> None:
    """Rebuild the search_index table from all content. Safe to run multiple times."""
    async with get_db() as db:
        await _prep(db)
        await db.execute("DELETE FROM search_index")

        terms = await db.execute_fetchall("SELECT id, name FROM terms")
        for t in terms:
            await db.execute(
                "INSERT INTO search_index (entity_type, entity_id, keyword) VALUES ('term', ?, ?)",
                (t["id"], t["name"]),
            )

        cards = await db.execute_fetchall("SELECT id, title FROM cards")
        for c in cards:
            await db.execute(
                "INSERT INTO search_index (entity_type, entity_id, keyword) VALUES ('card', ?, ?)",
                (c["id"], c["title"]),
            )

        items = await db.execute_fetchall("SELECT id, title FROM items")
        for i in items:
            await db.execute(
                "INSERT INTO search_index (entity_type, entity_id, keyword) VALUES ('item', ?, ?)",
                (i["id"], i["title"]),
            )

        questions = await db.execute_fetchall("SELECT id, question_text FROM questions")
        for q in questions:
            await db.execute(
                "INSERT INTO search_index (entity_type, entity_id, keyword) VALUES ('question', ?, ?)",
                (q["id"], q["question_text"]),
            )

        await db.commit()
    logger.info("Search index populated.")