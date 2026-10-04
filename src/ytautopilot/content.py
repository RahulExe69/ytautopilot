from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

HISTORY_PATH = Path("data") / "content_history.json"
MAX_HISTORY = 120

# Seven repeatable daily formats. Each format has eight distinct ideas so the
# first eight weeks can rotate without repeating the same seed topic.
TOPIC_BANK: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "close-range skills",
        (
            "Three close-range movement mistakes beginners make in Free Fire",
            "How to use cover properly during a close-range fight",
            "Why panic-jumping can lose an easy close-range fight",
            "Better peeking habits for shotgun fights",
            "How to reset a bad close-range fight instead of forcing it",
            "The safest way to cross a short open area in ranked",
            "How crouch and strafe timing affect close-range aim",
            "Three signs you should stop chasing an enemy in close range",
        ),
    ),
    (
        "weapon tests",
        (
            "Shotgun vs SMG for close-range fights: what changes",
            "A simple Free Fire recoil test you can do in training",
            "What actually changes when you switch between two similar weapons",
            "How reload time changes the way you should take a fight",
            "Testing body shots versus headshots at different ranges",
            "Which weapon is easier to recover with after a missed first shot",
            "How magazine size changes your decision in a 1v2",
            "A practical weapon test for ranked players who keep losing trades",
        ),
    ),
    (
        "characters and abilities",
        (
            "A simple character ability combo for aggressive players",
            "When a defensive ability is better than an offensive one",
            "How to choose a character ability for solo versus squad",
            "Three ability-combo mistakes that waste a skill slot",
            "How to counter an enemy ability without overcomplicating the fight",
            "When saving an ability is better than using it immediately",
            "A beginner-friendly way to learn one character ability",
            "How to build an ability setup around your preferred weapon",
        ),
    ),
    (
        "maps and tactics",
        (
            "How to pick a safer landing spot when playing for placement",
            "A simple rotation rule for moving between zones",
            "Why taking high ground early can change a mid-game fight",
            "How to avoid getting trapped between two enemy teams",
            "When holding a building is better than rotating again",
            "How to choose cover before you start healing",
            "Three map-positioning mistakes that create unnecessary fights",
            "How to rotate with a squad without leaving one player behind",
        ),
    ),
    (
        "myths and experiments",
        (
            "Testing a common Free Fire gloo-wall myth",
            "Does crouching really change how exposed you are behind cover",
            "Testing two movement habits side by side in training",
            "Does changing a weapon setup actually improve close-range control",
            "A simple test for a Free Fire claim players often repeat",
            "Testing how quickly two different reload habits get you back into a fight",
            "Does standing still for a moment really make your first shot better",
            "One popular Free Fire tip that is worth testing instead of guessing",
        ),
    ),
    (
        "ranked mistakes and clutches",
        (
            "Three ranked mistakes that make an easy fight harder",
            "What to do when your squad loses the first player",
            "How to play a 1v2 without rushing both enemies",
            "The biggest reason players throw an advantage after one knock",
            "How to decide between healing, rotating, and pushing",
            "A safer way to recover after getting caught in the open",
            "Three habits that help when the final zone gets crowded",
            "How to turn a bad start into a playable ranked match",
        ),
    ),
    (
        "underrated mechanics and discoveries",
        (
            "One underrated Free Fire habit that makes fights easier",
            "A small movement detail many beginners ignore",
            "A simple inventory habit that saves time during fights",
            "One positioning detail that changes how enemies can peek you",
            "A useful training-ground drill for improving fight decisions",
            "One small HUD or control habit worth testing",
            "A practical way to review your own mistakes after a match",
            "One Free Fire mechanic worth testing before calling it a myth",
        ),
    ),
)


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def load_content_history() -> dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {"version": 1, "entries": []}
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "entries": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        return {"version": 1, "entries": []}
    return payload


