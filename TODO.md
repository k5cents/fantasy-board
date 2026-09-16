# Fantasy Board TODO

This document tracks **ideas, deferred work, and open questions** for the board.

- `README.md` defines **how it works today**
- `CLAUDE.md` defines **what we measured and must not re-discover**
- This file defines **what remains**

Forward-looking only; finished work lives in the git history.

---

## Display

- [ ] **Bottom row: margin to the bonus cutoff instead of the ordinal**
  - League scoring: 1 win for the matchup, plus 1 bonus win for the **top 5**
    projected scores. So the useful question is not "what rank am I" but "how
    far am I from the cutoff", which is also the median line in a 10-team league.
  - Show `bonus_diff` signed, e.g. `+4.2` / `-6.8`; green above the line, red
    below. Reading a green projection next to a red margin = winning the matchup
    but missing the bonus, which is the state that currently needs arithmetic.
  - **No server work:** `bonus_diff` is already in the payload and unused, and
    `BONUS_PLACES = 5` already matches the league rule.
  - Widths measured and safe: `+4.2` is 20px, `-12.3` 25px, `-102.4` 30px, all
    inside the 32px column (the ordinal was 15px).
  - Open sub-question: keep the ordinal anywhere, or is the margin enough?
    `10 -12.3` is 40px, so the two do not fit on one row together.

- [ ] **League-wide scores on the UP/DOWN button**
  - Hold UP to page through the other four matchups, release (or 10s) to snap
    back. On demand, never on a timer — a rotating board is unreadable when you
    want one number.
  - Server already ranks every team's projection; needs a `matchups` array in
    the payload plus a second render mode on the board.

- [ ] **Players yet to play** — `3 LEFT` vs `1 LEFT` during games
  - The old 2024 JSON had this as `n_locked` / `n_unlocked`; it was dropped in
    the Python port.
  - Needs the 2.4MB `mRoster` view, so fetch it **only inside game windows** and
    keep the cheap view otherwise.

- [ ] Alternate layouts if the team names ever come off the top row
  - `tools/preview.py --compare` renders `compact` (3 rows, 2px bar) and
    `compact-thick` (3 rows, 4px bar); `display.py` supports them through
    `show_team_names: False`. Decided against for now — names stay.

---

## Open questions

- [ ] **Does `winProbability` update during a live game, or is it set pregame
      and frozen?** Unverified: everything was pregame when it was added. Log
      the value each poll through a Thursday or Sunday game to find out. If it
      moves, it deserves more real estate; if not, the pregame row is its job.

---

## Ops

- [ ] Add an Uptime Kuma monitor (already running on k5aux) against
      `http://k5aux.lan:8000/healthz`.

---

## Known bugs

None open.
