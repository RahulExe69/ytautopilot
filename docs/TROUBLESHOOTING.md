# Troubleshooting

## FFmpeg not found

The workflow explicitly installs/checks ffmpeg, ffprobe, fonts-noto-core, espeak-ng and libespeak-ng1. Inspect **Install system media tools** first.

## Python quality failure

`.github/workflows/python-quality.yml` runs `python -m compileall -q src`. Fix syntax before media testing.

## Robotic Hinglish

Inspect `output/script.json`. The pipeline is Gemini generation -> spoken-style lint -> up to two repair passes -> cleanup. Improve the prompt/quality rules before replacing the voice model.

## TTS rushes or ignores sentence endings

The fast path synthesizes sentence-by-sentence, inserts punctuation-aware pauses and encodes at `INDICVOICE_SPEED=1.20`. Check `tts_input` in the TTS manifest and inspect punctuation before increasing pauses.

## Pronunciation problems

The TTS layer normalizes common gaming shorthand including HP, low/full HP, 1v1/1v2/1v3, Gloo Wall, ADS and OP. Add repeatable vocabulary rules in `tts.py`.

## Repeated titles/topics

Inspect `data/content_history.json`. The selector now applies family cooldown and phrase overlap penalties, while Gemini is explicitly instructed to avoid repeated title templates.

## AI-looking --- or ___

Sanitization occurs at script generation, description construction and final publish metadata. Inspect `output/publish_metadata.json` to find what reaches the final boundary.

## State non-fast-forward

The workflow commits state, fetches `origin/main`, rebases and pushes. If conflicts occur, reconcile the JSON state rather than blindly overwriting another run.

## Slow Hugging Face startup

The workflow caches `~/.cache/huggingface` and enables offline mode when required model/voice assets are present. The first cold run can still be slow.

## IndicVoice voice tensor errors

The loader checks for Git-LFS/Xet pointer files and tries the configured repository, a known-good IndicVoice revision and the upstream Kokoro voice repository.

## OAuth failures

Verify the OAuth client, refresh token, intended channel, upload/read scopes and consent-screen state. Never put credentials in source or logs.

## Upload is private

Private can be expected for an unverified YouTube API project. See `YOUTUBE_API_AUDIT.md`. A private video with future `publishAt` may appear as Scheduled in Studio; that label alone does not prove API audit approval.

## Publish safety gate

Uploads intentionally require private visibility, a non-empty valid video/title/description and a deterministic fingerprint.

## Duplicate upload

`data/upload_history.json` plus the YouTube marker-tag lookup protect against retry duplicates.

## Visual repetition

Add more owned/licensed gameplay clips. A small source library limits montage diversity.

## Performance regression

Compare warm with warm and cold with cold. Check model/cache state, runner changes, scene settings, TTS, FFmpeg filters and artifact compression before changing code.
