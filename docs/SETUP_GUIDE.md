# YTAutoPilot — Complete Setup & Contributor Guide

This guide documents how to set up the current YTAutoPilot starter, troubleshoot it, and help another creator build a separate project inspired by the workflow.

> **Current status:** Stage 1 only. The current workflow supports a manual dry-run and Hindi/Hinglish gaming script generation. Video rendering and YouTube publishing are not implemented yet. Adding YouTube credentials does not enable uploads by itself. The workflow is manually triggered; no schedule is enabled.

## 1. What you need

- A GitHub account and a repository you control.
- A Google account for the intended YouTube channel.
- A Google Cloud project with YouTube Data API v3 enabled.
- A Gemini API key if you want live script generation.
- A phone or computer with a modern browser. Some Google Cloud screens are easier to use in desktop mode.
- For future video generation: FFmpeg and a Python environment, plus footage and audio you own or are licensed to use.

Never commit API keys, OAuth client JSON files, client secrets, refresh tokens, passwords, or private media to Git.

## 2. Create or select a Google Cloud project

1. Open https://console.cloud.google.com/ and sign in with the Google account you want to use.
2. Use the project selector to create or select a dedicated project, e.g. **Zynex Playz AutoPilot**.
3. Open **APIs & Services → Library** (or search the console for API Library).
4. Search for **YouTube Data API v3**, open it, and press **Enable**.
5. If using Gemini, create an API key in Google AI Studio / Gemini API setup and keep it private. Do not confuse a Gemini API key with YouTube OAuth credentials.

Enabling the YouTube API does not grant channel access; OAuth authorization is a separate step.

## 3. Configure Google OAuth consent

1. Open Google Auth Platform: https://console.cloud.google.com/auth/overview
2. Select the correct Cloud project.
3. Under **Branding**, set the app name (e.g. **Zynex Playz AutoPilot**), user-support email, and developer contact email.
4. Save changes when Google enables the Save button. A disabled Save button often means there are no unsaved changes.
5. Under **Audience**, choose **External** if offered for a personal Gmail account.
6. During development, keep the app in **Testing** and add the Google account that will authorize uploads as a test user.
7. Under **Data Access**, request only the scopes the app actually needs. Uploading videos normally uses https://www.googleapis.com/auth/youtube.upload
8. Google may require a homepage, privacy policy, verified domain, or OAuth verification before broader production use. Do not invent a domain or fake policy URLs. A free hosting URL can be used for genuine project information, but it does not automatically satisfy every Google verification requirement.

### OAuth client type

For GitHub Actions, the app needs a refresh token usable by a server-side process. A Desktop OAuth client can be used for an installed-app authorization flow. OAuth Playground is another way to test authorization, but if using it with your own credentials, the Web application client must have this exact authorized redirect URI:

https://developers.google.com/oauthplayground

Keep the OAuth Playground configuration and client type consistent. Do not publish the downloaded OAuth JSON file.

### Obtain a refresh token with OAuth Playground (testing workflow)

1. Open https://developers.google.com/oauthplayground
2. Open the gear/settings icon.
3. Enable **Use your own OAuth credentials** and enter the Client ID and Client Secret for the Web application client configured with the redirect URI above.
4. Under **Input your own scopes**, enter https://www.googleapis.com/auth/youtube.upload
5. Select **Authorize APIs**, sign in to the intended channel's Google account, and grant consent.
6. In Step 2, select **Exchange authorization code for tokens**.
7. Copy only the value of the refresh_token field from the returned JSON. Do not copy the field name, quotes, access token, or other fields.

**Token lifetime warning:** External OAuth apps left in Testing generally issue refresh tokens that expire after seven days when non-basic scopes such as YouTube upload are used. OAuth Playground may also show an explicit refresh_token_expires_in value. Check the actual response. Do not assume a token will last for a month. Moving an app to Production does not automatically mean it is verified or free of YouTube API restrictions. Check current Google requirements before relying on unattended uploads.

## 4. Add GitHub Actions secrets

Open the repository on GitHub, then go to **Settings → Secrets and variables → Actions → New repository secret**.

Add the secrets individually:

| Name | Value |
|---|---|
| GEMINI_API_KEY | Your private Gemini API key |
| YOUTUBE_CLIENT_ID | OAuth Client ID for the client used to obtain the refresh token |
| YOUTUBE_CLIENT_SECRET | OAuth Client Secret for that same client, if required by the chosen OAuth flow |
| YOUTUBE_REFRESH_TOKEN | The complete refresh-token value only |

Important:
- Use the Client ID and Client Secret from the same OAuth client that issued the refresh token.
- Never paste secret values into issues, chat, screenshots, logs, source files, or commits.
- If a secret is accidentally exposed, revoke/rotate it at the provider and update the GitHub secret.
- GitHub will not show you a saved secret's value again. To change one, replace it with a new value.
- The current Stage 1 workflow may not use the YouTube secrets yet because publishing has not been implemented.

