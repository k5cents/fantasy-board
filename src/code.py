import time
import supervisor
from config import config as cfg
from score_board import FantasyBoard
from read_json import fetch_scores_from_file

try:
    supervisor.disable_autoreload()
except AttributeError:
    supervisor.runtime.autoreload = False

def main():
    board = FantasyBoard(cfg)
    board.banner(cfg.get('banner_left'), cfg.get('banner_right'))

    cache_pair = None
    path = cfg['local_json_path']
    interval = cfg.get('refresh_interval', 60)

    while True:
        try:
            left, right = fetch_scores_from_file(path)
            cache_pair = (left, right)
            board.render_pair(left, right)
        except Exception:
            # Keep displaying the last good frame if available
            if cache_pair:
                board.render_pair(cache_pair[0], cache_pair[1])
        time.sleep(interval)

if __name__ == "__main__":
    main()
