# Fantasy Football Scoreboard

A homelab-style project that displays live fantasy football scores on an Adafruit MatrixPortal M4 + RGB LED matrix.  
The Raspberry Pi 5 scrapes and serves JSON over Wi-Fi, and the MatrixPortal polls it to render a clean, color-coded scoreboard.
The Raspberry Pi is required because the ESPN API returns too much data to be loaded into the memory of the MatrixPortal M4 board.

---

## Project Structure

```
.
├── pi/             # Raspberry Pi side (data fetch + serve)
│   ├── query_scores.py   # Fetches and formats JSON from ESPN APIs
│   ├── update_scores.sh  # Runs query, writes atomically to `www/scoreboard.json`
│   ├── scoreboard.log    # Log of updates/errors
│
├── src/            # CircuitPython side (MatrixPortal M4)
│   ├── code.py          # Main loop: Wi-Fi connect + fetch JSON + render
│   ├── config.py        # Display + runtime config (http_url, refresh_interval, colors)
│   ├── score_board.py   # Renderer: draws 2 teams, 4 rows
│   ├── read_json.py     # Minimal JSON fetcher/validator (HTTP only)
│   ├── secrets.py       # (deprecated; use settings.toml instead)
│
├── requirements.txt     # Python packages for the Pi side
├── lib.zip              # CircuitPython library bundle (subset needed for MatrixPortal)
└── README.md            # You are here
```

---

## How It Works

- **Pi 5 (`pi/`)**  
  - `query_scores.py` pulls matchup scores and projections, cleans them, and prints JSON.  
  - `update_scores.sh` runs the query, writes to a temp file, then atomically replaces `www/scoreboard.json`.  
  - Systemd timers run `update_scores.sh`:
    - **Gametime:** every minute (Thu night, Sun afternoon/evening, Mon night).  
    - **Off-hours:** on the half-hour, every 30 minutes.  
  - A simple `http.server` or systemd-managed Python server serves `www/scoreboard.json` on port 8000.

- **MatrixPortal M4 (`src/`)**  
  - `code.py`:
    - Connects to Wi-Fi via `Network` (uses `settings.toml` for SSID/PW).  
    - Polls `http_url` every `refresh_interval` seconds.  
    - Renders the two teams with `FantasyBoard`.  
  - `score_board.py`:  
    - 4 rows per team: team abbrev, live points, projected points (colored leader/trailer), projected rank (ordinal, green top-N / red bottom).  
  - `read_json.py`:  
    - Tiny HTTP fetcher + validator for expected JSON shape.  

---

## Setup

### 1. Raspberry Pi (server)
- Install dependencies:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Enable and start systemd service/timers for `update_scores.sh` and the HTTP server.  
- Verify JSON updates at:  
  ```bash
  curl http://<pi-ip>:8000/scoreboard.json | jq .
  ```

### 2. MatrixPortal (client)
- Flash CircuitPython 9.x to the MatrixPortal M4.  
- Copy `src/` contents to the CIRCUITPY root.  
- Unzip `lib.zip` into CIRCUITPY `lib/` (must include `adafruit_matrixportal`, `adafruit_portalbase`, `adafruit_requests`, `adafruit_bitmap_font`, `adafruit_display_text`, plus their deps).  
- Add `settings.toml` to CIRCUITPY root with Wi-Fi creds:
  ```toml
  CIRCUITPY_WIFI_SSID = "your-ssid"
  CIRCUITPY_WIFI_PASSWORD = "your-password"
  CIRCUITPY_TIMEZONE = "America/New_York"
  ```
- Press reset; the board should connect to Wi-Fi and begin displaying the matchup.