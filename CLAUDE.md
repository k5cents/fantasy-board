# fantasy-board

Live fantasy football scores on an Adafruit MatrixPortal M4 driving a 64x32 RGB
LED matrix. A small server on `k5aux` fetches the ESPN matchup and serves it as
JSON; the board polls and renders it.

## Architecture

Two tiers, and the split is not optional: the **smallest useful ESPN response is
~200 KB and the M4 has 192 KB of RAM**, so the board cannot call ESPN directly.
Don't "simplify" by removing the server.

```
server/app.py   stdlib only -> Docker Compose on k5aux:8000 (LAN only)
board/          copied to CIRCUITPY; polls SCOREBOARD_URL every 30s
tools/preview.py  renders the display to PNG without the board
tests/          unittest, stdlib only
```

## Commands

```bash
make test          # 47 tests: transform, windows, cache, layout, preview
make serve         # server locally on :8000
make preview       # all display states -> preview.png
make preview-live  # render what the board is showing right now
make board         # rsync board/ -> /Volumes/CIRCUITPY
make board-libs    # circup install -r board/requirements.txt
make deploy        # rsync server/ -> k5aux, docker compose up -d --build
make logs          # tail the container on k5aux
```

## Hardware facts

| | |
|---|---|
| Panel | Adafruit 2278, 64x32, **4mm pitch**, 255 x 127 mm, ~2.1mm emitter |
| Board | MatrixPortal M4 (SAMD51), CircuitPython 9.2.8 |
| Serial | `/dev/cu.usbmodem101`; drive mounts at `/Volumes/CIRCUITPY` |
| Wi-Fi | SSID `k24iot` (2.4 GHz only — the board cannot see `k5wifi`) |
| Board IP | 192.168.1.132 |
| Server | `k5aux` = 192.168.1.125, SSH on **port 55**, service at `~/services/fantasy-board/` |

- **Watchdog maximum is 16 seconds** on the SAMD51. Larger values raise
  `ValueError: timeout must be <= 16`. Naps feed it in <=5s slices.
- `rotation: 180` in config — the panel is mounted upside down, so the composed
  image reaches the viewer right way up. Don't "fix" it.
- The user's panel has an **acrylic diffuser**: emitters swell until they nearly
  touch but stay distinct dots. `tools/preview.py` simulates this by default.

## Display geometry — measured, not inferred

This cost two wrong guesses. **Do not infer glyph placement from
`bounding_box`**: it describes the box, not the lit rows.

Measured by reading a live label's own bitmap over the REPL:

```
label._bitmap is 8 rows tall; label._tilegrid.y is -4; glyph content
occupies bitmap rows 1..6, so the font's BLANK row sits at the TOP.

    lit rows = label.y - 3 .. label.y + 2     (a descender reaches y+3)
```

With `top_margin: 2` and `row_baselines [1, 9, 17, 25]`:

```
row 1 (team)   0-5     row 3 (proj)   16-21
row 2 (live)   8-13    row 4 (rank)   24-29
                       row 30 dark, bar at row 31
```

Layout rules that follow:

- A text row costs **6 lit rows**; rows sit **8 apart** to keep 2 dark rows
  between them.
- **One dark row reads as intra-character spacing, not separation.** A visible
  gap needs 2+ dark rows.
- Four text rows plus a 1px bar fill all 32 rows exactly. A bigger gap or a
  taller bar costs a whole text row — `LAYOUTS` in `tools/preview.py` has
  `compact` (3 rows, 2px bar) and `compact-thick` (3 rows, 4px bar) ready to
  compare; `display.py` supports them via `show_team_names: False`.
- `top_margin: 3` wastes row 0 and fuses the bar to the rank row. `2` is right.
- Font `board/fonts/5x7.bdf`: 5px advance, glyphs 4 wide plus a blank column, so
  `"102.3"` is exactly 25px. Text is placed by `.x` (left) or right-aligned to
  `width - 1 - bounding_box[2]`.

