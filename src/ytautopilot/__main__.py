from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .scriptgen import generate_script


def main() -> int:
    parser = argparse.ArgumentParser(description="ytautopilot gaming Shorts pipeline")
    parser.add_argument("--mode", choices=("dry-run", "prepare", "publish"), default="dry-run")
    parser.add_argument("--topic", default="Free Fire tips and lesser-known facts")
    args = parser.parse_args()

    if args.mode == "publish":
        print("Publishing is not implemented in this starter build. No upload was attempted.")
        return 2

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    script = generate_script(args.topic, allow_fallback=args.mode == "dry-run")
    output_path = output_dir / "script.json"
    output_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Script saved to {output_path}")
    print(json.dumps(script, ensure_ascii=False, indent=2))

    if args.mode != "dry-run":
        print("This starter stage generates scripts only; rendering and upload are not wired yet.")
        print("No video was uploaded. Next: validate footage rights, then implement rendering and YouTube OAuth.")
        return 0

    print("Dry-run complete. No video was uploaded and no YouTube account was changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
