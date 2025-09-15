# code.py — always fetch over Wi-Fi using MatrixPortal Network helper

import time
import supervisor
import os

from config import config as cfg
from score_board import FantasyBoard

# Use the HTTP fetcher + module-level session hook
import read_json as rj
from read_json import fetch_scores_from_http

# Disable autoreload so background file writes don't reboot the board
# try:
#     supervisor.disable_autoreload()
# except AttributeError:
#    supervisor.runtime.autoreload = False

# High-level Wi-Fi helper for MatrixPortal (ESP32 AirLift)
from adafruit_matrixportal.network import Network
import adafruit_requests as requests


def _wifi_connect():
    """
    Bring up Wi-Fi via MatrixPortal's Network helper.
    Uses credentials from settings.toml (preferred) or secrets.py (deprecated).
    Exposes a ready-to-use adafruit_requests.Session at net.requests.
    """
    net = Network(status_neopixel=None)  # silence status LED
    print("Connecting to Wi-Fi...")
    net.connect()
    print("Connected; IP:", net.ip_address)

    # Hand both the symbol and the session to read_json so its guard passes
    rj.requests = requests          # satisfy "if requests is None" check
    rj._session = net.requests      # reuse one Session for all GETs
    return net


def main():
    url = cfg.get("http_url")
    if not url:
        raise RuntimeError("Missing 'http_url' in config")

    interval = cfg.get("refresh_interval", 5)

    _wifi_connect()

    board = FantasyBoard(cfg)
    board.banner(cfg.get("banner_left"), cfg.get("banner_right"))

    cache_pair = None

    while True:
        try:
            left, right = fetch_scores_from_http(url)
            cache_pair = (left, right)
            board.render_pair(left, right)
        except Exception as e:
            # Keep last good frame if the network burps; log the error
            print("Fetch/render error:", e)
            if cache_pair:
                board.render_pair(cache_pair[0], cache_pair[1])
        time.sleep(interval)


if __name__ == "__main__":
    main()