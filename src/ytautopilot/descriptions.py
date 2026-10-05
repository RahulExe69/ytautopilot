from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .content import clean_user_text

HISTORY_PATH = Path("data") / "description_history.json"

STYLES: tuple[tuple[str, str], ...] = (
    (
        "practical",
        "Try this in Training Ground first, then use it in a real match.",
    ),
    (
        "question",
        "Have you been making this mistake too? Tell me what you noticed in the comments.",
    ),
    (
        "challenge",
        "Test this in your next match and see whether the difference helps your fights.",
    ),
    (
        "community",
        "Save this tip for your next ranked session and share it with your squad.",
    ),
    (
        "simple",
        "Small positioning changes can make a big difference when your timing is right.",
    ),
)


def _load() -> dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {"version": 1, "styles": []}
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "styles": []}
    return payload if isinstance(payload, dict) else {"version": 1, "styles": []}


def _save(payload: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def choose_style(preferred: list[str] | None = None) -> str:
    if preferred:
        for candidate in preferred:
            if any(name == candidate for name, _ in STYLES):
                return candidate

    profile_path = Path("data") / "strategy_profile.json"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        profile = {}
    style_scores = profile.get("description_style_scores", {}) if isinstance(profile, dict) else {}
    if isinstance(style_scores, dict) and style_scores:
        ranked = [
            name for name, _ in sorted(
                ((name, float(style_scores.get(name, 0.0))) for name, _ in STYLES),
                key=lambda item: item[1],
                reverse=True,
            )
        ]
        if profile.get("data_ready") and ranked:
            return ranked[0]

    payload = _load()
    counts: dict[str, int] = {}
    for item in payload.get("styles", []):
        if isinstance(item, dict):
            name = str(item.get("style", ""))
            counts[name] = counts.get(name, 0) + 1
    unused = [name for name, _ in STYLES if counts.get(name, 0) == 0]
    if unused:
        return unused[0]
    return min((name for name, _ in STYLES), key=lambda name: counts.get(name, 0))


def build_description(script: dict[str, Any], style: str) -> str:
    base = clean_user_text(str(script.get("description", "")))
    topic = clean_user_text(str(script.get("topic", "")))
    hashtag_values = script.get("hashtags", [])
    tags: list[str] = []
    if isinstance(hashtag_values, list):
        for item in hashtag_values:
            tag = str(item).strip()
            if tag and tag not in tags:
                tags.append(tag)
    if not tags:
        tags = ["#FreeFire", "#Gaming", "#Shorts"]
    cta = dict(STYLES).get(style, STYLES[0][1])

    paragraphs = [
        base or f"Quick Free Fire tip about {topic}.",
        cta,
        "Made for Zynex Playz — Hindi/Hinglish Free Fire Shorts.",
        " ".join(tags[:8]),
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph).strip()[:5000]


def record_style(style: str, fingerprint: str) -> None:
    payload = _load()
    entries = [item for item in payload.get("styles", []) if isinstance(item, dict)]
    entries.append({"style": style, "fingerprint": fingerprint})
    payload = {"version": 1, "styles": entries[-200:]}
    _save(payload)
