"""
Tests for the preview renderer.

The clipping assertion is the important one: it drives the board's real layout
through a 64x32 frame and fails if any glyph or bar pixel lands off-panel, which
is exactly the mistake a 1px margin change makes and the eye does not catch.
"""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import preview  # noqa: E402


class TestPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.FantasyBoard, cls.font = preview.load_board()

    def frame_for(self, name):
        _, render = preview.SCENARIOS[name]
        return preview.render_frame(render, self.font, self.cfg, self.FantasyBoard)

    def test_no_scenario_draws_off_panel(self):
        for name in preview.SCENARIOS:
            frame = self.frame_for(name)
            self.assertEqual(frame.clipped, 0, "%s clips off the panel" % name)

    def test_text_fills_the_panel_without_spilling(self):
        """
        The four rows should start at row 0 and end just above the bar.

        The font's 7px box has a blank bottom row, so lit text stops at y=29 and
        row 30 stays dark, separating the rank row from the bar at y=31.
        """
        frame = self.frame_for("pregame")
        rows = {y for (_, y) in frame.pixels}
        self.assertIn(0, rows, "top row is unused; the margin is too low")
        self.assertIn(29, rows, "rank row is not at the bottom of the text block")
        self.assertNotIn(30, rows, "row 30 should stay dark between text and bar")
        self.assertIn(31, rows, "win probability bar is missing")

    def test_bar_occupies_only_the_last_row(self):
        frame = self.frame_for("pregame")
        bar = [(x, y) for (x, y) in frame.pixels if y == 31]
        self.assertTrue(bar)
        xs = sorted(x for x, _ in bar)
        self.assertEqual(xs, list(range(min(xs), max(xs) + 1)), "bar has gaps")

    def test_columns_do_not_overlap(self):
        """Left and right columns must never share a column of pixels."""
        frame = self.frame_for("blowout")
        left = {x for (x, y) in frame.pixels if y < 31 and x < 32}
        right = {x for (x, y) in frame.pixels if y < 31 and x >= 32}
        self.assertTrue(left and right)
        self.assertLess(max(left), min(right), "columns collide")

    def test_writes_a_real_png(self):
        frame = self.frame_for("live")
        width, height, rows = preview.render_leds([frame], scale=6)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.png")
            preview.write_png(path, width, height, rows)
            data = open(path, "rb").read()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (width, height))
        self.assertEqual((width, height), (64 * 6, 32 * 6))

    def test_font_matches_the_device_metrics(self):
        """Measured on the board: '102.3' reports width 25, height 7."""
        self.assertEqual(self.font.text_width("102.3"), 25)
        self.assertEqual(self.font.text_width("8"), 5)
        top, bottom = self.font.vertical_extent("8")
        self.assertEqual(bottom - top + 1, 7)


if __name__ == "__main__":
    unittest.main()
