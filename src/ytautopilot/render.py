from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scenedetect import ContentDetector, SceneManager, open_video
from .tts import generate_indicvoice_tts


ROOT = Path.cwd()
GAMEPLAY_DIR = ROOT / "assets" / "gameplay"
MUSIC_DIR = ROOT / "assets" / "music"
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work" / "render"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
HIGHLIGHT_WORDS = {
    "secret",
    "hidden",
    "fact",
    "facts",
    "tip",
    "tips",
    "pro",
    "trick",
    "tricks",
    "op",
    "best",
    "fast",
    "faster",
    "slow",
    "prone",
    "headshot",
    "damage",
    "movement",
    "speed",
    "gloo",
    "awm",
    "sniper",
    "ranked",
    "one",
    "two",
    "three",
    "3",
}


@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str


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
    for name in ("ffmpeg", "ffprobe"):
        if shutil.which(name) is None:
            raise RuntimeError(
                f"Required tool '{name}' was not found on PATH. "
                "The GitHub Actions workflow installs FFmpeg and Python dependencies."
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
        raise RuntimeError(f"Media file has no usable duration: {path}")
    return duration


def has_audio(path: Path) -> bool:
    raw = command_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    return bool(raw.strip())


def find_gameplay() -> list[Path]:
    if not GAMEPLAY_DIR.exists():
        raise RuntimeError(
            "Gameplay directory is missing: assets/gameplay/. "
            "Upload gameplay videos that you own or have permission to reuse."
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


def find_music() -> list[Path]:
    if not MUSIC_DIR.exists():
        return []
    return sorted(
        p
        for p in MUSIC_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg"} and p.stat().st_size > 0
    )


def srt_time_to_ms(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    sec, millis = seconds.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(sec) * 1_000
        + int(millis)
    )


def ms_to_ass_time(value: int) -> str:
    value = max(0, int(value))
    hours = value // 3_600_000
    minutes = (value % 3_600_000) // 60_000
    seconds = (value % 60_000) // 1_000
    centiseconds = (value % 1_000) // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def parse_srt(path: Path) -> list[Cue]:
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").strip()
    if not raw:
        return []

    cues: list[Cue] = []
    blocks = re.split(r"\n\s*\n", raw)
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.split("\n") if line.strip()]
        if len(lines) < 3:
            continue
        timing = next((line for line in lines if " --> " in line), None)
        if timing is None:
            continue
        start_text, end_text = timing.split(" --> ", 1)
        text_lines = [line for line in lines if line != timing and not line.isdigit()]
        text = re.sub(r"\s+", " ", " ".join(text_lines)).strip()
        if not text:
            continue
        cues.append(Cue(srt_time_to_ms(start_text), srt_time_to_ms(end_text), text))
    return cues


def clean_caption_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("<", "").replace(">", "")
    return text


def split_caption_chunks(text: str, max_words: int = 3, max_chars: int = 24) -> list[str]:
    words = clean_caption_text(text).split()
    if len(words) <= max_words:
        return [" ".join(words)]

    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def split_cue(cue: Cue) -> list[tuple[int, int, str]]:
    chunks = split_caption_chunks(cue.text)
    if len(chunks) == 1:
        return [(cue.start_ms, cue.end_ms, chunks[0])]

    weights = [max(1, len(re.sub(r"\W", "", chunk, flags=re.UNICODE))) for chunk in chunks]
    total_weight = sum(weights)
    duration = max(1, cue.end_ms - cue.start_ms)

    result: list[tuple[int, int, str]] = []
    cursor = cue.start_ms
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        if index == len(chunks) - 1:
            end = cue.end_ms
        else:
            end = cursor + max(220, int(duration * (weight / total_weight)))
        if end <= cursor:
            end = cursor + 220
        result.append((cursor, min(end, cue.end_ms), chunk))
        cursor = end
    if result:
        start, _, chunk = result[-1]
        result[-1] = (start, cue.end_ms, chunk)
    return result


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")


def styled_chunk(text: str) -> str:
    words = text.split()
    out: list[str] = []
    for word in words:
        normalized = re.sub(r"[^A-Za-z0-9+#-]", "", word).lower()
        if normalized in HIGHLIGHT_WORDS or any(
            token and token in normalized
            for token in ("gloo", "awm", "prone", "headshot", "sniper")
        ):
            out.append(
                "{\\c&H0000D7FF&\\fs76}" + ass_escape(word) + "{\\c&H00FFFFFF&\\fs68}"
            )
        else:
            out.append(ass_escape(word))
    return " ".join(out)


def write_animated_ass(srt_path: Path, ass_path: Path, duration_ms: int) -> dict[str, Any]:
    cues = parse_srt(srt_path)
    if not cues:
        raise RuntimeError("TTS produced no usable subtitle cues.")

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, TertiaryColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, AlphaLevel",
        "Style: Caption,Noto Sans Devanagari,68,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H78000000,-1,0,1,5,2,5,50,50,50,0",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    event_count = 0
    for cue in cues:
        for start_ms, end_ms, chunk in split_cue(cue):
            start = ms_to_ass_time(start_ms)
            end = ms_to_ass_time(min(end_ms, duration_ms))
            if end_ms - start_ms < 120:
                continue
            text = styled_chunk(chunk)
            event = (
                f"Dialogue: 0,{start},{end},Caption,,0,0,0,,"
                f"{{\\an5\\move(540,1605,540,1485)\\fad(55,90)"
                f"\\fscx82\\fscy82\\t(0,110,\\fscx108\\fscy108)"
                f"\\t(110,210,\\fscx100\\fscy100)}}{text}"
            )
            lines.append(event)
            event_count += 1

    ass_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "caption_events": event_count,
        "caption_style": "animated-pop-lower-middle",
        "chunking": "1-3 words",
        "highlight_color": "gold",
    }


