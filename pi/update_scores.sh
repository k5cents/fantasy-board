#!/usr/bin/env bash
set -euo pipefail

LOCK="/tmp/scoreboard.lock"
RSCRIPT="/usr/bin/Rscript"
SCRIPT="/home/kiernan/Developer/scoreboard/query-scores.R"
LOG="/home/kiernan/Developer/scoreboard/scoreboard.log"

dow=$(date +%u)   # 1=Mon ... 7=Sun
hour=$(date +%H)  # 00..23
min=$(date +%M)   # 00..59

fast=0
# Sunday 08:00–23:59 ET
if [[ "$dow" -eq 7 && "$hour" -ge 08 && "$hour" -le 23 ]]; then fast=1; fi
# Monday Night Football
if [[ "$dow" -eq 1 && "$hour" -ge 19 && "$hour" -le 23 ]]; then fast=1; fi
if [[ "$dow" -eq 2 && "$hour" -ge 00 && "$hour" -le 01 ]]; then fast=1; fi
# Thursday Night Football
if [[ "$dow" -eq 4 && "$hour" -ge 19 && "$hour" -le 23 ]]; then fast=1; fi
if [[ "$dow" -eq 5 && "$hour" -ge 00 && "$hour" -le 01 ]]; then fast=1; fi

# Slow mode = only run every 15 minutes
if [[ "$fast" -eq 0 ]]; then
  if (( 10#$min % 15 != 0 )); then exit 0; fi
fi

flock -n "$LOCK" -c "$RSCRIPT $SCRIPT >>"$LOG" 2>&1"
