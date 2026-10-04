# YTAutoPilot — Complete Setup & Contributor Guide

This guide documents how to set up the current YTAutoPilot stages, troubleshoot them, and help another creator build a separate project inspired by the workflow.

> **Current status:** Stage 2 is implemented. The workflow supports a manual dry-run and Hindi/Hinglish gaming script generation. **Prepare** mode also renders a reviewable 9:16 Short with Edge TTS + FFmpeg. YouTube publishing is not implemented and no uploads happen automatically. The workflow is manually triggered; no schedule is enabled.

## 1. What you need

- A GitHub account and a repository you control.
- A Google account for the intended YouTube channel.
- A Google Cloud project with YouTube Data API v3 enabled if you plan to add uploads later.
- A Gemini API key for live script generation.
- Self-recorded gameplay or footage with permission/license to reuse.
- A phone or computer with a modern browser.
- For local rendering: Python 3.11+, FFmpeg, and a Devanagari font such as Noto Sans Devanagari.

Never commit API keys, OAuth client JSON files, client secrets, refresh tokens, passwords, or private media to Git.

## 2. Create or select a Google Cloud project

1. Open https://console.cloud.google.com/ and sign in with the Google account you want to use.
2. Use the project selector to create or select a dedicated project, e.g. **Zynex Playz AutoPilot**.
3. Open **APIs & Services → Library**.
4. Search for **YouTube Data API v3**, open it, and press **Enable**.
5. If using Gemini, create an API key in Google AI Studio / Gemini API setup and keep it private. Do not confuse a Gemini API key with YouTube OAuth credentials.

Enabling the YouTube API does not grant channel access; OAuth authorization is a separate step.

## 3. Configure Google OAuth consent

Use OAuth only when the project is ready for the future upload stage.

1. Open Google Auth Platform: https://console.cloud.google.com/auth/overview
2. Select the correct Cloud project.
3. Under **Branding**, set the app name, user-support email, and developer contact email.
4. Under **Audience**, choose **External** if offered for a personal Gmail account.
5. During development, keep the app in **Testing** and add the Google account that will authorize uploads as a test user.
6. Under **Data Access**, request only the scopes the future uploader actually needs. Uploading videos normally uses https://www.googleapis.com/auth/youtube.upload

Do not add OAuth credentials to the repository. The current Stage 2 workflow does not read the YouTube secrets.

## 4. Add GitHub Actions secrets and variables

Open **Settings → Secrets and variables → Actions**.

### Secret

Add:

| Name | Value |
|---|---|
| GEMINI_API_KEY | Your private Gemini API key |

Future upload stages may also use the YouTube OAuth secrets already documented in the project, but they are intentionally unused by Stage 2.

### Variables

Optional variables:

| Name | Default | Purpose |
|---|---|---|
| GEMINI_MODEL | Project-supported model | Gemini script generation |
| EDGE_TTS_VOICE | hi-IN-MadhurNeural | Hindi narration voice |
| EDGE_TTS_RATE | +5% | Narration speaking rate |

EDGE_TTS_VOICE is not a secret. The available Hindi voices are published by Microsoft; keep the value to a currently supported voice.

## 5. Add gameplay

Open assets/gameplay/ in GitHub and upload one or more gameplay videos that you own or have explicit permission/license to reuse.

Recommended:
- MP4 where possible.
- 30–60 seconds per clip for early tests.
- Vertical footage is ideal; landscape footage is center-cropped to 1080x1920.
- Multiple clips give the renderer more visual variety.
- Keep filenames simple. The renderer discovers supported video extensions automatically, so it does not require a special exact filename.

The renderer uses three visual beats and cycles through the available clips. One clip is enough for a first test.

## 6. Run the safe dry-run

1. Open **Actions** in the repository.
2. Select **ytautopilot**.
3. Tap **Run workflow**.
4. Choose **dry-run**.
5. Wait for the run to finish.
6. Download the generated artifact and inspect script.json.

This confirms Gemini/script generation only.

## 7. Run Stage 2 prepare mode

1. Open **Actions → ytautopilot → Run workflow**.
2. Keep your topic, for example Free Fire tips and lesser-known facts.
3. Change **mode** from **dry-run** to **prepare**.
4. Run the workflow.
5. Wait for the job to finish.
6. Open the artifact named like ytautopilot-output-<run-number>.
7. Download and play short_preview.mp4.

The artifact should also contain:
- script.json — generated script metadata.
- narration.mp3 — generated narration.
- captions.srt — subtitle cues from TTS.
- render_manifest.json — renderer settings and source clip paths.

