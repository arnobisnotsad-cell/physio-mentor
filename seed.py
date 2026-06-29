"""
seed.py — Run once before first deployment to populate the database.
Safe to run multiple times (idempotent).

Usage:
    python seed.py
"""

import asyncio
import json
import logging
from pathlib import Path

import aiosqlite
from database.db import init_db, get_db, populate_search_index

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent / "database" / "seed"


async def seed_terms(db: aiosqlite.Connection) -> dict[str, int]:
    """Insert terms, return name→id map."""
    terms_data = json.loads((SEED_DIR / "terms.json").read_text())
    term_ids: dict[str, int] = {}

    for t in terms_data:
        cur = await db.execute(
            "SELECT id FROM terms WHERE name = ? AND subject = ?", (t["name"], t["subject"])
        )
        row = await cur.fetchone()
        if row:
            term_ids[t["name"]] = row["id"]
            logger.info("Term exists: %s", t["name"])
        else:
            cur = await db.execute(
                "INSERT INTO terms (name, subject) VALUES (?, ?)", (t["name"], t["subject"])
            )
            term_ids[t["name"]] = cur.lastrowid
            logger.info("Inserted term: %s (id=%d)", t["name"], cur.lastrowid)

    await db.commit()
    return term_ids


async def seed_cards_items(db: aiosqlite.Connection, term_ids: dict[str, int]) -> dict[str, int]:
    """Insert cards and items, return item_title→id map."""
    data = json.loads((SEED_DIR / "cards_items.json").read_text())
    item_ids: dict[str, int] = {}

    for entry in data:
        term_name = entry["term"]
        term_id = term_ids.get(term_name)
        if not term_id:
            logger.warning("Unknown term '%s', skipping cards", term_name)
            continue

        for card_data in entry["cards"]:
            cur = await db.execute(
                "SELECT id FROM cards WHERE term_id = ? AND title = ?",
                (term_id, card_data["title"]),
            )
            row = await cur.fetchone()
            if row:
                card_id = row["id"]
            else:
                cur = await db.execute(
                    "INSERT INTO cards (term_id, title, order_index) VALUES (?, ?, ?)",
                    (term_id, card_data["title"], card_data.get("order_index", 0)),
                )
                card_id = cur.lastrowid
                logger.info("  Card: %s", card_data["title"])

            for item_data in card_data.get("items", []):
                cur = await db.execute(
                    "SELECT id FROM items WHERE card_id = ? AND title = ?",
                    (card_id, item_data["title"]),
                )
                row = await cur.fetchone()
                if row:
                    item_ids[item_data["title"]] = row["id"]
                else:
                    cur = await db.execute(
                        "INSERT INTO items (card_id, title, order_index) VALUES (?, ?, ?)",
                        (card_id, item_data["title"], item_data.get("order_index", 0)),
                    )
                    item_ids[item_data["title"]] = cur.lastrowid
                    logger.info("    Item: %s", item_data["title"])

    await db.commit()
    return item_ids


async def seed_questions(db: aiosqlite.Connection, item_ids: dict[str, int]) -> None:
    """Insert questions linked to items."""
    data = json.loads((SEED_DIR / "questions.json").read_text())

    for entry in data:
        item_title = entry["item"]
        item_id = item_ids.get(item_title)
        if not item_id:
            logger.warning("Item '%s' not found, skipping questions", item_title)
            continue

        for q in entry["questions"]:
            cur = await db.execute(
                "SELECT id FROM questions WHERE item_id = ? AND question_text = ?",
                (item_id, q["question_text"]),
            )
            if await cur.fetchone():
                logger.info("  Question exists: %s...", q["question_text"][:40])
                continue

            await db.execute(
                """
                INSERT INTO questions (
                    item_id, question_text,
                    answer_definition, answer_intro, answer_explanation,
                    answer_mechanism, answer_flowchart, answer_clinical,
                    answer_high_yield, answer_viva, guyton_chapter
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    item_id,
                    q["question_text"],
                    q.get("answer_definition", ""),
                    q.get("answer_intro", ""),
                    q.get("answer_explanation", ""),
                    q.get("answer_mechanism", ""),
                    q.get("answer_flowchart", ""),
                    q.get("answer_clinical", ""),
                    q.get("answer_high_yield", ""),
                    q.get("answer_viva", ""),
                    q.get("guyton_chapter", ""),
                ),
            )
            logger.info("  Question: %s...", q["question_text"][:50])

    await db.commit()


async def main() -> None:
    logger.info("=== PhysioMentor Seeder ===")
    await init_db()
    async with await get_db() as db:
        term_ids = await seed_terms(db)
        item_ids = await seed_cards_items(db, term_ids)
        await seed_questions(db, item_ids)
    await populate_search_index()
    logger.info("=== Seeding complete ===")


if __name__ == "__main__":
    asyncio.run(main())
