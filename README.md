# ytautopilot

Copyright (c) 2026 RahulExe69. All rights reserved.

This repository and its source code are proprietary. No permission is granted to copy, modify, distribute, sublicense, publish, sell, or create derivative works from this code without prior written permission from the copyright holder.

## Project status

**Stage 1 starter is in place.** The current workflow supports a manual dry-run and Hindi gaming script generation. Video rendering and YouTube publishing are not implemented yet, and no uploads happen automatically.

## Planned pipeline

1. Generate an original Hindi/Hinglish gaming script with Gemini.
2. Use self-recorded or explicitly licensed gameplay footage, with permission/provenance recorded.
3. Create Hindi narration, captions, and a vertical 9:16 Short with FFmpeg.
4. Review the rendered file before enabling uploads.
5. Upload through the official YouTube Data API with OAuth, then record upload IDs and basic metrics.

## First setup

1. Open **Settings → Secrets and variables → Actions**.
2. Add a repository secret named `GEMINI_API_KEY` using your own Gemini API key. Never place API keys in source files or commit them.
3. Optionally add a repository variable named `GEMINI_MODEL` with value `gemini-3.5-flash-lite`. If omitted, the code uses that default.
4. Open **Actions → ytautopilot → Run workflow**.
5. Choose `dry-run` and run it. This uses a sample script if the Gemini key is not configured, and does not publish anything.
6. Download the workflow artifact to inspect `script.json`.

## Safety defaults

- The workflow runs only when manually triggered; no schedule is enabled yet.
- Publishing is disabled unless explicitly enabled later.
- Never commit OAuth client files, refresh tokens, API keys, or generated media.
- Do not scrape or reuse a creator's footage based only on an assumption. Verify the creator's actual reuse terms and retain evidence, or use your own gameplay.
- Review facts, narration, captions, audio, and rights before publishing.
- YouTube API projects in the unverified state may be restricted from making uploaded videos public; we will verify this during OAuth setup.

## Local dry-run

Requires Python 3.11+.

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m ytautopilot --mode dry-run
```

The generated file is written to `output/script.json`.

## License

All rights reserved. This is not an open-source license. Viewing the public repository does not grant permission to reuse the code.
