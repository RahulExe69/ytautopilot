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
