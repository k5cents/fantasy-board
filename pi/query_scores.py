#!/usr/bin/env python3
"""
Format live ESPN fantasy football scores from API and save as JSON
https://github.com/k5cents/fantasy-board
Kiernan Nicholls (Python port, updated to match latest R version)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from statistics import median
from typing import Any, Dict, List, Optional

import pytz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------- config ---------------------------------------------

PARAM_LEAGUE = 252353
PARAM_SEASON = 2025
PARAM_TEAM = 6

JSON_FILE = "scoreboard.json"

BASE_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
    "seasons/{season}/segments/0/leagues/{league}?view=mScoreboard&view=mRoster"
)

# ---------------------- helpers --------------------------------------------

def print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))

def parse_resp_time(resp: requests.Response) -> str:
    """Parse HTTP Date header and convert to America/New_York."""
    try:
        date_str = resp.headers.get("Date")
        dt_utc = parsedate_to_datetime(date_str)  # already UTC
        ny_tz = pytz.timezone("America/New_York")
        return dt_utc.astimezone(ny_tz).isoformat()
    except Exception:
        return datetime.now(pytz.timezone("America/New_York")).isoformat()

def dense_rank_desc(values: List[Optional[float]]) -> List[int]:
    """Dense rank in descending order (ties share rank, next rank increments by 1)."""
    cleaned = [v for v in values if v is not None]
    uniq = sorted(set(cleaned), reverse=True)
    index = {v: i + 1 for i, v in enumerate(uniq)}
    return [index[v] if v is not None else None for v in values]

def get_team_abbrev_map(teams: List[Dict[str, Any]]) -> Dict[int, str]:
    return {int(t["id"]): t.get("abbrev") for t in teams}

def get_team_wins_map(teams: List[Dict[str, Any]]) -> Dict[str, int]:
    return {t.get("abbrev"): t.get("record", {}).get("overall", {}).get("wins") for t in teams}

# ---------------------- request --------------------------------------------

def fetch_league(season: int, league: int) -> Optional[requests.Response]:
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
        if resp.status_code >= 400:
            err = {
                "status": "http-error",
                "http_code": resp.status_code,
                "timestamp": parse_resp_time(resp),
            }
            write_json(err, JSON_FILE)
            return None
        return resp
    except requests.RequestException:
        err = {
            "status": "http-error",
            "http_code": None,
            "timestamp": datetime.now().isoformat(),
        }
        write_json(err, JSON_FILE)
        return None

# ---------------------- transform ------------------------------------------

def build_scoreboard(dat: Dict[str, Any], param_team: int) -> Optional[List[Dict[str, Any]]]:
    schedule = dat.get("schedule", [])
    teams = dat.get("teams", [])

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
        return None

    # Filter rows missing projections
    rows = [r for r in rows if r.get("proj_points") is not None]
    if not rows:
        return []

    # Round to 1 decimal
    for r in rows:
        r["live_points"] = round(r.get("live_points") or 0, 1)
        r["proj_points"] = round(r.get("proj_points") or 0, 1)

    # Bonus win threshold = 5th-highest projected score
    proj_vals = [r["proj_points"] for r in rows]
    proj_sorted = sorted([v for v in proj_vals if v is not None], reverse=True)
    proj_fifth = proj_sorted[4] if len(proj_sorted) >= 5 else proj_sorted[-1]

    for r in rows:
        r["bonus_win"] = int(r["proj_points"] >= proj_fifth)
        r["bonus_diff"] = round(r["proj_points"] - proj_fifth, 1)

    # score_rank
    ranks = dense_rank_desc(proj_vals)
    for r, rank in zip(rows, ranks):
        r["score_rank"] = int(rank)

    # team_abbrev
    id_to_abbrev = get_team_abbrev_map(teams)
    for r in rows:
        r["team_abbrev"] = id_to_abbrev.get(int(r["team_id"]), None)

    # match_win (per matchup_id)
    by_matchup: Dict[int, float] = {}
    for r in rows:
        mid = r["matchup_id"]
        by_matchup[mid] = max(by_matchup.get(mid, float("-inf")), r["proj_points"])
    for r in rows:
        r["match_win"] = int(r["proj_points"] == by_matchup[r["matchup_id"]])

    # Keep only selected matchup
    selected_mid = next((r["matchup_id"] for r in rows if r.get("team_id") == param_team), None)
    if selected_mid is None:
        return []
    rows = [r for r in rows if r.get("matchup_id") == selected_mid]

    # diffs vs opponent (live and projected)
    if len(rows) >= 2:
        lp = {int(r["team_id"]): float(r["live_points"]) for r in rows}
        pp = {int(r["team_id"]): float(r["proj_points"]) for r in rows}
        for r in rows:
            tid = int(r["team_id"])
            opp_lp = next((v for k, v in lp.items() if k != tid), None)
            opp_pp = next((v for k, v in pp.items() if k != tid), None)
            r["live_diff"] = round(lp[tid] - opp_lp, 1) if opp_lp is not None else None
            r["proj_diff"] = round(pp[tid] - opp_pp, 1) if opp_pp is not None else None
    else:
        for r in rows:
            r["live_diff"] = None
            r["proj_diff"] = None

    # Add current wins
    abbrev_to_wins = get_team_wins_map(teams)
    for r in rows:
        r["current_wins"] = abbrev_to_wins.get(r["team_abbrev"])

    # Re-order keys for output
    cleaned = []
    for r in rows:
        cleaned.append({
            "team_id": int(r["team_id"]),
            "team_abbrev": r["team_abbrev"],
            "live_points": r["live_points"],
            "live_diff": r["live_diff"],
            "proj_points": r["proj_points"],
            "proj_diff": r["proj_diff"],
            "bonus_win": r["bonus_win"],
            "bonus_diff": r["bonus_diff"],
            "score_rank": r["score_rank"],
            "match_win": r["match_win"],
            "current_wins": r["current_wins"],
        })

    cleaned.sort(key=lambda x: 0 if x["team_id"] == int(param_team) else 1)

    return cleaned

# ---------------------- main ----------------------------------------------

def main() -> int:
    resp = fetch_league(PARAM_SEASON, PARAM_LEAGUE)
    if resp is None:
        return 0

    dat = resp.json()
    resp_time = parse_resp_time(resp)

    rows = build_scoreboard(dat, PARAM_TEAM)
    if rows is None or len(rows) == 0:
        write_json({"status": "row-projections", "timestamp": resp_time}, JSON_FILE)
        return 0

    out = {
        "status": "ok",
        "league": PARAM_LEAGUE,
        "season": PARAM_SEASON,
        "week": dat.get("scoringPeriodId"),
        "timestamp": resp_time,
        "scoreboard": rows,
    }

    print_json(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())