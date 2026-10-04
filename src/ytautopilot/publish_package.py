from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

from .content import content_fingerprint
from .descriptions import build_description, choose_style


OUTPUT_DIR = Path("output")
TITLE_LIMIT = 100
DESCRIPTION_LIMIT = 5000
TAG_LIMIT = 500  # YouTube's combined tag text limit, in characters.


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _hashtags(script: dict[str, Any]) -> list[str]:
    raw = script.get("hashtags", [])
    if not isinstance(raw, list):
        raw = []
    values: list[str] = []
    for item in raw:
        tag = _clean_text(item).replace(" ", "")
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        if re.fullmatch(r"#[\w]+", tag, flags=re.UNICODE) and tag.lower() not in {v.lower() for v in values}:
            values.append(tag)
    if not values:
        values = ["#FreeFire", "#Gaming", "#Shorts"]
    return values[:8]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    # Devanagari needs a shaping engine for conjuncts and vowel marks.
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    layout = getattr(ImageFont, "Layout", None)
    engine = getattr(layout, "RAQM", None) if layout else None
    if engine is None:
        raise RuntimeError(
            "Pillow was installed without RAQM text shaping; Hindi thumbnail text "
            "cannot be rendered reliably. Use a Pillow build with libraqm support."
        )
    for candidate in candidates:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size, layout_engine=engine)
            except (OSError, ValueError):
                continue
    raise RuntimeError(
        "No usable thumbnail font found. Install fonts-noto-core and Pillow with "
        "libraqm support; refusing to create a cover with missing glyphs."
    )


def _cover_words(script: dict[str, Any]) -> str:
    source = _clean_text(script.get("hook") or script.get("title") or script.get("topic"))
    source = re.sub(r"(?i)#(?:shorts|freefire|gaming)\b", "", source)
    words = source.split()
    # Keep the cover glanceable; this is a candidate, not a claim that YouTube
    # will accept a custom thumbnail upload for every Shorts account.
    return " ".join(words[:5]).strip(" .,!?:;") or "FREE FIRE TIP"


def _thumbnail_frame_source(video_path: Path, manifest: dict[str, Any]) -> tuple[Path, float]:
    """Prefer a clean frame from the original gameplay, before burned captions."""
    segments = manifest.get("selected_segments", [])
    if isinstance(segments, list):
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            source = Path(str(segment.get("path") or ""))
            if not source.is_file() or source.stat().st_size == 0:
                continue
            start = max(0.0, float(segment.get("start", 0.0)))
            duration = max(0.0, float(segment.get("duration", 0.0)))
            # Avoid the exact scene boundary while staying inside the selected
            # segment. This gives the cover a clean gameplay frame instead of
            # the already-captioned final render.
            offset = min(max(0.45, duration * 0.45), max(0.45, duration - 0.1))
            return source, start + offset
    return video_path, 0.8


