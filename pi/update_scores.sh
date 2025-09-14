#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/fantasy-board"
OUTDIR="$PROJECT_DIR/www"
PY="$PROJECT_DIR/.venv/bin/python3"

mkdir -p "$OUTDIR"

TMP="$OUTDIR/.scoreboard.json.$$"
OUT="$OUTDIR/scoreboard.json"
LOG="$PROJECT_DIR/pi/scoreboard.log"

is_gametime() {
  # %u: 1=Mon ... 7=Sun ; %H%M: 0000..2359 (24h)
  local dow timehm
  dow="$(date +%u)"
  timehm="$(date +%H%M)"

  # Thu 19:00–23:59
  if [[ "$dow" -eq 4 && "$timehm" -ge 1900 ]]; then return 0; fi
  # Sun 12:00–23:59
  if [[ "$dow" -eq 7 && "$timehm" -ge 1200 ]]; then return 0; fi
  # Mon 19:00–23:59
  if [[ "$dow" -eq 1 && "$timehm" -ge 1900 ]]; then return 0; fi

  return 1
}

# How stale is the current OUT file?
now="$(date +%s)"
mtime=0
if [[ -f "$OUT" ]]; then
  mtime="$(stat -c %Y "$OUT" || echo 0)"
fi
age=$(( now - mtime ))

if is_gametime; then
  threshold=60          # update at most once per minute during games
  mode="gametime"
else
  threshold=$((30*60))  # update at most once every 30 minutes off-hours
  mode="offhours"
fi

if [[ -f "$OUT" && $age -lt $threshold ]]; then
  {
    echo "[$(date -Iseconds)] skip ($mode): age=${age}s < threshold=${threshold}s"
  } >> "$LOG" 2>&1
  exit 0
fi

# Run the query script and write atomically
{
  echo "[$(date -Iseconds)] update ($mode) start"
  "$PY" "$PROJECT_DIR/pi/query_scores.py" > "$TMP"
  mv -f "$TMP" "$OUT"
  echo "[$(date -Iseconds)] wrote $OUT (size $(wc -c < "$OUT") bytes)"
} >> "$LOG" 2>&1