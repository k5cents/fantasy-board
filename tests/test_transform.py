"""Tests for the scoreboard server: transform, schedule windows, cache behavior."""

import copy
import json
import os
import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import app  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "espn_week.json")
ZONE = ZoneInfo("America/New_York")

# Team 6 (KIER) plays team 4 (BILL) in the fixture
US, THEM = 6, 4


def load():
    with open(FIXTURE) as f:
        return json.load(f)


class TestTransform(unittest.TestCase):
    def setUp(self):
        self.dat = load()
        self.rows = app.transform(self.dat, US)

    def test_returns_our_matchup_with_us_first(self):
        self.assertEqual(len(self.rows), 2)
        self.assertEqual(self.rows[0]["team_id"], US)
        self.assertEqual(self.rows[0]["team_abbrev"], "KIER")
        self.assertEqual(self.rows[1]["team_id"], THEM)

    def test_output_keys(self):
        expected = {
            "team_id", "team_abbrev", "live_points", "live_diff", "proj_points",
            "proj_diff", "bonus_win", "bonus_diff", "score_rank", "match_win",
            "current_wins",
        }
        for row in self.rows:
            self.assertEqual(set(row), expected)

    def test_points_stay_floats_at_zero(self):
        """A 0.0 score must render as "0.0", not "0", before kickoff."""
        for row in self.rows:
            for key in ("live_points", "live_diff", "proj_points", "proj_diff"):
                self.assertIsInstance(row[key], float, key)
        self.assertEqual(self.rows[0]["live_points"], 0.0)

    def test_diffs_are_symmetric(self):
        us, them = self.rows
        self.assertEqual(us["live_diff"], -them["live_diff"])
        self.assertEqual(us["proj_diff"], -them["proj_diff"])
        self.assertEqual(
            us["proj_diff"], round(us["proj_points"] - them["proj_points"], 1)
        )

    def test_live_diff_tracks_live_points(self):
        dat = copy.deepcopy(self.dat)
        for game in dat["schedule"]:
            for side in ("home", "away"):
                if game[side].get("teamId") == US:
                    game[side]["totalPointsLive"] = 80.0
                elif game[side].get("teamId") == THEM:
                    game[side]["totalPointsLive"] = 65.5
        us, them = app.transform(dat, US)
        self.assertEqual(us["live_points"], 80.0)
        self.assertEqual(us["live_diff"], 14.5)
        self.assertEqual(them["live_diff"], -14.5)

    def test_rank_is_dense_and_descending(self):
        """Ranks span the whole league, not just our matchup."""
        proj = []
        for game in self.dat["schedule"]:
            for side in ("home", "away"):
                if "totalProjectedPointsLive" in game[side]:
                    proj.append(round(game[side]["totalProjectedPointsLive"], 1))
        ranked = sorted(set(proj), reverse=True)
        self.assertEqual(len(proj), 10)
        for row in self.rows:
            self.assertEqual(row["score_rank"], ranked.index(row["proj_points"]) + 1)
        best = app.transform(self.dat, self.top_team(ranked[0]))
        self.assertEqual(best[0]["score_rank"], 1)

    def top_team(self, points):
        for game in self.dat["schedule"]:
            for side in ("home", "away"):
                team = game[side]
                if round(team.get("totalProjectedPointsLive", -1), 1) == points:
                    return team["teamId"]
        raise AssertionError("no team with %s projected" % points)

    def test_ties_share_a_rank(self):
        dat = copy.deepcopy(self.dat)
        for game in dat["schedule"]:
            for side in ("home", "away"):
                if "totalProjectedPointsLive" in game[side]:
                    game[side]["totalProjectedPointsLive"] = 100.0
        rows = app.transform(dat, US)
        self.assertEqual([r["score_rank"] for r in rows], [1, 1])
        self.assertEqual([r["match_win"] for r in rows], [1, 1])
        self.assertEqual([r["bonus_win"] for r in rows], [1, 1])

    def test_match_win_goes_to_the_projected_leader(self):
        us, them = self.rows
        leader, trailer = (us, them) if us["proj_points"] > them["proj_points"] else (them, us)
        self.assertEqual(leader["match_win"], 1)
        self.assertEqual(trailer["match_win"], 0)

    def test_bonus_win_is_top_half_of_the_league(self):
        winners = 0
        for team in (t["id"] for t in self.dat["teams"]):
            rows = app.transform(self.dat, team)
            if rows:
                winners += rows[0]["bonus_win"]
        self.assertEqual(winners, app.BONUS_PLACES)

    def test_games_without_live_projections_are_ignored(self):
        """Past and future weeks are in the schedule but carry no live projections."""
        self.assertTrue(
            any("totalProjectedPointsLive" not in g["home"] for g in self.dat["schedule"])
        )
        ids = {r["team_id"] for r in self.rows}
        self.assertEqual(ids, {US, THEM})

    def test_unknown_team_returns_nothing(self):
        self.assertEqual(app.transform(self.dat, 999), [])

    def test_offseason_payload_returns_nothing(self):
        dat = copy.deepcopy(self.dat)
        for game in dat["schedule"]:
            for side in ("home", "away"):
                game[side].pop("totalProjectedPointsLive", None)
        self.assertEqual(app.transform(dat, US), [])


