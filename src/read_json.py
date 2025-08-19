# metro_api.py
import json

def fetch_scores_from_file(path="/scoreboard.json"):
    """
    Reads /scoreboard.json that looks like:
    {
      "status": [...],
      "league": [...],
      "season": [...],
      "timestamp": ["..."],
      "scoreboard": [ {team...}, {team...} ]
    }
    Returns (left_team, right_team).
    """
    with open(path, "r") as f:
        data = json.load(f)

    # Accept either the new wrapped object or the old top-level list
    if isinstance(data, dict):
        teams = data.get("scoreboard", [])
    elif isinstance(data, list):
        teams = data
    else:
        raise ValueError("Unexpected JSON format")

    if not isinstance(teams, list) or len(teams) != 2:
        raise ValueError("Expected exactly two teams in 'scoreboard'")

    left, right = teams[0], teams[1]

    # Minimal field check
    required = ("team_abbrev", "live_points", "proj_points", "n_locked", "n_unlocked")
    for t in (left, right):
        for k in required:
            if k not in t:
                raise ValueError(f"Missing '{k}' in team object: {t}")

    return left, right
