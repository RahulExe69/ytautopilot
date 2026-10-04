from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
GAMEPLAY_DIR = ROOT / "assets" / "gameplay"
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work" / "render"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def run(command: list[str], *, label: str) -> None:
    print(f"\n[render] {label}")
    print("$ " + shlex.join(command))
    subprocess.run(command, check=True)


def command_output(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def require_tools() -> None:
    for name in ("ffmpeg", "ffprobe", "edge-tts"):
        if shutil.which(name) is None:
            raise RuntimeError(
                f"Required tool '{name}' was not found on PATH. "
                "The GitHub Actions workflow installs FFmpeg and the Python dependencies."
            )


def ffprobe_duration(path: Path) -> float:
    raw = command_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        duration = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"Could not read duration for {path}") from exc
    if duration <= 0:
        raise RuntimeError(f"Gameplay file has no usable duration: {path}")
    return duration


def find_gameplay() -> list[Path]:
    if not GAMEPLAY_DIR.exists():
        raise RuntimeError(
            "Gameplay directory is missing: assets/gameplay/. "
            "Upload at least one gameplay video that you own or have permission to reuse."
        )

    files = sorted(
        p
        for p in GAMEPLAY_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS and p.stat().st_size > 0
    )

    if not files:
        raise RuntimeError(
            "No gameplay videos were found in assets/gameplay/. "
            "Upload at least one .mp4, .mov, .mkv, or .webm file."
        )

    return files


def generate_tts(text: str, audio_path: Path, subtitle_path: Path) -> None:
    voice = os.getenv("EDGE_TTS_VOICE", "hi-IN-MadhurNeural").strip()
    rate = os.getenv("EDGE_TTS_RATE", "+5%").strip()

    run(
        [
            "edge-tts",
            "--voice",
            voice,
            "--rate",
            rate,
            "--text",
            text,
            "--write-media",
            str(audio_path),
            "--write-subtitles",
            str(subtitle_path),
        ],
        label=f"Generate narration with {voice}",
    )

    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise RuntimeError("TTS completed without producing an audio file.")
    if not subtitle_path.exists() or subtitle_path.stat().st_size == 0:
        raise RuntimeError("TTS completed without producing subtitle cues.")


def get_audio_duration(path: Path) -> float:
    return ffprobe_duration(path)


def build_gameplay_track(
    gameplay_files: list[Path],
    duration: float,
    destination: Path,
) -> list[Path]:
    # Use three visual beats so a first render can switch between available gameplay clips.
    segment_ratios = (0.15, 0.50, 0.35)
    segment_durations = [duration * ratio for ratio in segment_ratios]

    selected = [gameplay_files[i % len(gameplay_files)] for i in range(3)]

    ffmpeg_args = ["ffmpeg", "-y"]
    filter_parts: list[str] = []

    for index, path in enumerate(selected):
        ffmpeg_args += ["-stream_loop", "-1", "-i", str(path)]
        segment = segment_durations[index]
        filter_parts.append(
            f"[{index}:v]"
            f"fps=30,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"setsar=1,"
            f"trim=duration={segment:.3f},"
            f"setpts=PTS-STARTPTS"
            f"[v{index}]"
        )

    concat_inputs = "".join(f"[v{i}]" for i in range(3))
    filter_parts.append(
        f"{concat_inputs}concat=n=3:v=1:a=0[gameplay]"
    )

    ffmpeg_args += [
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        "[gameplay]",
        "-t",
        f"{duration:.3f}",
        "-an",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        str(destination),
    ]

    run(ffmpeg_args, label="Build vertical gameplay track")
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce the gameplay track.")

    return selected


def subtitle_filter(subtitle_path: Path) -> str:
    # Noto Sans Devanagari is installed by the workflow so Hindi + Latin text render reliably.
    escaped = str(subtitle_path.resolve()).replace("\\", "/")
    style = (
        "FontName=Noto Sans Devanagari,"
        "FontSize=20,"
        "Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=3,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=120"
    )
    return f"subtitles={escaped}:force_style='{style}'"


def render_final_video(
    gameplay_track: Path,
    narration_audio: Path,
    subtitles: Path,
    duration: float,
    destination: Path,
) -> None:
    video_filter = subtitle_filter(subtitles)

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(gameplay_track),
            "-i",
            str(narration_audio),
            "-filter_complex",
            f"[0:v]{video_filter}[v]",
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        label="Render final 9:16 Short",
    )

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce the final Short.")


def render_short(script: dict[str, Any]) -> dict[str, Any]:
    require_tools()

    narration = str(script.get("narration") or "").strip()
    if not narration:
        raise RuntimeError("Generated script has no narration text.")

    hook = str(script.get("hook") or "").strip()
    include_hook = os.getenv("INCLUDE_HOOK_IN_NARRATION", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    spoken_text = f"{hook} {narration}".strip() if include_hook and hook else narration

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    narration_audio = WORK_DIR / "narration.mp3"
    narration_srt = WORK_DIR / "narration.srt"
    gameplay_track = WORK_DIR / "gameplay_track.mp4"
    final_video = OUTPUT_DIR / "short_preview.mp4"

    generate_tts(spoken_text, narration_audio, narration_srt)
    duration = get_audio_duration(narration_audio)

    if duration > 58:
        raise RuntimeError(
            f"Narration is {duration:.1f}s long. Keep Shorts narration at 58 seconds or less "
            "for this first renderer."
        )
    if duration < 8:
        raise RuntimeError(
            f"Narration is only {duration:.1f}s long. Generate a fuller script before rendering."
        )

    gameplay_files = find_gameplay()
    selected = build_gameplay_track(gameplay_files, duration, gameplay_track)
    render_final_video(
        gameplay_track,
        narration_audio,
        narration_srt,
        duration,
        final_video,
    )

    # Copy the generated audio/captions into output so the artifact is useful for debugging.
    output_audio = OUTPUT_DIR / "narration.mp3"
    output_srt = OUTPUT_DIR / "captions.srt"
    shutil.copy2(narration_audio, output_audio)
    shutil.copy2(narration_srt, output_srt)

    manifest = {
        "renderer": "ytautopilot-stage-2",
        "video": str(final_video),
        "duration_seconds": round(duration, 3),
        "resolution": "1080x1920",
        "fps": 30,
        "voice": os.getenv("EDGE_TTS_VOICE", "hi-IN-MadhurNeural").strip(),
        "rate": os.getenv("EDGE_TTS_RATE", "+5%").strip(),
        "spoken_text": spoken_text,
        "source_gameplay": [str(path) for path in selected],
        "available_gameplay_files": [str(path) for path in gameplay_files],
    }
    (OUTPUT_DIR / "render_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[render] Final video: {final_video}")
    print(f"[render] Duration: {duration:.1f}s")
    print(f"[render] Source clips: {', '.join(str(p) for p in selected)}")
    return manifest
