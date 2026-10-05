from __future__ import annotations

import hashlib
import random
import json
import os
import re
import shlex
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scenedetect import ContentDetector, SceneManager, open_video
from .tts import generate_indicvoice_tts
from .media import media_usage_counts, recent_media_sources


ROOT = Path.cwd()
GAMEPLAY_DIR = ROOT / "assets" / "gameplay"
MUSIC_DIR = ROOT / "assets" / "music"
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work" / "render"
FINAL_TAIL_SECONDS = 1.0

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}

def fast_mode() -> bool:
    return os.getenv("YTAP_FAST_MODE", "").lower() in {"1", "true", "yes", "on"}

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
    try:
        frame_skip = int(os.getenv("SCENE_FRAME_SKIP", "1" if fast_mode() else "0"))
    except ValueError:
        frame_skip = 1 if fast_mode() else 0
    frame_skip = max(0, min(2, frame_skip))
    manager.detect_scenes(video, show_progress=False, frame_skip=frame_skip)

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


def detect_active_picture_crop(path: Path) -> str | None:
    """Detect embedded black letterboxing and return a conservative FFmpeg crop.

    The crop is only accepted when it preserves almost all horizontal content
    and removes clear top/bottom bars. This avoids aggressive auto-crops that
    could cut the game HUD or character.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-ss", "0.5", "-i", str(path),
                "-vf", "cropdetect=limit=24:round=2:reset=0",
                "-frames:v", str(max(12, min(180, int(os.getenv("CROPDETECT_FRAMES", "48" if fast_mode() else "180"))))),
                "-an", "-f", "null", "-",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    matches = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", result.stderr)
    if not matches:
        return None
    width, height, x, y = map(int, matches[-1])
    try:
        probe = json.loads(command_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", str(path),
        ]))
        stream = probe["streams"][0]
        source_w, source_h = int(stream["width"]), int(stream["height"])
    except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None

    if not source_w or not source_h:
        return None
    # Only remove obvious letterboxing: preserve >= 94% of width and >= 72%
    # of height, and require meaningful vertical bars to avoid tiny crop noise.
    if width < source_w * 0.94 or height < source_h * 0.60:
        return None
    if height >= source_h * 0.97 or (y < 8 and source_h - (y + height) < 8):
        return None
    if x < 0 or y < 0 or x + width > source_w or y + height > source_h:
        return None
    print(f"[render] Detected embedded letterboxing in {path.name}: crop={width}:{height}:{x}:{y}")
    return f"{width}:{height}:{x}:{y}"


def select_gameplay_segments(
    gameplay_files: list[Path],
    duration: float,
) -> tuple[list[Path], list[dict[str, Any]]]:
    """Select complete detected scenes without encoding an intermediate video."""
    target_scene_count = max(6, min(len(gameplay_files), 10))
    target = max(2.2, min(5.5, duration / target_scene_count))
    max_scene_count = min(max(8, len(gameplay_files) * 2), 16)

    try:
        worker_count = int(os.getenv("SCENE_WORKERS", "2" if fast_mode() else "1"))
    except ValueError:
        worker_count = 2 if fast_mode() else 1
    worker_count = max(1, min(len(gameplay_files), worker_count))
    if worker_count > 1:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            scene_lists = list(executor.map(find_scene_segments, gameplay_files))
    else:
        scene_lists = [find_scene_segments(path) for path in gameplay_files]

    candidates: list[dict[str, Any]] = []
    for path, scenes in zip(gameplay_files, scene_lists):
        for scene in scenes:
            candidates.append({"path": path, **scene})
    if not candidates:
        raise RuntimeError("Scene detection produced no usable gameplay segments.")

    selected: list[dict[str, Any]] = []
    remaining = duration
    last_file: Path | None = None
    source_use_count: dict[Path, int] = {}
    rng = random.SystemRandom()
    usage_counts = media_usage_counts()
    recent_sources = recent_media_sources()

    while remaining >= 1.2 and len(selected) < max_scene_count:
        available = [
            item for item in candidates
            if item not in selected and item["duration"] <= remaining + 0.10
        ]
        if not available:
            break

        non_recent = [item for item in available if str(item["path"]) not in recent_sources]
        if len(non_recent) >= max(2, min(4, len(available))):
            available = non_recent

        def score(item: dict[str, Any]) -> float:
            source_path = Path(item["path"])
            use_count = source_use_count.get(source_path, 0)
            historical_penalty = 2.5 * usage_counts.get(str(source_path), 0)
            same_file_penalty = 4.0 if last_file == source_path else 0.0
            diversity_penalty = 5.0 * use_count
            return (
                abs(float(item["duration"]) - target)
                + same_file_penalty
                + diversity_penalty
                + historical_penalty
                + rng.random() * 0.75
            )

        ranked = sorted(available, key=score)
        chosen = rng.choice(ranked[: min(5, len(ranked))])
        selected.append(chosen)
        remaining -= float(chosen["duration"])
        last_file = Path(chosen["path"])
        chosen_path = Path(chosen["path"])
        source_use_count[chosen_path] = source_use_count.get(chosen_path, 0) + 1

    if not selected:
        raise RuntimeError("No gameplay scenes were selected.")
    return [Path(item["path"]) for item in selected], selected


def _crop_cache_for_segments(selected_segments: list[dict[str, Any]]) -> dict[Path, str | None]:
    paths = list(dict.fromkeys(Path(item["path"]) for item in selected_segments))
    if not paths:
        return {}
    workers = 2 if fast_mode() else 1
    workers = max(1, min(len(paths), workers))
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            crops = list(executor.map(detect_active_picture_crop, paths))
        return dict(zip(paths, crops))
    return {path: detect_active_picture_crop(path) for path in paths}


def build_gameplay_track(
    gameplay_files: list[Path],
    duration: float,
    destination: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    """Compatibility path for callers that still want a standalone montage."""
    selected_paths, selected = select_gameplay_segments(gameplay_files, duration)
    ffmpeg_args: list[str] = ["ffmpeg", "-y"]
    filters: list[str] = []
    crop_cache = _crop_cache_for_segments(selected)

    for index, item in enumerate(selected):
        path = Path(item["path"])
        segment = float(item["duration"])
        ffmpeg_args += ["-ss", str(item["start"]), "-t", str(segment), "-i", str(path)]
        active_crop = crop_cache.get(path)
        crop_filter = f"crop={active_crop}," if active_crop else ""
        filters.append(
            f"[{index}:v]{crop_filter}fps=30,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:(iw-1080)/2:(ih-1920)/2,"
            f"eq=contrast=1.04:saturation=1.06,setsar=1,"
            f"trim=duration={segment:.3f},setpts=PTS-STARTPTS[v{index}]"
        )

    count = len(selected)
    video_inputs = "".join(f"[v{i}]" for i in range(count))
    filters.append(f"{video_inputs}concat=n={count}:v=1:a=0[vg]")
    total = sum(float(item["duration"]) for item in selected)
    if total < duration - 0.05:
        filters.append(f"[vg]tpad=stop_mode=clone:stop_duration={duration - total:.3f}[gameplay]")
    else:
        filters.append("[vg]null[gameplay]")

    preset = os.getenv("FFMPEG_PRESET", "ultrafast" if fast_mode() else "veryfast")
    ffmpeg_args += [
        "-filter_complex", ";".join(filters),
        "-map", "[gameplay]",
        "-t", f"{duration:.3f}",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(destination),
    ]
    run(ffmpeg_args, label="Build scene-safe vertical gameplay montage")
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce the gameplay track.")
    return selected_paths, selected

def choose_background_music(seed: str) -> Path:
    files = find_music()
    if not files:
        raise RuntimeError(
            "No background music found in assets/music/. Add at least one supported audio file."
        )

    usage_counts = media_usage_counts()
    recent_sources = recent_media_sources()
    non_recent = [path for path in files if str(path) not in recent_sources]
    candidates = non_recent if non_recent else files
    weights = [1.0 / (1.0 + usage_counts.get(str(path), 0)) for path in candidates]
    chosen = random.SystemRandom().choices(candidates, weights=weights, k=1)[0]
    print(f"[render] Selected background music: {chosen.name}")
    return chosen


def render_final_video(
    selected_segments: list[dict[str, Any]],
    narration_audio: Path,
    animated_captions: Path,
    duration: float,
    destination: Path,
    music_seed: str,
) -> dict[str, Any]:
    """Render the final Short in one video encode instead of two."""
    tail_seconds = FINAL_TAIL_SECONDS
    final_duration = duration + tail_seconds
    music = choose_background_music(music_seed)
    crop_cache = _crop_cache_for_segments(selected_segments)

    command: list[str] = ["ffmpeg", "-y"]
    filters: list[str] = []
    for index, item in enumerate(selected_segments):
        path = Path(item["path"])
        segment = float(item["duration"])
        command += ["-ss", str(item["start"]), "-t", str(segment), "-i", str(path)]
        active_crop = crop_cache.get(path)
        crop_filter = f"crop={active_crop}," if active_crop else ""
        filters.append(
            f"[{index}:v]{crop_filter}fps=30,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:(iw-1080)/2:(ih-1920)/2,"
            f"eq=contrast=1.04:saturation=1.06,setsar=1,"
            f"trim=duration={segment:.3f},setpts=PTS-STARTPTS[v{index}]"
        )

    count = len(selected_segments)
    video_inputs = "".join(f"[v{i}]" for i in range(count))
    filters.append(f"{video_inputs}concat=n={count}:v=1:a=0[vg]")
    total = sum(float(item["duration"]) for item in selected_segments)
    if total < duration - 0.05:
        filters.append(f"[vg]tpad=stop_mode=clone:stop_duration={duration - total:.3f}[gameplay]")
    else:
        filters.append("[vg]null[gameplay]")

    narration_index = count
    music_index = count + 1
    command += ["-i", str(narration_audio), "-stream_loop", "-1", "-i", str(music)]

    if fast_mode():
        filters.extend([
            f"[gameplay]tpad=stop_mode=clone:stop_duration={tail_seconds:.3f},subtitles={animated_captions.resolve()}:si=0:force_style='Fade=0'[vout]",
            f"[{narration_index}:a]apad=pad_dur={tail_seconds:.3f},volume=1[narr]",
            f"[{music_index}:a]volume=0.055,atrim=duration={final_duration:.3f},afade=t=in:st=0:d=0.25,afade=t=out:st={max(0.0, final_duration-0.65):.3f}:d=0.65[bgm]",
            "[narr][bgm]amix=inputs=2:duration=longest:dropout_transition=0,alimiter=limit=0.97[aout]",
        ])
    else:
        filters.extend([
            f"[gameplay]tpad=stop_mode=clone:stop_duration={tail_seconds:.3f}[vpad]",
            f"[{music_index}:a]volume=0.055,atrim=duration={final_duration:.3f},afade=t=in:st=0:d=0.35,afade=t=out:st={max(0.0, final_duration-0.75):.3f}:d=0.75[bgm]",
            f"[{narration_index}:a]loudnorm=I=-15:TP=-1.5:LRA=8,apad=pad_dur={tail_seconds:.3f}[narr_tail]",
            "[narr_tail][bgm]amix=inputs=2:duration=longest:dropout_transition=0,loudnorm=I=-14:TP=-1.5:LRA=10[aout]",
            f"[vpad]subtitles={animated_captions.resolve()}:si=0:force_style='Fade=0'[vout]",
        ])

    preset = os.getenv("FFMPEG_PRESET", "ultrafast" if fast_mode() else "veryfast")
    command += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
        "-t", f"{final_duration:.3f}",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", "20" if fast_mode() else "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k" if fast_mode() else "160k",
    ]
    if not fast_mode():
        command += ["-movflags", "+faststart"]
    command += [str(destination)]

    run(command, label="Render creator-style 9:16 Short in one video encode")
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not produce the final Short.")

    return {
        "music": str(music) if music else None,
        "caption_track": str(animated_captions),
        "mix": "narration + selected background music; gameplay audio muted",
        "final_duration_seconds": round(final_duration, 3),
        "tail_seconds": round(tail_seconds, 3),
        "fast_mode": fast_mode(),
        "video_encode_passes": 1,
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

    gameplay_files = find_gameplay()
    try:
        available_gameplay_seconds = float(
            os.getenv("YTAP_AVAILABLE_GAMEPLAY_SECONDS", "0")
        )
    except ValueError:
        available_gameplay_seconds = 0.0
    if available_gameplay_seconds <= 0:
        available_gameplay_seconds = sum(ffprobe_duration(path) for path in gameplay_files)
    safe_gameplay_limit = max(0.0, available_gameplay_seconds - 0.5)
    if duration > safe_gameplay_limit:
        raise RuntimeError(
            f"Narration is {duration:.1f}s but the available gameplay totals "
            f"only {available_gameplay_seconds:.1f}s. Refusing to render a Short "
            "that outlasts its footage. Add more gameplay clips and rerun; the "
            "next script will automatically target the available footage length."
        )

    if duration > 52:
        raise RuntimeError(
            f"Narration is {duration:.1f}s long. Keep the creator-style Short at 52 seconds or less."
        )
    if duration < 10:
        raise RuntimeError(
            f"Narration is only {duration:.1f}s long. Generate a fuller script before rendering."
        )

    caption_meta = write_animated_ass(
        narration_srt,
        animated_ass,
        int(duration * 1000),
    )
    selected_paths, selected_segments = select_gameplay_segments(
        gameplay_files,
        duration,
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
        selected_segments,
        narration_audio,
        animated_ass,
        duration,
        final_video,
        music_seed=str(script.get("topic") or script.get("title") or "ytautopilot"),
    )

    output_audio = OUTPUT_DIR / "narration.mp3"
    output_srt = OUTPUT_DIR / "captions.srt"
    output_ass = OUTPUT_DIR / "captions.ass"
    shutil.copy2(narration_audio, output_audio)
    shutil.copy2(narration_srt, output_srt)
    shutil.copy2(animated_ass, output_ass)

    manifest = {
        "renderer": "ytautopilot-fast-path-local-tts-scene-safe",
        "video": str(final_video),
        "duration_seconds": float(audio_meta["final_duration_seconds"]),
        "resolution": "1080x1920",
        "fps": 30,
        "voice": tts_meta.get("voice"),
        "tts_engine": tts_meta.get("engine"),
        "tts_model": tts_meta.get("model"),
        "spoken_text": spoken_text,
        "narration_audio": str(output_audio),
        "caption_text": caption_text,
        "source_gameplay": [str(path) for path in selected_paths],
        "selected_segments": selected_segments,
        "available_gameplay_files": [str(path) for path in gameplay_files],
        "editing": {
            **caption_meta,
            **audio_meta,
            "visual_beats": len(selected_segments),
            "gameplay_file_count": len(gameplay_files),
            "unique_gameplay_files_used": len({str(item["path"]) for item in selected_segments}),
            "fast_cut": True,
            "scene_safe": True,
            "caption_position": "lower-middle",
            "caption_behavior": "short phrase pop-ins synced to audio-duration-based timing",
        },
    }
    (OUTPUT_DIR / "render_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[render] Final video: {final_video}")
    print(
        f"[render] Duration: {audio_meta['final_duration_seconds']:.1f}s "
        f"(includes {audio_meta['tail_seconds']:.1f}s smooth tail)"
    )
    print(f"[render] TTS: {tts_meta.get('engine')} / {tts_meta.get('voice')}")
    print(f"[render] Scene-safe segments: {len(selected_segments)}")
    return manifest


if __name__ == "__main__":
    pass