Prepare mode does **not** publish to YouTube.

## 8. How the renderer works

The Stage 2 renderer is intentionally simple so it can be debugged.

1. The script's hook and narration are combined into the spoken text.
2. edge-tts sends that text to Microsoft's online Edge text-to-speech service and saves MP3 + subtitle cues.
3. FFmpeg probes the narration duration.
4. Three gameplay beats are created with the available assets.
5. Each beat is scaled/cropped to 1080x1920 at 30 fps.
6. The subtitle file is burned into the video using the Noto Sans Devanagari font.
7. The narration is added as AAC audio and normalized.
8. The finished file is written to output/short_preview.mp4.
9. The workflow uploads output/ as a GitHub Actions artifact.

The renderer currently does not:
- upload to YouTube,
- automatically fact-check the script,
- fetch external gameplay,
- remove watermarks,
- synthesize background music,
- generate thumbnails,
- schedule publishing.

## 9. Troubleshooting Stage 2

### No gameplay found

Check that at least one supported video exists inside assets/gameplay/. Do not place the only copy in the repository root.

### edge-tts failed

Check the job log around the TTS step. The current renderer needs network access to Microsoft's Edge TTS service. You do not need an Azure Speech API key for this Stage 2 implementation.

If a voice is rejected, remove the EDGE_TTS_VOICE repository variable and retry with the default hi-IN-MadhurNeural, or choose another currently supported Hindi voice.

### FFmpeg subtitles failed

The workflow installs fonts-noto-core and FFmpeg. Make sure the error is not caused by a malformed subtitle file. The generated captions.srt in the artifact is the quickest file to inspect.

### Video is too short or too long

The renderer follows the narration duration and rejects narration shorter than 8 seconds or longer than 58 seconds. Shorten/expand the generated narration rather than hard-coding video duration.

### Video is black or heavily cropped

Landscape gameplay is center-cropped into portrait. For better framing, upload vertical gameplay or record with the subject near the center.

### Captions look wrong

The renderer uses Noto Sans Devanagari. Check the subtitle artifact and the video. Future iterations can add animated word-level captions or more advanced styling.

### Workflow succeeds but no YouTube video appears

Expected. Stage 2 ends at a reviewable MP4. Publishing is not implemented yet.

## 10. Current quality gate before publishing

Before any future uploader is enabled, manually verify:

- The facts in the script.
- The gameplay is yours or properly licensed.
- The narration matches the script.
- Captions are synchronized and readable.
- Audio has no clipping or excessive noise.
- The video opens correctly on a phone.
- The title/description are accurate.
- The video does not accidentally include private data or unrelated copyrighted material.

## 11. Starting a separate project inspired by this repository

For a new project:

1. Create your own repository and document its goal and current stage.
2. Use your own Google Cloud project, API keys, OAuth client, channel, and GitHub secrets. Never reuse another creator's tokens.
3. Read the upstream repository's license and permissions before copying any code. This repository currently states **All rights reserved**, so it is not an open-source license and does not grant permission to copy, modify, distribute, or create derivatives. You can learn from the general ideas, but obtain written permission before reusing its code.
4. Document setup, secret names, manual test steps, known limitations, and recovery instructions in your own README or setup guide.
5. Keep dry-run as the default. Add rendering only after confirming your media rights.
6. Add publishing only after the rendered output is reliable.
7. Use version control, small commits, logs that redact secrets, and a rollback path.

## 12. Security checklist

- [ ] Secrets are stored only in GitHub Actions secrets or an appropriate secret manager.
- [ ] OAuth client JSON and refresh tokens are not committed.
- [ ] Only the intended channel account will grant future upload consent.
- [ ] Media sources and permissions are documented.
- [ ] Dry-run passes and generated scripts are reviewed.
- [ ] Prepare mode produces a playable MP4.
- [ ] No public upload or recurring schedule is enabled until the full pipeline is tested.

## Useful official references

- Google Cloud Console: https://console.cloud.google.com/
- Google Auth Platform: https://console.cloud.google.com/auth/overview
- YouTube Data API v3: https://console.cloud.google.com/apis/library/youtube.googleapis.com
- OAuth Playground: https://developers.google.com/oauthplayground
- YouTube Data API documentation: https://developers.google.com/youtube/v3
- GitHub Actions artifacts: https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts
- Microsoft Speech language/voice support: https://learn.microsoft.com/azure/cognitive-services/speech-service/language-support
- edge-tts package: https://pypi.org/project/edge-tts/

---
Last reviewed: 2026-10-04. Re-check provider documentation because API, voice, and OAuth requirements can change.
