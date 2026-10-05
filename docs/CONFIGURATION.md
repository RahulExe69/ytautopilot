# Configuration Reference

## GitHub Actions secrets

| Name | Required | Purpose |
|---|---:|---|
| `GEMINI_API_KEY` | yes | Gemini generation |
| `YOUTUBE_CLIENT_ID` | publish/scheduled | OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | publish/scheduled | OAuth client secret |
| `YOUTUBE_REFRESH_TOKEN` | publish/scheduled | OAuth refresh credential |

Never commit these values.

## GitHub Actions variables

| Name | Default | Purpose |
|---|---|---|
| `GEMINI_MODEL` | project/model default | Gemini model override |
| `INDICVOICE_MODEL` | `Bindkushal/IndicVoice-82M` | IndicVoice repository |

## Current workflow environment

| Variable | Current value | Purpose |
|---|---:|---|
| `YTAP_FAST_MODE` | `1` | optimized path |
| `SCENE_FRAME_SKIP` | `1` | scene detection sampling |
| `CROPDETECT_FRAMES` | `48` | crop detection budget |
| `SCENE_WORKERS` | `2` | parallel analysis |
| `TORCH_NUM_THREADS` | `0` | resolves to CPU count |
| `FFMPEG_PRESET` | `ultrafast` | fast encode |
| `INDICVOICE_VOICE` | `hf_beta` | fixed narrator |
| `INDICVOICE_SPEED` | `1.20` | default speech speed |
| `INDICVOICE_VOICE_FALLBACK_REPO` | `hexgrad/Kokoro-82M` | voice fallback |
| `INCLUDE_HOOK_IN_NARRATION` | `true` | include hook in speech |

## Manual workflow inputs

`mode`: `dry-run`, `prepare`, `publish`.

`topic`: `auto` for normal automatic selection, or an explicit topic for testing.

## Local requirements

Python 3.11+, FFmpeg/ffprobe, eSpeak-NG, Noto fonts and network access for Gemini/model downloads.

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m ytautopilot --mode prepare --topic auto
```

## Inputs

Put owned/licensed gameplay in `assets/gameplay/` and permitted music in `assets/music/`. Video files are discovered automatically.

## Scheduling

Scheduled Actions runs are configured for 12:00 and 19:30 Asia/Kolkata. The pipeline calculates future publication targets for those slots. Manual publish clears `YOUTUBE_PUBLISH_AT`.

## Website credentials

The companion ZynexPlayz Vercel site uses separate `YOUTUBE_API_KEY` and `YOUTUBE_CHANNEL_HANDLE` variables. These are not substitutes for GitHub OAuth secrets.
