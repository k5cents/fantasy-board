#!/usr/bin/env bash
set -euo pipefail

PI_DIR="/home/kiernan/fantasy-board/pi"
OUT_JSON="$PI_DIR/scoreboard.json"
TMP_JSON="$PI_DIR/scoreboard.json.tmp"

CIRCUITPY="/mnt/CIRCUITPY"
CIRCUITPY_TMP="$CIRCUITPY/scoreboard.json.tmp"
CIRCUITPY_JSON="$CIRCUITPY/scoreboard.json"

VENV="/home/kiernan/fantasy-board/.venv"
PY="$VENV/bin/python"

cd "$PI_DIR"

# Generate fresh JSON atomically
"$PY" "$PI_DIR/query_scores.py" > "$TMP_JSON"

# Validate JSON (uses stdlib json.tool via the same interpreter)
"$PY" -m json.tool "$TMP_JSON" >/dev/null || exit 1
mv -f "$TMP_JSON" "$OUT_JSON"

# Copy to CIRCUITPY atomically if mounted
if mountpoint -q "$CIRCUITPY"; then
  install -m 0644 -T "$OUT_JSON" "$CIRCUITPY_TMP"
  sync
  mv -f "$CIRCUITPY_TMP" "$CIRCUITPY_JSON"
  sync
else
  echo "[update-scoreboard] WARN: $CIRCUITPY not mounted; skipped device copy" >&2
fi

echo "[update-scoreboard] Updated $(date -Is)"
