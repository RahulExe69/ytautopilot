from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any


_DEVANAGARI_PRONUNCIATIONS = (
    # Multi-word Free Fire terms first; replacements are case-insensitive and
    # token-boundary-aware in _prepare_hindi_tts_text.
    ("battle royale", "बैटल रॉयल"),
    ("free fire max", "फ्री फायर मैक्स"),
    ("training ground", "ट्रेनिंग ग्राउंड"),
    ("clash squad", "क्लैश स्क्वाड"),
    ("rank push", "रैंक पुश"),
    ("one tap", "वन टैप"),
    ("one-tap", "वन टैप"),
    ("drag shot", "ड्रैग शॉट"),
    ("drag headshot", "ड्रैग हेडशॉट"),
    ("head level", "हेड लेवल"),
    ("red dot", "रेड डॉट"),
    ("2x scope", "टू एक्स स्कोप"),
    ("4x scope", "फोर एक्स स्कोप"),
    ("free look", "फ्री लुक"),
    ("aim assist", "एम असिस्ट"),
    ("med kit", "मेडकिट"),
    ("medkit", "मेडकिट"),
    ("gloo wall", "ग्लू वॉल"),
    ("free fire", "फ्री फायर"),
    ("crosshair", "क्रॉसहेयर"),
    ("cross-hair", "क्रॉस हेयर"),
    ("cross hair", "क्रॉस हेयर"),
    ("headshot", "हेडशॉट"),
    ("head shot", "हेडशॉट"),
    ("sensitivity", "सेंसिटिविटी"),
    ("bermuda", "बरमूडा"),
    ("kalahari", "कलाहारी"),
    ("purgatory", "पर्गेटरी"),
    ("booyah", "बूयाह"),
    ("m1887", "एम अठारह अट्ठासी"),
    ("mp40", "एम पी चालीस"),
    ("ak47", "ए के सैंतालीस"),
    ("awm", "ए डब्ल्यू एम"),
    ("smg", "एस एम जी"),
    ("hp", "एच पी"),
    ("hud", "एच यू डी"),
    ("fps", "एफ पी एस"),
    ("loot", "लूट"),
    ("lobby", "लॉबी"),
    ("grenade", "ग्रेनेड"),
    ("revive", "रिवाइव"),
    ("backpack", "बैकपैक"),
    ("armor", "आर्मर"),
    ("armour", "आर्मर"),
    ("vest", "वेस्ट"),
    ("booyah", "बूयाह"),
    ("headshot", "हेडशॉट"),
    ("crosshair", "क्रॉसहेयर"),
    ("cross-hair", "क्रॉस हेयर"),
    ("cross hair", "क्रॉस हेयर"),
    ("shotgun", "शॉटगन"),
    ("sniper", "स्नाइपर"),
    ("scope", "स्कोप"),
    ("enemy", "एनिमी"),
    ("gameplay", "गेमप्ले"),
    ("ranked", "रैंक्ड"),
    ("movement", "मूवमेंट"),
    ("damage", "डैमेज"),
    ("reload", "रीलोड"),
    ("clutch", "क्लच"),
    ("weapon", "वेपन"),
    ("weapons", "वेपन्स"),
    ("ability", "एबिलिटी"),
    ("abilities", "एबिलिटीज"),
    ("solo", "सोलो"),
    ("squad", "स्क्वाड"),
    ("smg", "एसएमजी"),
    ("awm", "एडब्ल्यूएम"),
    ("push", "पुश"),
    ("rush", "रश"),
    ("heal", "हील"),
    ("cover", "कवर"),
    ("fight", "फाइट"),
    ("peek", "पीक"),
    ("rotate", "रोटेट"),
    ("rotation", "रोटेशन"),
    ("zone", "ज़ोन"),
    ("close range", "क्लोज़ रेंज"),
    ("long range", "लॉन्ग रेंज"),
    ("body shot", "बॉडी शॉट"),
    ("knock", "नॉक"),
    ("loot", "लूट"),
    ("loadout", "लोडआउट"),
    ("aim", "एम"),
    ("recoil", "रिकॉइल"),
    ("tumhara", "तुम्हारा"),
    ("tumhe", "तुम्हें"),
    ("tumne", "तुमने"),
    ("tumko", "तुमको"),
    ("tum", "तुम"),
    ("toh", "तो"),
    ("yeh", "ये"),
    ("ye", "ये"),
    ("woh", "वो"),
    ("kya", "क्या"),
    ("kyun", "क्यों"),
    ("kaise", "कैसे"),
    ("kaafi", "काफी"),
    ("sirf", "सिर्फ"),
    ("thoda", "थोड़ा"),
    ("pehle", "पहले"),
    ("phir", "फिर"),
    ("abhi", "अभी"),
    ("agar", "अगर"),
    ("lekin", "लेकिन"),
    ("aur", "और"),
    ("ek", "एक"),
    ("do", "दो"),
    ("teen", "तीन"),
    ("wala", "वाला"),
    ("wali", "वाली"),
    ("wale", "वाले"),
    ("karna", "करना"),
    ("karo", "करो"),
    ("karte", "करते"),
    ("kar", "कर"),
    ("hai", "है"),
    ("hain", "हैं"),
    ("hoga", "होगा"),
    ("hogi", "होगी"),
    ("hota", "होता"),
    ("nahi", "नहीं"),
    ("nahin", "नहीं"),
    ("mat", "मत"),
    ("matlab", "मतलब"),
    ("bas", "बस"),
    ("bhi", "भी"),
    ("bahut", "बहुत"),
    ("zyada", "ज़्यादा"),
    ("sahi", "सही"),
    ("galat", "गलत"),
    ("sakta", "सकता"),
    ("sakti", "सकती"),
    ("chahiye", "चाहिए"),
    ("dekho", "देखो"),
    ("sun", "सुन"),
    ("waise", "वैसे"),
    ("apna", "अपना"),
    ("apni", "अपनी"),
    ("apne", "अपने"),
    ("liye", "लिए"),
    ("mein", "में"),
    ("me", "में"),
    ("se", "से"),
    ("par", "पर"),
    ("pe", "पे"),
    ("ko", "को"),
    ("jo", "जो"),
    ("jab", "जब"),
    ("tab", "तब"),
    ("har", "हर"),
    ("koi", "कोई"),
    ("kuch", "कुछ"),
    ("accha", "अच्छा"),
    ("acha", "अच्छा"),
    ("best", "बेस्ट"),
    ("better", "बेटर"),
    ("easy", "ईज़ी"),
    ("simple", "सिंपल"),
    ("basic", "बेसिक"),
    ("timing", "टाइमिंग"),
    ("time", "टाइम"),
    ("trick", "ट्रिक"),
    ("tip", "टिप"),
    ("tips", "टिप्स"),
    ("comment", "कमेंट"),
    ("comments", "कमेंट्स"),
    ("favorite", "फेवरेट"),
    ("favourite", "फेवरेट"),
    ("try", "ट्राय"),
    ("test", "टेस्ट"),
    ("tested", "टेस्टेड"),
    ("notice", "नोटिस"),
    ("actually", "एक्चुअली"),
    ("really", "रियली"),
    ("quick", "क्विक"),
    ("quickly", "क्विकली"),
    ("because", "बिकॉज़"),
    ("before", "बिफोर"),
    ("after", "आफ्टर"),
    ("again", "अगेन"),
    ("always", "ऑलवेज़"),
    ("never", "नेवर"),
    ("inside", "इनसाइड"),
    ("outside", "आउटसाइड"),
    ("front", "फ्रंट"),
    ("back", "बैक"),
    ("start", "स्टार्ट"),
    ("stop", "स्टॉप"),
)

