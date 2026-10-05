# YTAutoPilot Performance

The workflow now has a dedicated fast path aimed at reducing wall-clock time on GitHub-hosted CPU runners while preserving the existing content, duplicate-protection, and private-upload safety gates.

## What was optimized

- GitHub Actions uses `checkout@v7`, `setup-python@v7`, `actions/cache@v6`, and `upload-artifact@v7`.
- A warm `.venv` is cached by the requirements hash so later runs can skip installing Torch and the full Python dependency tree.
- Pip and Hugging Face caches remain enabled.
- Hugging Face Xet parallel range downloads are raised to 32 for first-run model downloads.
- Expensive per-run IndicVoice dependency and voice-tensor validation steps were removed; the real TTS run is the runtime validation.
- Artifact compression is disabled for already-compressed media.
- Scene detection can skip every other source frame in fast mode and can process independent gameplay files in parallel.
- Crop detection is shortened and parallelized for selected source files.
- The renderer selects scenes once and feeds those source segments directly into the final FFmpeg graph.
- The old intermediate gameplay MP4 encode is bypassed on the main path, leaving one final video encode.
- Fast rendering uses x264 `ultrafast`, a lighter audio filter chain, no `+faststart`, and a lower AAC bitrate.
- IndicVoice is called once for the complete prepared Hindi text in fast mode instead of one Python pipeline call per sentence.
- Gemini 3.x requests use `thinkingLevel=minimal`; Gemini 2.5 requests use `thinkingBudget=0`.
- Gameplay duration probes are reused between target calculation and rendering.

## Speed / quality trade-offs

Fast mode is intentionally a speed-first profile. It trades some compression efficiency and audio-processing precision for lower CPU time. Scene detection uses frame skipping, so the selected cut points can be less frame-accurate on lower-FPS footage. The non-fast renderer remains available through the code path when `YTAP_FAST_MODE` is disabled.

## Measuring the result

Use a GitHub Actions **prepare** run before and after changing the fast-path settings. Compare the total job duration and the time spent in:
1. dependency/setup,
2. Gemini generation,
3. IndicVoice,
4. scene detection/selection,
5. final FFmpeg encode,
6. artifact upload.

The first run after a cache miss will still be slower because the Python environment and Hugging Face model files have to be downloaded. Warm runs are the meaningful benchmark for the daily scheduled workflow.