class TestPayload(unittest.TestCase):
    def test_ok_payload(self):
        payload = app.build_payload(load(), 2026, "2026-09-15T18:00:00-04:00")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["week"], 2)
        self.assertEqual(payload["season"], 2026)
        self.assertEqual(len(payload["scoreboard"]), 2)

    def test_error_payload_when_no_matchup(self):
        dat = load()
        dat["schedule"] = []
        payload = app.build_payload(dat, 2026, "2026-09-15T18:00:00-04:00")
        self.assertEqual(payload["status"], "error")
        self.assertNotIn("scoreboard", payload)


class TestSchedule(unittest.TestCase):
    def at(self, *args):
        return datetime(*args, tzinfo=ZONE)

    def test_quiet_hours(self):
        self.assertTrue(app.is_quiet_hours(self.at(2026, 9, 15, 0, 0)))
        self.assertTrue(app.is_quiet_hours(self.at(2026, 9, 15, 7, 59)))
        self.assertFalse(app.is_quiet_hours(self.at(2026, 9, 15, 8, 0)))
        self.assertFalse(app.is_quiet_hours(self.at(2026, 9, 15, 23, 0)))

    def test_gametime_windows(self):
        # Thu 2026-09-17, Sun 2026-09-20, Mon 2026-09-21
        self.assertTrue(app.is_gametime(self.at(2026, 9, 17, 19, 0)))
        self.assertFalse(app.is_gametime(self.at(2026, 9, 17, 18, 59)))
        self.assertTrue(app.is_gametime(self.at(2026, 9, 20, 12, 0)))
        self.assertFalse(app.is_gametime(self.at(2026, 9, 20, 11, 59)))
        self.assertTrue(app.is_gametime(self.at(2026, 9, 21, 22, 30)))
        # Tuesday is never gametime
        self.assertFalse(app.is_gametime(self.at(2026, 9, 15, 20, 0)))

    def test_ttl_matches_window(self):
        self.assertEqual(app.cache_ttl(self.at(2026, 9, 20, 13, 0)), app.GAME_TTL)
        self.assertEqual(app.cache_ttl(self.at(2026, 9, 15, 13, 0)), app.IDLE_TTL)

    def test_season_rolls_over_in_march(self):
        self.assertEqual(app.current_season(self.at(2026, 9, 15, 12, 0)), 2026)
        self.assertEqual(app.current_season(self.at(2027, 1, 5, 12, 0)), 2026)
        self.assertEqual(app.current_season(self.at(2027, 3, 1, 12, 0)), 2027)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.dat = load()
        self.calls = []
        self.real_fetch = app.fetch_league
        app.fetch_league = self.fake_fetch
        self.board = app.Scoreboard()
        self.fail_with = None

    def tearDown(self):
        app.fetch_league = self.real_fetch

    def fake_fetch(self, *args, **kwargs):
        self.calls.append(args)
        if self.fail_with:
            raise self.fail_with
        return self.dat, "2026-09-15T18:00:00-04:00"

    def test_sleep_during_quiet_hours_without_fetching(self):
        payload = self.board.get(datetime(2026, 9, 15, 3, 0, tzinfo=ZONE))
        self.assertEqual(payload, {"status": "sleep", "timestamp": "2026-09-15T03:00:00-04:00"})
        self.assertEqual(self.calls, [])

    def test_second_request_inside_ttl_is_served_from_cache(self):
        now = datetime(2026, 9, 15, 12, 0, tzinfo=ZONE)
        first = self.board.get(now)
        second = self.board.get(now)
        self.assertEqual(len(self.calls), 1)
        self.assertIs(first, second)
        self.assertEqual(first["status"], "ok")

    def test_failure_serves_last_good_payload_marked_stale(self):
        now = datetime(2026, 9, 15, 12, 0, tzinfo=ZONE)
        good = self.board.get(now)
        self.board._fetched_at = 0  # force a refresh
        self.fail_with = OSError("espn is down")
        stale = self.board.get(now)
        self.assertTrue(stale["stale"])
        self.assertEqual(stale["scoreboard"], good["scoreboard"])
        self.assertEqual(stale["timestamp"], good["timestamp"])
        self.assertNotIn("stale", good, "cached payload must not be mutated")

    def test_failure_with_no_cache_is_an_error_payload(self):
        self.fail_with = OSError("espn is down")
        payload = self.board.get(datetime(2026, 9, 15, 12, 0, tzinfo=ZONE))
        self.assertEqual(payload["status"], "error")
        self.assertIn("espn is down", payload["detail"])


if __name__ == "__main__":
    unittest.main()
