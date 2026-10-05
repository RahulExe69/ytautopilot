from __future__ import annotations

import json
import os
import re
from typing import Any

from .content import choose_daily_topic, classify_hook_style, history_prompt_context, is_duplicate_script, topic_family
from .analytics import strategy_prompt_context

import requests




_SPOKEN_STYLE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("isse behtar hai", "essay-like comparison"),
    ("jiske chalte", "formal causal connector"),
    ("jiske karan", "formal causal connector"),
    ("is prakar", "formal connector"),
    ("is prakaar", "formal connector"),
    ("prapt", "bookish Hindi"),
    ("upyog", "bookish Hindi"),
    ("upayog", "bookish Hindi"),
    ("avashyak", "bookish Hindi"),
    ("sunishchit", "bookish Hindi"),
    ("dauran", "bookish Hindi"),
    ("keval", "bookish Hindi"),
    ("tatha", "bookish Hindi"),
    ("yadi", "bookish Hindi"),
    ("atah", "bookish Hindi"),
    ("uparant", "bookish Hindi"),
)

def _spoken_style_warnings(hook: str, narration: str) -> list[str]:
    """Reject phrasing that sounds written rather than spoken by a gaming creator."""
    combined = re.sub(r"\s+", " ", f"{hook} {narration}".strip()).lower()
    warnings: list[str] = []

    for phrase, reason in _SPOKEN_STYLE_REPLACEMENTS:
        if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", combined):
            warnings.append(f"{phrase!r}: {reason}")

    if re.search(r"\bjab tak\b", combined) and re.search(r"\btab tak\b", combined):
        warnings.append("'jab tak ... tab tak': sounds formulaic; use a shorter spoken construction")

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", combined) if part.strip()]
    for sentence in sentences:
        words = re.findall(r"[a-z0-9]+", sentence)
        if len(words) > 22:
            warnings.append(f"long sentence ({len(words)} words): break it into two spoken beats")
        if len(re.findall(r"\b(aur|phir|toh|bas)\b", sentence)) >= 4:
            warnings.append("too many connector/filler words in one sentence")

    if re.search(r"\b(gameplay|content|video|strategy)\s+(ka|ki|ke)\s+(anubhav|upyog|sandarbh)\b", combined):
        warnings.append("generic article-like gaming language")

    return warnings[:8]


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
<voice>
- You are writing for ZynexPlayz, a young Indian gaming creator. Every spoken line should sound like something a real player would say in a casual voice note to a friend.
- Use everyday Hindi/Hinglish, not "shuddh Hindi". Keep it confident and useful, but never theatrical or over-written.
- Run a mental "voice-note test": if a line would feel awkward when spoken aloud in one breath, rewrite it before returning the JSON.
</voice>
<style>
- Vary sentence openings and sentence length. Prefer short spoken beats over polished essay sentences.
- Use contractions and natural phrasing such as "HP low hai", "fight force mat karo", "peeche ho jao", "cover le lo", and "phir wapas peek karo" when they fit the meaning.
- Do not stack formal connectors like "isse behtar hai", "isliye", "is prakar", "jiske karan", "dauran", or "keval" just to connect ideas.
- Avoid constructions that feel translated from English, such as "agar tum ... karte rahoge, toh..." when a simpler spoken line works.
- Do not make every sentence start with "Agar", "Jab", "Pehle", or "Phir".
</style>
<before_after_examples>
- Robotic: "Isse behtar hai ki ek second ke liye piche hato, koi paas ka cover lo, aur pehle heal karo."
  Natural: "Better hai ek second peeche ho jao, cover lo... aur pehle heal kar lo."
- Robotic: "Agar tum low HP ke saath bhi push karte rahoge, toh enemy tumhe aasaani se eliminate kar dega."
  Natural: "HP low hai toh fight force mat karo. Warna enemy ko easy knock mil jayega."
- Robotic: "Jab tak tumhara health bar full nahi hota, tab tak bas defensive khelo."
  Natural: "HP full hone tak bas thoda defensive khelo."
- Keep the same gaming fact and advice; only make the delivery sound more like a real creator.
</before_after_examples>
- Address the viewer as "tum/tumhara/tumhe", never "tu/tujhe/tera/teri"; keep it friendly and respectful, not over-familiar.
- Use natural Hinglish freely: common English words such as "body", "use", "side", "aim", "enemy", "damage", "fight", "timing", "movement", "cover", "game", "match", "push", "try", and "practice" are welcome when they sound more natural than formal Hindi.
- Avoid formal/bookish wording such as "sharir", "upayog/istamal" when "body/use" would sound natural, "dauran", "nuksan uthana", "prapt", "avsar", "pratyaksh", "sahayata", or other unnecessarily Sanskritised vocabulary. Prefer simple spoken forms like "body", "use", "karte waqt", "damage", "mil jata hai", "dikhta hai", and "try karna".
- Do not force Hindi words just to make the script look Hindi. Natural Hinglish is the goal.
- Also output a separate "tts_text" field containing the exact same spoken content as hook + narration, converted into natural Devanagari for Hindi words. Do not omit the hook from tts_text.
- In tts_text, transliterate the actual spoken Hinglish naturally for pronunciation, for example "बॉडी", "यूज़", "साइड", "एम", "एनेमी", "डैमेज", "फाइट", "टाइमिंग", "मूवमेंट", "कवर", "गेम", "मैच", and "ट्राय" when those are used in narration. Do not rewrite the meaning into more formal Hindi while converting to Devanagari.
- Prefer Devanagari for ordinary Hindi and common gaming terms when that improves Indian-Hindi pronunciation, for example "फ्री फायर", "ग्लू वॉल", "हेडशॉट", "रैंक्ड", "स्कोप", "स्नाइपर", and "गेमप्ले". Keep product or weapon names in Latin only when their pronunciation is clearly better that way.
- Example style: "Cover ke peeche ho toh body pura bahar mat nikalo. Thoda side se peek karo, bas jitna aim karne ke liye chahiye." This is the target feel: natural spoken Hinglish, not formal Hindi.
- Keep personality subtle: don't cram "bhai", "sun", "dekho", "matlab", or "na" into every script.
- Prefer the smallest natural sentence that can carry the point. Two short lines are better than one polished paragraph.
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
        if not duplicate and not style_warnings:
            break

        repair_reasons: list[str] = []
        if duplicate:
            repair_reasons.append(
                "The draft is too similar to a recent Short. Change the angle, hook, title, and narration while staying truthful to the requested topic."
            )
        if style_warnings:
            repair_reasons.append(
                "The spoken wording sounds written or formulaic. Rewrite it in natural everyday Indian gaming Hinglish. Fix these signals: "
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
    required = ("topic", "hook", "narration", "tts_text", "title", "description")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        raise RuntimeError("Generated script is missing required fields: " + ", ".join(missing))
    data["topic"] = re.sub(r"\s+", " ", str(data["topic"])).strip()
    data["hook"] = re.sub(r"\s+", " ", str(data["hook"])).strip()
    data["narration"] = re.sub(r"\s+", " ", data["narration"]).strip()
    data["tts_text"] = re.sub(r"\s+", " ", str(data["tts_text"])).strip()
    data["topic_family"] = topic_family(str(data["topic"]))
    data["hook_style"] = classify_hook_style(str(data["hook"]))
    return data
