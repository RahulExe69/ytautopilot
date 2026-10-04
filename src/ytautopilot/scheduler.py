from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PROFILE_PATH = Path("data") / "strategy_profile.json"
IST = ZoneInfo("Asia/Kolkata")


def _best_hour(slot: str, now: datetime) -> int:
    defaults = {"midday": 13, "evening": 20}
    windows = {
        "midday": {13, 14},
        "evening": {20, 21},
    }
    try:
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8")) if PROFILE_PATH.exists() else {}
    except (OSError, json.JSONDecodeError):
        profile = {}
    hours = profile.get("best_publish_hours_ist", []) if isinstance(profile, dict) else []
    candidates = [int(hour) for hour in hours if str(hour).isdigit() and int(hour) in windows.get(slot, set())]
    return candidates[0] if profile.get("data_ready") and candidates else defaults.get(slot, 13)


def scheduled_publish_at(slot: str, now: datetime | None = None) -> str:
    current = (now or datetime.now(IST)).astimezone(IST)
    hour = _best_hour(slot, current)
    minute = 0 if slot == "midday" else 30
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return target.isoformat()
