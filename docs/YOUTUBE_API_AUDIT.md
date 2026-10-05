# YouTube API compliance & verification notes

Last updated: 2026-10-05.

## Current status

The ZynexPlayz AutoPilot project has a working authenticated YouTube upload/scheduling path through the official YouTube Data API.

The YouTube API Services compliance/audit form was submitted for this project. Submission is **not the same as audit approval**. Approval should only be recorded here when Google/YouTube provides an explicit approval result.

## Important distinction: unverified upload restriction vs scheduled publishing

YouTube's videos.insert documentation states that videos uploaded through videos.insert by API projects created after 28 July 2020 that have not completed the required audit are restricted to private viewing. The audit is required to lift that restriction.

This restriction does **not** mean that publishAt cannot be used.

YouTube's status.publishAt field is specifically a scheduled publication time and can only be set while the video's privacy status is private. YouTube Studio represents that private video with a future publish time as **Scheduled**.

Therefore:

- Private after an upload does **not**, by itself, prove that the API project is unverified.
- Scheduled after an upload does **not**, by itself, prove that the API audit has been approved.
- A successful publishAt schedule proves that the authenticated API request accepted the scheduled publication target.
- Explicit Google/YouTube audit approval is the only reliable evidence that the compliance audit restriction has been lifted.

## Evidence from the automated pipeline

On 2026-10-05, GitHub Actions run **#40** (run id 37329637062) was triggered by the scheduled workflow and completed successfully.

The run completed these relevant steps successfully:

1. Set pipeline and publishing context
2. Verify YouTube OAuth scopes before publishing
3. Update performance learning profile
4. Run pipeline
5. Persist generation and learning state
6. Upload generated output

The OAuth verification step is part of the workflow and checks the required scopes using the stored refresh-token credentials. A successful result confirms that the GitHub Actions credentials could authenticate and that the required YouTube scopes were accepted by the API.

This is evidence of a working OAuth/upload integration, **not evidence of Google audit approval**.

## Current OAuth scopes

The automation requests:

- https://www.googleapis.com/auth/youtube.upload
- https://www.googleapis.com/auth/youtube.readonly

The upload module uses the official youtube.videos.insert endpoint. It also reads channel/upload metadata and statistics through the official YouTube Data API.

## Scheduled workflow

The GitHub Actions workflow uses Asia/Kolkata and currently runs:

- 12:00 IST
- 19:30 IST

Scheduled runs use PIPELINE_MODE=publish and calculate a YouTube publishAt target. Manual publish runs intentionally leave YOUTUBE_PUBLISH_AT empty, so they exercise the upload path without the scheduled-publication target.

## Compliance submission evidence

The submitted audit/compliance package included the project website and documentation evidence prepared during setup, including:

- Privacy Policy screenshot
- Homepage screenshot with YouTube branding and privacy link
- Terms of Service documentation
- OAuth consent-screen evidence
- Upload-interface evidence
- Dashboard/feature evidence for analytics/reporting
- Architecture documentation

The form was submitted successfully. Keep any Google confirmation email or approval message as the authoritative audit-status record.

## References

- YouTube Data API videos.insert: https://developers.google.com/youtube/v3/docs/videos/insert
- YouTube Data API video resource / status.publishAt: https://developers.google.com/youtube/v3/docs/videos
- YouTube Data API revision history (July 28, 2020 private-upload restriction): https://developers.google.com/youtube/v3/revision_history
- YouTube Help — scheduled publishing: https://support.google.com/youtube/answer/1270709

Do not put OAuth client secrets, API keys, or refresh tokens in this document or in Git.