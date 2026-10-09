# YTAutoPilot Architecture

YTAutoPilot is a GitHub Actions based Free Fire Shorts production pipeline. It turns a topic into a script, local Hindi/Hinglish narration, scene-safe vertical gameplay, captions, music, a publish package, and optionally a private/scheduled YouTube upload.

## End-to-end flow

```
GitHub Actions
  -> restore Python/Hugging Face caches
  -> install/check FFmpeg, fonts, eSpeak-NG
  -> choose mode + topic
  -> analytics learning profile (publish/scheduled runs)
  -> content selector
       -> topic bank
       -> recent history
       -> family cooldown
       -> phrase-overlap penalty
       -> performance learning
  -> Gemini script generation
       -> natural spoken Hinglish prompt
       -> recent title/topic context
       -> duplicate/style quality gate
       -> up to two repair passes
       -> AI-artifact sanitizer
  -> IndicVoice
       -> Hindi G2P
       -> fixed af_bella female preset
       -> sentence-aware synthesis
       -> punctuation-driven pacing
       -> controlled pauses
       -> MP3 encoding
  -> renderer
       -> scene detection
       -> crop detection
       -> gameplay/music rotation
       -> animated captions
       -> one final vertical FFmpeg encode
  -> validation + media fingerprint
  -> publish package
       -> sanitized title/description/tags
       -> thumbnail candidate
  -> optional YouTube upload
       -> OAuth refresh
       -> private upload
       -> optional publishAt
       -> upload dedupe marker
  -> persist data/*.json
```

## Modes

- **dry-run:** generate `output/script.json`; no rendering or upload.
- **prepare:** render and validate a reviewable Short; no YouTube upload.
- **publish:** run the complete pipeline and upload privately. Scheduled runs also set a future `publishAt`.

## Main modules

| Module | Responsibility |
|---|---|
| `__main__.py` | orchestration and retry loop |
| `content.py` | topic bank, diversity, history, fingerprints |
| `scriptgen.py` | Gemini generation, quality gates, repair and cleanup |
| `tts.py` | IndicVoice synthesis, pronunciation and prosody |
| `render.py` | scene selection, captions, music and FFmpeg |
| `media.py` | media fingerprints/history |
| `descriptions.py` | description/CTA rotation |
| `publish_package.py` | final metadata and thumbnail candidate |
| `validate_output.py` | final artifact validation |
| `youtube_upload.py` | OAuth, private upload, scheduling and upload dedupe |
| `analytics.py` | YouTube statistics and learned strategy |
| `scheduler.py` | IST publication target calculation |

## Duplicate protection

1. Unused-topic filtering.
2. Recent family cooldown.
3. Phrase-overlap and full-string similarity penalties.
4. Script duplicate/style gate with repair passes.
5. Deterministic rendered-media fingerprint.
6. Up to four generation/render attempts.
7. YouTube deterministic marker-tag lookup after ambiguous uploads.
8. Persistent state committed back to `main`.

## Persistent state

| File | Purpose |
|---|---|
| `data/content_history.json` | topics, titles, hooks and content fingerprints |
| `data/media_history.json` | rendered media fingerprints |
| `data/upload_history.json` | uploaded video IDs/status |
| `data/performance_history.json` | YouTube observations |
| `data/strategy_profile.json` | learned topic/hook/hour/duration/style preferences |
| `data/description_history.json` | description style usage |

## Generated artifacts

- `short_preview.mp4`
- `narration.mp3`
- `captions.srt`
- `captions.ass`
- `script.json`
- `render_manifest.json`
- `publish_metadata.json`
- `thumbnail_candidate.jpg`

## Design principle

Content intelligence, speech rendering, visual rendering, publishing and learning are separate layers. Each can be improved without rewriting the entire pipeline.
