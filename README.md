# Fantasy Football Scoreboard

Live fantasy football scores on an Adafruit MatrixPortal M4 + 64x32 RGB LED matrix.

A small server on the Pi (`k5aux`) fetches the current ESPN matchup and serves it as
compact JSON; the board polls that endpoint and renders it. The server exists because
ESPN's smallest useful response is ~200 KB, and the M4 has 192 KB of RAM.

---

## Project Structure

```
.
├── server/              # runs on k5aux via Docker Compose
│   ├── app.py           # HTTP server + cache + ESPN fetch + transform (stdlib only)
│   ├── Dockerfile
│   └── compose.yml
│
├── board/               # copied to the CIRCUITPY drive
│   ├── code.py          # boot, Wi-Fi, poll loop, watchdog
│   ├── display.py       # FantasyBoard renderer + status screens
│   ├── config.py        # display, colors, intervals
│   ├── fonts/5x7.bdf
│   ├── requirements.txt         # CircuitPython libs for circup
│   └── settings.toml.example    # Wi-Fi creds + SCOREBOARD_URL
│
├── tests/               # unit tests over a saved ESPN response
└── Makefile
```

---

## How It Works

### Server (`server/app.py`)

- `GET /scoreboard.json` returns the payload below; `GET /healthz` returns `ok`.
- ESPN is queried lazily, when a request arrives and the cache has aged out:
  - **Gametime** (Thu/Mon 19:00+, Sun 12:00+ ET): 60 seconds.
  - **Otherwise:** 30 minutes.
- **Quiet hours** (00:00–07:59 ET): returns `{"status": "sleep"}` without calling ESPN.
- If ESPN fails, the last good payload is served with `"stale": true`; with no cache at
  all, `{"status": "error", "detail": ...}`.
- The season is derived from the date (rolls over in March), so nothing needs editing
  each year. League and team come from the environment.

| Variable | Default | Meaning |
|---|---|---|
| `LEAGUE_ID` | `252353` | ESPN league |
| `TEAM_ID` | `6` | the team whose matchup is displayed |
| `SEASON` | *(derived)* | override the season year |
| `PORT` | `8000` | listen port |
| `TZ` | `America/New_York` | zone for quiet hours and gametime |

Payload:

```json
{
  "status": "ok",
  "league": 252353,
  "season": 2026,
  "week": 2,
  "timestamp": "2026-09-15T18:00:00-04:00",
  "scoreboard": [
    {"team_id": 6, "team_abbrev": "KIER", "live_points": 44.7, "live_diff": -50.2,
     "proj_points": 81.5, "proj_diff": -19.1, "win_prob": 54, "bonus_win": 0,
     "bonus_diff": -17.6, "score_rank": 9, "match_win": 0, "current_wins": 1},
    {"team_id": 12, "...": "opponent"}
  ]
}
```

Your team is always first. `score_rank` is the dense rank of projected points across
the league; `bonus_win` marks the top five projected scores.

**`win_prob` is the FantasyCast number**, as a whole percent. It lives in ESPN's
`view=mMatchupScore` — the `mScoreboard` view returns the same matchup objects with
`winProbability` absent, which is why it looks like the API doesn't expose it. The
matchup view is also 80 KB smaller and carries `matchupPeriodId`, so the current week is
selected explicitly rather than inferred.

### Board (`board/code.py`)

- Brings up the display **first**, so `BOOT`, `WIFI`, `NO WIFI`, `NO URL` and `NO DATA`
  are visible on the panel instead of a dark board.
- Polls `SCOREBOARD_URL` every 30 seconds and renders two columns, 4 rows each:
  team abbreviation, live points, projected points (green leader / red trailer / yellow
  tie), and projected rank (green in the top 5, red below).
- **Row 2 shows the win percentage until someone scores.** Both teams sit on `0.0` from
  Tuesday to Thursday, so the row carries the odds instead, and switches to live points
  at the first snap.
- **The bottom pixel row is a win probability bar**, mirroring FantasyCast: each half is
  a 32 px gauge filling outward from the center, so the lit block slides toward whoever
  is favored. Favored side green, underdog red, dead heat yellow. It hides itself if
  ESPN omits the probability.
- `{"status": "sleep"}` blanks the panel and slows polling to 5 minutes.
- A dim dot in the corner means the data has stopped updating (server marked it stale,
  or nothing fresh for 5 minutes). The last good frame stays on screen.
- A hardware watchdog resets the board if the loop wedges; unexpected errors reload the
  program rather than dropping to the REPL.

---

## Setup

### Server (k5aux)

```bash
make deploy
curl http://k5aux.lan:8000/scoreboard.json | jq .
```

Runs as the `fantasy-board` container with `restart: unless-stopped`, LAN-only on 8000.
`make logs` tails it.

### Board

1. Flash CircuitPython 9.x to the MatrixPortal M4.
2. `make board-libs` — installs the libraries in `board/requirements.txt` with
   [circup](https://github.com/adafruit/circup) (`uv tool install circup`).
3. Copy `board/settings.toml.example` to `CIRCUITPY/settings.toml` and fill in the Wi-Fi
   credentials (2.4 GHz only) and `SCOREBOARD_URL`.
4. `make board` — copies the code, skipping macOS `._*` junk and `settings.toml`.

---

## Development

```bash
make test          # unit tests: transform, windows, cache, layout, preview
make serve         # run the server locally on :8000
make preview       # render every display state to preview.png
make preview-live  # render what the board is showing right now
```

### Previewing without the board

`tools/preview.py` drives the real `board/display.py` through a stubbed
CircuitPython display stack and rasterizes the same `5x7.bdf`, so the PNG is what
`FantasyBoard` actually draws. Panel geometry follows the hardware (Adafruit 2278:
64x32 on a 4mm pitch, 255 x 127 mm), and it simulates the acrylic diffuser by
default; `--bare` renders the naked panel. `--compare` puts candidate layouts side
by side, `--scenario` picks one state, `--url` renders a live payload.

**Row geometry, measured on the board** (by reading a label's own bitmap over the
REPL, since `bounding_box` describes the box and not the lit rows): `bitmap_label`
renders into an 8-row bitmap at tilegrid `y-4` with glyph content in rows 1-6, so
**lit pixels run `y-3` to `y+2`** and a descender would reach `y+3`. With
`top_margin: 2` the four rows light 0-5, 8-13, 16-21 and 24-29, leaving row 30 dark
above the bar at 31. Tests pin the preview to those measured rows.

Note that one dark row reads as intra-character spacing rather than separation, so
a wider gap or a taller bar costs a whole text row.

`tests/fixtures/espn_week.json` is a trimmed real ESPN response, so the transform can be
tested without a live game.
