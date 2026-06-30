"""
seed.py â€” Run once before first deployment to populate the database.
Safe to run multiple times (idempotent).

Usage:
    python seed.py
"""

import asyncio
import json
import logging
from pathlib import Path

from database.db import init_db, get_db, _prep, populate_search_index

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent / "database" / "seed"


async def seed_terms(db) -> None:
    terms = json.loads((SEED_DIR / "terms.json").read_text(encoding="utf-8-sig"))
    for t in terms:
        cur = await db.execute("SELECT id FROM terms WHERE id = ?", (t["id"],))
        if await cur.fetchone():
            continue
        await db.execute(
            "INSERT INTO terms (id, name, subject) VALUES (?, ?, ?)",
            (t["id"], t["name"], t["subject"]),
        )
        logger.info("Inserted term: %s", t["name"])
    await db.commit()


async def seed_cards(db) -> None:
    cards = json.loads((SEED_DIR / "cards.json").read_text(encoding="utf-8-sig"))
    for c in cards:
        cur = await db.execute("SELECT id FROM cards WHERE id = ?", (c["id"],))
        if await cur.fetchone():
            continue
        await db.execute(
            "INSERT INTO cards (id, term_id, title, order_index) VALUES (?, ?, ?, ?)",
            (c["id"], c["term_id"], c["title"], c.get("card_no", 0)),
        )
        logger.info("Inserted card: %s", c["title"])
    await db.commit()


async def seed_items(db) -> None:
    items = json.loads((SEED_DIR / "items.json").read_text(encoding="utf-8-sig"))
    for i in items:
        cur = await db.execute("SELECT id FROM items WHERE id = ?", (i["id"],))
        if await cur.fetchone():
            continue
        await db.execute(
            "INSERT INTO items (id, card_id, title, order_index) VALUES (?, ?, ?, ?)",
            (i["id"], i["card_id"], i["title"], i.get("sl_no", 0)),
        )
        logger.info("Inserted item id=%d", i["id"])
    await db.commit()


async def seed_questions(db) -> None:
    questions = json.loads((SEED_DIR / "questions.json").read_text(encoding="utf-8-sig"))
    for q in questions:
        cur = await db.execute("SELECT id FROM questions WHERE id = ?", (q["id"],))
        if await cur.fetchone():
            continue
        await db.execute(
            """
            INSERT INTO questions (id, item_id, question_text, guyton_chapter)
            VALUES (?, ?, ?, ?)
            """,
            (q["id"], q["item_id"], q["question_text"], q.get("guyton_chapter", "")),
        )
    await db.commit()
    logger.info("Inserted %d questions", len(questions))


async def main() -> None:
    logger.info("=== PhysioMentor Seeder ===")
    await init_db()
    async with get_db() as db:
        await _prep(db)
        await seed_terms(db)
        await seed_cards(db)
        await seed_items(db)
        await seed_questions(db)
    await populate_search_index()
    logger.info("=== Seeding complete ===")


if __name__ == "__main__":
    asyncio.run(main())
