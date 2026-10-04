from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

from googleapiclient.discovery import build

from .content import TOPIC_BANK
from .youtube_upload import _credentials

PERFORMANCE_HISTORY_PATH = Path("data") / "performance_history.json"
STRATEGY_PROFILE_PATH = Path("data") / "strategy_profile.json"


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return value if isinstance(value, dict) else default


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize(value: str) -> str:
    return " ".join(str(value).lower().split())


def topic_family(topic: str) -> str:
    normalized = _normalize(topic)
    best_family = "other"
    best_score = 0
    for family, candidates in TOPIC_BANK:
        for candidate in candidates:
            candidate_norm = _normalize(candidate)
            score = 1 if normalized == candidate_norm else (
                0.75 if normalized.startswith(candidate_norm) or candidate_norm.startswith(normalized) else 0
            )
            if score > best_score:
                best_family = family
                best_score = score
    return best_family


def _parse_duration_seconds(value: str) -> float:
    try:
        text = value.strip().upper()
        if not text.startswith("PT"):
            return 0.0
        text = text[2:]
        total = 0.0
        number = ""
        for char in text:
            if char.isdigit() or char == ".":
                number += char
                continue
            if not number:
                continue
            amount = float(number)
            if char == "H":
                total += amount * 3600
            elif char == "M":
                total += amount * 60
            elif char == "S":
                total += amount
            number = ""
        return total
    except (TypeError, ValueError):
        return 0.0


def _performance_score(record: dict[str, Any]) -> float:
    views = max(0, int(record.get("views", 0) or 0))
    likes = max(0, int(record.get("likes", 0) or 0))
    comments = max(0, int(record.get("comments", 0) or 0))
    engagement = (likes + 2 * comments) / max(views, 1)
    return round(math.log1p(views) + 35.0 * engagement, 4)


def collect_performance(upload_history_path: Path = Path("data") / "upload_history.json") -> dict[str, Any]:
    history = _load(upload_history_path, {"uploads": []})
    uploads = [item for item in history.get("uploads", []) if isinstance(item, dict)]
    ids = []
    metadata_by_id: dict[str, dict[str, Any]] = {}
    for item in uploads[-100:]:
        video_id = str(item.get("youtube_video_id", "")).strip()
        if video_id:
            ids.append(video_id)
            metadata_by_id[video_id] = item
    ids = list(dict.fromkeys(ids))

    if not ids:
        payload = {
            "version": 1,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "videos": [],
        }
        _save(PERFORMANCE_HISTORY_PATH, payload)
        _save(STRATEGY_PROFILE_PATH, build_strategy_profile(payload))
        return payload

    youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
    videos: list[dict[str, Any]] = []
    for start in range(0, len(ids), 50):
        response = (
            youtube.videos()
            .list(
                part="snippet,statistics,contentDetails,status",
                id=",".join(ids[start:start + 50]),
            )
            .execute()
        )
        videos.extend(response.get("items", []))

    previous = _load(PERFORMANCE_HISTORY_PATH, {"videos": []})
    previous_by_id = {
        str(item.get("video_id")): item
        for item in previous.get("videos", [])
        if isinstance(item, dict) and item.get("video_id")
    }

    now = datetime.now(timezone.utc).isoformat()
    for item in videos:
        video_id = str(item.get("id", "")).strip()
        if not video_id:
            continue
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        upload_meta = metadata_by_id.get(video_id, {})
        record = {
            **previous_by_id.get(video_id, {}),
            "video_id": video_id,
            "title": str(snippet.get("title", upload_meta.get("title", ""))),
            "topic": str(upload_meta.get("topic", "")),
            "topic_family": topic_family(str(upload_meta.get("topic", ""))),
            "description_style": str(upload_meta.get("description_style", "default")),
            "published_at": snippet.get("publishedAt"),
            "fetched_at_utc": now,
            "privacy_status": status.get("privacyStatus"),
            "duration_seconds": round(_parse_duration_seconds(str(content.get("duration", ""))), 3),
            "views": int(stats.get("viewCount", 0) or 0),
            "likes": int(stats.get("likeCount", 0) or 0),
            "comments": int(stats.get("commentCount", 0) or 0),
        }
        record["engagement_rate"] = round(
            (record["likes"] + record["comments"]) / max(record["views"], 1),
            6,
        )
        record["performance_score"] = _performance_score(record)
        previous_by_id[video_id] = record

    payload = {
        "version": 1,
        "updated_at_utc": now,
        "videos": list(previous_by_id.values())[-200:],
    }
    _save(PERFORMANCE_HISTORY_PATH, payload)
    _save(STRATEGY_PROFILE_PATH, build_strategy_profile(payload))
    return payload


