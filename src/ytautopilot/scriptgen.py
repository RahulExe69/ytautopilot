from __future__ import annotations

import json
import os
import re
from typing import Any

from .content import choose_daily_topic, classify_hook_style, clean_user_text, history_prompt_context, is_duplicate_script, topic_family
from .analytics import strategy_prompt_context

import requests




_ROMANIZED_HINDI_MARKERS = (
    "kya", "hai", "hain", "mein", "toh", "tum", "tumhara", "tumhe",
    "nahi", "nahin", "karna", "karo", "pehle", "phir", "kaise", "kyun",
    "yeh", "woh", "bahut", "accha", "acha",
)


_SPOKEN_STYLE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("in conclusion", "essay-style wrap-up"),
    ("it is important to note", "formal filler"),
    ("moreover", "formal connector"),
    ("furthermore", "formal connector"),
    ("subsequently", "formal transition"),
    ("in order to", "wordy connector"),
    ("with that being said", "formulaic transition"),
    ("at the end of the day", "generic filler"),
    ("as you can see", "generic narration"),
    ("utilize", "prefer the simpler word 'use'"),
    ("leverage", "corporate-sounding verb"),
)

def _spoken_style_warnings(hook: str, narration: str) -> list[str]:
    """Flag written, formulaic, or non-English wording before narration."""
    combined = re.sub(r"\s+", " ", f"{hook} {narration}".strip()).lower()
    warnings: list[str] = []

    if re.search(r"[\u0900-\u097f]", combined):
        warnings.append("Hindi/Devanagari text detected; rewrite the spoken copy in English")
    for marker in _ROMANIZED_HINDI_MARKERS:
        if re.search(rf"(?<![a-z]){re.escape(marker)}(?![a-z])", combined):
            warnings.append("Romanized Hindi detected; rewrite the spoken copy in English")
            break

    for phrase, reason in _SPOKEN_STYLE_REPLACEMENTS:
        if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", combined):
            warnings.append(f"{phrase!r}: {reason}")

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", combined) if part.strip()]
    for sentence in sentences:
        words = re.findall(r"[a-z0-9]+", sentence)
        if len(words) > 28:
            warnings.append(f"long sentence ({len(words)} words): break it into two natural spoken beats")
        if len(re.findall(r"\b(so|basically|literally|actually|really|just)\b", sentence)) >= 4:
            warnings.append("too many filler words in one sentence")

    if re.search(r"\b(when it comes to|the fact of the matter is|needless to say)\b", combined):
        warnings.append("generic article-like phrasing")

    return warnings[:8]


def _non_english_visible_copy_warning(data: dict[str, Any]) -> str | None:
    """Reject Hindi leakage in viewer-facing fields beyond the spoken narration."""
    values: list[str] = []
    for key in ("topic", "title", "description", "hook", "narration", "tts_text"):
        value = data.get(key)
        if isinstance(value, str):
            values.append(value)
    for key in ("visual_plan", "fact_check_notes"):
        value = data.get(key)
        if isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
    combined = " ".join(values).lower()
    if re.search(r"[\u0900-\u097f]", combined):
        return "Hindi/Devanagari detected in user-facing copy; rewrite all copy in English"
    for marker in _ROMANIZED_HINDI_MARKERS:
        if re.search(rf"(?<![a-z]){re.escape(marker)}(?![a-z])", combined):
            return "Romanized Hindi detected in user-facing copy; rewrite all copy in English"
    return None


