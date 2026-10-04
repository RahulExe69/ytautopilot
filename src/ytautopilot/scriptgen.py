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

    model = (os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = f"""
Create an original Hindi/Hinglish gaming YouTube Short plan about: {topic!r}.
Return ONLY valid JSON with these keys:
topic, language, hook, narration, visual_plan, title, description, hashtags, fact_check_notes.
Requirements:
- Write like a real Indian gaming creator speaking to viewers, not like an article or translated script.
- Prefer casual "tum/tera/tum log" phrasing. Avoid stiff phrases such as "aapko", "hum samjhenge", "core mechanic hai", and textbook Hindi.
- The hook must be short, punchy, and immediately interesting (roughly 8-16 spoken words).
- Keep the combined hook + narration around 75-95 spoken words so the rendered Short lands roughly in the 30-45 second range.
- Use short natural sentences and conversational reactions such as "sun", "dekho", "na", "matlab", and "socho" when they fit naturally.
- Build the narration around 2-3 concrete beats. Every beat should have a visible gameplay action that an editor can emphasize.
- Do not write paragraph-style narration intended to stay on screen as one block. The renderer will convert speech into short animated caption phrases.
- Do not invent facts about real players, updates, or game mechanics. Flag uncertain claims for verification in fact_check_notes.
- Do not imitate a named creator's voice or copy another video's script. Match only the broad pacing and editing conventions of professional gaming Shorts.
- Suggest practical visual beats that can be created from owned/licensed gameplay footage.
- Keep the title accurate, punchy, and non-misleading.
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
