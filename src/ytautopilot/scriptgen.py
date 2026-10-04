from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


def fallback_script(topic: str) -> dict[str, Any]:
    """Safe sample used only for dry-run checks; it is not ready to publish."""
    return {
        "topic": topic,
        "language": "Hindi",
        "hook": "Free Fire ki ye baat shayad aapne notice nahi ki hogi!",
        "narration": (
            "Aaj hum Free Fire ke ek interesting point ko samjhenge. "
            "Kisi bhi tip ko ranked match mein use karne se pehle training ground mein test zaroor karein. "
            "Aapki favourite trick kya hai? Comments mein batao."
        ),
        "visual_plan": [
            "Open with self-recorded or properly licensed gameplay.",
            "Show original captions synced to the Hindi narration.",
            "End with a short question for viewers.",
        ],
        "title": "Free Fire ki interesting baat 🔥 #shorts",
        "description": "Hindi gaming commentary with original narration. Verify factual claims and footage permissions before publishing.",
        "hashtags": ["#FreeFire", "#Gaming", "#Shorts"],
        "fact_check_notes": ["Sample fallback only; research and verify before publishing."],
    }


def generate_script(topic: str, allow_fallback: bool = False) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        if allow_fallback:
            return fallback_script(topic)
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to GitHub Actions secrets before prepare/publish.")

    model = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = f"""
Create a short, original Hindi/Hinglish gaming YouTube Short plan about: {topic!r}.
Return ONLY valid JSON with these keys:
topic, language, hook, narration, visual_plan, title, description, hashtags, fact_check_notes.
Requirements:
- Natural spoken Hindi narration, around 80-120 words for a 30-45 second Short.
- Do not invent facts about real players, updates, or game mechanics. Flag claims that need verification.
- Do not imitate a named creator's voice or copy another video's script.
- Suggest visual beats only; never imply that we have permission to use a creator's footage.
- Keep the title accurate and non-misleading.
"""
    response = requests.post(
        url,
        params={"key": api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    try:
        raw = payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(raw)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini returned an unexpected response; inspect the API response and retry.") from exc

    required = ("topic", "hook", "narration", "title", "description")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        raise RuntimeError("Generated script is missing required fields: " + ", ".join(missing))
    data["narration"] = re.sub(r"\s+", " ", data["narration"]).strip()
    return data