def generate_tts(text: str, caption_text: str, audio_path: Path, subtitle_path: Path) -> dict[str, Any]:
    meta = generate_indicvoice_tts(
        text=text,
        audio_path=audio_path,
        caption_text=caption_text,
        subtitle_path=subtitle_path,
    )
    meta["audio_path"] = str(audio_path.with_suffix(".mp3"))
    return meta


def find_scene_segments(path: Path) -> list[dict[str, float]]:
    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=28.0, min_scene_len=18))
    manager.detect_scenes(video, show_progress=False)

    scenes: list[dict[str, float]] = []
    for start, end in manager.get_scene_list(start_in_scene=True):
        a = start.get_seconds()
        b = end.get_seconds()
        if b - a >= 1.2:
            scenes.append({
                "start": round(a, 3),
                "end": round(b, 3),
                "duration": round(b - a, 3),
            })
    if scenes:
        return scenes

    return [{
        "start": 0.0,
        "end": ffprobe_duration(path),
        "duration": ffprobe_duration(path),
    }]


def build_gameplay_track(
    gameplay_files: list[Path],
    duration: float,
    destination: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    """Build the montage only from detected scene boundaries.

    This deliberately avoids cutting at arbitrary timestamps. Each selected
    unit is a complete detected scene, so an action is much less likely to be
    chopped in the middle.
    """
    target = max(2.5, min(6.5, duration / 6.0))
    candidates: list[dict[str, Any]] = []

    for path in gameplay_files:
        for scene in find_scene_segments(path):
            candidates.append({"path": path, **scene})

    if not candidates:
        raise RuntimeError("Scene detection produced no usable gameplay segments.")

    selected: list[dict[str, Any]] = []
    remaining = duration
    last_file: Path | None = None

    while remaining >= 1.2 and len(selected) < 8:
        available = [
            item
            for item in candidates
            if item not in selected
            and item["duration"] <= remaining + 0.10
        ]
        if not available:
            break

        def score(item: dict[str, Any]) -> float:
            same_file_penalty = 1.5 if last_file == item["path"] else 0.0
            return abs(float(item["duration"]) - target) + same_file_penalty

        chosen = min(available, key=score)
        selected.append(chosen)
        remaining -= float(chosen["duration"])
        last_file = chosen["path"]

    if not selected:
        chosen = dict(min(candidates, key=lambda item: abs(float(item["duration"]) - target)))
        if float(chosen["duration"]) > duration:
            chosen["end"] = round(float(chosen["start"]) + duration, 3)
            chosen["duration"] = round(duration, 3)
        selected = [chosen]
        remaining = max(0.0, duration - float(chosen["duration"]))

    ffmpeg_args: list[str] = ["ffmpeg", "-y"]
    filters: list[str] = []

    for index, item in enumerate(selected):
        path = Path(item["path"])
        segment = float(item["duration"])
        ffmpeg_args += ["-ss", f"{item['start']:.3f}", "-t", f"{segment:.3f}", "-i", str(path)]
        filters.append(
            f"[{index}:v]fps=30,"
            f"scale=1160:2062:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:(iw-1080)/2:(ih-1920)/2,"
            f"eq=contrast=1.04:saturation=1.06,"
            f"setsar=1,trim=duration={segment:.3f},setpts=PTS-STARTPTS[v{index}]"
        )

        if has_audio(path):
            filters.append(
                f"[{index}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"atrim=duration={segment:.3f},asetpts=PTS-STARTPTS,volume=0.10[a{index}]"
            )
        else:
            filters.append(
                f"anullsrc=r=48000:cl=stereo:d={segment:.3f}[a{index}]"
            )

    count = len(selected)
    video_inputs = "".join(f"[v{i}]" for i in range(count))
    audio_inputs = "".join(f"[a{i}]" for i in range(count))
    filters.append(f"{video_inputs}concat=n={count}:v=1:a=0[vg]")
    filters.append(f"{audio_inputs}concat=n={count}:v=0:a=1[ag]")

    total = sum(float(item["duration"]) for item in selected)
    if total < duration - 0.05:
        filters.append(
            f"[vg]tpad=stop_mode=clone:stop_duration={duration - total:.3f}[gameplay]"
        )
    else:
        filters.append("[vg]null[gameplay]")

    ffmpeg_args += [
        "-filter_complex", ";".join(filters),
        "-map", "[gameplay]",
        "-map", "[ag]",
        "-t", f"{duration:.3f}",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "96k",
        "-ar", "48000",
        "-ac", "2",
        str(destination),
    ]

    run(ffmpeg_args, label="Build scene-safe vertical gameplay montage")

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce the gameplay track.")

    return [Path(item["path"]) for item in selected], selected


def find_primary_music() -> Path | None:
    files = find_music()
    return files[0] if files else None


def render_final_video(
    gameplay_track: Path,
    narration_audio: Path,
    animated_captions: Path,
    duration: float,
    destination: Path,
) -> dict[str, Any]:
    music = find_primary_music()
    filter_parts = [
        "[0:v]null[v]",
        "[0:a]volume=0.90[ga]",
        "[1:a]loudnorm=I=-15:TP=-1.5:LRA=8[narr]",
    ]

    mix_inputs = "[narr][ga]"
    input_count = 2
    if music is not None:
        filter_parts += [
            f"[2:a]volume=0.045,atrim=duration={duration:.3f}[bgm]"
        ]
        mix_inputs += "[bgm]"
        input_count = 3

    filter_parts += [
        f"{mix_inputs}amix=inputs={input_count}:duration=longest:dropout_transition=0,"
        "loudnorm=I=-14:TP=-1.5:LRA=10[aout]",
        f"[v]subtitles={animated_captions.resolve()}:si=0[vout]",
    ]

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(gameplay_track),
        "-i",
        str(narration_audio),
    ]
    if music is not None:
        command += ["-stream_loop", "-1", "-i", str(music)]

    command += [
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(destination),
    ]

    run(command, label="Render creator-style 9:16 Short with animated captions")

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce the final Short.")

    return {
        "music": str(music) if music else None,
        "caption_track": str(animated_captions),
        "mix": "narration + low-volume gameplay audio" + (" + optional background music" if music else ""),
    }


