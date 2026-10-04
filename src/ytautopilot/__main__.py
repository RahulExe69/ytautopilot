from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .content import choose_daily_topic, record_content_history
from .scriptgen import generate_script
from .publish_package import create_publish_package
from .validate_output import validate_generated_outputs
from .youtube_upload import upload_private_video


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def estimate_target_seconds() -> float | None:
    """Estimate a safe narration target from all available gameplay files."""
    gameplay_dir = Path("assets/gameplay")
    files = [p for p in gameplay_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS and p.stat().st_size > 0] if gameplay_dir.exists() else []
    if not files:
        return None
    total = 0.0
    for path in files:
        try:
            raw = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            total += max(0.0, float(raw))
        except (OSError, subprocess.CalledProcessError, ValueError):
            continue
    if total <= 0:
        return None
    # Reserve 18% for scene-boundary selection, transitions, and encoding variance.
    return max(10.0, min(52.0, total * 0.82))


def main() -> int:
    parser = argparse.ArgumentParser(description="ytautopilot gaming Shorts pipeline")
    parser.add_argument(
        "--mode",
        choices=("dry-run", "prepare", "publish"),
        default="dry-run",
        help="dry-run generates JSON; prepare renders a reviewable Short; publish uploads it as private",
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
            "for an intentional private upload run."
        )
        return 2

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    requested_topic = args.topic.strip()
    resolved_topic = (
        choose_daily_topic()
        if requested_topic.lower() in {"", "auto", "daily"}
        else requested_topic
    )
    print(f"Selected topic: {resolved_topic}")

    target_seconds = estimate_target_seconds() if args.mode in {"prepare", "publish"} else None
    if target_seconds is not None:
        print(f"Gameplay-aware narration target: about {target_seconds:.0f}s")
    script = generate_script(
        resolved_topic,
        allow_fallback=args.mode == "dry-run",
        target_seconds=target_seconds,
    )
    output_path = output_dir / "script.json"
    output_path.write_text(
        json.dumps(script, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Script saved to {output_path}")
    print(json.dumps(script, ensure_ascii=False, indent=2))

    if args.mode in {"prepare", "publish"}:
        from .render import render_short

        manifest = render_short(script)
        package = create_publish_package(script, manifest)
        validation = validate_generated_outputs()
        print(
            "\nPublish package validated: "
            f"title={package['title']!r}, "
            f"duration={validation['duration_seconds']:.1f}s, "
            f"resolution={validation['resolution']}, "
            "privacy_status=private"
        )

        if args.mode == "publish":
            package = upload_private_video()
            print(
                "\nPrivate YouTube upload ready: "
                f"video_id={package.get('youtube_video_id')}, "
                f"status={package.get('status')}"
            )
            record_content_history(
                script,
                gameplay_files=[str(path) for path in manifest.get("source_gameplay", [])],
            )
            print("\nPublish mode complete. The video was uploaded with privacy=private.")
            return 0

        record_content_history(
            script,
            gameplay_files=[str(path) for path in manifest.get("source_gameplay", [])],
        )
        print("\nPrepare mode complete.")
        print("A reviewable 9:16 Short was rendered and validated locally/in the workflow.")
        print("No YouTube upload was attempted.")
        return 0

    print("Dry-run complete. No video was rendered or uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
