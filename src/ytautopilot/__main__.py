from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .content import choose_daily_topic, content_fingerprint, record_content_history
from .descriptions import record_style
from .media import (
    build_media_identity,
    is_duplicate_media,
    record_media_generation,
)
from .scriptgen import generate_script
from .publish_package import create_publish_package
from .validate_output import validate_generated_outputs
from .youtube_upload import upload_private_video


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
MAX_GENERATION_ATTEMPTS = 4


def estimate_target_seconds() -> float | None:
    """Estimate a safe narration target from all available gameplay files."""
    gameplay_dir = Path("assets/gameplay")
    files = [
        p
        for p in gameplay_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS and p.stat().st_size > 0
    ] if gameplay_dir.exists() else []
    if not files:
        return None

    total = 0.0
    for path in files:
        try:
            raw = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            total += max(0.0, float(raw))
        except (OSError, subprocess.CalledProcessError, ValueError):
            continue

    if total <= 0:
        return None

    # Reuse this already-probed total during rendering so the same gameplay
    # files do not need a second ffprobe pass in render_short().
    os.environ["YTAP_AVAILABLE_GAMEPLAY_SECONDS"] = f"{total:.6f}"
    return max(10.0, min(52.0, total * 0.82))


def _generate_unique_rendered_short(
    *,
    requested_topic: str,
    target_seconds: float | None,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Generate, render, and reject exact/reproducible media duplicates."""
    from .render import render_short

    attempted_topics: set[str] = set()
    resolved_topic = (
        choose_daily_topic()
        if requested_topic.lower() in {"", "auto", "daily"}
        else requested_topic
    )

    last_identity: dict[str, Any] | None = None
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        if attempt > 1:
            if requested_topic.lower() not in {"", "auto", "daily"}:
                resolved_topic = choose_daily_topic(exclude_topics=attempted_topics)
            else:
                resolved_topic = choose_daily_topic(exclude_topics=attempted_topics)

        attempted_topics.add(resolved_topic)
        print(f"[generator] Attempt {attempt}/{MAX_GENERATION_ATTEMPTS}: {resolved_topic}")

        script = generate_script(
            resolved_topic,
            allow_fallback=mode == "dry-run",
            target_seconds=target_seconds,
        )
        manifest = render_short(script)
        identity = build_media_identity(manifest)
        manifest["media_identity"] = identity
        (Path("output") / "render_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if is_duplicate_media(identity):
            last_identity = identity
            print(
                "[dedupe] Rendered media is already in generation history; "
                "discarding it and generating a fresh Short."
            )
            continue

        return script, manifest, identity

    raise RuntimeError(
        "Could not produce a unique Short after "
        f"{MAX_GENERATION_ATTEMPTS} generation attempts. "
        f"Last media fingerprint: {last_identity.get('composite_fingerprint') if last_identity else 'none'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ytautopilot gaming Shorts pipeline")
    parser.add_argument(
        "--mode",
        choices=("dry-run", "prepare", "publish"),
        default="dry-run",
        help="dry-run generates JSON; prepare renders a reviewable Short; publish uploads it privately/scheduled",
    )
    parser.add_argument(
        "--topic",
        default="auto",
        help="Use 'auto' to select the next unused Free Fire topic from the daily rotation.",
    )
    args = parser.parse_args()

    if args.mode == "publish" and os.environ.get("YOUTUBE_PUBLISH_ENABLED", "").lower() != "true":
        print(
            "Publishing is safety-gated. Set YOUTUBE_PUBLISH_ENABLED=true only "
            "for an intentional private/scheduled upload run."
        )
        return 2

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    target_seconds = estimate_target_seconds() if args.mode in {"prepare", "publish"} else None
    if target_seconds is not None:
        print(f"Gameplay-aware narration target: about {target_seconds:.0f}s")

    if args.mode in {"prepare", "publish"}:
        script, manifest, identity = _generate_unique_rendered_short(
            requested_topic=args.topic.strip(),
            target_seconds=target_seconds,
            mode=args.mode,
        )
    else:
        requested_topic = args.topic.strip()
        resolved_topic = (
            choose_daily_topic()
            if requested_topic.lower() in {"", "auto", "daily"}
            else requested_topic
        )
        print(f"Selected topic: {resolved_topic}")
        script = generate_script(
            resolved_topic,
            allow_fallback=True,
            target_seconds=None,
        )
        manifest = {}
        identity = {}

    output_path = output_dir / "script.json"
    output_path.write_text(
        json.dumps(script, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Script saved to {output_path}")
    print(json.dumps(script, ensure_ascii=False, indent=2))

    if args.mode in {"prepare", "publish"}:
        package = create_publish_package(script, manifest)
        validation = validate_generated_outputs()

        print(
            "\nPublish package validated: "
            f"title={package['title']!r}, "
            f"duration={validation['duration_seconds']:.1f}s, "
            f"resolution={validation['resolution']}, "
            "privacy_status=private"
        )

        # Persist generation state before attempting YouTube. This prevents a
        # failed upload from causing the exact same Short to be generated again.
        record_media_generation(
            identity=identity,
            script_fingerprint=content_fingerprint(script),
            topic=str(script.get("topic", "")).strip(),
            status="generated_ready_for_upload" if args.mode == "publish" else "generated_prepare",
        )
        record_content_history(
            script,
            gameplay_files=[str(path) for path in manifest.get("source_gameplay", [])],
        )
        if package.get("description_style"):
            record_style(
                str(package["description_style"]),
                content_fingerprint(script),
            )

        if args.mode == "publish":
            package = upload_private_video()
            print(
                "\nYouTube upload ready: "
                f"video_id={package.get('youtube_video_id')}, "
                f"status={package.get('status')}, "
                f"publish_at={package.get('scheduled_publish_at')}"
            )
            print("\nPublish mode complete.")
            return 0

        print("\nPrepare mode complete.")
        print("A unique reviewable 9:16 Short was rendered and validated locally/in the workflow.")
        print("No YouTube upload was attempted.")
        return 0

    print("Dry-run complete. No video was rendered or uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
