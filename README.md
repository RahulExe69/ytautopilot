# ytautopilot

Copyright (c) 2026 RahulExe69. All rights reserved.

This repository and its source code are proprietary. No permission is granted to copy, modify, distribute, sublicense, publish, sell, or create derivative works from this code without prior written permission from the copyright holder.

## Project status

**Stage 7 scheduled generation, duplicate-proof media rotation, descriptions, performance learning, and automated YouTube scheduling are now wired in.** The workflow supports manual dry-run, prepare, and an explicit **publish** mode. Scheduled runs calculate a future YouTube publishAt target; manual publish runs intentionally omit that target.

The generation/render pipeline currently:
1. Generates a conversational Hindi/Hinglish script with Gemini, targeting short spoken beats rather than article-style narration. Generated copy also passes a spoken-naturalness lint and can receive up to two repair passes before the renderer accepts it.
2. Generates Hindi narration locally with the Apache-2.0 IndicVoice model using the fixed female `hf_beta` voice preset and a Devanagari TTS text layer, avoiding paid TTS APIs.
3. Builds estimated caption timing from the spoken text, then renders 1-3 word animated lower-middle pop-ins with highlighted keywords.
4. Detects scene boundaries in every file under `assets/gameplay/` and builds the 1080x1920, 30 fps montage only from complete detected scenes, while preferring unused source files before reusing one. The script word budget is automatically based on the total available gameplay duration, and rendering refuses to create a Short longer than its source footage. Add `gameplay5.mp4`, `gameplay6.mp4`, and so on without changing code.
5. Mutes gameplay audio completely and automatically selects one supplied track from `assets/music/` as low-volume background music. The workflow normalizes arbitrary music filenames to `music_01`, `music_02`, `music_03`, and so on.
6. Randomly rotates gameplay scenes and background music using recent-use avoidance and inverse-use weighting, so repeated runs do not deterministically reuse the same montage.
7. After rendering, the pipeline fingerprints the final video, narration, music, and selected scene sequence. If the generated media is already in history, it is discarded and a fresh script/render is attempted (up to four attempts).
8. Burns the animated caption track into the video.
9. Exports output/short_preview.mp4 plus script, narration, SRT, ASS captions, a render manifest, a generated vertical thumbnail candidate, and validated output/publish_metadata.json as a GitHub Actions artifact.
10. Uses a rotating description/CTA system and feeds historical YouTube performance back into Gemini as a soft learning signal.

**YouTube upload and scheduling are implemented.** Publish mode refreshes the OAuth access token from the existing GitHub Actions secrets, validates the output package, uploads through videos.insert, records the returned video ID, and keeps persistent upload history for duplicate prevention. Scheduled runs also provide a future YouTube publishAt target. YouTube restricts uploads from unverified API projects created after 28 July 2020 to private viewing until the project completes Google's audit; see docs/YOUTUBE_API_AUDIT.md for the important distinction between that restriction and scheduled publishing.

## Fast workflow path

The GitHub Actions pipeline is tuned for warm-run latency: cached Python dependencies and Hugging Face assets, parallel gameplay scene analysis, a single final FFmpeg video encode, fast x264 settings, streamlined IndicVoice synthesis, low-latency Gemini thinking, and zero-compression media artifacts. The speed-first settings live in the workflow environment and can be disabled by setting `YTAP_FAST_MODE=0`. See `docs/PERFORMANCE.md` for the benchmark plan and the quality/speed trade-offs.

## Planned pipeline

The scheduled experiment runs twice per day in Asia/Kolkata. GitHub Actions starts the jobs at 12:00 and 19:30 IST, then uploads private videos with default YouTube publication targets of 13:00 and 20:30 IST. YouTube's publishAt scheduling mechanism can schedule a private video for future publication; API audit approval is a separate compliance status and should not be inferred merely from the Studio 'Scheduled' label.

Performance collection uses the official YouTube Data API statistics available to the authorized channel. The learning profile tracks views, likes, comments, topic family, description style, duration bucket, and publish hour. After enough public videos exist, it can softly prefer better-performing topics, descriptions, durations, and publish hours while preserving exploration.

## Setup

