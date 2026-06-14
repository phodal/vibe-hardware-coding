# Evidence Packs

This directory stores committed hardware evidence packs that are useful for articles, handoffs, and agent-to-agent verification.

Each `ok-qoder-*` pack is produced by:

```bash
make ok-qoder-evidence
```

Use `ALLOW_PARTIAL=1 make ok-qoder-evidence` only when you intentionally want to preserve a failed or partial run for debugging. A full visual claim requires:

- `summary.md` reports build, smoke, serial, and camera OCR as passed
- `summary.json` reports the same statuses for agents and scripts
- `camera-ocr-*.jpg` exists as the raw camera frame
- `camera-ocr-*.processed.png` exists as the OCR input image
- `camera-ocr-*.txt` contains the expected marker

Serial logs prove firmware control flow. Camera/OCR artifacts prove the AMOLED rendered the expected screen.
