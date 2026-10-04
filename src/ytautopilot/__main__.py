from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .content import choose_daily_topic, record_content_history
from .scriptgen import generate_script


def main() -> int:
    parser = argparse.ArgumentParser(description="ytautopilot gaming Shorts pipeline")
    parser.add_argument(
        "--mode",
        choices=("dry-run", "prepare", "publish"),
        default="dry-run",
        help="dry-run only generates JSON; prepare also renders a reviewable Short; publish is still gated",
    )
    parser.add_argument(
        "--topic",
        default="auto",
        help="Use 'auto' to select the next unused Free Fire topic from the daily rotation.",
    )
    args = parser.parse_args()

    if args.mode == "publish":
        print("Publishing is not implemented in this build. No upload was attempted.")
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

    script = generate_script(resolved_topic, allow_fallback=args.mode == "dry-run")
    output_path = output_dir / "script.json"
    output_path.write_text(
        json.dumps(script, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Script saved to {output_path}")
    print(json.dumps(script, ensure_ascii=False, indent=2))

    if args.mode == "prepare":
        from .render import render_short

        manifest = render_short(script)
        record_content_history(
            script,
            gameplay_files=[str(path) for path in manifest.get("source_gameplay", [])],
        )
        print("\nPrepare mode complete.")
        print("A reviewable 9:16 Short was rendered locally/in the workflow.")
        print("No YouTube upload was attempted.")
        return 0

    print("Dry-run complete. No video was rendered or uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