def _detect_thumbnail_crop(path: Path) -> str | None:
    """Return a conservative crop for obvious black bars in source gameplay."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "info", "-ss", "0.5",
                "-i", str(path), "-vf", "cropdetect=limit=24:round=2:reset=0",
                "-frames:v", "180", "-an", "-f", "null", "-",
            ],
            check=False, capture_output=True, text=True, timeout=30,
        )
        matches = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", result.stderr)
        if not matches:
            return None
        width, height, x, y = map(int, matches[-1])
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        source_w, source_h = map(int, probe.split("x", 1))
        if width < source_w * 0.94 or height < source_h * 0.60:
            return None
        if height >= source_h * 0.97 or (y < 8 and source_h - y - height < 8):
            return None
        if x < 0 or y < 0 or x + width > source_w or y + height > source_h:
            return None
        return f"{width}:{height}:{x}:{y}"
    except (OSError, subprocess.SubprocessError, ValueError, subprocess.TimeoutExpired):
        return None


def create_thumbnail_candidate(
    video_path: Path,
    script: dict[str, Any],
    manifest: dict[str, Any] | None = None,
) -> Path:
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise RuntimeError(f"Cannot create cover: video is missing or empty: {video_path}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_frame = OUTPUT_DIR / "thumbnail_frame_tmp.jpg"
    thumbnail = OUTPUT_DIR / "thumbnail_candidate.jpg"
    frame_source, frame_time = _thumbnail_frame_source(video_path, manifest or {})
    detected_crop = _detect_thumbnail_crop(frame_source)
    crop_filter = f"crop={detected_crop}," if detected_crop else ""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{frame_time:.3f}", "-i", str(frame_source), "-frames:v", "1",
            "-vf", f"{crop_filter}scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-q:v", "2", str(raw_frame),
        ],
        check=True,
    )
    if not raw_frame.is_file() or raw_frame.stat().st_size == 0:
        raise RuntimeError("FFmpeg could not extract a frame for the cover image.")

    with Image.open(raw_frame) as source:
        image = ImageOps.fit(source.convert("RGB"), (1080, 1920))
    raw_frame.unlink(missing_ok=True)

    # Darken and soften the lower-middle area so the hook remains legible over
    # unpredictable gameplay frames without hiding the main action entirely.
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shade)
    draw.rounded_rectangle((64, 590, 1016, 1260), radius=54, fill=(0, 0, 0, 155), outline=(255, 255, 255, 85), width=3)
    shade = shade.filter(ImageFilter.GaussianBlur(1.2))
    image = Image.alpha_composite(image.convert("RGBA"), shade)
    draw = ImageDraw.Draw(image)

    title = _cover_words(script)
    font = _font(78)
    max_width = 850
    lines: list[str] = []
    current = ""
    for word in title.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font, stroke_width=2)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    lines = lines[:4]

    line_heights = []
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font, stroke_width=3)
        line_heights.append(box[3] - box[1])
    total_height = sum(line_heights) + max(0, len(lines) - 1) * 24
    y = (1920 - total_height) // 2
    for line, line_height in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=3)
        x = (1080 - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0, 245))
        y += line_height + 24

    badge_font = _font(42)
    badge = "FREE FIRE • HINGLISH"
    badge_box = draw.textbbox((0, 0), badge, font=badge_font)
    badge_x = (1080 - (badge_box[2] - badge_box[0])) // 2
    draw.rounded_rectangle((badge_x - 28, 500, badge_x + (badge_box[2] - badge_box[0]) + 28, 570), radius=24, fill=(255, 183, 0, 235))
    draw.text((badge_x, 508), badge, font=badge_font, fill=(20, 20, 20, 255))
    image.convert("RGB").save(thumbnail, "JPEG", quality=92, optimize=True)
    return thumbnail


def build_publish_metadata(script: dict[str, Any], manifest: dict[str, Any], thumbnail_path: Path) -> dict[str, Any]:
    title = _clean_text(script.get("title"))
    description_style = choose_style()
    description = build_description(script, description_style)
    if not title:
        raise RuntimeError("Publish metadata validation failed: title is empty.")
    if not description:
        raise RuntimeError("Publish metadata validation failed: description is empty.")
    if len(title) > TITLE_LIMIT:
        title = title[:TITLE_LIMIT].rsplit(" ", 1)[0].rstrip(" .,!?:;") or title[:TITLE_LIMIT]
    hashtags = _hashtags(script)
    # Append only tags not already present, keeping description readable.
    existing = {token.lower() for token in re.findall(r"#[\w]+", description, flags=re.UNICODE)}
    missing = [tag for tag in hashtags if tag.lower() not in existing]
    if missing:
        description = (description + "\n\n" + " ".join(missing)).strip()
    description = description[:DESCRIPTION_LIMIT].rstrip()

    raw_tags = script.get("tags", [])
    if not isinstance(raw_tags, list):
        raw_tags = []
    tags: list[str] = []
    for item in raw_tags:
        tag = _clean_text(item).lstrip("#")
        if tag and tag.lower() not in {value.lower() for value in tags}:
            tags.append(tag)
    # Leave headroom under the combined tag text limit.
    bounded_tags: list[str] = []
    total = 0
    for tag in tags:
        cost = len(tag) + (1 if bounded_tags else 0)
        if total + cost > TAG_LIMIT:
            break
        bounded_tags.append(tag)
        total += cost

    video_path = Path(str(manifest.get("video") or "output/short_preview.mp4"))
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise RuntimeError("Publish metadata validation failed: rendered video is missing.")
    if not thumbnail_path.is_file() or thumbnail_path.stat().st_size == 0:
        raise RuntimeError("Publish metadata validation failed: thumbnail candidate is missing.")

    fingerprint = content_fingerprint(script)
    topic_key = hashlib.sha256(_clean_text(script.get("topic")).lower().encode("utf-8")).hexdigest()[:16]
    metadata = {
        "schema_version": 2,
        "fingerprint": fingerprint,
        "topic_key": topic_key,
        "upload_marker": f"ytautopilot-topic-{topic_key}",
        "status": "ready_for_private_upload",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "topic": _clean_text(script.get("topic")),
        "language": _clean_text(script.get("language") or "Hindi/Hinglish"),
        "title": title,
        "description": description,
        "description_style": description_style,
        "hashtags": hashtags,
        "tags": bounded_tags,
        "category_id": "20",
        "thumbnail_candidate": str(thumbnail_path),
        "thumbnail_dimensions": "1080x1920",
        "thumbnail_strategy": "clean source-gameplay frame from a selected scene segment, with generated hook text overlay",
        "thumbnail_note": "Candidate cover is generated from the original gameplay segment rather than the caption-burned render. Applying a custom video thumbnail through YouTube depends on the authorized channel and current platform support.",
        "video": str(video_path),
        "duration_seconds": manifest.get("duration_seconds"),
        "resolution": manifest.get("resolution", "1080x1920"),
        "privacy_status": "private",
        "youtube_video_id": None,
        "fact_check_notes": script.get("fact_check_notes", []),
        "media_identity": manifest.get("media_identity", {}),
    }
    output_path = OUTPUT_DIR / "publish_metadata.json"
    output_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[package] Publish metadata: {output_path}")
    print(f"[package] Thumbnail candidate: {thumbnail_path}")
    print(f"[package] Title length: {len(title)}/{TITLE_LIMIT}; description length: {len(description)}/{DESCRIPTION_LIMIT}")
    return metadata


def create_publish_package(script: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    video_path = Path(str(manifest.get("video") or "output/short_preview.mp4"))
    thumbnail = create_thumbnail_candidate(video_path, script, manifest)
    return build_publish_metadata(script, manifest, thumbnail)
