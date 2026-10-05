# YTAutoPilot operations log

Last updated: 2026-10-05.

## What was proven today

The ZynexPlayz AutoPilot pipeline has now completed a real scheduled GitHub Actions run successfully.

GitHub Actions run:

- Workflow: ytautopilot
- Run: **#40**
- Event: schedule
- Result: **success**
- Run ID: 37329637062
- Started: 2026-10-05T15:03:01Z
- Completed: 2026-10-05T15:08:33Z

The job's YouTube-related steps all completed successfully:

- OAuth scope verification — success
- Performance learning update — success
- Pipeline — success
- State persistence — success
- Output artifact upload — success

## Manual vs scheduled publishing

There are two intentionally different paths:

### Manual publish

A manual workflow dispatch with mode=publish sets YOUTUBE_PUBLISH_AT to empty.

The pipeline still uploads through the YouTube Data API, but it does not request a future publishAt target from the scheduler.

### Scheduled run

A scheduled GitHub Actions event sets PIPELINE_MODE=publish and calculates YOUTUBE_PUBLISH_AT from the configured midday/evening scheduler slot.

This is why an automated run can arrive in YouTube Studio already showing **Scheduled**.

## Current schedule

Workflow timezone: Asia/Kolkata

- 12:00 IST
- 19:30 IST

The scheduled publication target is calculated separately from the workflow start time. Do not assume the workflow start time and the YouTube publication time are identical.

## Verification interpretation

A green OAuth-scope step means the stored OAuth credentials work and the requested scopes are available to the workflow.

It does **not** mean the separate YouTube API Services compliance audit has been approved.

Likewise, a YouTube Studio **Scheduled** label is evidence that a future publishAt target was accepted; it is not proof of audit approval.

See docs/YOUTUBE_API_AUDIT.md for the full explanation.

## Evidence captured

The following user-side evidence was observed on 2026-10-05:

- YouTube Studio Content list showed the latest generated Short.
- The video's details showed Visibility: Scheduled.
- The edit screen showed the scheduled date/time.
- The generated description and hashtags were present.
- GitHub Actions showed the scheduled workflow run as successful.

Screenshots are treated as external evidence; credentials and tokens must never be stored in the repository.

## Operational rule

After a successful scheduled run, do not manually publish the same generated video. Let YouTube's scheduled publication handle it.

If a scheduled run fails:

1. Inspect the GitHub Actions run.
2. Check the first failed step.
3. Do not immediately launch multiple manual publish runs.
4. Check data/upload_history.json and the YouTube channel first to avoid duplicate uploads.