Optional: add a repository variable named GEMINI_MODEL if you want to override the default model documented in the README. Use a model currently available to your API project.

## 5. Run the current safe dry-run

1. Open **Actions** in the repository.
2. Select the **ytautopilot** workflow.
3. Tap **Run workflow**.
4. Choose **dry-run** and run it.
5. Wait for the run to finish. Open the run to inspect any errors.
6. Download the generated artifact and inspect script.json.

The dry-run generates or uses a sample script; it does not upload a video. If the run fails, inspect the failed step and its log. Share only the error text after removing API keys, tokens, personal data, and other secrets.

## 6. Current capabilities and missing pieces

The current starter is not a complete autopublishing system. Before enabling a real channel workflow, implement and test each stage:

1. **Script generation:** produce original scripts, validate factual claims, and avoid misleading titles.
2. **Footage:** use self-recorded gameplay or footage with documented permission/licensing. Keep a record of source and terms. Permission to reuse a video does not guarantee that it satisfies YouTube monetization or reused-content rules.
3. **Narration and captions:** generate or record narration, create accurate captions, and verify audio rights.
4. **Rendering:** use FFmpeg to create vertical 9:16 videos with readable captions and sensible audio levels.
5. **Quality checks:** confirm video duration, dimensions, audio, caption timing, and that no duplicate or corrupted file is uploaded.
6. **OAuth upload:** use the official YouTube Data API; handle expired/revoked credentials, quota errors, retries, and privacy settings.
7. **Idempotency:** record uploaded video IDs so reruns do not upload duplicates.
8. **Scheduling:** only add a schedule after manual runs and failure handling are reliable. Start with private/unlisted test uploads.
9. **Monitoring:** record workflow status, errors, API quota, upload IDs, and performance metrics without logging secrets.
10. **Review:** review actual views, retention, watch time, subscribers, and costs before scaling.

Do not enable unattended public publishing until every stage has been tested and a human review process is in place.

## 7. Troubleshooting

- **Publish app disabled:** check Branding for missing required fields and save any actual changes. Do not enter fake domains. Google may require more information depending on the requested scopes.
- **OAuth access blocked:** check that the app is External (where applicable), the account is a test user while in Testing, and the correct Google account is selected.
- **No refresh token in response:** revoke the old test grant if appropriate, then repeat consent with offline access/consent prompt. Avoid generating many tokens unnecessarily.
- **Token stops working after several days:** check OAuth app publishing status and the response's refresh_token_expires_in field. Testing-mode expiration is expected for some scopes.
- **invalid_client:** the Client ID and Client Secret do not match, or the wrong client type was used.
- **invalid_grant:** the refresh token may be expired, revoked, issued to a different client, or otherwise invalid. Re-authorize and replace the GitHub secret.
- **Gemini errors:** confirm the API key is correct, the API is enabled for the right project, billing/limits are satisfied if applicable, and the selected model is available.
- **Workflow does not appear:** confirm the workflow file is on the default branch and that GitHub Actions is enabled for the repository.
- **Workflow succeeds but no video appears:** expected for the current dry-run; publishing is not implemented in this stage.

## 8. Starting a separate project inspired by this repository

For a new project:
1. Create your own repository and write down its goal and current stage.
2. Use your own Google Cloud project, API keys, OAuth client, channel, and GitHub secrets. Never reuse another creator's tokens.
3. Read the upstream repository's license and permissions before copying any code. This repository currently states **All rights reserved**, so it is not an open-source license and does not grant permission to copy, modify, distribute, or create derivatives. You can learn from the general ideas, but obtain written permission before reusing its code.
4. Document setup, secret names, manual test steps, known limitations, and recovery instructions in your own README or setup guide.
5. Keep dry-run as the default. Add publishing only after testing and rights checks.
6. Use version control, small commits, logs that redact secrets, and a rollback path.

## 9. Security checklist

- [ ] Secrets are stored only in GitHub Actions secrets or an appropriate secret manager.
- [ ] OAuth client JSON and refresh tokens are not committed.
- [ ] Only the intended channel account granted consent.
- [ ] OAuth testing/production status and token expiry have been checked.
- [ ] Media sources and permissions are documented.
- [ ] Dry-run passes and generated scripts are reviewed.
- [ ] No public upload or recurring schedule is enabled until the full pipeline is tested.

## Useful official links

- Google Cloud Console: https://console.cloud.google.com/
- Google Auth Platform: https://console.cloud.google.com/auth/overview
- YouTube Data API v3: https://console.cloud.google.com/apis/library/youtube.googleapis.com
- OAuth Playground: https://developers.google.com/oauthplayground
- YouTube Data API documentation: https://developers.google.com/youtube/v3
- GitHub Actions secrets: https://docs.github.com/actions/security-guides/using-secrets-in-github-actions

---
Last reviewed: 2026-10-04. Re-check provider documentation because OAuth and API requirements can change.
