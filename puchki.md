# Puchki Project Context — ytautopilot

Last updated: 2026-10-05

This file is persistent working context for Puchki (ChatGPT) and future coding agents. Read it before changing the project so we continue from the actual state rather than asking Rahul to repeat setup work.

## Owner and goal

- Owner: Rahul.
- Repository: https://github.com/RahulExe69/ytautopilot
- Target channel: **Zynex Playz**. Channel branding, logo, banner, and description were already completed.
- Goal: a zero-cost, mostly self-running 30-day experiment producing Hindi/Hinglish Free Fire YouTube Shorts. Pipeline goals include topic/script generation, Hindi narration, gameplay selection/editing, captions, publish metadata and thumbnail, safe YouTube upload, scheduling, and performance-informed iteration.
- Prioritize free services and GitHub Actions where feasible. Be honest about API quotas, platform restrictions, OAuth limitations, and any cost risks. Never claim code or output was tested unless there is actual run evidence.

## Secrets and OAuth — ALREADY CONFIGURED

Rahul confirmed on 2026-10-04 that these repository GitHub Actions secrets have already been added:
- `GEMINI_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

**Do not ask Rahul to add these secrets again.** Do not ask him to paste secret values into chat, commits, logs, or this file. This file must contain names/status only, never credentials or tokens.

YouTube Data API v3 was enabled. An OAuth Desktop client JSON was downloaded, the channel owner's Gmail was added as a test user, and authorization/refresh-token acquisition was completed. The OAuth consent app was still in **Testing** when last discussed; the refresh token was reported to have an approximately **7-day lifetime** in that configuration. This may expire or require reauthorization. Before depending on unattended publishing, check the current Google OAuth publishing/testing status and document the least disruptive valid fix. Do not assume the refresh token is still valid without a real authorized API test.

## Current pipeline and repository state

- GitHub Actions workflow: `.github/workflows/shorts.yml`.
- Workflow is manually triggered with `workflow_dispatch`, offering `dry-run` and `prepare`; it runs `python -m ytautopilot --mode ... --topic ...`.
- Output artifacts are uploaded from `output/` with a name like `ytautopilot-output-<run number>` and a 7-day retention.
- The workflow updates `data/content_history.json` in prepare mode.
- `dry-run` generates a script; `prepare` renders a reviewable vertical Short and creates a publish package. `publish` mode is currently gated/not implemented for actual upload.
- The render pipeline lives in `src/ytautopilot/render.py`; the entry point is `src/ytautopilot/__main__.py`; publish metadata and thumbnail generation live in `src/ytautopilot/publish_package.py`.
- Prepare mode creates `output/short_preview.mp4`, `output/publish_metadata.json`, and `output/thumbnail_candidate.jpg` (plus narration/captions/manifests).
- An earlier successful video was confirmed by Rahul. A past workflow run was run #30, ID `37228596095`, at commit `e850911f9d6e7cb123aa8414f51ec27fd200022b`; artifact ID `11313431413` was named `ytautopilot-output-30`. This is historical evidence only, not evidence that the latest code passes.
- Recent code commits address a prior render `tail_seconds` NameError, publish metadata/thumbnail packaging, Hindi thumbnail font shaping, and conservative detection/cropping of black letterboxing:
  - `15c572713d4b6bd11d372ed41840863c80871c3f`: detect/remove embedded gameplay letterboxing in render.
  - `c84ac99e3feac6de99bde840a5cf30f656346e3e`: allow conservative removal of larger top/bottom bars.
  - `6c5c99ee9f56eb3f66ae3ecabef10760b5cde9b1`: crop letterboxing from thumbnail source frames.
  - `985f66a1fea57b7debe8eb9733bd4ef0a284af00` and `908c91af56d10e34b12b693a1f1d43b67b772208`: improve Hindi thumbnail text rendering with Devanagari font and shaping checks.
- These latest visual fixes have been committed but **have not yet been visually verified by a fresh render**. Never state otherwise.

## Immediate next work

1. Inspect the current repo and workflow before editing; verify the latest commit and dependencies. Do not assume a change is wired just because a module exists.
2. Add or improve automated checks that validate generated MP4 dimensions/duration, output files, metadata, thumbnail dimensions, and font availability. Make failures visible in Actions logs.
3. Wire actual YouTube upload in a deliberate, idempotent way using the existing secrets and OAuth refresh flow. First perform a private-only test upload; no public publishing by default.
4. Ensure the upload code handles refresh-token expiry, API errors, retries, duplicate prevention, and records the YouTube video ID/status without leaking credentials.
5. Investigate the OAuth consent app's Testing status and short refresh-token lifetime before unattended runs. Do not silently assume the token is permanent.
6. Only after the manual prepare/private-upload path is reliable, add daily scheduling and the 30-day experiment workflow. Avoid public uploads or paid services without Rahul's explicit decision.
7. Add analytics/feedback only within API availability and quota; don't promise unlimited free API usage.

## Working rules

- Rahul expects direct repository changes when he asks to implement something, not just a plan.
- Use the GitHub integration to inspect/edit the repository. Make focused commits and report exact commit links.
- Do not ask Rahul to repeat setup already listed here.
- Never put API keys, OAuth client secrets, refresh tokens, or personal account data in this file.
- Distinguish clearly between **committed**, **workflow-tested**, and **visually verified**.
- If a workflow run is needed but cannot be triggered through available tools, say so plainly and give Rahul the single action needed—don't pretend the run happened.


## 2026-10-05 private YouTube publishing implementation

The repository now includes the first real YouTube upload path:
- `src/ytautopilot/youtube_upload.py`: OAuth refresh from the existing `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN` secrets; scope verification; resumable `videos.insert`; private-only safety gate; transient retry handling; upload-history deduplication; recent-owned-upload marker check; no credential logging.
- `src/ytautopilot/validate_output.py`: validates final MP4 resolution (1080x1920), duration (10-60s), audio presence, thumbnail dimensions (1080x1920), metadata presence, and private privacy status.
- `data/upload_history.json`: persistent upload history written after successful or deduplicated uploads.
- `src/ytautopilot/publish_package.py`: publish metadata now includes a script fingerprint, stable topic key, upload marker, and category 20.
- `src/ytautopilot/__main__.py`: `publish` mode now renders, validates, and uploads privately. The code requires `YOUTUBE_PUBLISH_ENABLED=true`.
- `.github/workflows/shorts.yml`: workflow_dispatch now offers `dry-run`, `prepare`, and `publish`; existing YouTube secrets are passed only through the Actions environment; upload runs get 35 minutes. Workflow remains manual-only; no schedule has been enabled yet.
- Custom thumbnails are intentionally not sent through `thumbnails.set`; `thumbnail_candidate.jpg` remains an artifact.
- Latest implementation commit: `3011af5a420eeef7f1ee09e5ba5150d551562361`.

Important: the new upload path has NOT been workflow-tested yet because the available GitHub integration can edit/fetch workflow files but cannot dispatch a new workflow run. Do not claim a private upload succeeded until an actual GitHub Actions run proves it.

OAuth note: Google currently documents that external OAuth apps left in Publishing status `Testing` issue test-user refresh tokens that expire after 7 days. Moving the app to production/in-production is the long-term fix for unattended publishing. See the current Google Cloud OAuth testing guidance before relying on the existing refresh token for daily automation.