`tests/test_preview.py` pins the preview's output to the rows measured on the
device. If that test fails, the model drifted — re-measure, don't adjust it.

## ESPN API

League **252353**, team **6** (`KIER`). No API key; `lm-api-reads.fantasy.espn.com`.

| View | Size | Notes |
|---|---|---|
| `mMatchupScore` + `mTeam` | 260 KB | **what we use**: has `winProbability` and `matchupPeriodId` |
| `mScoreboard` | 343 KB | same matchup objects but `winProbability` is **absent**, not null |
| `+ mRoster` | 2.4 MB | rosters, unused; would be needed for players-yet-to-play counts |

- **`winProbability` is the FantasyCast number** (0.54 = 54%). It only appears in
  `mMatchupScore`. This is why it looks like the API doesn't expose it.
- Only the **current matchup period** carries `totalPointsLive` /
  `totalProjectedPointsLive`. Filter on `matchupPeriodId ==
  status.currentMatchupPeriod` rather than relying on that.
- These views have **no top-level `scoringPeriodId`**; use
  `status.currentMatchupPeriod` for the week.
- A 0.0 score is falsy — `x or 0` turns it into int `0` and the panel shows `0`
  instead of `0.0`. Use `float(... or 0.0)`.
- Season rolls over in March (`current_season`), so nothing needs editing yearly.

**Open question:** whether `winProbability` updates *during* a game or is set
pregame and frozen. Unverified — everything was pregame when it was added. Check
during a Thursday/Sunday game.

## Debugging the board over serial

On success `code.py` prints nothing; only errors reach the console. Silence plus
a rendered panel means it is working.

Reading the console: after any reload the USB CDC re-enumerates and a held fd
dies with `OSError: [Errno 6] Device not configured`. Loop and reopen:

```python
fd = os.open('/dev/cu.usbmodem101', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
os.write(fd, b'\x03')  # Ctrl-C -> REPL
os.write(fd, b'\x04')  # Ctrl-D -> reload code.py
# on OSError: close, sleep 1, reopen
```

To measure anything about the display, drive the REPL and inspect live objects —
this is how the row geometry above was settled:

```python
b = FantasyBoard(cfg); b.render_pair(L, R)
bm, tg = b.lab_rank_l._bitmap, b.lab_rank_l._tilegrid
[r for r in range(bm.height) if any(bm[c, r] for c in range(bm.width))]
```

Note the REPL disables auto-reload, so send Ctrl-D when finished or the board
sits idle at the prompt.

## Gotchas

- **Never `rsync --delete` or `--delete-excluded` to CIRCUITPY.** It would erase
  `lib/` and `settings.toml`, which are not in the repo. `make board` is safe.
- macOS writes `._*` AppleDouble files onto the FAT volume. `make board` sets
  `COPYFILE_DISABLE=1` and runs `dot_clean`.
- `settings.toml` holds Wi-Fi credentials and `SCOREBOARD_URL`; it lives only on
  the board and is gitignored. `board/settings.toml.example` is the template.
  **Never write a password into it** — ask the user to fill that line in.
- `circup` resolves dependencies itself; `board/requirements.txt` lists only the
  four top-level modules.
- The server logs one line per ESPN fetch and nothing per request, so an absence
  of logs does not mean the board is not polling. Requests are milliseconds long,
  so sampling `ss` on k5aux will usually miss them.

## Conventions

- Server and tests are **standard library only** — no venv, no pip on the Pi, and
  the Dockerfile installs nothing.
- Board code targets CircuitPython, whose f-string support is partial; the board
  files use `"{}".format(...)` throughout, and catch broadly so the panel never
  goes dark.
- Failure is always visible: status screens (`WIFI`, `NO WIFI`, `NO DATA`), a
  stale dot at the top-right corner, watchdog reset, `supervisor.reload()` on
  fatal errors.
- Deployment mirrors `majorpool` on k5aux (`~/services/<name>/`, Docker Compose,
  `restart: unless-stopped`). Homelab docs live in `~/Developer/homelab`, under
  `devices/k5aux/`.