def _prepare_hindi_tts_text(text: str) -> str:
    prepared = text.strip()
    for source, replacement in sorted(_DEVANAGARI_PRONUNCIATIONS, key=lambda item: len(item[0]), reverse=True):
        prepared = re.sub(
            rf"(?<![A-Za-z]){re.escape(source)}(?![A-Za-z])",
            replacement,
            prepared,
            flags=re.IGNORECASE,
        )
    return re.sub(r"\s+", " ", prepared).strip()


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



def write_srt_from_sentence_timings(
    caption_text: str,
    sentence_durations: list[float],
    pause_seconds: float,
    duration_seconds: float,
    speech_speed: float = 1.0,
) -> str:
    """Build captions from measured sentence timings so text cannot drift past the voice."""
    caption_sentences = _split_tts_sentences(caption_text)
    if not caption_sentences:
        caption_sentences = [caption_text.strip()]
    if not sentence_durations:
        raise RuntimeError("Measured sentence timing is empty.")
    if speech_speed <= 0:
        raise RuntimeError("Speech speed must be positive.")

    def stamp(value: float) -> str:
        total_ms = max(0, int(round(value * 1000)))
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        seconds = (total_ms % 60_000) // 1_000
        millis = total_ms % 1_000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    # sentence_durations are measured before the final atempo pass, while the
    # rendered MP3 is shorter by speech_speed. Scale both speech and pauses so
    # caption boundaries follow the actual encoded narration.
    scaled_durations = [max(0.05, float(value) / speech_speed) for value in sentence_durations]
    scaled_pause = max(0.0, float(pause_seconds) / speech_speed)
    measured_total = sum(scaled_durations) + scaled_pause * max(0, len(scaled_durations) - 1)
    if measured_total <= 0:
        raise RuntimeError("Measured sentence timing is empty.")

    # Gemini is asked to keep tts_text semantically identical to hook+narration,
    # so matching sentence counts let us use the real per-sentence timings.
    # If punctuation differs and counts do not match, use a conservative fallback.
    if len(caption_sentences) == len(scaled_durations):
        timings: list[float] = []
        cursor = 0.0
        for index, sentence_duration in enumerate(scaled_durations):
            end = cursor + sentence_duration
            if index < len(scaled_durations) - 1:
                end += scaled_pause
            timings.append(end)
            cursor = end
    else:
        total = min(duration_seconds, measured_total)
        weights = [max(1, len(re.sub(r"\s+", "", sentence))) for sentence in caption_sentences]
        total_weight = sum(weights)
        timings = []
        cursor = 0.0
        for index, weight in enumerate(weights):
            end = total if index == len(weights) - 1 else cursor + total * (weight / total_weight)
            timings.append(max(cursor + 0.05, min(total, end)))
            cursor = timings[-1]

    blocks: list[str] = []
    cursor = 0.0
    for index, sentence in enumerate(caption_sentences, start=1):
        end = min(duration_seconds, timings[index - 1])
        if index == len(caption_sentences):
            end = min(duration_seconds, max(cursor + 0.05, measured_total))
        if end <= cursor:
            end = min(duration_seconds, cursor + 0.20)
        blocks.append(
            f"{index}\n"
            f"{stamp(cursor)} --> {stamp(end)}\n"
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
        import torch
        from huggingface_hub import hf_hub_download
        from indicvoice import IndicPipeline
        _configure_system_espeak()

        # IndicVoice's current HF repo has a packaging regression in its
        # standard Kokoro voice files: several were re-uploaded as 131-byte
        # Git-LFS pointer text instead of real voice tensors. The last known
        # good IndicVoice revision (b000ade...) still points to the original
        # ~523 KB voice objects. Public Kokoro integrations use the same
        # voice tensors from hexgrad/Kokoro-82M, so keep a second fallback.
        voice_legacy_revision = (
            os.getenv("INDICVOICE_VOICE_REVISION")
            or "b000adea5df849c41d49d8aac3aa50f9bc736afa"
        )
        voice_source_repo = (
            os.getenv("INDICVOICE_VOICE_REPO")
            or os.getenv("INDICVOICE_MODEL")
            or "Bindkushal/IndicVoice-82M"
        ).strip()
        voice_fallback_repo = (
            os.getenv("INDICVOICE_VOICE_FALLBACK_REPO")
            or "hexgrad/Kokoro-82M"
        ).strip()

        def _is_pointer_file(path: str | Path) -> bool:
            candidate = Path(path)
            try:
                size = candidate.stat().st_size
                if size >= 4096:
                    return False
                head = candidate.read_bytes()[:512]
            except OSError:
                return False
            return (
                b"version https://git-lfs.github.com/spec/v1" in head
                or b"oid sha256:" in head
            )

        def _download_voice(voice_name: str) -> str:
            filename = f"voices/{voice_name}.pt"
            candidates: list[tuple[str, str | None]] = [
                (voice_source_repo, None),
                (voice_source_repo, voice_legacy_revision),
                (voice_fallback_repo, None),
            ]
            seen: set[tuple[str, str | None]] = set()
            errors: list[str] = []

            for candidate_repo, revision in candidates:
                key = (candidate_repo, revision)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    kwargs = {
                        "repo_id": candidate_repo,
                        "filename": filename,
                    }
                    if revision:
                        kwargs["revision"] = revision
                    voice_file = hf_hub_download(**kwargs)
                    if _is_pointer_file(voice_file):
                        errors.append(
                            f"{candidate_repo}@{revision or 'main'} returned a Git-LFS/Xet pointer "
                            f"for {filename}"
                        )
                        continue
                    size = Path(voice_file).stat().st_size
                    if size < 100_000:
                        errors.append(
                            f"{candidate_repo}@{revision or 'main'} returned an unexpectedly small "
                            f"voice file ({size} bytes)"
                        )
                        continue
                    print(
                        f"[tts] Voice pack source: {candidate_repo}@{revision or 'main'} "
                        f"({size} bytes)"
                    )
                    return voice_file
                except Exception as exc:
                    errors.append(f"{candidate_repo}@{revision or 'main'}: {exc}")

            detail = " | ".join(errors[-3:])
            raise RuntimeError(
                f"Could not obtain a real IndicVoice voice tensor for '{voice_name}'. "
                f"Tried the current model repo, the last known-good IndicVoice revision, "
                f"and the upstream Kokoro voice repo. {detail}"
            )

        def _load_voice_compat(self, voice):
            if voice in self.voices:
                return self.voices[voice]

            if voice.endswith(".pt"):
                voice_file = voice
            else:
                voice_file = _download_voice(voice)

            try:
                pack = torch.load(
                    voice_file,
                    map_location="cpu",
                    weights_only=True,
                )
            except Exception as exc:
                if "Weights only load failed" not in str(exc) and "WeightsUnpickler" not in str(exc):
                    raise
                print(
                    "[tts] Voice tensor uses a legacy pickle format; loading the "
                    "already-validated public checkpoint with weights_only=False."
                )
                pack = torch.load(
                    voice_file,
                    map_location="cpu",
                    weights_only=False,
                )

            if not isinstance(pack, torch.Tensor):
                raise RuntimeError(
                    f"IndicVoice voice pack '{voice}' did not contain a torch.Tensor "
                    f"(got {type(pack).__name__})."
                )

            self.voices[voice] = pack
            return pack

        # Compatibility shim for the current upstream IndicVoice release.
        IndicPipeline.load_single_voice = _load_voice_compat
    except ImportError as exc:
        raise RuntimeError(
            "IndicVoice dependencies are missing. Install requirements.txt before rendering."
        ) from exc

    # Fixed narrator: hf_beta is the requested female voice. Do not silently
    # switch to a different voice if this preset fails to load.
    voice_candidates = ["hf_beta"]

    repo_id = (os.getenv("INDICVOICE_MODEL") or "Bindkushal/IndicVoice-82M").strip()
    sample_rate = 24_000

    # Warm, CPU-only GitHub runners benefit from explicit thread sizing. Avoid
    # over-subscribing Torch/OpenMP when FFmpeg is also using the host CPUs.
    try:
        requested_threads = int(os.getenv("TORCH_NUM_THREADS", "0"))
    except ValueError:
        requested_threads = 0
    if requested_threads <= 0:
        requested_threads = max(1, int(os.cpu_count() or 2))
    try:
        torch.set_num_threads(requested_threads)
    except RuntimeError:
        pass
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    fast_mode = os.getenv("YTAP_FAST_MODE", "").lower() in {"1", "true", "yes", "on"}
    prepared_text = _prepare_hindi_tts_text(text)
    print(f"[tts] Hindi TTS input: {prepared_text}")

    pipeline = IndicPipeline(lang_code="hi", repo_id=repo_id)
    spoken_sentences = _split_tts_sentences(prepared_text)
    if not spoken_sentences:
        spoken_sentences = [prepared_text]

    # IndicVoice already chunks Hindi internally into manageable pieces and
    # reuses the loaded model/voice. Calling the pipeline once avoids repeated
    # G2P setup and Python-loop overhead for every sentence on the fast path.
    pause_seconds = 0.025
    chunks: list[np.ndarray] = []
    sentence_durations: list[float] = []
    voice = None
    voice_errors: list[str] = []

    for candidate_voice in voice_candidates:
        try:
            print(f"[tts] Trying Hindi voice: {candidate_voice}")
            candidate_chunks: list[np.ndarray] = []
            candidate_sentence_durations: list[float] = []

            if fast_mode:
                for result in pipeline(prepared_text, voice=candidate_voice):
                    audio = result.audio
                    if audio is None:
                        continue
                    if hasattr(audio, "detach"):
                        audio = audio.detach().cpu().numpy()
                    array = np.asarray(audio, dtype=np.float32).squeeze()
                    if array.size:
                        candidate_chunks.append(array)
                if not candidate_chunks:
                    raise RuntimeError("IndicVoice returned no audio.")
            else:
                for index, spoken_sentence in enumerate(spoken_sentences):
                    sentence_arrays: list[np.ndarray] = []
                    for _, _, audio in pipeline(spoken_sentence, voice=candidate_voice):
                        if hasattr(audio, "detach"):
                            audio = audio.detach().cpu().numpy()
                        array = np.asarray(audio, dtype=np.float32)
                        if array.ndim > 1:
                            array = np.squeeze(array)
                        sentence_arrays.append(array)

                    if not sentence_arrays:
                        raise RuntimeError(
                            f"IndicVoice returned no audio for sentence {index + 1}."
                        )

                    sentence_audio = np.concatenate(sentence_arrays).astype(np.float32)
                    candidate_chunks.append(sentence_audio)
                    candidate_sentence_durations.append(
                        float(len(sentence_audio)) / float(sample_rate)
                    )

                    if index < len(spoken_sentences) - 1:
                        candidate_chunks.append(
                            np.zeros(int(sample_rate * pause_seconds), dtype=np.float32)
                        )
                    )

            chunks = candidate_chunks
            sentence_durations = candidate_sentence_durations
            voice = candidate_voice
            break
        except Exception as exc:
            voice_errors.append(f"{candidate_voice}: {exc}")
            print(f"[tts] Voice {candidate_voice} failed; trying next voice.")

    if not chunks or voice is None:
        raise RuntimeError(
            "The fixed hf_beta female voice did not produce audio. "
            + " | ".join(voice_errors[-4:])
        )

    audio = np.concatenate(chunks).astype(np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(audio_path, audio, sample_rate)

    # FFmpeg is used only for consistent MP3 output in the workflow artifact.
    mp3_path = audio_path.with_suffix(".mp3")
    try:
        speech_speed = float(os.getenv("INDICVOICE_SPEED", "1.28"))
    except ValueError:
        speech_speed = 1.28
    speech_speed = min(1.35, max(0.90, speech_speed))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-filter:a",
            f"atempo={speech_speed:.3f}",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "3",
            str(mp3_path),
        ],
        check=True,
    )
    print(f"[tts] Speech speed: {speech_speed:.2f}x")
    if mp3_path != audio_path:
        audio_path.unlink(missing_ok=True)
    encoded_duration = _duration_seconds(mp3_path)
    if fast_mode:
        subtitle_text = estimate_srt(caption_text, encoded_duration)
    else:
        subtitle_text = write_srt_from_sentence_timings(
            caption_text=caption_text,
            sentence_durations=sentence_durations,
            pause_seconds=pause_seconds,
            duration_seconds=encoded_duration,
            speech_speed=speech_speed,
        )
    subtitle_path.write_text(subtitle_text, encoding="utf-8")

    return {
        "engine": "indicvoice",
        "model": str(repo_id),
        "voice": str(voice),
        "tts_input": prepared_text,
        "sample_rate": int(sample_rate),
        "caption_timing": "estimated-audio-duration" if fast_mode else "real-audio-duration-based",
        "speech_speed": speech_speed,
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
