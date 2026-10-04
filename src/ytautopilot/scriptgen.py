from __future__ import annotations

import json
import os
import re
from typing import Any

from .content import choose_daily_topic, history_prompt_context, is_duplicate_script

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


def generate_script(
    topic: str,
    allow_fallback: bool = False,
    target_seconds: float | None = None,
) -> dict[str, Any]:
    if topic.strip().lower() in {"", "auto", "daily"}:
        topic = choose_daily_topic()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        if allow_fallback:
            return fallback_script(topic)
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to GitHub Actions secrets before prepare/publish.")

    configured_model = (os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    model_candidates = []
    for candidate in (configured_model, "gemini-2.5-flash-lite", "gemini-2.5-flash"):
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)
    target_seconds = max(10.0, min(52.0, float(target_seconds or 30.0)))
    target_words = max(24, min(90, int(target_seconds * 1.8)))
    prompt = f"""
Create an original Hindi/Hinglish gaming YouTube Short plan about: {topic!r}.
Return ONLY valid JSON with these keys:
topic, language, hook, narration, tts_text, visual_plan, title, description, hashtags, fact_check_notes.
Requirements:
- Write like a real Indian gaming creator speaking to viewers, not like an article, school essay, news script, or translated Hindi script.
- The spoken narration must sound like the everyday Hindi/Hinglish people actually use while gaming with friends. Keep it casual and conversational rather than "shuddh Hindi".
- Address the viewer as "tum/tumhara/tumhe", never "tu/tujhe/tera/teri"; keep it friendly and respectful, not over-familiar.
- Use natural Hinglish freely: common English words such as "body", "use", "side", "aim", "enemy", "damage", "fight", "timing", "movement", "cover", "game", "match", "push", "try", and "practice" are welcome when they sound more natural than formal Hindi.
- Avoid formal/bookish wording such as "sharir", "upayog/istamal" when "body/use" would sound natural, "dauran", "nuksan uthana", "prapt", "avsar", "pratyaksh", "sahayata", or other unnecessarily Sanskritised vocabulary. Prefer simple spoken forms like "body", "use", "karte waqt", "damage", "mil jata hai", "dikhta hai", and "try karna".
- Do not force Hindi words just to make the script look Hindi. Natural Hinglish is the goal.
- Also output a separate "tts_text" field containing the exact same spoken content as hook + narration, converted into natural Devanagari for Hindi words. Do not omit the hook from tts_text.
- In tts_text, transliterate the actual spoken Hinglish naturally for pronunciation, for example "बॉडी", "यूज़", "साइड", "एम", "एनेमी", "डैमेज", "फाइट", "टाइमिंग", "मूवमेंट", "कवर", "गेम", "मैच", and "ट्राय" when those are used in narration. Do not rewrite the meaning into more formal Hindi while converting to Devanagari.
- Prefer Devanagari for ordinary Hindi and common gaming terms when that improves Indian-Hindi pronunciation, for example "फ्री फायर", "ग्लू वॉल", "हेडशॉट", "रैंक्ड", "स्कोप", "स्नाइपर", and "गेमप्ले". Keep product or weapon names in Latin only when their pronunciation is clearly better that way.
- Example style: "Cover ke peeche ho toh body pura bahar mat nikalo. Thoda side se peek karo, bas jitna aim karne ke liye chahiye." This is the target feel: natural spoken Hinglish, not formal Hindi.
- Sound like a genuine Indian gaming creator casually explaining something to a friend. Avoid robotic hype, fake urgency, repeated "secret trick" hooks, forced slang, and generic lines like "gameplay next level ho jayega".
- Use everyday spoken Hinglish with varied sentence lengths, natural pauses, and a little personality; don't cram "bhai", "sun", "dekho", "matlab", and "na" into every script.
- Stay tightly grounded in the supplied topic. Do not invent or introduce a named technique, hidden mechanic, weapon behaviour, percentage, pro-player habit, or special jargon that the topic does not call for. In particular, do not turn a vague topic into a made-up "secret" mechanic just to make the Short sound interesting.
- Start with a specific curiosity or gameplay situation, not a generic clickbait promise. Keep the hook around 6-12 spoken words.
- Keep combined hook + narration close to {target_words} spoken words for a target of about {target_seconds:.0f} seconds. The footage duration is a hard limit: be concise, do not add filler, and finish the thought naturally.
- Build around 2-3 clear beats, and explain each in a way that sounds natural when read aloud by a Hindi TTS voice.
- Prefer demonstrable, useful tips over vague "facts". Never invent percentages, hidden mechanics, pro-player habits, or guaranteed results. If a claim cannot be supported, omit it or clearly flag it in fact_check_notes.
- Use punctuation for spoken rhythm, but don't write stage directions that the voice would read aloud.
- The renderer will split the timed speech into short animated caption phrases; do not format narration as a visible paragraph.
- Flag uncertain claims for verification in fact_check_notes.
- Do not imitate a named creator's voice or copy another video's script. Match only the broad pacing and editing conventions of professional gaming Shorts.
- Suggest practical visual beats that can be created from owned/licensed gameplay footage.
- Keep the title accurate, punchy, and non-misleading.
- Do not reuse the same core idea, title, or hook from the recent history below. Choose a clearly different angle even when the broad weekly format is the same.
- Recent Shorts to avoid repeating:
${history_prompt_context()}
"""

    def request_script(request_prompt: str, temperature: float) -> dict[str, Any]:
        errors: list[str] = []
        for candidate_model in model_candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent"
            for attempt in range(3):
                try:
                    response = requests.post(
                        url,
                        params={"key": api_key},
                        json={
                            "contents": [{"parts": [{"text": request_prompt}]}],
                            "generationConfig": {
                                "temperature": temperature,
                                "responseMimeType": "application/json",
                            },
                        },
                        timeout=60,
                    )
                    if response.status_code in {429, 500, 502, 503, 504}:
                        errors.append(f"{candidate_model} attempt {attempt + 1}: HTTP {response.status_code}")
                        if attempt < 2:
                            import time
                            time.sleep(2 ** attempt)
                            continue
                        break
                    response.raise_for_status()
                    payload = response.json()
                    try:
                        raw = payload["candidates"][0]["content"]["parts"][0]["text"]
                        data = json.loads(raw)
                        data["_model_used"] = candidate_model
                        return data
                    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                        raise RuntimeError(
                            "Gemini returned an unexpected response; inspect the API response and retry."
                        ) from exc
                except requests.RequestException as exc:
                    errors.append(f"{candidate_model} attempt {attempt + 1}: {exc}")
                    if attempt < 2:
                        import time
                        time.sleep(2 ** attempt)
                        continue
                    break

        raise RuntimeError(
            "Gemini script generation failed after retries. " + " | ".join(errors[-8:])
        )

    data = request_script(prompt, 0.7)
    if is_duplicate_script(data):
        retry_prompt = prompt + """
The first draft was too similar to a recent Short. Discard that angle and create a genuinely different topic, hook, title, and narration while staying inside the same Free Fire content strategy. Do not mention that you are avoiding duplicates.
"""
        data = request_script(retry_prompt, 0.82)
        if is_duplicate_script(data):
            raise RuntimeError(
                "Gemini produced a Short that is too similar to a recent run twice. "
                "Choose a different topic seed and retry."
            )

    data.pop("_model_used", None)
    required = ("topic", "hook", "narration", "tts_text", "title", "description")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        raise RuntimeError("Generated script is missing required fields: " + ", ".join(missing))
    data["topic"] = re.sub(r"\s+", " ", str(data["topic"])).strip()
    data["hook"] = re.sub(r"\s+", " ", str(data["hook"])).strip()
    data["narration"] = re.sub(r"\s+", " ", data["narration"]).strip()
    data["tts_text"] = re.sub(r"\s+", " ", str(data["tts_text"])).strip()
    return data
