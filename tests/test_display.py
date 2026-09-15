"""
Tests for the board renderer, with the CircuitPython display stack stubbed out.

Covers the win probability bar geometry and the state-dependent second row --
the parts that are hard to verify by squinting at a 64x32 panel.
"""

import os
import sys
import types
import unittest

BOARD = os.path.join(os.path.dirname(__file__), "..", "board")


# ---------------------- CircuitPython stubs --------------------------------


class FakeBitmap:
    def __init__(self, width, height, colors):
        self.width, self.height = width, height
        self.pixels = {}

    def __setitem__(self, xy, value):
        self.pixels[xy] = value

    def __getitem__(self, xy):
        return self.pixels.get(xy, 0)

    def row(self, y=0):
        return [self[x, y] for x in range(self.width)]


class FakePalette(list):
    def __init__(self, n):
        super().__init__([0] * n)

    def make_transparent(self, i):
        pass


class FakeGroup(list):
    def __init__(self, x=0, y=0):
        super().__init__()
        self.x, self.y = x, y


class FakeTileGrid:
    def __init__(self, bitmap, pixel_shader=None, x=0, y=0):
        self.bitmap, self.pixel_shader = bitmap, pixel_shader
        self.x, self.y = x, y
        self.hidden = False


class FakeLabel:
    def __init__(self, font, text="", color=0):
        self.font, self._text, self.color = font, text, color
        self.x = self.y = 0

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

    @property
    def bounding_box(self):
        return (0, 0, len(self._text) * 6, 7)


class FakeDisplay:
    def __init__(self):
        self.brightness = 0.0
        self.auto_refresh = True
        self.root_group = None
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1


class FakeMatrix:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.display = FakeDisplay()


def install_stubs():
    displayio = types.ModuleType("displayio")
    displayio.Bitmap = FakeBitmap
    displayio.Palette = FakePalette
    displayio.Group = FakeGroup
    displayio.TileGrid = FakeTileGrid

    matrix_mod = types.ModuleType("adafruit_matrixportal.matrix")
    matrix_mod.Matrix = FakeMatrix
    portal = types.ModuleType("adafruit_matrixportal")
    portal.matrix = matrix_mod

    label_mod = types.ModuleType("adafruit_display_text.bitmap_label")
    label_mod.Label = FakeLabel
    text_pkg = types.ModuleType("adafruit_display_text")
    text_pkg.bitmap_label = label_mod

    font_mod = types.ModuleType("adafruit_bitmap_font.bitmap_font")
    font_mod.load_font = lambda path: "font:" + path
    font_pkg = types.ModuleType("adafruit_bitmap_font")
    font_pkg.bitmap_font = font_mod

    sys.modules.update({
        "displayio": displayio,
        "adafruit_matrixportal": portal,
        "adafruit_matrixportal.matrix": matrix_mod,
        "adafruit_display_text": text_pkg,
        "adafruit_display_text.bitmap_label": label_mod,
        "adafruit_bitmap_font": font_pkg,
        "adafruit_bitmap_font.bitmap_font": font_mod,
    })


install_stubs()
sys.path.insert(0, BOARD)

from config import config as cfg  # noqa: E402
from display import FantasyBoard  # noqa: E402


def team(abbrev, live, proj, rank, prob):
    return {
        "team_abbrev": abbrev, "live_points": live, "proj_points": proj,
        "score_rank": rank, "win_prob": prob,
    }


class TestLayout(unittest.TestCase):
    def test_rows_and_bar_fit_the_panel(self):
        """
        The text rows plus the bar must land inside 32px with no overlap.

        Lit pixels run y-3 .. y+2, measured by reading a label's own bitmap on
        the board: the glyph's blank row sits at the top of the box, not the
        bottom. A descender would reach y+3, which no row here uses.
        """
        height = cfg['matrix_height']
        top = cfg['top_margin']
        spans = [(b + top - 3, b + top + 2) for b in cfg['row_baselines']]

        self.assertGreaterEqual(spans[0][0], 0, "top row clips")
        bar_y = cfg['wp_bar_y']
        self.assertLess(spans[-1][1], bar_y, "bottom row collides with the bar")
        self.assertLess(bar_y + cfg['wp_bar_height'] - 1, height, "bar falls off the panel")
        for (_, end), (start, _) in zip(spans, spans[1:]):
            self.assertLess(end, start, "rows overlap")

    def test_layout_leaves_a_dark_row_above_the_bar(self):
        """
        A single dark row reads as intra-character spacing, not separation --
        but with no dark row at all the bar fuses to the rank row, which is
        what top_margin 3 did on the real panel.
        """
        top = cfg['top_margin']
        last_lit = cfg['row_baselines'][-1] + top + 2
        self.assertLess(last_lit, cfg['wp_bar_y'], "bar touches the text")
        self.assertGreaterEqual(cfg['row_baselines'][0] + top - 3, 0, "row 0 clipped")

    def test_top_row_is_not_wasted(self):
        """Row 0 should carry pixels; margin 3 left it dark for no reason."""
        self.assertEqual(cfg['row_baselines'][0] + cfg['top_margin'] - 3, 0)


