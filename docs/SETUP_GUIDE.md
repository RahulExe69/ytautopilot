# YTAutoPilot — Complete Setup & Contributor Guide

This guide documents how to set up the current YTAutoPilot stages, troubleshoot them, and help another creator build a separate project inspired by the workflow.

> **Current status:** Stage 4 free/local voice and scene-safe rendering is implemented. The workflow supports a manual dry-run and Hindi/Hinglish gaming script generation. Prepare mode renders a reviewable 9:16 Short with conversational narration, local IndicVoice TTS, scene-safe gameplay cuts, and animated pop-up captions using FFmpeg. YouTube publishing is not implemented and no uploads happen automatically. The workflow is manually triggered; no schedule is enabled.

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
2. Use the project selector to create or select a dedicated project, for example Zynex Playz AutoPilot.
3. Open **APIs & Services → Library**.
4. Search for **YouTube Data API v3**, open it, and press **Enable**.
5. If using Gemini, create an API key in Google AI Studio / Gemini API setup and keep it private. Do not confuse a Gemini API key with YouTube OAuth credentials.

Enabling the YouTube API does not grant channel access; OAuth authorization is a separate step.

## 3. Configure Google OAuth for the future upload stage

The current Stage 2 renderer does not need YouTube OAuth. Do this now only if you want the upload credentials ready for a later stage.

1. Open Google Auth Platform: https://console.cloud.google.com/auth/overview
2. Select the correct Cloud project.
3. Under **Branding**, set the app name, support email, and developer contact email.
4. Under **Audience**, choose **External** if offered for a personal Gmail account.
5. During development, keep the app in **Testing** and add the Google account that will authorize uploads as a test user.
6. Under **Data Access**, request only the scope that a future uploader actually needs. YouTube uploads normally use:
   https://www.googleapis.com/auth/youtube.upload

### OAuth client for OAuth Playground

If you use OAuth Playground to obtain a refresh token:

1. Go to **Google Auth Platform → Clients** and create a **Web application** OAuth client.
2. Add this exact authorized redirect URI:
   https://developers.google.com/oauthplayground
3. Save the client.
4. Open:
   https://developers.google.com/oauthplayground
5. Open the settings gear.
6. Enable **Use your own OAuth credentials**.
7. Enter the Client ID and Client Secret from the Web application client created above.
8. In **Input your own scopes**, enter:
   https://www.googleapis.com/auth/youtube.upload
9. Choose **Authorize APIs** and sign into the intended YouTube channel account.
10. Grant consent.
11. Choose **Exchange authorization code for tokens**.
12. In the returned JSON, copy only the complete value of refresh_token.

Do not paste the refresh token into chat, an issue, source code, screenshots, or a normal log.

### Important OAuth testing warning

External OAuth apps left in Testing can issue refresh tokens that expire after about seven days for certain non-basic scopes. OAuth Playground can expose the actual refresh_token_expires_in value in its response. Treat that value as authoritative for the token you just received.

Do not assume a Testing-mode refresh token will last for a month, and do not assume moving an app to Production automatically removes all verification or YouTube restrictions.

## 4. Add GitHub Actions secrets and variables

Open **Settings → Secrets and variables → Actions**.

### Secret used now

Add:

| Name | Value |
|---|---|
| GEMINI_API_KEY | Your private Gemini API key |

### Future YouTube secrets

The project may later use these names:

| Name | Value |
|---|---|
| YOUTUBE_CLIENT_ID | Client ID for the OAuth client that issued the refresh token |
| YOUTUBE_CLIENT_SECRET | Client Secret for that same client |
| YOUTUBE_REFRESH_TOKEN | The complete refresh-token value only |

The current Stage 2 workflow intentionally does not use those YouTube secrets.

### Optional variables

| Name | Default | Purpose |
|---|---|---|
| GEMINI_MODEL | Project-supported model | Gemini script generation |
| INDICVOICE_VOICE | am_adam | Local Hindi voice style |
| INDICVOICE_MODEL | Bindkushal/IndicVoice-82M | Local Apache-2.0 TTS model |

EDGE_TTS_VOICE and EDGE_TTS_RATE are not secrets.

## 5. Add gameplay

Open assets/gameplay/ in GitHub and upload one or more gameplay videos that you own or have explicit permission/license to reuse.

Recommended:
- MP4 where possible.
- 30–60 seconds per clip for early tests.
- Vertical footage is ideal; landscape footage is center-cropped to 1080x1920.
- Multiple clips give the renderer more visual variety.
- Filenames do not need to follow a special pattern. The renderer discovers supported video extensions automatically.

The Stage 4 renderer detects scene boundaries and selects complete gameplay scenes. It no longer cuts at arbitrary fixed timestamps. Multiple clips are recommended for variety.

## 6. Run the safe dry-run

1. Open **Actions** in the repository.
2. Select **ytautopilot**.
3. Tap **Run workflow**.
4. Choose **dry-run**.
5. Keep the topic or enter your own.
6. Wait for the run to finish.
7. Download the artifact and inspect script.json.

This confirms script generation only.

## 7. Run Stage 4 prepare mode

1. Open **Actions → ytautopilot → Run workflow**.
2. Keep your topic, for example Free Fire tips and lesser-known facts.
3. Change **mode** from **dry-run** to **prepare**.
4. Run the workflow.
5. Wait for the job to finish.
6. Open the artifact named like ytautopilot-output-<run-number>.
7. Download and play short_preview.mp4.

