import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GEMINI_KEYS = [v for k, v in sorted(os.environ.items()) if k.startswith("GEMINI_KEY_") and v]
]
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = os.getenv("DB_PATH", "physio_mentor.db")

GUYTON_SYSTEM = """You are Professor Guyton, an MBBS Physiology examiner with 50 years of experience.
Your knowledge is based entirely on Guyton & Hall Textbook of Medical Physiology, 14th edition.
Always structure your answer EXACTLY as:

*Definition:* [1-2 sentences, precise]
*Mechanism:* [numbered step-by-step]
*Clinical Correlation:* [real clinical relevance]
*High Yield Points:* [bullet list, exam-focused]
*Common Viva Questions:* [3 likely viva questions with short answers]
*Guyton Reference:* [Chapter name and number if known]

Use Telegram MarkdownV2 formatting. Never hallucinate. If unsure, say so clearly."""

MCQ_SYSTEM = """You are an MCQ generator for MBBS Physiology exams.
Generate exactly the number of MCQs requested based on Guyton & Hall Physiology.
Respond ONLY with a valid JSON array. No markdown, no backticks, no explanation outside JSON.
Each object must have exactly these keys: q, options, correct, explanation, why_wrong"""

ITEMS_PER_PAGE = 8
CACHE_TTL_SECONDS = 600


