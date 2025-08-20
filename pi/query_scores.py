#!/usr/bin/env python3
"""
Format live ESPN fantasy football scores from API and save as JSON
https://github.com/k5cents/fantasy-board
Kiernan Nicholls (Python port)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------- config ---------------------------------------------

# set parameters for league and team
PARAM_LEAGUE = 252353
PARAM_SEASON = 2024
PARAM_TEAM = 6

JSON_FILE = "/home/kiernan/Developer/scoreboard/scoreboard.json"

BASE_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{league}?view=mScoreboard&view=mRoster"

# ---------------------- helpers --------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_json(payload: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def dense_rank_desc(values: List[Optional[float]]) -> List[int]:
    """Dense rank in descending order (ties share rank, next rank increments by 1)."""
    # Handle None as missing
    cleaned = [v for v in values if v is not None]
    uniq = sorted(set(cleaned), reverse=True)
    index = {v: i + 1 for i, v in enumerate(uniq)}
    return [index[v] if v is not None else None for v in values]

def get_team_abbrev_map(teams: List[Dict[str, Any]]) -> Dict[int, str]:
    return {int(t["id"]): t.get("abbrev") for t in teams}

def sum_bool(iterable) -> int:
    return sum(1 for x in iterable if x)

# ---------------------- request --------------------------------------------

def fetch_league(season: int, league: int) -> Optional[Dict[str, Any]]:
    url = BASE_URL.format(season=season, league=league)
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    headers = {
        "Accept": "application/json",
        "User-Agent": "https://github.com/k5cents/fflr/",
    }
    try:
        resp = session.get(url, headers=headers, timeout=10)
        status = resp.status_code
        if status >= 400:
            err = {
                "status": "http-error",
                "http_code": status,
                "timestamp": now_iso(),
            }
            write_json(err, JSON_FILE)
            return None
        return resp.json()
    except requests.RequestException:
        err = {
            "status": "http-error",
            "http_code": None,
            "timestamp": now_iso(),
        }
        write_json(err, JSON_FILE)
        return None

# ---------------------- transform ------------------------------------------

def build_scoreboard(dat: Dict[str, Any], param_team: int) -> Optional[List[Dict[str, Any]]]:
    schedule = dat.get("schedule", [])
    teams = dat.get("teams", [])

    # Build rows from home/away sides
    rows: List[Dict[str, Any]] = []
    current_matchup_period = dat.get("status", {}).get("currentMatchupPeriod")

    for game in schedule:
        mid = game.get("id")
        home = game.get("home", {}) or {}
        away = game.get("away", {}) or {}

        rows.append({
            "matchup_period": current_matchup_period,
            "matchup_id": mid,
            "team_id": home.get("teamId"),
            "live_points": home.get("totalPointsLive"),
            "proj_points": home.get("totalProjectedPointsLive"),
        })
        rows.append({
            "matchup_period": current_matchup_period,
            "matchup_id": mid,
            "team_id": away.get("teamId"),
            "live_points": away.get("totalPointsLive"),
            "proj_points": away.get("totalProjectedPointsLive"),
        })

    if not rows:
        return None  # handled by caller

    # Filter rows missing projected points
    rows = [r for r in rows if r.get("proj_points") is not None]
    if not rows:
        return []  # signal "row-projections" to caller

    # Round points
    for r in rows:
        r["live_points"] = round(r.get("live_points") or 0)
        r["proj_points"] = round(r.get("proj_points") or 0)

    # bonus_win (top half of projections)
    proj_vals = [r["proj_points"] for r in rows]
    proj_med = median(proj_vals)
    for r in rows:
        r["bonus_win"] = r["proj_points"] > proj_med

    # score_rank (dense rank, desc)
    ranks = dense_rank_desc(proj_vals)
    for r, rank in zip(rows, ranks):
        r["score_rank"] = rank

    # team_abbrev
    id_to_abbrev = get_team_abbrev_map(teams)
    for r in rows:
        r["team_abbrev"] = id_to_abbrev.get(int(r["team_id"]), None)

    # Keep only the selected matchup for param_team
    # Find the matchup_id containing the selected team
    selected_mid = next(
        (r["matchup_id"] for r in rows if r.get("team_id") == param_team),
        None
    )
    if selected_mid is None:
        # If the team isn't in any row, keep nothing (will fall to error path)
        return []

    rows = [r for r in rows if r.get("matchup_id") == selected_mid]

    # Final selection of fields and ordering
    cleaned = [
        {
            "team_id": int(r["team_id"]),
            "team_abbrev": r["team_abbrev"],
            "live_points": int(r["live_points"]),
            "proj_points": int(r["proj_points"]),
            "score_rank": int(r["score_rank"]),
        }
        for r in rows
    ]
    return cleaned

def add_player_status(dat: Dict[str, Any], scoreboard_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add n_locked and n_unlocked by team based on roster entries (exclude bench 20 & IR 21)."""
    team_ids = {row["team_id"] for row in scoreboard_rows}
    teams = dat.get("teams", [])

    # Build a flat list of (team_id, slot_id, is_locked) for starters
    entries: List[Dict[str, Any]] = []
    for t in teams:
        tid = int(t.get("id"))
        if tid not in team_ids:
            continue
        roster = (t.get("roster") or {}).get("entries") or []
        for e in roster:
            ppe = e.get("playerPoolEntry") or {}
            lineup_slot = e.get("lineupSlotId")
            is_locked = ppe.get("lineupLocked")
            on_team = ppe.get("onTeamId")
            # filter out bench (20) and IR (21), keep only players on team
            if on_team == tid and lineup_slot not in (20, 21):
                entries.append({
                    "team_id": tid,
                    "slot_id": lineup_slot,
                    "is_locked": bool(is_locked),
                })

    # Count per team
    counts: Dict[int, Dict[str, int]] = {}
    for tid in team_ids:
        team_entries = [e for e in entries if e["team_id"] == tid]
        locked = sum_bool(e["is_locked"] for e in team_entries)
        unlocked = sum_bool(not e["is_locked"] for e in team_entries)
        counts[tid] = {"n_locked": locked, "n_unlocked": unlocked}

    # Merge into rows
    for r in scoreboard_rows:
        c = counts.get(r["team_id"], {"n_locked": 0, "n_unlocked": 0})
        r.update(c)

    return scoreboard_rows

# ---------------------- main ----------------------------------------------

def main() -> int:
    dat = fetch_league(PARAM_SEASON, PARAM_LEAGUE)
    if dat is None:
        # Already wrote an error JSON.
        return 0

    # Build scoreboard rows
    rows = build_scoreboard(dat, PARAM_TEAM)
    if rows is None:
        write_json(
            {"status": "row-projections", "timestamp": now_iso()},
            JSON_FILE,
        )
        return 0
    if len(rows) == 0:
        write_json(
            {"status": "row-projections", "timestamp": now_iso()},
            JSON_FILE,
        )
        return 0

    # Add player status (locked/unlocked counts)
    rows = add_player_status(dat, rows)

    out = {
        "status": "ok",
        "league": PARAM_LEAGUE,
        "season": PARAM_SEASON,
        "timestamp": now_iso(),
        "scoreboard": rows,
    }

    write_json(out, JSON_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