The artifact should contain:
- script.json
- short_preview.mp4
- narration.mp3
- captions.srt
- captions.ass
- render_manifest.json

Prepare mode does **not** publish to YouTube.

## 8. How Stage 4 works

1. Gemini creates the script JSON in conversational Hindi/Hinglish, using short spoken beats and casual "tum" phrasing.
2. Gemini creates both Roman-Hinglish caption text and a Devanagari TTS text layer so Hindi words such as "hume" can be spoken as "हमें".
3. IndicVoice renders the Hindi narration locally using the Apache-2.0 IndicVoice-82M model; no paid TTS API is required.
4. The renderer estimates caption timing from the spoken text and converts it into short 1-3 word caption events.
5. Each caption event pops up from below, scales into place, fades out, and highlights important gaming keywords rather than leaving a paragraph on screen.
6. PySceneDetect finds complete gameplay scenes, and the renderer selects those scenes instead of cutting at arbitrary timestamps.
7. Gameplay is scaled/cropped to 1080x1920 at 30 fps with a small visual grade.
8. Gameplay audio is muted completely. One of the supplied tracks in `assets/music/` is automatically selected and mixed quietly under the narration.
9. output/short_preview.mp4 is created with animated ASS captions burned into the video.
10. GitHub Actions uploads the output folder as an artifact so you can review it.

The renderer intentionally does not:
- upload to YouTube,
- automatically fact-check the generated claims,
- fetch external gameplay,
- remove watermarks,
- provide a built-in music library; only user-supplied tracks in `assets/music/` are used,
- generate thumbnails,
- schedule publishing.

## 9. Troubleshooting Stage 4

### No gameplay found

Check that at least one supported video exists inside assets/gameplay/.

### IndicVoice failed

Check the job log around the TTS step. The first run needs network access to download the open-source model from Hugging Face; later runs can reuse the GitHub Actions model cache. The workflow also installs espeak-ng for the model's phonemizer fallback.

If a voice style is unavailable, remove INDICVOICE_VOICE and retry with the default am_adam.

### FFmpeg subtitles failed

The workflow installs FFmpeg and fonts-noto-core. Inspect captions.srt in the artifact if FFmpeg reports malformed subtitles.

### Video is too short or too long

The creator-style renderer targets 10-52 seconds. The Gemini prompt aims for roughly 30-45 seconds. Shorten or expand the script rather than hard-coding video duration.

### Video is black or heavily cropped

Landscape gameplay is center-cropped into portrait. Vertical recordings usually give a better result.

### Captions look wrong

The renderer uses Noto Sans Devanagari and converts estimated speech timing into short animated ASS caption events. Inspect captions.ass for the event timing. The Roman-Hinglish caption layer is intentionally separate from the Devanagari TTS layer.

### Workflow succeeds but no YouTube video appears

Expected. Stage 2 ends at a reviewable MP4. Publishing is not implemented yet.

## 10. Quality gate before publishing

Before any future uploader is enabled, manually verify:

- The facts in the script.
- The gameplay is yours or properly licensed.
- The narration matches the script.
- Captions are synchronized and readable.
- Audio has no clipping or excessive noise.
- The MP4 opens correctly on a phone.
- The title and description are accurate.
- No private data or unrelated copyrighted material appears.

## 11. Starting a separate project inspired by this repository

For a new project:

1. Create your own repository and document its goal and current stage.
2. Use your own Google Cloud project, API keys, OAuth client, channel, and GitHub secrets. Never reuse another creator's tokens.
3. Read the upstream repository's license and permissions before copying any code. This repository currently states **All rights reserved**, so it is not an open-source license and does not grant permission to copy, modify, distribute, or create derivatives. You can learn from the general ideas, but obtain written permission before reusing its code.
4. Document setup, secret names, manual test steps, known limitations, and recovery instructions.
5. Keep dry-run as the default.
6. Add rendering only after confirming media rights.
7. Add publishing only after rendered output is reliable.
8. Use version control, small commits, logs that redact secrets, and a rollback path.

## 12. Security checklist

- [ ] Secrets are stored only in GitHub Actions secrets or another secret manager.
- [ ] OAuth client JSON and refresh tokens are not committed.
- [ ] Only the intended channel account will grant future upload consent.
- [ ] Media sources and permissions are documented.
- [ ] Dry-run passes and generated scripts are reviewed.
- [ ] Prepare mode produces a playable MP4.
- [ ] No public upload or recurring schedule is enabled until the full pipeline is tested.

## Useful references

- Google Cloud Console: https://console.cloud.google.com/
- Google Auth Platform: https://console.cloud.google.com/auth/overview
- YouTube Data API v3: https://console.cloud.google.com/apis/library/youtube.googleapis.com
- OAuth Playground: https://developers.google.com/oauthplayground
- YouTube Data API documentation: https://developers.google.com/youtube/v3
- GitHub Actions artifacts: https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts
- Microsoft Speech language and voice support: https://learn.microsoft.com/azure/cognitive-services/speech-service/language-support
- IndicVoice: https://github.com/Bindkushal/indic-voice
- Indic G2P: https://github.com/Bindkushal/indic-g2p
- PySceneDetect: https://www.scenedetect.com/

---
Last reviewed: 2026-10-04. Re-check provider documentation because API, voice, and OAuth requirements can change.
