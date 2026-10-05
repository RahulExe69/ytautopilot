# Testing and Release Checklist

## Code

- Python quality workflow passes.
- No secrets in source.
- Generated text has artifact sanitization.
- Duplicate/content history protections remain enabled.
- TTS keeps the intended voice and sentence boundaries.
- Render remains 1080x1920/30 fps.
- Upload defaults to private.

## Prepare run

Confirm gameplay/music rights and required secrets. Run `prepare` and inspect the full artifact.

Check:

- natural hook
- clear sentence endings and pauses
- pronunciation
- caption alignment
- no `---` / `___` / markdown artifacts
- topic/title differs from recent uploads
- useful gameplay scene transitions
- music stays under narration

## Publish run

Before publishing, verify facts, title, description, footage/music rights, thumbnail readability, privacy and schedule.

## After publishing

Record the video ID/status/schedule and observe views, likes, comments, topic family, hook style, duration and publish hour. The analytics profile should optimize softly and retain exploration rather than overfit to one Short.

## Safe iteration order

When quality is poor, change one layer at a time:

1. script naturalness
2. TTS prosody
3. pronunciation
4. caption timing
5. gameplay selection
6. music level
7. final encoding