def build_strategy_profile(payload: dict[str, Any]) -> dict[str, Any]:
    videos = [
        item for item in payload.get("videos", [])
        if isinstance(item, dict) and str(item.get("privacy_status")) == "public"
    ]

    family_groups: dict[str, list[float]] = {}
    style_groups: dict[str, list[float]] = {}
    hour_groups: dict[int, list[float]] = {}
    duration_groups: dict[str, list[float]] = {}

    for item in videos:
        score = float(item.get("performance_score", 0.0) or 0.0)
        family_groups.setdefault(str(item.get("topic_family", "other")), []).append(score)
        style_groups.setdefault(str(item.get("description_style", "default")), []).append(score)

        published_at = str(item.get("published_at", "")).replace("Z", "+00:00")
        try:
            hour_ist = int(datetime.fromisoformat(published_at).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%H"))
        except ValueError:
            hour_ist = -1
        if hour_ist >= 0:
            hour_groups.setdefault(hour_ist, []).append(score)

        duration = float(item.get("duration_seconds", 0.0) or 0.0)
        bucket = "short" if duration < 20 else "medium" if duration < 30 else "long"
        duration_groups.setdefault(bucket, []).append(score)

    def average_map(groups: dict[Any, list[float]]) -> dict[str, float]:
        return {str(key): round(sum(values) / len(values), 4) for key, values in groups.items() if values}

    family_scores = average_map(family_groups)
    style_scores = average_map(style_groups)
    hour_scores = average_map(hour_groups)
    duration_scores = average_map(duration_groups)

    best_families = [
        key for key, _ in sorted(family_scores.items(), key=lambda item: item[1], reverse=True)[:3]
    ]
    best_hours = [
        int(key) for key, _ in sorted(hour_scores.items(), key=lambda item: item[1], reverse=True)[:3]
        if str(key).isdigit()
    ]

    return {
        "version": 1,
        "updated_at_utc": payload.get("updated_at_utc"),
        "data_ready": len(videos) >= 5,
        "public_videos_measured": len(videos),
        "best_topic_families": best_families,
        "best_publish_hours_ist": best_hours,
        "topic_family_scores": family_scores,
        "description_style_scores": style_scores,
        "duration_bucket_scores": duration_scores,
        "note": (
            "Use as a soft learning signal only. Keep exploring until enough public "
            "Shorts exist; do not overfit to one or two videos."
        ),
    }


def strategy_prompt_context() -> str:
    profile = _load(STRATEGY_PROFILE_PATH, {})
    if not profile:
        return "No reliable performance learning data is available yet; prioritize exploration."
    lines = [
        f"Measured public Shorts: {profile.get('public_videos_measured', 0)}",
        f"Data ready for soft optimization: {profile.get('data_ready', False)}",
        f"Better-performing topic families so far: {', '.join(profile.get('best_topic_families', [])) or 'none yet'}",
        f"Better-performing publish hours (IST): {', '.join(map(str, profile.get('best_publish_hours_ist', []))) or 'none yet'}",
        f"Duration bucket scores: {json.dumps(profile.get('duration_bucket_scores', {}), ensure_ascii=False)}",
        f"Description style scores: {json.dumps(profile.get('description_style_scores', {}), ensure_ascii=False)}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    collect_performance()
