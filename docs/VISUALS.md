# Visual provenance

- `osintcli/assets/banner-readme.png`: original supplied banner from OSINTCLI_PRD_Assets.zip; owner-provided generated art direction, not a real terminal capture.
- `icon-source.svg`: editable original geometric globe + inspection lens, cyan #00C6D7, green #35D18A, dark #09121B.
- `icon-source.png`, RGB/256 ANSI variants at 24/28/32 cells and plain text: reproducible via `python3 scripts/make-ansi.py` (Pillow). Script uses the same geometric construction for vector and raster master.
- `docs/screenshots/terminal-demo.cast`: actual output from a Linux PTY at 40 columns, with a seeded offline fixture case. GIF frames are rendered from this recording, not generated imaginary UI.
- Font DejaVu Sans: license included in package assets and docs/licenses.

The supplied PRD's image-generation prompts are preserved in `docs/PRD-source.txt`. Banner images do not prove that a collection or scan occurred. Android light/dark device screenshots are still pending physical-device testing.
