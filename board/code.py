# code.py — MatrixPortal M4 fantasy scoreboard client.
#
# Boots the display first so failures are visible, connects to Wi-Fi, then polls
# the server (SCOREBOARD_URL in settings.toml) and renders the matchup.
# A watchdog resets the board if a fetch or the network stack ever wedges.

import os
import time
import supervisor
import microcontroller
from watchdog import WatchDogMode

from adafruit_matrixportal.network import Network

from config import config as cfg
from display import FantasyBoard

WATCHDOG_TIMEOUT = 16  # seconds; the SAMD51 hardware maximum, fed every loop and nap
REQUIRED_KEYS = ("team_abbrev", "live_points", "proj_points", "score_rank")


def start_watchdog():
    dog = microcontroller.watchdog
    try:
        dog.timeout = WATCHDOG_TIMEOUT
        dog.mode = WatchDogMode.RESET
        return dog
    except Exception as err:  # not fatal; the board just loses self-healing
        print("Watchdog unavailable:", err)
        return None


def nap(dog, seconds):
    """Sleep in small slices so the watchdog stays fed."""
    end = time.monotonic() + seconds
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        if dog:
            dog.feed()
        time.sleep(min(remaining, 5))


def connect(board, dog):
    """Bring up Wi-Fi, reporting progress on the panel."""
    net = Network(status_neopixel=None)
    delay = 5
    while True:
        try:
            board.status("WIFI")
            print("Connecting to Wi-Fi...")
            net.connect()
            print("Connected; IP:", net.ip_address)
            return net
        except Exception as err:
            print("Wi-Fi failed:", err)
            board.status("NO WIFI", cfg['trail_color'])
            nap(dog, delay)
            delay = min(delay * 2, 60)


def parse_payload(data):
    """
    Reduce a server payload to (status, left, right).

    status is "ok", "sleep", or "error"; teams are None unless status is "ok".
    """
    if not isinstance(data, dict):
        return "error", None, None

    status = data.get("status", "")
    if status == "sleep":
        return "sleep", None, None
    if status != "ok":
        return "error", None, None

    teams = data.get("scoreboard", [])
    if not isinstance(teams, list) or len(teams) != 2:
        return "error", None, None

    for team in teams:
        if not isinstance(team, dict):
            return "error", None, None
        for key in REQUIRED_KEYS:
            if key not in team:
                print("Missing", key, "in", team)
                return "error", None, None

    return "ok", teams[0], teams[1]


def main():
    dog = start_watchdog()

    board = FantasyBoard(cfg)
    board.status("BOOT")

    url = os.getenv("SCOREBOARD_URL")
    if not url:
        board.status("NO URL", cfg['trail_color'])
        raise RuntimeError("Missing SCOREBOARD_URL in settings.toml")

    net = connect(board, dog)

    interval = cfg.get('refresh_interval', 30)
    sleep_interval = cfg.get('sleep_interval', 300)
    stale_after = cfg.get('stale_after', 300)

    last_pair = None
    last_good = None  # time.monotonic() of the last fresh payload

    while True:
        if dog:
            dog.feed()

        wait = interval
        try:
            resp = net.requests.get(url, timeout=10)
            try:
                data = resp.json()
            finally:
                resp.close()

            status, left, right = parse_payload(data)

            if status == "sleep":
                board.set_awake(False)
                board.set_stale(False)
                last_good = time.monotonic()
                wait = sleep_interval

            elif status == "ok":
                board.set_awake(True)
                last_pair = (left, right)
                board.render_pair(left, right)
                if not data.get("stale"):
                    last_good = time.monotonic()
                board.set_stale(
                    bool(data.get("stale"))
                    or (last_good is not None and time.monotonic() - last_good > stale_after)
                )

            else:
                print("Server error payload:", data.get("detail"))
                board.set_awake(True)
                if last_pair:
                    board.set_stale(True)
                else:
                    board.status("NO DATA", cfg['trail_color'])

        except Exception as err:
            # Keep the last good frame if the network burps, but flag it
            print("Fetch/render error:", err)
            board.set_awake(True)
            if last_pair is None:
                board.status("NO DATA", cfg['trail_color'])
            elif last_good is None or time.monotonic() - last_good > stale_after:
                board.set_stale(True)

        nap(dog, wait)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        # Never leave the panel dead: log, pause, and restart the program
        print("Fatal error:", err)
        time.sleep(10)
        supervisor.reload()
