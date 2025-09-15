# code.py — Wi-Fi fetch + server-signaled quiet hours (status:"sleep")

import time
import supervisor

from config import config as cfg
from score_board import FantasyBoard

# HTTP fetcher + session hook
import read_json as rj
from read_json import fetch_scores_from_http

# MatrixPortal Wi-Fi helper
from adafruit_matrixportal.network import Network
import adafruit_requests as requests


def _wifi_connect():
    """
    Bring up Wi-Fi via MatrixPortal's Network helper.
    Uses settings.toml creds; exposes a ready adafruit_requests.Session at net.requests.
    """
    # Optional: avoid auto-reload resets on file changes
    try:
        supervisor.disable_autoreload()
    except Exception:
        pass

    net = Network(status_neopixel=None)
    print("Connecting to Wi-Fi...")
    net.connect()
    print("Connected; IP:", net.ip_address)

    # Hand both the symbol and the session to read_json so its guard passes
    rj.requests = requests
    rj._session = net.requests
    return net


def main():
    url = cfg.get("http_url")
    if not url:
        raise RuntimeError("Missing 'http_url' in config")

    interval = cfg.get("refresh_interval", 5)

    _wifi_connect()

    board = FantasyBoard(cfg)
    board.banner(cfg.get("banner_left"), cfg.get("banner_right"))
    normal_brightness = cfg.get("brightness", 0.2)

    cache_pair = None

    while True:
        try:
            # Ask for meta so we can honor server "sleep"
            left, right, meta = fetch_scores_from_http(url, return_meta=True)

            if isinstance(meta, dict) and meta.get("status") == "sleep":
                # Quiet hours from server: blank + dim to 0, then back off polling
                if board.display.brightness != 0:
                    board.display.brightness = 0
                    board.banner("", "")
                time.sleep(300)  # check again in ~5 minutes
                continue
            else:
                # Ensure brightness is restored when active again
                if board.display.brightness == 0:
                    board.display.brightness = normal_brightness

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