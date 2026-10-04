# ytautopilot

Copyright (c) 2026 RahulExe69. All rights reserved.

This repository and its source code are proprietary. No permission is granted to copy, modify, distribute, sublicense, publish, sell, or create derivative works from this code without prior written permission from the copyright holder.

## Project status

**Stage 2 is now in place.** The workflow supports a manual dry-run and Hindi/Hinglish gaming script generation, plus a **prepare** mode that creates a reviewable vertical Short from gameplay assets.

The prepare mode currently:
1. Generates a script with Gemini.
2. Generates Hindi narration and subtitle cues with the edge-tts package using Microsoft's online Edge text-to-speech service.
3. Detects gameplay videos in assets/gameplay/.
4. Builds a 1080x1920, 30 fps gameplay track with four visual beats.
5. Burns the generated captions into the video.
6. Exports output/short_preview.mp4 plus the script, narration, captions, and a render manifest as a GitHub Actions artifact.

**YouTube publishing is still not implemented. Nothing is uploaded to YouTube.**

## Planned pipeline

1. Generate an original Hindi/Hinglish gaming script with Gemini.
2. Use self-recorded or explicitly licensed gameplay footage, with permission/provenance recorded.
3. Create Hindi narration, captions, and a vertical 9:16 Short with FFmpeg.
4. Review the rendered file before enabling uploads.
5. Upload through the official YouTube Data API with OAuth, then record upload IDs and basic metrics.

## Setup

1. Open **Settings → Secrets and variables → Actions**.
2. Add a repository secret named GEMINI_API_KEY using your own Gemini API key. Never place API keys in source files or commit them.
3. Optionally add a repository variable named GEMINI_MODEL with a model currently available to your Gemini API project.
4. Optional TTS tuning variables:
   - EDGE_TTS_VOICE — defaults to hi-IN-MadhurNeural.
   - EDGE_TTS_RATE — defaults to +5%.
5. Put your own/licensed gameplay videos in assets/gameplay/. One clip is enough for the first test; multiple clips give the renderer more visual variety.
6. Open **Actions → ytautopilot → Run workflow**.

### Dry-run

Choose **dry-run** to generate only output/script.json. No video is rendered and no YouTube upload is attempted.

### Prepare

Choose **prepare** to generate the script and render a reviewable Short. The workflow artifact should contain:

- script.json
- short_preview.mp4
- narration.mp3
- captions.srt
- render_manifest.json

The rendered MP4 is a preview only. Review its factual accuracy, audio, captions, footage rights, and overall quality before publishing anywhere.

## Safety defaults

- The workflow runs only when manually triggered; no schedule is enabled.
- Publishing is disabled and not implemented in this stage.
- Never commit OAuth client files, refresh tokens, API keys, or generated media.
- Do not scrape or reuse a creator's footage based only on an assumption. Verify the creator's actual reuse terms and retain evidence, or use your own gameplay.
- Review facts, narration, captions, audio, and rights before publishing.
- YouTube API projects in the unverified state may be restricted from making uploaded videos public; verify current Google requirements before enabling future upload functionality.

## Local prepare

Requires Python 3.11+, FFmpeg, and a working network connection for Gemini and Edge TTS.

    pip install -r requirements.txt
    sudo apt-get install ffmpeg fonts-noto-core
    PYTHONPATH=src python -m ytautopilot --mode prepare --topic "Free Fire tips"

The generated files are written to output/.

## License

All rights reserved. This is not an open-source license. Viewing the public repository does not grant permission to reuse the code.