1. Open **Settings → Secrets and variables → Actions**.
2. Add a repository secret named GEMINI_API_KEY using your own Gemini API key. Never place API keys in source files or commit them.
3. Optionally add a repository variable named GEMINI_MODEL with a model currently available to your Gemini API project.
4. The narrator is fixed to the female `hf_beta` voice, with a default speaking speed of 1.28x. No voice selector is exposed in the workflow.
   - INDICVOICE_MODEL — defaults to `Bindkushal/IndicVoice-82M`.
   - Hindi voice tensors are sourced from `hexgrad/Kokoro-82M` when the IndicVoice repository does not contain a usable copy.
5. Put your own/licensed gameplay videos in assets/gameplay/. One clip is enough for the first test; multiple clips give the renderer more visual variety.
6. Open **Actions → ytautopilot → Run workflow**. Use topic `auto` for the next unused topic from the weekly Free Fire content rotation. Successful prepare runs are recorded in `data/content_history.json`, allowing the generator to avoid repeating recent titles, hooks, and topics.

### ZynexPlayz website configuration

The companion **ZynexPlayz** website is deployed on Vercel and reads YouTube channel statistics through its serverless `api/channel-stats.js` endpoint.

Keep the website credentials in **Vercel Environment Variables**, not in GitHub source:

| Vercel variable | Value | Secret? |
|---|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API v3 API key | Yes |
| `YOUTUBE_CHANNEL_HANDLE` | `@ZynexPlayz` | No |

Configure these under **Vercel → ZynexPlayz → Settings → Environment Variables**, then redeploy. The API key should be restricted in Google Cloud to the YouTube Data API v3. The current website uses the channel **handle** rather than a hardcoded channel ID; a channel ID is public and is not a secret.

The website key and the automation's YouTube OAuth credentials serve different purposes. GitHub Actions secrets such as `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` are for the automation's authenticated YouTube operations. Never commit API keys, client secrets, or refresh tokens to Git.

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
- publish_metadata.json
- thumbnail_candidate.jpg
- publish_metadata.json (title, description, hashtags, optional tags, video path, cover candidate, and private-upload default)
- thumbnail_candidate.jpg (generated from a frame of the rendered Short)

The rendered MP4 is a preview only. Review its factual accuracy, audio, captions, footage rights, and overall quality before publishing anywhere.

### Publish

Choose **publish** only for an intentional upload run. The same generation, render, and validation pipeline runs first. The upload module has hard safety gates that refuse anything except private visibility, and it never requests public or unlisted status.

A successful run writes the YouTube video ID to output/publish_metadata.json and updates data/upload_history.json. The upload module uses resumable uploads with retry handling for transient server and network failures. It also checks recent owned uploads for a deterministic topic marker stored as a non-display tag before creating a new video, so a retry after an ambiguous upload response can be deduplicated.

The generated thumbnail remains a candidate artifact. This implementation intentionally does not call thumbnails.set because custom thumbnail support can vary by channel.

## Safety defaults

- The workflow is manual for testing and also has two scheduled daily runs at 12:00 and 19:30 IST.
- Publishing and scheduled publication are implemented. The scheduled path sends a private video with publishAt; see docs/YOUTUBE_API_AUDIT.md for the current audit/compliance status and interpretation.
- Never commit OAuth client files, refresh tokens, API keys, or generated media.
- Do not scrape or reuse a creator's footage based only on an assumption. Verify the creator's actual reuse terms and retain evidence, or use your own gameplay.
- Review facts, narration, captions, audio, and rights before publishing.
- YouTube API projects in the unverified state can be restricted to private uploads. A future publishAt can still make a private upload appear as Scheduled in YouTube Studio; this is not proof of audit approval.

## Local prepare

Requires Python 3.11+, FFmpeg, espeak-ng, and a working network connection for Gemini script generation plus the first model download.

    pip install -r requirements.txt
    sudo apt-get install ffmpeg fonts-noto-core espeak-ng
    PYTHONPATH=src python -m ytautopilot --mode prepare --topic "Free Fire tips"

The generated files are written to output/.

## License

All rights reserved. This is not an open-source license. Viewing the public repository does not grant permission to reuse the code.
