# Natural spoken Hinglish

The narrator now treats spoken naturalness as a quality gate rather than only a prompt preference.

## Pipeline

1. Gemini is instructed to write for a real Indian gaming creator and to apply a "voice-note test" before returning the draft.
2. The generator checks for common essay-like Hindi connectors, over-long spoken sentences, formulaic constructions, and stacked filler words.
3. A flagged draft gets up to two targeted repair passes. The repair keeps the topic and factual scope instead of inventing new mechanics just to make the line more exciting.
4. The TTS layer normalizes common gaming shorthand and punctuation for the Hindi voice, including HP, 1v2, Gloo Wall, ADS, and similar speech-pronunciation cases.
5. The fast IndicVoice path still synthesizes the full prepared text in one call; the naturalness improvements do not add a second TTS engine or paid API.

## Research basis

Google's current Gemini prompting guidance recommends concise, precise instructions and explicitly steering the model when a conversational or chatty persona is desired. It also recommends clear prompt structure and examples for style control.

IndicVoice documents Hindi and English support and uses a native Indic phonemizer, while code-switching research treats Hindi-English mixed speech as a distinct linguistic phenomenon. For this project, that means keeping the language mix natural in the script while making the TTS input phonetic and pronunciation-friendly.

References:
- https://ai.google.dev/gemini-api/docs/prompting-strategies
- https://ai.google.dev/gemini-api/docs/gemini-3
- https://github.com/Bindkushal/indic-voice
- https://arxiv.org/abs/1810.00662
- https://arxiv.org/abs/2105.08807


## Prompting principles used

The current implementation follows Google's Gemini guidance to use clear, specific constraints, consistent prompt structure, explicit conversational steering, and a small number of concrete examples. Gemini's documentation also recommends structured JSON output when the response has a more complex schema. The project currently validates its generated JSON locally and can be migrated to native structured output if the selected Gemini API path makes that advantageous.

## Why this is layered

No single prompt can guarantee natural speech. The project therefore treats naturalness as a pipeline property:

- generation prompt controls vocabulary and creator persona
- examples demonstrate the desired spoken style
- linting catches recurring written-language patterns
- repair passes give Gemini a chance to rewrite
- sanitization removes visual AI artifacts
- TTS sentence segmentation creates explicit thought boundaries
- punctuation-aware pauses preserve those boundaries
- pronunciation rules handle gaming shorthand
- human listening remains the final quality check

## Current TTS behavior

The fast path uses the fixed `af_bella` female IndicVoice preset. It does not synthesize one large paragraph and hope the model discovers every boundary. It splits the prepared text into sentence units, synthesizes each unit, adds a small terminal pause based on punctuation, concatenates the units, and applies the configured `INDICVOICE_SPEED` (currently 1.20x).

This intentionally spends some synthesis overhead to improve intelligibility and prosody.

## Research references

- Google Gemini prompt design: https://ai.google.dev/gemini-api/docs/prompting-strategies
- Google Gemini 3 developer guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Google Gemini structured outputs: https://ai.google.dev/gemini-api/docs/structured-output
- IndicVoice: https://github.com/Bindkushal/indic-voice
- Hindi-English code-switching research: https://arxiv.org/abs/1810.00662
- Code-switching ASR research: https://arxiv.org/abs/2105.08807
