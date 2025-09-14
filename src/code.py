# code.py
import time
import supervisor
from config import config as cfg
from score_board import FantasyBoard
from read_json import fetch_scores_from_file, fetch_scores_from_http
from secrets import secrets

# --- Disable autoreload so JSON updates don't reset the board ---
try:
    supervisor.disable_autoreload()
except AttributeError:
    supervisor.runtime.autoreload = False

# --- Optional Wi-Fi setup (only if using HTTP mode) ---
def _wifi_connect():
    import wifi
    import ipaddress

    ssid = secrets.get("ssid")
    password = secrets.get("password")
    if not ssid or not password:
        raise RuntimeError("Missing Wi-Fi credentials in secrets.py")

    print("Connecting to", ssid, "...")
    wifi.radio.connect(ssid, password)
    print("Connected, IP address:", wifi.radio.ipv4_address)

try:
    supervisor.disable_autoreload()
except AttributeError:
    supervisor.runtime.autoreload = False

def main():
    mode = cfg.get("mode", "FANTASY_LOCAL")
    path = cfg.get("local_json_path", "/scoreboard.json")
    url = cfg.get("http_url")
    interval = cfg.get("refresh_interval", 60)

    if mode == "FANTASY_HTTP":
        _wifi_connect()

    board = FantasyBoard(cfg)
    board.banner(cfg.get("banner_left"), cfg.get("banner_right"))

    cache_pair = None

    while True:
        try:
            if mode == "FANTASY_HTTP":
                left, right = fetch_scores_from_http(url)
            else:
                left, right = fetch_scores_from_file(path)

            cache_pair = (left, right)
            board.render_pair(left, right)

        except Exception as e:
            print("Error fetching scores:", e)
            # Keep displaying the last good frame if available
            if cache_pair:
                board.render_pair(cache_pair[0], cache_pair[1])

        time.sleep(interval)

if __name__ == "__main__":
    main()