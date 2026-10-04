from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image


def _probe(path: Path, *entries: str) -> list[str]:
    command = [
        "ffprobe",
        "-v",
        "error",
    ]
    for entry in entries:
        command.extend(["-show_entries", entry])
    command.extend(["-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def validate_generated_outputs(
    metadata_path: Path = Path("output") / "publish_metadata.json",
) -> dict[str, Any]:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("Output validation requires ffprobe on PATH.")

    if not metadata_path.is_file():
        raise RuntimeError(f"Publish metadata file is missing: {metadata_path}")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not parse publish metadata: {metadata_path}") from exc
    if not isinstance(metadata, dict):
        raise RuntimeError("Publish metadata must be a JSON object.")

    video = Path(str(metadata.get("video") or ""))
    thumbnail = Path(str(metadata.get("thumbnail_candidate") or ""))
    required = {
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "privacy_status": metadata.get("privacy_status"),
    }
    for key, value in required.items():
        if not str(value or "").strip():
            raise RuntimeError(f"Output validation failed: metadata field '{key}' is empty.")

    if str(metadata.get("privacy_status")).lower() != "private":
        raise RuntimeError("Output validation failed: privacy_status must remain private.")

    if not video.is_file() or video.stat().st_size == 0:
        raise RuntimeError(f"Output validation failed: video is missing or empty: {video}")
    if not thumbnail.is_file() or thumbnail.stat().st_size == 0:
        raise RuntimeError(
            f"Output validation failed: thumbnail is missing or empty: {thumbnail}"
        )

    dimensions = _probe(video, "stream=width,height")
    if not dimensions or len(dimensions) < 2:
        raise RuntimeError("Output validation failed: could not read video dimensions.")
    width, height = int(dimensions[0]), int(dimensions[1])
    if (width, height) != (1080, 1920):
        raise RuntimeError(
            f"Output validation failed: expected 1080x1920, got {width}x{height}."
        )

    duration_rows = _probe(video, "format=duration")
    if not duration_rows:
        raise RuntimeError("Output validation failed: video duration is unavailable.")
    duration = float(duration_rows[0])
    if not 10.0 <= duration <= 60.0:
        raise RuntimeError(
            f"Output validation failed: Short duration {duration:.2f}s is outside 10-60s."
        )

    audio_rows = _probe(
        video,
        "stream=codec_type",
    )
    if "audio" not in audio_rows:
        raise RuntimeError("Output validation failed: final video has no audio stream.")

    with Image.open(thumbnail) as image:
        thumb_size = image.size
        image.verify()
    if thumb_size != (1080, 1920):
        raise RuntimeError(
            "Output validation failed: expected 1080x1920 thumbnail, "
            f"got {thumb_size[0]}x{thumb_size[1]}."
        )

    report = {
        "video": str(video),
        "thumbnail": str(thumbnail),
        "resolution": f"{width}x{height}",
        "duration_seconds": round(duration, 3),
        "has_audio": True,
        "thumbnail_dimensions": f"{thumb_size[0]}x{thumb_size[1]}",
        "privacy_status": str(metadata["privacy_status"]),
        "title_length": len(str(metadata["title"])),
        "description_length": len(str(metadata["description"])),
    }
    report_path = Path("output") / "validation_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[validate] "
        f"{report['resolution']} / {report['duration_seconds']:.2f}s / "
        "audio=yes / thumbnail=1080x1920 / privacy=private"
    )
    return report
