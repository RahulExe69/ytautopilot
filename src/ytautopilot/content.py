from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

HISTORY_PATH = Path("data") / "content_history.json"
STRATEGY_PROFILE_PATH = Path("data") / "strategy_profile.json"
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




TOPIC_FAMILY_HINTS: dict[str, tuple[str, ...]] = {
    "close-range skills": (
        "close", "movement", "shotgun", "smg", "strafe", "peek", "cover",
        "crouch", "fight", "rush", "aim",
    ),
    "weapon tests": (
        "weapon", "gun", "shotgun", "smg", "recoil", "reload", "damage",
        "headshot", "body shot", "magazine", "training",
    ),
    "characters and abilities": (
        "character", "ability", "skill", "combo", "defensive", "offensive",
        "setup",
    ),
    "maps and tactics": (
        "map", "landing", "rotation", "zone", "high ground", "building",
        "positioning", "squad", "placement",
    ),
    "myths and experiments": (
        "myth", "test", "testing", "experiment", "claim", "true", "really",
        "compare",
    ),
    "ranked mistakes and clutches": (
        "ranked", "1v2", "clutch", "squad", "mistake", "final zone",
        "heal", "push", "placement",
    ),
    "underrated mechanics and discoveries": (
        "underrated", "mechanic", "discovery", "hidden", "hud", "control",
        "inventory", "training-ground", "training ground", "detail", "habit",
    ),
}



AI_ARTIFACT_PATTERN = re.compile(r"(?<!\w)(?:[-_=*]{3,})(?!\w)|[—–]")
RECENT_FAMILY_COOLDOWN = 3


def clean_user_text(value: str) -> str:
    """Normalize generated viewer-facing text so it reads like human copy."""
    text = str(value or "")
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = re.sub(r"(?m)^\s*[-_=*]{3,}\s*$", "", text)
    text = re.sub(r"(?<!\w)[-_=*]{3,}(?!\w)", " ", text)
    text = re.sub(r"(\*\*|__|\*)", "", text)
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"\.{4,}", "...", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _content_bigrams(value: str) -> set[str]:
    tokens = _normalise(value).split()
    if len(tokens) < 2:
        return set()
    return {" ".join(tokens[i:i + 2]) for i in range(len(tokens) - 1)}


def _recent_phrase_overlap(value: str, recent_values: list[str]) -> float:
    current = _content_bigrams(value)
    if not current:
        return 0.0
    best = 0.0
    for previous in recent_values:
        old = _content_bigrams(previous)
        if not old:
            continue
        overlap = len(current & old) / max(1, len(current))
        best = max(best, overlap)
    return best


