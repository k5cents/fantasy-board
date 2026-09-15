#!/usr/bin/env python3
"""
Fantasy football scoreboard server.
https://github.com/k5cents/fantasy-board

Serves the current ESPN matchup as JSON for the MatrixPortal to render.
ESPN is queried lazily: a request refreshes the cache only when it has aged
past the TTL for the current window (fast during games, slow otherwise).

Standard library only, so the container needs no pip install.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# ---------------------- config ---------------------------------------------

LEAGUE_ID = int(os.getenv("LEAGUE_ID", "252353"))
TEAM_ID = int(os.getenv("TEAM_ID", "6"))
PORT = int(os.getenv("PORT", "8000"))
ZONE = ZoneInfo(os.getenv("TZ", "America/New_York"))
SEASON = int(os.getenv("SEASON")) if os.getenv("SEASON") else None

# Cache TTLs (seconds)
GAME_TTL = 60
IDLE_TTL = 30 * 60

# Quiet hours: display sleeps, ESPN is not queried
QUIET_START, QUIET_END = 0, 8

# Bonus win goes to the top half of a 10 team league
BONUS_PLACES = 5

BASE_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
    "seasons/{season}/segments/0/leagues/{league}?view=mScoreboard"
)
USER_AGENT = "https://github.com/k5cents/fflr/"
TIMEOUT = 10

# ---------------------- schedule -------------------------------------------


def current_season(now: datetime) -> int:
    """ESPN labels a season by the year it starts; it runs into January."""
    return now.year if now.month >= 3 else now.year - 1


def is_quiet_hours(now: datetime) -> bool:
    return QUIET_START <= now.hour < QUIET_END


def is_gametime(now: datetime) -> bool:
    """Thu and Mon night, Sunday afternoon through evening."""
    dow = now.isoweekday()  # 1=Mon ... 7=Sun
    hhmm = now.hour * 100 + now.minute
    if dow in (1, 4) and hhmm >= 1900:
        return True
    if dow == 7 and hhmm >= 1200:
        return True
    return False


def cache_ttl(now: datetime) -> int:
    return GAME_TTL if is_gametime(now) else IDLE_TTL


# ---------------------- request --------------------------------------------


def fetch_league(season: int, league: int, attempts: int = 3) -> Tuple[Dict[str, Any], str]:
    """Return (payload, ESPN response time as ISO string). Raises on failure."""
    url = BASE_URL.format(season=season, league=league)
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )

    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read()
                stamp = parse_resp_time(resp.headers.get("Date"))
            return json.loads(body), stamp
        except urllib.error.HTTPError as err:
            last_error = err
            if err.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            last_error = err
        if attempt < attempts - 1:
            time.sleep(0.5 * (attempt + 1))

    raise last_error if last_error else RuntimeError("fetch failed")


def parse_resp_time(date_header: Optional[str]) -> str:
    """HTTP Date header (UTC) as a local ISO timestamp."""
    try:
        return parsedate_to_datetime(date_header).astimezone(ZONE).isoformat()
    except Exception:
        return datetime.now(ZONE).isoformat()


# ---------------------- transform ------------------------------------------


def dense_rank_desc(values: List[float]) -> List[int]:
    """Dense rank, highest first; ties share a rank and the next increments by 1."""
    index = {v: i + 1 for i, v in enumerate(sorted(set(values), reverse=True))}
    return [index[v] for v in values]


def transform(dat: Dict[str, Any], team_id: int) -> List[Dict[str, Any]]:
    """
    Reduce a league payload to the two teams of `team_id`'s current matchup.

    ESPN only carries totalProjectedPointsLive on games in the current matchup
    period, so that field doubles as the week filter.
    """
    rows: List[Dict[str, Any]] = []
    for game in dat.get("schedule", []):
        for side in ("home", "away"):
            team = game.get(side) or {}
            if "totalProjectedPointsLive" not in team:
                continue
            rows.append(
                {
                    "matchup_id": game.get("id"),
                    "team_id": int(team.get("teamId")),
                    # float() keeps a 0 score as 0.0, so the panel shows "0.0"
                    "live_points": round(float(team.get("totalPointsLive") or 0.0), 1),
                    "proj_points": round(float(team.get("totalProjectedPointsLive") or 0.0), 1),
                }
            )

    if not rows:
        return []

    # Bonus win threshold: the BONUS_PLACES-highest projected score league wide
    proj = [r["proj_points"] for r in rows]
    ranked = sorted(proj, reverse=True)
    cutoff = ranked[BONUS_PLACES - 1] if len(ranked) >= BONUS_PLACES else ranked[-1]
    for r, rank in zip(rows, dense_rank_desc(proj)):
        r["score_rank"] = rank
        r["bonus_win"] = int(r["proj_points"] >= cutoff)
        r["bonus_diff"] = round(r["proj_points"] - cutoff, 1)

    # Winner of each matchup, by projection
    best: Dict[Any, float] = {}
    for r in rows:
        best[r["matchup_id"]] = max(best.get(r["matchup_id"], float("-inf")), r["proj_points"])
    for r in rows:
        r["match_win"] = int(r["proj_points"] == best[r["matchup_id"]])

    # Keep only our matchup
    mine = next((r["matchup_id"] for r in rows if r["team_id"] == team_id), None)
    if mine is None:
        return []
    rows = [r for r in rows if r["matchup_id"] == mine]
    if len(rows) != 2:
        return []

    rows.sort(key=lambda r: 0 if r["team_id"] == team_id else 1)
    us, them = rows

    teams = dat.get("teams", [])
    abbrevs = {int(t["id"]): t.get("abbrev") for t in teams}
    wins = {int(t["id"]): (t.get("record", {}).get("overall", {}) or {}).get("wins") for t in teams}

    out = []
    for r, opp in ((us, them), (them, us)):
        out.append(
            {
                "team_id": r["team_id"],
                "team_abbrev": abbrevs.get(r["team_id"]),
                "live_points": r["live_points"],
                "live_diff": round(r["live_points"] - opp["live_points"], 1),
                "proj_points": r["proj_points"],
                "proj_diff": round(r["proj_points"] - opp["proj_points"], 1),
                "bonus_win": r["bonus_win"],
                "bonus_diff": r["bonus_diff"],
                "score_rank": r["score_rank"],
                "match_win": r["match_win"],
                "current_wins": wins.get(r["team_id"]),
            }
        )
    return out


def build_payload(dat: Dict[str, Any], season: int, stamp: str) -> Dict[str, Any]:
    rows = transform(dat, TEAM_ID)
    if not rows:
        return {
            "status": "error",
            "detail": "no live projections for this team",
            "timestamp": stamp,
        }
    return {
        "status": "ok",
        "league": LEAGUE_ID,
        "season": season,
        "week": (dat.get("status") or {}).get("currentMatchupPeriod"),
        "timestamp": stamp,
        "scoreboard": rows,
    }


# ---------------------- cache ----------------------------------------------


class Scoreboard:
    """Caches the last good payload and refreshes it on demand."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: Optional[Dict[str, Any]] = None
        self._fetched_at = 0.0

    def get(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(ZONE)

        if is_quiet_hours(now):
            return {"status": "sleep", "timestamp": now.isoformat()}

        with self._lock:
            age = time.monotonic() - self._fetched_at
            if self._payload is not None and age < cache_ttl(now):
                return self._payload

            season = SEASON or current_season(now)
            try:
                dat, stamp = fetch_league(season, LEAGUE_ID)
                payload = build_payload(dat, season, stamp)
            except Exception as err:  # network, HTTP, malformed JSON
                log("espn fetch failed: %s: %s" % (type(err).__name__, err))
                if self._payload is not None:
                    return dict(self._payload, stale=True)
                return {
                    "status": "error",
                    "detail": "%s: %s" % (type(err).__name__, err),
                    "timestamp": now.isoformat(),
                }

            self._payload = payload
            self._fetched_at = time.monotonic()
            log("espn fetch ok: season=%s status=%s" % (season, payload.get("status")))
            return payload


def log(message: str) -> None:
    print("[%s] %s" % (datetime.now(ZONE).isoformat(timespec="seconds"), message), flush=True)


# ---------------------- http -----------------------------------------------

BOARD = Scoreboard()


class Handler(BaseHTTPRequestHandler):
    server_version = "fantasy-board"

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        path = self.path.split("?", 1)[0]
        if path in ("/scoreboard.json", "/"):
            self._send_json(BOARD.get())
        elif path == "/healthz":
            self._send(b"ok\n", "text/plain")
        else:
            self._send(b"not found\n", "text/plain", status=404)

    def _send_json(self, payload: Dict[str, Any]) -> None:
        self._send(json.dumps(payload).encode() + b"\n", "application/json")

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        """Quiet: the board polls constantly and only ESPN fetches are worth logging."""


def main() -> int:
    log("serving on :%d (league=%d team=%d)" % (PORT, LEAGUE_ID, TEAM_ID))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
