# read_json.py
# Minimal JSON loading + validation for the MatrixPortal scoreboard.
# Supports reading from local filesystem or over Wi-Fi (HTTP) on CircuitPython.

import json

# ---- Validation ----
_MIN_REQUIRED = ("team_abbrev", "live_points", "proj_points", "score_rank")

def _validate_team(team):
    for k in _MIN_REQUIRED:
        if k not in team:
            raise ValueError(f"Missing '{k}' in team object: {team}")

def _extract_meta(data):
    if isinstance(data, dict):
        return {k: data[k] for k in ("status", "league", "season", "week", "timestamp", "sleep") if k in data}
    return {}

def _handle_sleep_if_present(data, return_meta):
    """
    If the payload is a dict with {"status":"sleep"}, return (None, None, meta or None)
    so callers can blank the display without raising.
    """
    if isinstance(data, dict) and str(data.get("status", "")).lower() == "sleep":
        meta = _extract_meta(data) if return_meta else None
        return True, (None, None, meta) if return_meta else (None, None)
    return False, None

# ---- Local file path ----
def fetch_scores_from_file(path="/scoreboard.json", return_meta=False):
    with open(path, "r") as f:
        data = json.load(f)

    # Quiet-hours / sleep payload
    is_sleep, ret = _handle_sleep_if_present(data, return_meta)
    if is_sleep:
        return ret

    # Normalize "teams" to a list of exactly two dicts
    if isinstance(data, dict):
        teams = data.get("scoreboard", [])
    elif isinstance(data, list):
        teams = data
    else:
        raise ValueError("Unexpected JSON format (dict or list expected)")

    if not isinstance(teams, list) or len(teams) != 2:
        raise ValueError("Expected exactly two teams in 'scoreboard'")

    left, right = teams[0], teams[1]
    _validate_team(left)
    _validate_team(right)

    if return_meta and isinstance(data, dict):
        meta = _extract_meta(data)
        return left, right, meta

    return left, right

# ---- HTTP path (CircuitPython) ----
# Only available on-device where the CircuitPython network stack exists.
try:
    import wifi
    import socketpool
    import ssl
    import adafruit_requests as requests
except Exception:
    # Allow this module to be imported on CPython (your Pi / desktop) without errors.
    requests = None

_session = None  # cached adafruit_requests Session

def _get_session():
    """
    Lazily return a requests.Session.
    If code.py has already injected _session (e.g., Network.requests), we use that.
    Otherwise, create one from wifi.radio (CircuitPython only).
    """
    global _session
    if _session is not None:
        return _session
    pool = socketpool.SocketPool(wifi.radio)
    _session = requests.Session(pool, ssl.create_default_context())
    return _session

def fetch_scores_from_http(url, return_meta=False, timeout=5):
    """
    Fetch scoreboard JSON from an HTTP(S) endpoint (MatrixPortal over Wi-Fi).
    - url: e.g., "http://<pi-ip>:8000/scoreboard.json"
    - return_meta: include top-level metadata if present
    - timeout: seconds for the HTTP request
    """
    if requests is None:
        raise RuntimeError("HTTP fetch requires CircuitPython (adafruit_requests)")

    sess = _get_session()
    resp = sess.get(url, timeout=timeout)
    try:
        data = resp.json()
    finally:
        resp.close()

    # Quiet-hours / sleep payload
    is_sleep, ret = _handle_sleep_if_present(data, return_meta)
    if is_sleep:
        return ret

    # Normalize "teams" to a list of exactly two dicts
    if isinstance(data, dict):
        teams = data.get("scoreboard", [])
    elif isinstance(data, list):
        teams = data
    else:
        raise ValueError("Unexpected JSON format (dict or list expected)")

    if not isinstance(teams, list) or len(teams) != 2:
        raise ValueError("Expected exactly two teams in 'scoreboard'")

    left, right = teams[0], teams[1]
    _validate_team(left)
    _validate_team(right)

    if return_meta and isinstance(data, dict):
        meta = _extract_meta(data)
        return left, right, meta

    return left, right