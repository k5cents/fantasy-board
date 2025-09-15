#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/fantasy-board"
OUTDIR="$PROJECT_DIR/www"
PY="$PROJECT_DIR/.venv/bin/python3"

mkdir -p "$OUTDIR"

TMP="$OUTDIR/.scoreboard.json.$$"
OUT="$OUTDIR/scoreboard.json"
LOG="$PROJECT_DIR/pi/scoreboard.log"

# Quiet hours: 00:00–07:59 local time -> write sleep JSON and exit
is_quiet_hours() {
  # 0..23 hour
  local h
  h="$(date +%H)"
  # 00 <= hour < 08
  [[ "$h" -ge 0 && "$h" -lt 8 ]]
}

# Gametime windows (Thu 19:00–23:59, Sun 12:00–23:59, Mon 19:00–23:59)
is_gametime() {
  local dow timehm
  dow="$(date +%u)"     # 1=Mon ... 7=Sun
  timehm="$(date +%H%M)"

  [[ "$dow" -eq 4 && "$timehm" -ge 1900 ]] && return 0  # Thu
  [[ "$dow" -eq 7 && "$timehm" -ge 1200 ]] && return 0  # Sun
  [[ "$dow" -eq 1 && "$timehm" -ge 1900 ]] && return 0  # Mon
  return 1
}

# Quiet-hours short-circuit
if is_quiet_hours; then
  {
    echo "[$(date -Iseconds)] quiet-hours: writing sleep JSON"
    printf '%s\n' '{"status":"sleep"}' > "$TMP"
    mv -f "$TMP" "$OUT"
    echo "[$(date -Iseconds)] wrote $OUT (sleep)"
  } >> "$LOG" 2>&1
  exit 0
fi

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