def recent_history(limit: int = 16) -> list[dict[str, Any]]:
    entries = load_content_history().get("entries", [])
    return [item for item in entries if isinstance(item, dict)][-limit:]


def choose_daily_topic(run_date: date | None = None, exclude_topics: set[str] | None = None) -> str:
    current = run_date or date.today()
    _, candidates = TOPIC_BANK[current.weekday()]
    used = {
        _normalise(str(entry.get("topic", "")))
        for entry in load_content_history().get("entries", [])
        if isinstance(entry, dict)
    }
    used.update(_normalise(str(topic)) for topic in (exclude_topics or set()))

    for topic in candidates:
        if _normalise(topic) not in used:
            return topic

    angles = (
        "for beginners",
        "in Clash Squad",
        "in ranked",
        "with shotguns",
        "with SMGs",
        "when playing solo",
        "when playing aggressively",
        "when playing for placement",
    )
    pass_index = sum(
        1
        for entry in load_content_history().get("entries", [])
        if isinstance(entry, dict)
        and str(entry.get("weekday")) == str(current.weekday())
    )
    base = candidates[pass_index % len(candidates)]
    angle = angles[pass_index % len(angles)]
    candidate = f"{base} ({angle})"
    suffix = 2
    while _normalise(candidate) in used:
        candidate = f"{base} ({angle} {suffix})"
        suffix += 1
    return candidate


def history_prompt_context(limit: int = 12) -> str:
    items = recent_history(limit)
    if not items:
        return "No previous Shorts are recorded yet."
    lines = []
    for item in items:
        lines.append(
            f"- Topic: {item.get('topic', '')} | Title: {item.get('title', '')} | "
            f"Hook: {item.get('hook', '')}"
        )
    return "\n".join(lines)


def _entry_similarity(script: dict[str, Any], entry: dict[str, Any]) -> float:
    current_title = _normalise(str(script.get("title", "")))
    current_hook = _normalise(str(script.get("hook", "")))
    old_title = _normalise(str(entry.get("title", "")))
    old_hook = _normalise(str(entry.get("hook", "")))
    title_score = (
        SequenceMatcher(None, current_title, old_title).ratio()
        if current_title and old_title
        else 0.0
    )
    hook_score = (
        SequenceMatcher(None, current_hook, old_hook).ratio()
        if current_hook and old_hook
        else 0.0
    )
    return max(title_score, hook_score)


def is_duplicate_script(script: dict[str, Any]) -> bool:
    current_topic = _normalise(str(script.get("topic", "")))
    current_title = _normalise(str(script.get("title", "")))
    for entry in recent_history(32):
        old_topic = _normalise(str(entry.get("topic", "")))
        old_title = _normalise(str(entry.get("title", "")))
        if current_topic and current_topic == old_topic:
            return True
        if current_title and current_title == old_title:
            return True
        if _entry_similarity(script, entry) >= 0.90:
            return True
    return False


def content_fingerprint(script: dict[str, Any]) -> str:
    material = " | ".join(
        _normalise(str(script.get(key, "")))
        for key in ("topic", "hook", "narration", "title")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def record_content_history(
    script: dict[str, Any],
    gameplay_files: list[str] | None = None,
) -> None:
    payload = load_content_history()
    entries = [item for item in payload.get("entries", []) if isinstance(item, dict)]
    now = datetime.now(timezone.utc)

    fingerprint = content_fingerprint(script)
    if any(str(item.get("fingerprint", "")) == fingerprint for item in entries):
        return

    entries.append(
        {
            "generated_at": now.isoformat(),
            "weekday": now.weekday(),
            "topic": str(script.get("topic", "")).strip(),
            "title": str(script.get("title", "")).strip(),
            "hook": str(script.get("hook", "")).strip(),
            "fingerprint": fingerprint,
            "gameplay_files": [str(path) for path in (gameplay_files or [])],
            "status": "generated",
        }
    )
    payload = {"version": 1, "entries": entries[-MAX_HISTORY:]}
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
