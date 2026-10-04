from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEDIA_HISTORY_PATH = Path("data") / "media_history.json"
MAX_MEDIA_HISTORY = 200


def _empty() -> dict[str, Any]:
    return {"version": 1, "entries": []}


def load_media_history() -> dict[str, Any]:
    if not MEDIA_HISTORY_PATH.exists():
        return _empty()
    try:
        payload = json.loads(MEDIA_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        return _empty()
    return {
        "version": 1,
        "entries": [item for item in payload["entries"] if isinstance(item, dict)][-MAX_MEDIA_HISTORY:],
    }


def save_media_history(payload: dict[str, Any]) -> None:
    MEDIA_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        "version": 1,
        "entries": [item for item in payload.get("entries", []) if isinstance(item, dict)][-MAX_MEDIA_HISTORY:],
    }
    MEDIA_HISTORY_PATH.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _segment_signature(manifest: dict[str, Any]) -> str:
    segments = manifest.get("selected_segments", [])
    normalized: list[tuple[str, float, float, float]] = []
    if isinstance(segments, list):
        for item in segments:
            if not isinstance(item, dict):
                continue
            normalized.append(
                (
                    str(item.get("path", "")),
                    round(float(item.get("start", 0.0)), 3),
                    round(float(item.get("end", 0.0)), 3),
                    round(float(item.get("duration", 0.0)), 3),
                )
            )
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def build_media_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    video = Path(str(manifest.get("video") or ""))
    narration = Path(str(manifest.get("narration_audio") or "output/narration.mp3"))
    editing = manifest.get("editing") if isinstance(manifest.get("editing"), dict) else {}
    music = str(editing.get("music") or "").strip()
    segments = _segment_signature(manifest)

    if not video.is_file() or video.stat().st_size == 0:
        raise RuntimeError(f"Cannot fingerprint missing video: {video}")
    if not narration.is_file() or narration.stat().st_size == 0:
        raise RuntimeError(f"Cannot fingerprint missing narration: {narration}")

    video_hash = sha256_file(video)
    narration_hash = sha256_file(narration)
    composite = " | ".join((video_hash, narration_hash, music, segments))
    composite_hash = hashlib.sha256(composite.encode("utf-8")).hexdigest()[:24]

    return {
        "video_sha256": video_hash,
        "narration_sha256": narration_hash,
        "music": music,
        "segment_signature": segments,
        "composite_fingerprint": composite_hash,
    }


def is_duplicate_media(identity: dict[str, Any]) -> bool:
    video_hash = str(identity.get("video_sha256", ""))
    composite_hash = str(identity.get("composite_fingerprint", ""))
    for entry in reversed(load_media_history()["entries"]):
        if video_hash and video_hash == str(entry.get("video_sha256", "")):
            return True
        if composite_hash and composite_hash == str(entry.get("composite_fingerprint", "")):
            return True
    return False


def record_media_generation(
    *,
    identity: dict[str, Any],
    script_fingerprint: str,
    topic: str,
    status: str = "generated",
) -> None:
    payload = load_media_history()
    video_hash = str(identity.get("video_sha256", ""))
    composite_hash = str(identity.get("composite_fingerprint", ""))

    entries = [
        item for item in payload["entries"]
        if str(item.get("video_sha256", "")) != video_hash
        and str(item.get("composite_fingerprint", "")) != composite_hash
    ]
    entries.append(
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "script_fingerprint": script_fingerprint,
            "topic": topic,
            "status": status,
            **identity,
        }
    )
    save_media_history({"version": 1, "entries": entries})


def media_usage_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in load_media_history()["entries"]:
        music = str(entry.get("music", "")).strip()
        if music:
            counts[music] = counts.get(music, 0) + 1
        segments = str(entry.get("segment_signature", ""))
        try:
            decoded = json.loads(segments)
        except (TypeError, json.JSONDecodeError):
            decoded = []
        for item in decoded if isinstance(decoded, list) else []:
            if isinstance(item, list) and item:
                path = str(item[0])
                if path:
                    counts[path] = counts.get(path, 0) + 1
    return counts


def recent_media_sources(limit: int = 4) -> set[str]:
    values: set[str] = set()
    for entry in load_media_history()["entries"][-limit:]:
        music = str(entry.get("music", "")).strip()
        if music:
            values.add(music)
        try:
            decoded = json.loads(str(entry.get("segment_signature", "")))
        except (TypeError, json.JSONDecodeError):
            decoded = []
        for item in decoded if isinstance(decoded, list) else []:
            if isinstance(item, list) and item:
                values.add(str(item[0]))
    return values
