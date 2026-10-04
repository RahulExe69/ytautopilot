from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any


def _split_tts_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।！？])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def estimate_srt(text: str, duration_seconds: float) -> str:
    """Create readable caption cues from the same text used for TTS.

    IndicVoice is offline and does not expose word timestamps through its public
    pipeline API, so we distribute sentence/phrase timing by character weight.
    The existing renderer then turns each cue into short 1-3 word pop-ins.
    """
    sentences = _split_tts_sentences(text)
    if not sentences:
        sentences = [text.strip()]

    weights = [max(1, len(re.sub(r"\s+", "", item))) for item in sentences]
    total = sum(weights)
    cursor = 0.0
    blocks: list[str] = []

    def stamp(value: float) -> str:
        total_ms = max(0, int(round(value * 1000)))
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        seconds = (total_ms % 60_000) // 1_000
        millis = total_ms % 1_000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    for index, (sentence, weight) in enumerate(zip(sentences, weights), start=1):
        if index == len(sentences):
            end = duration_seconds
        else:
            end = cursor + duration_seconds * (weight / total)
        end = max(end, cursor + 0.35)
        blocks.append(
            f"{index}\n"
            f"{stamp(cursor)} --> {stamp(min(end, duration_seconds))}\n"
            f"{sentence}\n"
        )
        cursor = end

    return "\n".join(blocks).strip() + "\n"


def _configure_system_espeak() -> None:
    """Prefer Ubuntu's system eSpeak-NG over the broken bundled loader wheel."""
    import shutil

    candidates = [
        Path("/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"),
        Path("/usr/lib/aarch64-linux-gnu/libespeak-ng.so.1"),
        Path("/usr/lib64/libespeak-ng.so.1"),
    ]
    library = next((path for path in candidates if path.is_file()), None)
    if library is None:
        resolved = shutil.which("espeak-ng")
        if resolved:
            # Keep the system binary available to phonemizer; the wrapper below
            # will still resolve its shared library through the configured path.
            library = Path("/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1")

    if library is None or not library.is_file():
        raise RuntimeError(
            "System eSpeak-NG library not found. Install libespeak-ng1/ espeak-ng."
        )

    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    data_candidates = [
        Path("/usr/lib/x86_64-linux-gnu/espeak-ng-data"),
        Path("/usr/lib/aarch64-linux-gnu/espeak-ng-data"),
        Path("/usr/lib/arm-linux-gnueabihf/espeak-ng-data"),
        Path("/usr/share/espeak-ng-data"),
    ]
    data_path = next((path for path in data_candidates if path.is_dir()), None)
    if data_path is None:
        raise RuntimeError(
            "System eSpeak-NG data directory not found. Install espeak-ng-data."
        )

    EspeakWrapper.set_library(str(library))
    if hasattr(EspeakWrapper, "set_data_path"):
        EspeakWrapper.set_data_path(str(data_path))

    os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(library)
    os.environ["ESPEAK_DATA_PATH"] = str(data_path)

def generate_indicvoice_tts(
    text: str,
    audio_path: Path,
    caption_text: str,
    subtitle_path: Path,
) -> dict[str, Any]:
    """Render Hindi/Indic speech locally with the Apache-2.0 IndicVoice model."""
    try:
        import numpy as np
        import soundfile as sf
        from indicvoice import IndicPipeline
        _configure_system_espeak()
    except ImportError as exc:
        raise RuntimeError(
            "IndicVoice dependencies are missing. Install requirements.txt before rendering."
        ) from exc

    voice = (os.getenv("INDICVOICE_VOICE") or "am_adam").strip()
    repo_id = (os.getenv("INDICVOICE_MODEL") or "Bindkushal/IndicVoice-82M").strip()
    sample_rate = 24_000

    print(f"[tts] Loading IndicVoice model: {repo_id} / voice={voice}")
    pipeline = IndicPipeline(lang_code="hi", repo_id=repo_id)

    chunks: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=voice):
        array = np.asarray(audio, dtype=np.float32)
        if array.ndim > 1:
            array = np.squeeze(array)
        chunks.append(array)
        # A tiny natural pause between generated chunks keeps the delivery from
        # sounding like one long synthetic block.
        chunks.append(np.zeros(int(sample_rate * 0.025), dtype=np.float32))

    if not chunks:
        raise RuntimeError("IndicVoice returned no audio chunks.")

    audio = np.concatenate(chunks).astype(np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(audio_path, audio, sample_rate)

    # FFmpeg is used only for consistent MP3 output in the workflow artifact.
    mp3_path = audio_path.with_suffix(".mp3")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "3",
            str(mp3_path),
        ],
        check=True,
    )
    if mp3_path != audio_path:
        audio_path.unlink(missing_ok=True)

    subtitle_path.write_text(
        estimate_srt(caption_text, _duration_seconds(mp3_path)),
        encoding="utf-8",
    )

    return {
        "engine": "indicvoice",
        "model": repo_id,
        "voice": voice,
        "sample_rate": sample_rate,
        "caption_timing": "estimated-from-text-duration",
        "audio_file": str(mp3_path),
    }


def _duration_seconds(path: Path) -> float:
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
    ).strip()
    return float(raw)