def render_short(script: dict[str, Any]) -> dict[str, Any]:
    require_tools()

    narration = str(script.get("narration") or "").strip()
    hook = str(script.get("hook") or "").strip()
    tts_text = str(script.get("tts_text") or "").strip()
    if not narration:
        raise RuntimeError("Generated script has no narration text.")
    if not tts_text:
        raise RuntimeError("Generated script has no Devanagari tts_text. Regenerate the script.")

    caption_text = f"{hook} {narration}".strip() if hook else narration
    spoken_text = tts_text

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    narration_wav = WORK_DIR / "narration.wav"
    narration_audio = WORK_DIR / "narration.mp3"
    narration_srt = WORK_DIR / "narration.srt"
    animated_ass = WORK_DIR / "captions.ass"
    gameplay_track = WORK_DIR / "gameplay_track.mp4"
    final_video = OUTPUT_DIR / "short_preview.mp4"

    tts_meta = generate_tts(
        spoken_text,
        caption_text,
        narration_wav,
        narration_srt,
    )
    if not narration_audio.exists():
        raise RuntimeError("IndicVoice did not produce the expected MP3 narration.")

    duration = ffprobe_duration(narration_audio)

    if duration > 52:
        raise RuntimeError(
            f"Narration is {duration:.1f}s long. Keep the creator-style Short at 52 seconds or less."
        )
    if duration < 10:
        raise RuntimeError(
            f"Narration is only {duration:.1f}s long. Generate a fuller script before rendering."
        )

    gameplay_files = find_gameplay()
    caption_meta = write_animated_ass(
        narration_srt,
        animated_ass,
        int(duration * 1000),
    )
    selected_paths, selected_segments = build_gameplay_track(
        gameplay_files,
        duration,
        gameplay_track,
    )
    # Normalize scene metadata immediately. Some Python path-like values can
    # otherwise leak into the final manifest and make json.dumps() fail.
    selected_segments = [
        {
            "path": str(item.get("path")),
            "start": float(item.get("start", 0.0)),
            "end": float(item.get("end", 0.0)),
            "duration": float(item.get("duration", 0.0)),
        }
        for item in selected_segments
    ]
    audio_meta = render_final_video(
        gameplay_track,
        narration_audio,
        animated_ass,
        duration,
        final_video,
    )

    output_audio = OUTPUT_DIR / "narration.mp3"
    output_srt = OUTPUT_DIR / "captions.srt"
    output_ass = OUTPUT_DIR / "captions.ass"
    shutil.copy2(narration_audio, output_audio)
    shutil.copy2(narration_srt, output_srt)
    shutil.copy2(animated_ass, output_ass)

    manifest = {
        "renderer": "ytautopilot-stage-4-free-local-tts-scene-safe",
        "video": str(final_video),
        "duration_seconds": round(duration, 3),
        "resolution": "1080x1920",
        "fps": 30,
        "voice": tts_meta.get("voice"),
        "tts_engine": tts_meta.get("engine"),
        "tts_model": tts_meta.get("model"),
        "spoken_text": spoken_text,
        "caption_text": caption_text,
        "source_gameplay": [str(path) for path in selected_paths],
        "selected_segments": selected_segments,
        "available_gameplay_files": [str(path) for path in gameplay_files],
        "editing": {
            **caption_meta,
            **audio_meta,
            "visual_beats": len(selected_segments),
            "fast_cut": True,
            "scene_safe": True,
            "caption_position": "lower-middle",
            "caption_behavior": "short phrase pop-ins synced to estimated speech timing",
        },
    }
    (OUTPUT_DIR / "render_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[render] Final video: {final_video}")
    print(f"[render] Duration: {duration:.1f}s")
    print(f"[render] TTS: {tts_meta.get('engine')} / {tts_meta.get('voice')}")
    print(f"[render] Scene-safe segments: {len(selected_segments)}")
    return manifest


if __name__ == "__main__":
    pass
