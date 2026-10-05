from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

from googleapiclient.discovery import build

from .content import classify_hook_style, topic_family
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



def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _group_metrics(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        group = str(record.get(key) or "unknown")
        grouped.setdefault(group, []).append(record)

    result: dict[str, dict[str, Any]] = {}
    for group, items in grouped.items():
        scores = [float(item.get("performance_score", 0.0) or 0.0) for item in items]
        velocities = [float(item.get("views_per_hour", 0.0) or 0.0) for item in items]
        engagement = [float(item.get("engagement_rate", 0.0) or 0.0) for item in items]
        result[group] = {
            "samples": len(items),
            "avg_performance_score": _average(scores),
            "avg_views_per_hour": _average(velocities),
            "avg_engagement_rate": _average(engagement),
        }
    return result

def collect_performance(upload_history_path: Path = Path("data") / "upload_history.json") -> dict[str, Any]:
    history = _load(upload_history_path, {"uploads": []})
    uploads = [item for item in history.get("uploads", []) if isinstance(item, dict)]

    ids: list[str] = []
    metadata_by_id: dict[str, dict[str, Any]] = {}
    for item in uploads[-100:]:
        video_id = str(item.get("youtube_video_id", "")).strip()
        if video_id:
            ids.append(video_id)
            metadata_by_id[video_id] = item
    ids = list(dict.fromkeys(ids))

    content_payload = _load(Path("data") / "content_history.json", {"entries": []})
    content_by_fingerprint: dict[str, dict[str, Any]] = {}
    for item in content_payload.get("entries", []):
        if not isinstance(item, dict):
            continue
        fingerprint = str(item.get("fingerprint", "")).strip()
        if fingerprint:
            content_by_fingerprint[fingerprint] = item

    if not ids:
        payload = {
            "version": 2,
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

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()

    for item in videos:
        video_id = str(item.get("id", "")).strip()
        if not video_id:
            continue

        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        upload_meta = metadata_by_id.get(video_id, {})
        content_meta = content_by_fingerprint.get(
            str(upload_meta.get("fingerprint", "")).strip(),
            {},
        )

        topic = str(upload_meta.get("topic") or content_meta.get("topic") or "").strip()
        hook = str(upload_meta.get("hook") or content_meta.get("hook") or "").strip()
        previous_record = previous_by_id.get(video_id, {})

        published_at = snippet.get("publishedAt") or previous_record.get("published_at")
        published_dt = _parse_timestamp(str(published_at) if published_at else None)
        age_hours = (
            max(0.25, (now_dt - published_dt).total_seconds() / 3600.0)
            if published_dt
            else 0.25
        )

        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        previous_views = int(previous_record.get("views", views) or views)

        previous_fetched = _parse_timestamp(str(previous_record.get("fetched_at_utc", "")))
        elapsed_since_fetch = (
            max(0.25, (now_dt - previous_fetched).total_seconds() / 3600.0)
            if previous_fetched
            else 0.25
        )
        views_delta = max(0, views - previous_views)
        velocity = views / age_hours
        recent_velocity = views_delta / elapsed_since_fetch

        duration_seconds = round(
            _parse_duration_seconds(str(details.get("duration", ""))),
            3,
        )
        record = {
            **previous_record,
            "video_id": video_id,
            "title": str(snippet.get("title", upload_meta.get("title", ""))),
            "topic": topic,
            "topic_family": topic_family(topic),
            "hook": hook,
            "hook_style": classify_hook_style(hook),
            "description_style": str(
                upload_meta.get("description_style", previous_record.get("description_style", "default"))
            ),
            "published_at": published_at,
            "fetched_at_utc": now,
            "privacy_status": status.get("privacyStatus"),
            "duration_seconds": duration_seconds,
            "age_hours": round(age_hours, 3),
            "views": views,
            "views_delta_since_last_fetch": views_delta,
            "views_per_hour": round(velocity, 4),
            "recent_views_per_hour": round(recent_velocity, 4),
            "likes": likes,
            "comments": comments,
            "engagement_rate": round((likes + comments) / max(views, 1), 6),
            "like_rate": round(likes / max(views, 1), 6),
            "comment_rate": round(comments / max(views, 1), 6),
        }
        record["performance_score"] = _performance_score(record)
        previous_by_id[video_id] = record

    payload = {
        "version": 2,
        "updated_at_utc": now,
        "videos": list(previous_by_id.values())[-200:],
    }
    _save(PERFORMANCE_HISTORY_PATH, payload)
    _save(STRATEGY_PROFILE_PATH, build_strategy_profile(payload))
    return payload


def build_strategy_profile(payload: dict[str, Any]) -> dict[str, Any]:
    videos = [
        item
        for item in payload.get("videos", [])
        if isinstance(item, dict) and str(item.get("privacy_status")) == "public"
    ]

    family_stats = _group_metrics(videos, "topic_family")
    hook_stats = _group_metrics(videos, "hook_style")
    style_stats = _group_metrics(videos, "description_style")

    hour_records: list[dict[str, Any]] = []
    duration_records: list[dict[str, Any]] = []
    for item in videos:
        published_at = _parse_timestamp(str(item.get("published_at", "")))
        if published_at:
            hour_records.append(
                {
                    "group": str(
                        published_at.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%H")
                    ),
                    "performance_score": item.get("performance_score", 0.0),
                    "views_per_hour": item.get("views_per_hour", 0.0),
                    "engagement_rate": item.get("engagement_rate", 0.0),
                }
            )

        duration = float(item.get("duration_seconds", 0.0) or 0.0)
        bucket = "short" if duration < 20 else "medium" if duration < 30 else "long"
        duration_records.append(
            {
                "group": bucket,
                "performance_score": item.get("performance_score", 0.0),
                "views_per_hour": item.get("views_per_hour", 0.0),
                "engagement_rate": item.get("engagement_rate", 0.0),
            }
        )

    def records_to_groups(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            grouped.setdefault(str(record.get("group", "unknown")), []).append(record)
        result: dict[str, dict[str, Any]] = {}
        for group, items in grouped.items():
            result[group] = {
                "samples": len(items),
                "avg_performance_score": _average(
                    [float(item.get("performance_score", 0.0) or 0.0) for item in items]
                ),
                "avg_views_per_hour": _average(
                    [float(item.get("views_per_hour", 0.0) or 0.0) for item in items]
                ),
                "avg_engagement_rate": _average(
                    [float(item.get("engagement_rate", 0.0) or 0.0) for item in items]
                ),
            }
        return result

    hour_stats = records_to_groups(hour_records)
    duration_stats = records_to_groups(duration_records)

    baseline = _average(
        [float(item.get("performance_score", 0.0) or 0.0) for item in videos]
    )

    def top_groups(groups: dict[str, dict[str, Any]], minimum_samples: int = 2) -> list[str]:
        eligible = [
            (key, value)
            for key, value in groups.items()
            if int(value.get("samples", 0) or 0) >= minimum_samples
        ]
        return [
            key
            for key, _ in sorted(
                eligible,
                key=lambda item: float(item[1].get("avg_performance_score", 0.0) or 0.0),
                reverse=True,
            )[:3]
        ]

    best_families = top_groups(family_stats)
    best_hooks = top_groups(hook_stats)

    avoid_families = []
    if baseline > 0:
        avoid_families = [
            key
            for key, value in sorted(family_stats.items())
            if int(value.get("samples", 0) or 0) >= 3
            and float(value.get("avg_performance_score", 0.0) or 0.0) < baseline * 0.65
        ]

    best_hours = [
        int(key)
        for key in top_groups(hour_stats)
        if str(key).isdigit()
    ]

    return {
        "version": 2,
        "updated_at_utc": payload.get("updated_at_utc"),
        "data_ready": len(videos) >= 5,
        "public_videos_measured": len(videos),
        "baseline_performance_score": baseline,
        "best_topic_families": best_families,
        "best_hook_styles": best_hooks,
        "best_publish_hours_ist": best_hours,
        "avoid_topic_families": avoid_families[:3],
        "topic_family_stats": family_stats,
        "hook_style_stats": hook_stats,
        "description_style_scores": {
            key: value.get("avg_performance_score", 0.0)
            for key, value in style_stats.items()
        },
        "duration_bucket_scores": {
            key: value.get("avg_performance_score", 0.0)
            for key, value in duration_stats.items()
        },
        "duration_bucket_stats": duration_stats,
        "exploration_policy": {
            "minimum_public_shorts_before_strong_optimization": 5,
            "minimum_samples_per_family_before_preference": 2,
            "keep_exploring_under_sampled_families": True,
        },
        "note": (
            "Learning signals are intentionally soft. Explore broadly with small "
            "samples, then increase exploitation as topic and hook evidence grows."
        ),
    }


def strategy_prompt_context() -> str:
    profile = _load(STRATEGY_PROFILE_PATH, {})
    if not profile:
        return (
            "No reliable performance learning data is available yet. "
            "Explore topic families and hook styles instead of over-optimizing."
        )

    family_stats = profile.get("topic_family_stats", {})
    hook_stats = profile.get("hook_style_stats", {})
    def summarize(groups: dict[str, Any], limit: int = 4) -> str:
        rows = []
        for key, value in sorted(
            groups.items(),
            key=lambda item: float(item[1].get("avg_performance_score", 0.0) or 0.0),
            reverse=True,
        )[:limit]:
            rows.append(
                f"{key} ({int(value.get('samples', 0) or 0)} samples, "
                f"score {float(value.get('avg_performance_score', 0.0) or 0.0):.2f})"
            )
        return ", ".join(rows) or "none yet"

    lines = [
        f"Measured public Shorts: {profile.get('public_videos_measured', 0)}",
        f"Data ready for stronger optimization: {profile.get('data_ready', False)}",
        f"Better-performing topic families: {summarize(family_stats)}",
        f"Better-performing hook styles: {summarize(hook_stats)}",
        f"Recommended family names: {', '.join(profile.get('best_topic_families', [])) or 'none yet'}",
        f"Recommended hook styles: {', '.join(profile.get('best_hook_styles', [])) or 'none yet'}",
        f"Families to de-emphasize after enough samples: {', '.join(profile.get('avoid_topic_families', [])) or 'none yet'}",
        f"Better publish hours (IST): {', '.join(map(str, profile.get('best_publish_hours_ist', []))) or 'not enough evidence'}",
        f"Duration bucket scores: {json.dumps(profile.get('duration_bucket_scores', {}), ensure_ascii=False)}",
        (
            "Learning rule: use these as soft signals only. Keep exploring new "
            "families and hooks; never force a learned pattern when it does not fit the topic."
        ),
    ]
    return "\n".join(lines)



if __name__ == "__main__":
    collect_performance()
