from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
REQUIRED_SCOPES = [UPLOAD_SCOPE, READONLY_SCOPE]
TOKEN_URI = "https://oauth2.googleapis.com/token"
UPLOAD_HISTORY_PATH = Path("data") / "upload_history.json"
DEFAULT_CATEGORY_ID = "20"  # Gaming
UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024
MAX_RETRIES = 5
TRANSIENT_HTTP_STATUSES = {500, 502, 503, 504}


class YouTubeUploadError(RuntimeError):
    """Raised when the private YouTube upload cannot safely complete."""


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise YouTubeUploadError(
            f"Required YouTube credential environment variable is missing: {name}"
        )
    return value


def _credentials() -> Credentials:
    client_id = _require_env("YOUTUBE_CLIENT_ID")
    client_secret = _require_env("YOUTUBE_CLIENT_SECRET")
    refresh_token = _require_env("YOUTUBE_REFRESH_TOKEN")

    credentials = Credentials.from_authorized_user_info(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "token_uri": TOKEN_URI,
        },
        scopes=REQUIRED_SCOPES,
    )
    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        raise YouTubeUploadError(
            "YouTube OAuth refresh failed. The saved refresh token may be "
            "expired, revoked, or missing the youtube.upload scope. "
            "Re-authorize the same OAuth client if Google reports invalid_grant."
        ) from exc
    if not credentials.valid:
        raise YouTubeUploadError("Google OAuth returned an invalid access token.")
    if not credentials.has_scopes(REQUIRED_SCOPES):
        granted = sorted(str(scope) for scope in (credentials.granted_scopes or []))
        raise YouTubeUploadError(
            "The YouTube OAuth credential is missing a required scope. "
            "This uploader needs both youtube.upload (for videos.insert) and "
            "youtube.readonly (for the authenticated-channel/duplicate check). "
            f"Granted scopes reported by Google: {granted}"
        )
    return credentials


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise YouTubeUploadError(f"Could not read JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise YouTubeUploadError(f"Expected a JSON object in {path}")
    return payload


def load_upload_history() -> dict[str, Any]:
    if not UPLOAD_HISTORY_PATH.exists():
        return {"version": 1, "uploads": []}
    payload = _load_json(UPLOAD_HISTORY_PATH)
    uploads = payload.get("uploads")
    if not isinstance(uploads, list):
        return {"version": 1, "uploads": []}
    return {"version": 1, "uploads": [item for item in uploads if isinstance(item, dict)]}


def _write_upload_history(payload: dict[str, Any]) -> None:
    UPLOAD_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_HISTORY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def record_upload(
    *,
    fingerprint: str,
    video_id: str,
    title: str,
    topic: str,
    status: str,
    description_style: str = "default",
    scheduled_publish_at: str | None = None,
) -> None:
    payload = load_upload_history()
    uploads = [
        item for item in payload["uploads"]
        if str(item.get("fingerprint", "")) != fingerprint
    ]
    uploads.append(
        {
            "uploaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "youtube_video_id": video_id,
            "title": title,
            "topic": topic,
            "status": status,
            "description_style": description_style,
            "scheduled_publish_at": scheduled_publish_at,
        }
    )
    # Keep the persistent file bounded while leaving enough history to guard
    # against accidental re-uploads from old workflow retries.
    payload["uploads"] = uploads[-200:]
    _write_upload_history(payload)


def _history_match(fingerprint: str) -> dict[str, Any] | None:
    for item in reversed(load_upload_history()["uploads"]):
        if str(item.get("fingerprint", "")) == fingerprint:
            return item
    return None


def _channel_and_uploads_playlist(youtube: Any) -> tuple[str, str]:
    response = (
        youtube.channels()
        .list(part="id,contentDetails", mine=True)
        .execute()
    )
    items = response.get("items", [])
    if not items:
        raise YouTubeUploadError(
            "The OAuth account does not expose a YouTube channel. "
            "Check that the refresh token was authorized for the intended channel."
        )
    item = items[0]
    channel_id = str(item.get("id") or "").strip()
    uploads_id = str(
        item.get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    ).strip()
    if not channel_id or not uploads_id:
        raise YouTubeUploadError("YouTube returned no uploads playlist for the channel.")
    return channel_id, uploads_id


def _find_existing_marker(youtube: Any, marker: str) -> dict[str, str] | None:
    """Look through recent owned uploads for the deterministic automation marker.

    The marker is stored as a non-display YouTube tag so a workflow retry after
    an ambiguous network failure can find an already-created private video
    without changing the viewer-facing description.
    """
    _, uploads_playlist = _channel_and_uploads_playlist(youtube)
    page_token: str | None = None

    # A retry collision will normally be among the most recent uploads. Walk a
    # few pages so a busy channel still has a useful safety net without making
    # every upload expensive.
    for _ in range(4):
        response = (
            youtube.playlistItems()
            .list(
                part="contentDetails",
                playlistId=uploads_playlist,
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )
        ids = [
            str(item.get("contentDetails", {}).get("videoId", "")).strip()
            for item in response.get("items", [])
        ]
        ids = [video_id for video_id in ids if video_id]
        for start in range(0, len(ids), 50):
            chunk = ids[start : start + 50]
            if not chunk:
                continue
            videos = (
                youtube.videos()
                .list(part="id,snippet,status", id=",".join(chunk))
                .execute()
            )
            for item in videos.get("items", []):
                tags = item.get("snippet", {}).get("tags", [])
                if isinstance(tags, list) and marker in {str(tag) for tag in tags}:
                    return {
                        "video_id": str(item.get("id")),
                        "title": str(item.get("snippet", {}).get("title", "")),
                    }

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return None


def _validate_private_package(metadata: dict[str, Any]) -> tuple[Path, str, str]:
    video_path = Path(str(metadata.get("video") or ""))
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise YouTubeUploadError(f"Rendered video is missing or empty: {video_path}")

    title = str(metadata.get("title") or "").strip()
    description = str(metadata.get("description") or "").strip()
    if not title:
        raise YouTubeUploadError("YouTube upload blocked: title is empty.")
    if len(title) > 100:
        raise YouTubeUploadError("YouTube upload blocked: title exceeds 100 characters.")
    if len(description) > 5000:
        raise YouTubeUploadError(
            "YouTube upload blocked: description exceeds 5,000 characters."
        )

    privacy = str(metadata.get("privacy_status") or "private").lower().strip()
    if privacy != "private":
        raise YouTubeUploadError(
            "Safety gate refused the upload because privacy_status is not exactly 'private'."
        )

    fingerprint = str(metadata.get("fingerprint") or "").strip()
    if not fingerprint:
        raise YouTubeUploadError(
            "Publish metadata has no deterministic fingerprint for duplicate protection."
        )

    return video_path, title, description


def _add_marker_tag(tags: list[Any], marker: str) -> list[str]:
    normalized = [str(tag).strip() for tag in tags if str(tag).strip()]
    if marker in normalized:
        return normalized
    candidate = normalized + [marker]
    combined_length = sum(len(tag) for tag in candidate) + max(0, len(candidate) - 1)
    if combined_length > 500:
        raise YouTubeUploadError(
            "Adding the duplicate-protection tag would exceed YouTube's "
            "500-character combined tag limit."
        )
    return candidate


def _upload_resumable(youtube: Any, body: dict[str, Any], video_path: Path) -> dict[str, Any]:
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=UPLOAD_CHUNK_SIZE,
        resumable=True,
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=False,
    )

    response: dict[str, Any] | None = None
    retries = 0
    while response is None:
        try:
            progress, response = request.next_chunk()
            if progress is not None:
                print(
                    f"[youtube] Upload progress: {progress.progress() * 100:.1f}%"
                )
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status not in TRANSIENT_HTTP_STATUSES or retries >= MAX_RETRIES:
                raise YouTubeUploadError(
                    f"YouTube upload failed with HTTP {status}. "
                    "No credentials were printed."
                ) from exc
            delay = 2 ** retries
            retries += 1
            print(
                f"[youtube] Transient HTTP {status}; retry {retries}/{MAX_RETRIES} "
                f"after {delay}s."
            )
            time.sleep(delay)
        except (OSError, TimeoutError) as exc:
            if retries >= MAX_RETRIES:
                raise YouTubeUploadError(
                    "YouTube upload stopped after repeated network/IO failures."
                ) from exc
            delay = 2 ** retries
            retries += 1
            print(
                f"[youtube] Transient network error; retry {retries}/{MAX_RETRIES} "
                f"after {delay}s."
            )
            time.sleep(delay)

    video_id = str(response.get("id") or "").strip()
    if not video_id:
        raise YouTubeUploadError("YouTube returned a successful response without a video ID.")
    return response


def upload_private_video(
    metadata_path: Path = Path("output") / "publish_metadata.json",
) -> dict[str, Any]:
    metadata = _load_json(metadata_path)
    video_path, title, description = _validate_private_package(metadata)
    fingerprint = str(metadata["fingerprint"])
    marker = str(metadata.get("upload_marker") or f"ytautopilot-{fingerprint}").strip()
    if not marker:
        raise YouTubeUploadError("Publish metadata has no upload duplicate marker.")

    previous = _history_match(fingerprint)
    if previous and str(previous.get("youtube_video_id", "")).strip():
        video_id = str(previous["youtube_video_id"])
        metadata.update(
            {
                "status": "already_uploaded",
                "youtube_video_id": video_id,
                "upload_marker": marker,
                "upload_status": "deduplicated_from_history",
                "uploaded_at_utc": previous.get("uploaded_at_utc"),
            }
        )
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[youtube] Duplicate prevented by upload history: {video_id}")
        return metadata

    print("[youtube] Authenticating with the existing GitHub Actions OAuth secret set...")
    credentials = _credentials()
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    existing = _find_existing_marker(youtube, marker)
    if existing:
        video_id = existing["video_id"]
        record_upload(
            fingerprint=fingerprint,
            video_id=video_id,
            title=title,
            topic=str(metadata.get("topic") or ""),
            status="deduplicated_from_youtube",
            description_style=str(metadata.get("description_style") or "default"),
            scheduled_publish_at=str(metadata.get("publish_at") or "") or None,
        )
        metadata.update(
            {
                "status": "already_uploaded",
                "youtube_video_id": video_id,
                "upload_marker": marker,
                "upload_status": "deduplicated_from_youtube",
                "uploaded_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[youtube] Duplicate prevented by recent owned upload: {video_id}")
        return metadata

    upload_tags = _add_marker_tag(list(metadata.get("tags") or []), marker)
    publish_at = os.environ.get("YOUTUBE_PUBLISH_AT", "").strip()
    status_body: dict[str, Any] = {
        # Keep uploads private at insertion time so YouTube can validate/schedule
        # them safely. An audited API project can publish them at publishAt.
        "privacyStatus": "private",
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        status_body["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": upload_tags,
            "categoryId": str(metadata.get("category_id") or DEFAULT_CATEGORY_ID),
        },
        "status": status_body,
    }

    if publish_at:
        print(f"[youtube] Uploading private video scheduled for {publish_at}: {title}")
    else:
        print(f"[youtube] Uploading private video: {title}")
    response = _upload_resumable(youtube, body, video_path)
    video_id = str(response["id"])

    record_upload(
        fingerprint=fingerprint,
        video_id=video_id,
        title=title,
        topic=str(metadata.get("topic") or ""),
        status="uploaded_private",
        description_style=str(metadata.get("description_style") or "default"),
        scheduled_publish_at=publish_at or None,
    )

    metadata.update(
        {
            "status": "uploaded_private",
            "youtube_video_id": video_id,
            "upload_marker": marker,
            "upload_status": "uploaded_private",
            "scheduled_publish_at": publish_at or None,
            "uploaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_upload": "not_attempted",
            "note": (
                "The generated thumbnail remains a candidate artifact. "
                "This upload path intentionally does not call thumbnails.set, "
                "because custom thumbnail availability/support can vary by channel."
            ),
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[youtube] Private upload complete: {video_id}")
    return metadata
