"""
services/gemini.py
Async Gemini wrapper with:
 - API key rotation on 429 errors with cooldown
 - Per-key cooldown tracking (skips exhausted keys)
 - Simple in-memory prompt cache (TTL-based)
 - Never crashes — returns a user-friendly fallback string on total failure
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx
from config import GEMINI_KEYS, CACHE_TTL_SECONDS, GUYTON_SYSTEM, MCQ_SYSTEM

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"

_cache: dict[str, tuple[str, float]] = {}
_key_index = 0
_key_lock = asyncio.Lock()
_key_cooldown: dict[str, float] = {}  # key -> timestamp when it can be used again
COOLDOWN_SECONDS = 60


def _cache_key(prompt: str, system: str) -> str:
    raw = f"{system}|||{prompt}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(ck: str) -> str | None:
    if ck in _cache:
        response, expiry = _cache[ck]
        if time.time() < expiry:
            return response
        del _cache[ck]
    return None


def _set_cache(ck: str, response: str) -> None:
    _cache[ck] = (response, time.time() + CACHE_TTL_SECONDS)


def _is_key_available(key: str) -> bool:
    cooldown_until = _key_cooldown.get(key, 0)
    return time.time() >= cooldown_until


def _mark_key_exhausted(key: str) -> None:
    _key_cooldown[key] = time.time() + COOLDOWN_SECONDS
    logger.warning("Key %s...%s marked exhausted, cooldown %ds", key[:4], key[-4:], COOLDOWN_SECONDS)


async def _get_available_key() -> str | None:
    global _key_index
    async with _key_lock:
        # Try all keys, find one not in cooldown
        for _ in range(len(GEMINI_KEYS)):
            key = GEMINI_KEYS[_key_index % len(GEMINI_KEYS)]
            _key_index += 1
            if _is_key_available(key):
                return key
        # All keys in cooldown — return the one with shortest wait
        soonest = min(GEMINI_KEYS, key=lambda k: _key_cooldown.get(k, 0))
        wait = max(0, _key_cooldown.get(soonest, 0) - time.time())
        logger.warning("All keys in cooldown. Soonest recovers in %.0fs", wait)
        return None


async def _call_gemini(api_key: str, system: str, prompt: str) -> str:
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            GEMINI_URL,
            params={"key": api_key},
            json=payload,
        )

    if resp.status_code == 429:
        raise RateLimitError("Rate limit hit")
    resp.raise_for_status()

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response shape: {e}") from e


class RateLimitError(Exception):
    pass


class GeminiService:
    """Singleton-style service. Import and call directly."""

    async def generate(
        self,
        prompt: str,
        system: str = "",
        use_cache: bool = True,
    ) -> str:
        if not GEMINI_KEYS:
            return "⚠️ No Gemini API keys configured. Please check your .env file."

        ck = _cache_key(prompt, system)
        if use_cache:
            cached = _get_cached(ck)
            if cached:
                logger.debug("Cache hit for prompt: %s…", prompt[:40])
                return cached

        # Try each available key once
        for attempt in range(len(GEMINI_KEYS)):
            key = await _get_available_key()
            if key is None:
                logger.warning("All keys exhausted, waiting 5s before retry…")
                await asyncio.sleep(5)
                continue
            try:
                result = await _call_gemini(key, system, prompt)
                if use_cache:
                    _set_cache(ck, result)
                return result
            except RateLimitError:
                _mark_key_exhausted(key)
                await asyncio.sleep(1)  # small pause before trying next key
                continue
            except httpx.HTTPStatusError as e:
                logger.error("HTTP error from Gemini: %s", e)
                continue
            except Exception as e:
                logger.error("Gemini call failed: %s", e)
                continue

        return "⚠️ AI is currently busy. Please try again in a few minutes."

    async def ask_guyton(self, question: str) -> str:
        return await self.generate(prompt=question, system=GUYTON_SYSTEM)

    async def generate_mcqs(
        self, item_title: str, difficulty: str, count: int
    ) -> list[dict]:
        prompt = (
            f"Generate {count} {difficulty} MCQs on the topic: \"{item_title}\" "
            f"from Guyton & Hall Medical Physiology. "
            f"Respond ONLY with a valid JSON array. No markdown, no backticks, just raw JSON.\n"
            f"Each object must have exactly: q, options (array of 4 strings starting with A. B. C. D.), "
            f"correct (0-based index), explanation, why_wrong"
        )
        raw = await self.generate(prompt=prompt, system=MCQ_SYSTEM, use_cache=False)

        # Strip potential markdown fences
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(clean)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError as e:
            logger.error("MCQ JSON parse failed: %s\nRaw: %s", e, raw[:200])

        return []


# Module-level singleton
gemini = GeminiService()