def _strategy_profile() -> dict[str, Any]:
    if not STRATEGY_PROFILE_PATH.exists():
        return {}
    try:
        payload = json.loads(STRATEGY_PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def topic_family(topic: str) -> str:
    """Infer a stable content family even when Gemini paraphrases the topic."""
    normalized = _normalise(topic)
    if not normalized:
        return "other"

    tokens = set(normalized.split())
    best_family = "other"
    best_score = 0.0
    for family, hints in TOPIC_FAMILY_HINTS.items():
        score = 0.0
        for hint in hints:
            hint_norm = _normalise(hint)
            if not hint_norm:
                continue
            if hint_norm in normalized:
                score += 1.0
            elif hint_norm in tokens:
                score += 0.8
        if family.lower() in normalized:
            score += 1.5
        if score > best_score:
            best_family = family
            best_score = score

    return best_family if best_score > 0 else "other"


def classify_hook_style(hook: str) -> str:
    """Classify a generated hook into a small, learnable set of patterns."""
    text = _normalise(hook)
    if not text:
        return "unknown"

    if "?" in str(hook) or re.match(r"^(kya|kaise|kyun|kab|why|how|did|does)\b", text):
        return "question"
    if re.search(r"\b(3|three|4|four|5|five|top)\b", text):
        return "list"
    if re.search(r"\b(galti|mistake|mat karo|avoid|stop)\b", text):
        return "warning"
    if re.search(r"\b(test|testing|try|challenge|myth|experiment)\b", text):
        return "test_challenge"
    if re.search(r"\b(underrated|hidden|secret|actually|really|notice|pata)\b", text):
        return "curiosity"
    if re.search(r"\b(how to|tareeka|rule|habit|tip|use karo|try karo)\b", text):
        return "direct_tip"
    return "statement"

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
    """Select an unused topic using rotation + learned performance signals.

    The selector keeps exploration high when the channel has little data, then
    gradually gives more weight to topic families that actually perform.
    """
    current = run_date or date.today()
    used = {
        _normalise(str(entry.get("topic", "")))
        for entry in load_content_history().get("entries", [])
        if isinstance(entry, dict)
    }
    used.update(_normalise(str(topic)) for topic in (exclude_topics or set()))

    profile = _strategy_profile()
    family_stats = profile.get("topic_family_stats", {})
    baseline = float(profile.get("baseline_performance_score", 0.0) or 0.0)
    best_families = {
        str(item) for item in profile.get("best_topic_families", [])
        if str(item).strip()
    }
    data_ready = bool(profile.get("data_ready", False))

    candidates: list[tuple[str, str]] = []
    for family, topics in TOPIC_BANK:
        for topic in topics:
            if _normalise(topic) not in used:
                candidates.append((family, topic))

    if not candidates:
        # The fixed bank is exhausted; create a deterministic fresh angle.
        family, topics = TOPIC_BANK[current.weekday() % len(TOPIC_BANK)]
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
        for index, base in enumerate(topics):
            angle = angles[(current.toordinal() + index) % len(angles)]
            candidate = f"{base} ({angle})"
            if _normalise(candidate) not in used:
                candidates.append((family, candidate))
                break

    if not candidates:
        raise RuntimeError("No unused topic candidate is available.")

    recent_entries = recent_history(24)
    recent_topics = [
        _normalise(str(item.get("topic", "")))
        for item in recent_entries
        if str(item.get("topic", "")).strip()
    ]
    recent_titles = [
        _normalise(str(item.get("title", "")))
        for item in recent_entries
        if str(item.get("title", "")).strip()
    ]
    recent_hooks = [
        _normalise(str(item.get("hook", "")))
        for item in recent_entries
        if str(item.get("hook", "")).strip()
    ]
    recent_families = [
        str(item.get("topic_family") or topic_family(str(item.get("topic", "")))).strip()
        for item in recent_entries
        if isinstance(item, dict)
    ]
    recent_family_counts: dict[str, int] = {}
    for family in recent_families:
        recent_family_counts[family] = recent_family_counts.get(family, 0) + 1

    # The old weekday prior could repeatedly select the same family (for example
    # Monday -> close-range skills) for many consecutive runs. Prefer families
    # that have not appeared in the recent cooldown window, then use performance
    # learning as a soft signal.
    cooldown_families = set(recent_families[-RECENT_FAMILY_COOLDOWN:])
    available_families = {
        family for family, _ in candidates
        if family not in cooldown_families
    }
    preferred_family = (
        next(iter(available_families))
        if available_families
        else TOPIC_BANK[current.weekday() % len(TOPIC_BANK)][0]
    )

    def similarity_to_recent(topic: str) -> float:
        from difflib import SequenceMatcher
        normalized = _normalise(topic)
        return max(
            (
                SequenceMatcher(None, normalized, previous).ratio()
                for previous in recent_topics
                if previous
            ),
            default=0.0,
        )

    def candidate_score(family: str, topic: str) -> float:
        stats = family_stats.get(family, {})
        samples = int(stats.get("samples", 0) or 0) if isinstance(stats, dict) else 0
        average = float(stats.get("avg_performance_score", 0.0) or 0.0) if isinstance(stats, dict) else 0.0

        score = 0.0
        # Preserve the original seven-family rotation as a soft prior.
        if family == preferred_family:
            score += 0.18

        # Prefer measured winners only after enough data exists, while keeping
        # explicit exploration for under-sampled families.
        if data_ready and samples >= 2 and baseline > 0:
            relative = max(-0.35, min(0.35, (average / baseline) - 1.0))
            score += 0.42 * relative
        score += 0.18 / (1.0 + samples ** 0.5)

        if family in best_families:
            score += 0.08

        similarity = similarity_to_recent(topic)
        score -= max(0.0, similarity - 0.64) * 0.9

        # Penalize repeated wording independently of full-string similarity.
        # This catches cases like:
        # "Close-Range Fight Mein Cover..."
        # "Close-Range Fight Mein Jump..."
        topic_overlap = _recent_phrase_overlap(topic, recent_topics)
        score -= topic_overlap * 0.95

        if recent_family_counts.get(family, 0) > 0:
            score -= min(0.28, recent_family_counts[family] * 0.10)

        # Stable per-day tie breaking without randomness in workflow retries.
        digest = hashlib.sha256(f"{current.isoformat()}|{topic}".encode("utf-8")).hexdigest()
        score += int(digest[:4], 16) / 65535.0 * 0.02
        return score

    ranked = sorted(
        candidates,
        key=lambda item: candidate_score(item[0], item[1]),
        reverse=True,
    )
    return ranked[0][1]


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
    current_hook = _normalise(str(script.get("hook", "")))
    current_family = str(script.get("topic_family") or topic_family(str(script.get("topic", ""))))
    for entry in recent_history(32):
        old_topic = _normalise(str(entry.get("topic", "")))
        old_title = _normalise(str(entry.get("title", "")))
        old_hook = _normalise(str(entry.get("hook", "")))
        old_family = str(entry.get("topic_family") or topic_family(str(entry.get("topic", ""))))
        if current_topic and current_topic == old_topic:
            return True
        if current_title and current_title == old_title:
            return True
        if _entry_similarity(script, entry) >= 0.84:
            return True

        # Prevent near-identical packaging even when Gemini rewrites the same
        # idea with different words.
        if old_family == current_family:
            phrase_scores = (
                _recent_phrase_overlap(current_topic, [old_topic, old_title]),
                _recent_phrase_overlap(current_title, [old_title, old_topic]),
            )
            if max(phrase_scores) >= 0.50:
                return True
            if (
                current_hook
                and old_hook
                and SequenceMatcher(None, current_hook, old_hook).ratio() >= 0.82
            ):
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
            "topic_family": topic_family(str(script.get("topic", ""))),
            "hook_style": classify_hook_style(str(script.get("hook", ""))),
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
