# Natural spoken English

YTAutoPilot creates English-language gaming Shorts with a native English text-to-speech path. Script quality is checked before rendering rather than relying on one prompt to produce a natural take every time.

## Pipeline

1. Gemini is instructed to write like a real gaming creator talking to viewers, using concise and conversational English.
2. The generator checks for Hindi/Devanagari leakage, formal essay connectors, corporate-sounding wording, excessive filler and over-long spoken sentences.
3. A flagged draft gets up to two targeted repair passes. The repairs preserve the requested topic and factual scope rather than inventing game mechanics for excitement.
4. The English TTS text is derived directly from the cleaned hook and narration. This prevents a separate phonetic/transliteration field from changing the spoken words.
5. IndicVoice runs with `lang_code="en"` and the fixed `af_bella` female voice preset. Sentence boundaries receive short punctuation-aware pauses; the workflow uses a conservative `INDICVOICE_SPEED=1.08`.

## Prompting principles

The script prompt asks for:

- Everyday English and naturally used contractions.
- Short, varied sentences with one clear thought per beat.
- Normal gaming vocabulary without forced slang or fake hype.
- Specific, useful hooks rather than generic introductions.
- Plain English in the hook, narration, captions and TTS input.
- Claims grounded in the supplied topic, with uncertain details flagged for review.

It also includes before/after examples so the model can distinguish natural spoken lines from stiff, article-like narration.

## Why this is layered

No single prompt guarantees natural speech. The generation prompt controls voice and vocabulary; linting catches recurring written patterns; repair passes give Gemini another chance; sanitization removes visible AI artifacts; sentence-aware synthesis improves pacing; and human listening remains the final quality check.

## TTS and captions

The same English hook and narration are sent to the TTS layer and displayed in captions. Text is cleaned for punctuation and spacing only; the TTS layer does not translate or transliterate the words. The fast path synthesizes sentence units, inserts short pauses between them, concatenates the audio and encodes the final MP3 at the configured speed.

English-language support is documented by the [IndicVoice project](https://github.com/Bindkushal/indic-voice). The generator's style and structure follow the general guidance in Google's [Gemini prompting documentation](https://ai.google.dev/gemini-api/docs/prompting-strategies).

## Human review

Before publishing, listen to the entire render rather than relying on a successful build alone. Check pronunciation of weapon names and abbreviations, natural stress, speed, sentence endings, caption timing, factual claims, footage/music rights and title accuracy.
