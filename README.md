# ytautopilot

Copyright (c) 2026 RahulExe69. All rights reserved.

This repository and its source code are proprietary. No permission is granted to copy, modify, distribute, sublicense, publish, sell, or create derivative works from this code without prior written permission from the copyright holder.

## Project status

**Stage 5 publish-ready packaging is now in place, building on the Stage 4 free/local voice + scene-safe renderer.** The workflow supports a manual dry-run and Hindi/Hinglish gaming script generation, plus a **prepare** mode that creates a reviewable vertical Short from gameplay assets.

The prepare mode currently:
1. Generates a conversational Hindi/Hinglish script with Gemini, targeting short spoken beats rather than article-style narration.
2. Generates Hindi narration locally with the Apache-2.0 IndicVoice model using the fixed female `hf_beta` voice preset and a Devanagari TTS text layer, avoiding paid TTS APIs.
3. Builds estimated caption timing from the spoken text, then renders 1-3 word animated lower-middle pop-ins with highlighted keywords.
4. Detects scene boundaries in every file under `assets/gameplay/` and builds the 1080x1920, 30 fps montage only from complete detected scenes, while preferring unused source files before reusing one. The script word budget is automatically based on the total available gameplay duration, and rendering refuses to create a Short longer than its source footage. Add `gameplay5.mp4`, `gameplay6.mp4`, and so on without changing code.
5. Mutes gameplay audio completely and automatically selects one supplied track from `assets/music/` as low-volume background music. The workflow normalizes arbitrary music filenames to `music_01`, `music_02`, `music_03`, and so on.
6. Burns the animated caption track into the video.
7. Exports output/short_preview.mp4 plus script, narration, SRT, ASS captions, a render manifest, a generated vertical thumbnail candidate, and validated output/publish_metadata.json as a GitHub Actions artifact.

**YouTube publishing is still not implemented. Nothing is uploaded to YouTube.** Prepare mode now creates a publish-ready metadata file and a thumbnail candidate from the rendered video; it does not claim the candidate was applied as a YouTube Shorts cover.

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
4. The narrator is fixed to the female `hf_beta` voice, with a default speaking speed of 1.28x. No voice selector is exposed in the workflow.
   - INDICVOICE_MODEL — defaults to `Bindkushal/IndicVoice-82M`.
   - Hindi voice tensors are sourced from `hexgrad/Kokoro-82M` when the IndicVoice repository does not contain a usable copy.
5. Put your own/licensed gameplay videos in assets/gameplay/. One clip is enough for the first test; multiple clips give the renderer more visual variety.
6. Open **Actions → ytautopilot → Run workflow**. Use topic `auto` for the next unused topic from the weekly Free Fire content rotation. Successful prepare runs are recorded in `data/content_history.json`, allowing the generator to avoid repeating recent titles, hooks, and topics.

### Dry-run

Choose **dry-run** to generate only output/script.json. No video is rendered and no YouTube upload is attempted.

### Prepare

Choose **prepare** to generate the script and render a reviewable Short. The workflow artifact should contain:

- script.json
- short_preview.mp4
- narration.mp3
- captions.srt
- captions.ass
- render_manifest.json
- publish_metadata.json (title, description, hashtags, optional tags, video path, cover candidate, and private-upload default)
- thumbnail_candidate.jpg (generated from a frame of the rendered Short)

The rendered MP4 is a preview only. Review its factual accuracy, audio, captions, footage rights, and overall quality before publishing anywhere.

## Safety defaults

- The workflow runs only when manually triggered; no schedule is enabled.
- Publishing is disabled and not implemented in this stage.
- Never commit OAuth client files, refresh tokens, API keys, or generated media.
- Do not scrape or reuse a creator's footage based only on an assumption. Verify the creator's actual reuse terms and retain evidence, or use your own gameplay.
- Review facts, narration, captions, audio, and rights before publishing.
- YouTube API projects in the unverified state may be restricted from making uploaded videos public; verify current Google requirements before enabling future upload functionality.

## Local prepare

Requires Python 3.11+, FFmpeg, espeak-ng, and a working network connection for Gemini script generation plus the first model download.

    pip install -r requirements.txt
    sudo apt-get install ffmpeg fonts-noto-core espeak-ng
    PYTHONPATH=src python -m ytautopilot --mode prepare --topic "Free Fire tips"

The generated files are written to output/.

## License

All rights reserved. This is not an open-source license. Viewing the public repository does not grant permission to reuse the code.
