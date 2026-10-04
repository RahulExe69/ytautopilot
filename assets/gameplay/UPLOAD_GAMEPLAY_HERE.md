# Gameplay assets — creator-style renderer

The Stage 3 creator-style renderer automatically discovers video files in this folder.

Use:
- Your own self-recorded gameplay, or footage you have explicit permission/license to reuse.
- `.mp4`, `.mov`, `.mkv`, or `.webm` files.
- Vertical 9:16 footage where possible. Landscape footage is center-cropped to 1080x1920 by the renderer.
- Several short clips for better visual variety. The creator-style renderer uses six fast visual beats and cycles through the available clips.

For the first test, one usable clip is enough.

The renderer does not upload these clips anywhere. It reads them during the GitHub Actions job and produces a reviewable video artifact.

Do not store private or unlicensed footage here.