class TestWinProbBar(unittest.TestCase):
    def setUp(self):
        self.board = FantasyBoard(cfg)
        self.half = cfg['matrix_width'] // 2

    def lit(self):
        return self.board.bar_bitmap.row(0)

    def test_even_odds_fill_the_middle_half(self):
        self.board.render_win_prob(50, 50)
        row = self.lit()
        self.assertEqual(row[:16], [0] * 16)
        self.assertEqual(row[16:32], [1] * 16)
        self.assertEqual(row[32:48], [2] * 16)
        self.assertEqual(row[48:], [0] * 16)

    def test_lopsided_odds_slide_the_block(self):
        """80/20 lights 80% of the left half and 20% of the right."""
        self.board.render_win_prob(80, 20)
        row = self.lit()
        self.assertEqual(row.count(1), 26)  # round(0.8 * 32)
        self.assertEqual(row.count(2), 6)   # round(0.2 * 32)
        # both halves fill outward from the center, so the lit run is contiguous
        first, last = row.index(1), len(row) - 1 - row[::-1].index(2)
        self.assertEqual(row[first:last + 1].count(0), 0)

    def test_bar_is_always_anchored_at_the_center(self):
        for left in (0, 25, 46, 54, 73, 100):
            self.board.render_win_prob(left, 100 - left)
            row = self.lit()
            self.assertEqual(row[self.half - 1] if left else 0, 1 if left else 0)
            self.assertEqual(row[self.half] if left < 100 else 0, 2 if left < 100 else 0)

    def test_favored_side_is_green(self):
        self.board.render_win_prob(54, 46)
        self.assertEqual(self.board.bar_palette[1], cfg['lead_color'])
        self.assertEqual(self.board.bar_palette[2], cfg['trail_color'])

        self.board.render_win_prob(46, 54)
        self.assertEqual(self.board.bar_palette[1], cfg['trail_color'])
        self.assertEqual(self.board.bar_palette[2], cfg['lead_color'])

        self.board.render_win_prob(50, 50)
        self.assertEqual(self.board.bar_palette[1], cfg['tie_color'])
        self.assertEqual(self.board.bar_palette[2], cfg['tie_color'])

    def test_certainty_fills_one_half_only(self):
        self.board.render_win_prob(100, 0)
        row = self.lit()
        self.assertEqual(row[:self.half], [1] * self.half)
        self.assertEqual(row[self.half:], [0] * self.half)

    def test_missing_probability_hides_the_bar(self):
        self.board.render_win_prob(54, 46)
        self.assertFalse(self.board.bar.hidden)
        self.board.render_win_prob(None, None)
        self.assertTrue(self.board.bar.hidden)

    def test_status_screen_hides_the_bar(self):
        self.board.render_win_prob(54, 46)
        self.board.status("NO DATA")
        self.assertTrue(self.board.bar.hidden)


class TestRowTwo(unittest.TestCase):
    def setUp(self):
        self.board = FantasyBoard(cfg)

    def test_pregame_shows_win_percent(self):
        self.board.render_pair(
            team("KIER", 0.0, 102.3, 1, 54), team("BILL", 0.0, 95.9, 8, 46)
        )
        self.assertEqual(self.board.lab_live_l.text, "54%")
        self.assertEqual(self.board.lab_live_r.text, "46%")

    def test_live_points_take_over_once_anyone_scores(self):
        self.board.render_pair(
            team("KIER", 0.0, 102.3, 1, 54), team("BILL", 6.4, 95.9, 8, 46)
        )
        self.assertEqual(self.board.lab_live_l.text, "0.0")
        self.assertEqual(self.board.lab_live_r.text, "6.4")

    def test_pregame_without_probability_falls_back_to_points(self):
        self.board.render_pair(
            team("KIER", 0.0, 102.3, 1, None), team("BILL", 0.0, 95.9, 8, None)
        )
        self.assertEqual(self.board.lab_live_l.text, "0.0")
        self.assertTrue(self.board.bar.hidden)

    def test_right_column_stays_flush_with_the_edge(self):
        self.board.render_pair(
            team("KIER", 0.0, 102.3, 1, 54), team("BILL", 0.0, 95.9, 8, 46)
        )
        right_edge = cfg['matrix_width'] - 1
        for lbl in (self.board.lab_team_r, self.board.lab_live_r,
                    self.board.lab_proj_r, self.board.lab_rank_r):
            self.assertEqual(lbl.x + lbl.bounding_box[2], right_edge)


if __name__ == "__main__":
    unittest.main()