def _clean_ai_style_artifacts(value: str) -> str:
    """Remove markdown/separator artifacts that make generated copy look synthetic."""
    text = str(value or "")
    # Replace typographic dashes with ordinary spoken punctuation. Keep normal
    # single hyphens in compounds such as "close-range".
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    # Remove standalone markdown separators and long runs such as --- or _____.
    text = re.sub(r"(?m)^\s*[-_=*]{3,}\s*$", "", text)
    text = re.sub(r"(?<!\w)[-_=*]{3,}(?!\w)", " ", text)
    # Unwrap common markdown emphasis instead of letting punctuation leak into
    # captions/descriptions.
    text = re.sub(r"(\*\*|__|\*)", "", text)
    # Collapse repeated punctuation while keeping a single natural ellipsis.
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"\.{4,}", "...", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _clean_generated_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Clean user-visible generated strings without changing factual content."""
    for key in ("topic", "language", "hook", "narration", "tts_text", "title", "description"):
        if isinstance(data.get(key), str):
            data[key] = _clean_ai_style_artifacts(data[key])
    for key in ("hashtags", "visual_plan", "fact_check_notes"):
        value = data.get(key)
        if isinstance(value, list):
            data[key] = [
                _clean_ai_style_artifacts(item) if isinstance(item, str) else item
                for item in value
            ]
    return data


def fallback_script(topic: str) -> dict[str, Any]:
    """Safe English sample used only for dry-run checks; it is not ready to publish."""
    hook = "Still losing close-range fights in Free Fire? Try this."
    narration = (
        "Low on HP? Do not force the push. Break line of sight, heal up, "
        "then re-peek when you have an opening. Try it in training first. "
        "What weapon should I cover next?"
    )
    return {
        "topic": topic,
        "language": "English",
        "hook": hook,
        "narration": narration,
        "tts_text": f"{hook} {narration}",
        "visual_plan": [
            "Open with self-recorded or properly licensed gameplay.",
            "Show original captions synced to the English narration.",
            "End with a short question for viewers.",
        ],
        "title": "Stop forcing low-HP fights in Free Fire 🔥 #shorts",
        "description": "Natural English Free Fire commentary with original narration. Verify factual claims and footage permissions before publishing.",
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
Create an original English-language gaming YouTube Short plan about: {topic!r}.
Return ONLY valid JSON with these keys:
topic, language, hook, narration, tts_text, visual_plan, title, description, hashtags, fact_check_notes.
Requirements:
<voice>
- You are writing for ZynexPlayz, a gaming creator based in India. The narration must be natural, fluent English, like a real gaming creator speaking to viewers, not a script being read from an article.
- Use clear, everyday conversational English with a confident, friendly tone. Contractions are welcome when they sound natural.
- Write every user-facing field in English: topic, hook, narration, tts_text, title, description, visual_plan, and fact_check_notes. Do not use Hindi, Hinglish, Romanized Hindi, or Devanagari. Do not add forced slang, fake hype, or an exaggerated announcer voice.
- Apply a read-aloud test: if a line sounds awkward or unnatural when spoken in one breath, rewrite it.
</voice>
<style>
- Vary sentence openings and length. Prefer short spoken beats and specific wording over polished essay sentences.
- Use natural gaming language where it fits: low HP, take cover, heal up, aim, crosshair, enemy, damage, close range, re-peek, ranked, and training ground.
- Avoid stiff phrases such as "in conclusion", "moreover", "furthermore", "it is important to note", "subsequently", "in order to", and "at the end of the day".
- Do not start every sentence with "If", "When", "First", or "Then". Connect ideas only when the transition sounds natural aloud.
</style>
<before_after_examples>
- Robotic: "In order to survive the encounter, it is important to make use of nearby cover."
  Natural: "Low on HP? Get behind cover, heal up, and take the fight when you have an opening."
- Robotic: "Furthermore, you should refrain from engaging the enemy at close range."
  Natural: "Don't force a close-range fight when you're not ready for it."
- Robotic: "It is important to note that practice is essential for improving your aim."
  Natural: "Want steadier aim? Spend a few minutes practising in the training ground."
- Keep the same gaming fact and advice; only make the delivery sound more natural.
</before_after_examples>
- The final audience is gaming Shorts viewers. Avoid generic intros like "Hey guys, welcome back" and filler that delays the useful point.
- Keep personality subtle. Do not cram "bro", "literally", "insane", or "trust me" into every script.
- Keep every spoken sentence easy to say aloud. Use natural contractions, varied rhythm, clean punctuation, and a clear thought per sentence.
- Stay grounded in the supplied topic. Do not invent hidden mechanics, percentages, weapon behaviour, pro-player habits, or guaranteed results. If a claim cannot be supported, omit it or flag it in fact_check_notes.
- Start with a specific curiosity or gameplay situation, not a generic clickbait promise. Keep the hook around 6-12 spoken words.
- Keep combined hook + narration close to {target_words} spoken words for a target of about {target_seconds:.0f} seconds. The footage duration is a hard limit: be concise, avoid filler, and finish the thought naturally.
- Build around 2-3 clear beats, with practical advice or a useful observation viewers can actually follow.
- Use punctuation for spoken rhythm, but do not write stage directions or phonetic spellings that the narrator would read aloud.
- In the "language" field, write "English".
- The "tts_text" field must contain the exact same spoken words as hook + narration, in plain English. Do not transliterate, rewrite, or add any words to tts_text.
- Make tts_text sentence boundaries match the spoken hook and narration so the TTS layer can create natural pauses.
- Never use em dashes, en dashes, markdown dividers, repeated hyphens, underscore separators, or decorative punctuation in user-visible copy.
- The renderer splits the timed speech into short animated caption phrases; do not format narration as a visible paragraph.
- Flag uncertain claims for verification in fact_check_notes.
- Do not imitate a named creator's voice or copy another video's script. Match only broad pacing and editing conventions of professional gaming Shorts.
- Suggest practical visual beats that can be created from owned/licensed gameplay footage.
- Keep the title accurate, punchy, and non-misleading.
- Do not reuse the same core idea, title, or hook from recent history below. Choose a clearly different angle even when the broad weekly format is the same.
- Avoid repeated title templates; a new topic must feel packaged differently, not just have one word changed.
- Prefer a different topic family from the most recent Shorts when a reasonable candidate is supplied. Do not force consecutive Shorts into the same narrow sub-topic.
- Recent Shorts to avoid repeating:
{history_prompt_context()}
Performance learning context (soft signal only):
{strategy_prompt_context()}
"""

    def request_script(request_prompt: str, temperature: float) -> dict[str, Any]:
        errors: list[str] = []
        for candidate_model in model_candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent"
            for attempt in range(3):
                try:
                    generation_config = {
                        "temperature": temperature,
                        "responseMimeType": "application/json",
                    }
                    candidate_lower = candidate_model.lower()
                    if candidate_lower.startswith("gemini-3"):
                        # Gemini 3.5 supports minimal thinking for lower latency.
                        generation_config["thinkingConfig"] = {"thinkingLevel": "minimal"}
                    elif candidate_lower.startswith("gemini-2.5"):
                        # Gemini 2.5 Flash can disable thinking for fast structured-output calls.
                        generation_config["thinkingConfig"] = {"thinkingBudget": 0}

                    response = requests.post(
                        url,
                        params={"key": api_key},
                        json={
                            "contents": [{"parts": [{"text": request_prompt}]}],
                            "generationConfig": generation_config,
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

    data = request_script(prompt, 0.78)
    for repair_attempt in range(2):
        duplicate = is_duplicate_script(data)
        style_warnings = _spoken_style_warnings(
            str(data.get("hook", "")),
            str(data.get("narration", "")),
        )
        visible_copy_warning = _non_english_visible_copy_warning(data)
        if visible_copy_warning:
            style_warnings.append(visible_copy_warning)
        if not duplicate and not style_warnings:
            break

        repair_reasons: list[str] = []
        if duplicate:
            repair_reasons.append(
                "The draft is too similar to a recent Short. Change the angle, hook, title, and narration while staying truthful to the requested topic."
            )
        if style_warnings:
            repair_reasons.append(
                "The spoken wording sounds written, formulaic, or non-English. Rewrite it in natural, conversational English. Fix these signals: "
                + "; ".join(style_warnings)
            )

        repair_prompt = prompt + f"""
<repair>
This is a repair pass. Preserve the factual scope and the core topic. Do not invent mechanics, statistics, weapons, or claims.
Return the same JSON keys.
Keep the title accurate.
Rewrite only as much as needed to fix the problems below.

Problems:
- {" ".join(repair_reasons)}

Current draft:
{json.dumps(data, ensure_ascii=False, indent=2)}
</repair>
"""
        data = request_script(repair_prompt, 0.84)
    else:
        duplicate = is_duplicate_script(data)
        style_warnings = _spoken_style_warnings(
            str(data.get("hook", "")),
            str(data.get("narration", "")),
        )
        visible_copy_warning = _non_english_visible_copy_warning(data)
        if visible_copy_warning:
            style_warnings.append(visible_copy_warning)
        if duplicate:
            raise RuntimeError(
                "Gemini produced a Short that is too similar to a recent run after two repair passes."
            )
        if style_warnings:
            raise RuntimeError(
                "Gemini could not produce natural spoken phrasing after two repair passes: "
                + "; ".join(style_warnings)
            )

    data.pop("_model_used", None)
    data = _clean_generated_fields(data)
    # Run the shared final cleaner again after any Gemini repair pass.
    for key in ("topic", "language", "hook", "narration", "tts_text", "title", "description"):
        if isinstance(data.get(key), str):
            data[key] = clean_user_text(data[key])
    required = ("topic", "hook", "narration", "title", "description")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        raise RuntimeError("Generated script is missing required fields: " + ", ".join(missing))
    data["topic"] = re.sub(r"\s+", " ", str(data["topic"])).strip()
    data["hook"] = re.sub(r"\s+", " ", str(data["hook"])).strip()
    data["narration"] = re.sub(r"\s+", " ", data["narration"]).strip()
    data["language"] = "English"
    data["tts_text"] = f"{data['hook']} {data['narration']}".strip()
    data["topic_family"] = topic_family(str(data["topic"]))
    data["hook_style"] = classify_hook_style(str(data["hook"]))
    return data
