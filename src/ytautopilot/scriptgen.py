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
        "hook": "Free Fire khelte ho? Toh ye trick shayad tumne notice hi nahi ki hogi!",
        "narration": (
            "Ek chhoti si Free Fire trick hai jo gameplay mein kaafi kaam aa sakti hai. "
            "Pehle training ground mein test kar lena, phir ranked mein try karna. "
            "Tumhari favourite trick kya hai? Comment mein batao."
        ),
        "tts_text": (
            "एक छोटी सी Free Fire trick है, जो gameplay में काफी काम आ सकती है। "
            "पहले training ground में test कर लेना, फिर ranked में try करना। "
            "तुम्हारी favourite trick क्या है? Comment में बताओ।"
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
topic, language, hook, narration, tts_text, visual_plan, title, description, hashtags, fact_check_notes.
Requirements:
- Write like a real Indian gaming creator speaking to viewers, not like an article or translated script.
- Address the viewer as "tum/tumhara/tumhe", never "tu/tujhe/tera/teri"; keep it friendly and respectful, not over-familiar.
- Also output a separate "tts_text" field containing the exact same spoken words converted into natural Devanagari for Hindi words. Keep gaming/product names such as Free Fire, Gloo Wall, scope, sniper, AWM, ranked, gameplay, headshot, etc. in Latin script when that gives a natural Indian gaming pronunciation.
- Example pronunciation spelling: "अक्सर हमें लगता है" rather than "aksar hume lagta hai". The tts_text must never be Roman-Hinglish for ordinary Hindi words.
- Sound like a genuine Indian gaming creator casually explaining something to a friend. Avoid robotic hype, fake urgency, repeated "secret trick" hooks, forced slang, and generic lines like "gameplay next level ho jayega".
- Use everyday spoken Hinglish with varied sentence lengths, natural pauses, and a little personality; don't cram "bhai", "sun", "dekho", "matlab", and "na" into every script.
- Start with a specific curiosity or gameplay situation, not a generic clickbait promise. Keep the hook around 6-12 spoken words.
- Keep combined hook + narration around 65-85 spoken words for a roughly 30-42 second Short.
- Build around 2-3 clear beats, and explain each in a way that sounds natural when read aloud by a Hindi TTS voice.
- Prefer demonstrable, useful tips over vague "facts". Never invent percentages, hidden mechanics, pro-player habits, or guaranteed results. If a claim cannot be supported, omit it or clearly flag it in fact_check_notes.
- Use punctuation for spoken rhythm, but don't write stage directions that the voice would read aloud.
- The renderer will split the timed speech into short animated caption phrases; do not format narration as a visible paragraph.
- Flag uncertain claims for verification in fact_check_notes.
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

    required = ("topic", "hook", "narration", "tts_text", "title", "description")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        raise RuntimeError("Generated script is missing required fields: " + ", ".join(missing))
    data["narration"] = re.sub(r"\s+", " ", data["narration"]).strip()
    return data
