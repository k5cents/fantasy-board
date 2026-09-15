# ---- FantasyBoard: 2-column, 4-row scoreboard for 64x32 ----
import displayio
from adafruit_matrixportal.matrix import Matrix
from adafruit_display_text import bitmap_label as label
from adafruit_bitmap_font import bitmap_font


class FantasyBoard:
    """
    Renders two teams with 4 rows:
      Row 1: team_abbrev         team_abbrev
      Row 2: live_points         live_points
      Row 3: proj_points         proj_points (colored: leader/trailer/tie)
      Row 4: projected rank      projected rank (ordinal; green for top-N)

    Also renders single-line status screens and a corner dot for stale data.
    Expects numbers already rounded by the server.
    """

    def __init__(self, cfg_dict):
        self.cfg = cfg_dict

        self.matrix = Matrix(
            width=self.cfg['matrix_width'],
            height=self.cfg['matrix_height'],
            serpentine=True,
            bit_depth=4,
            rotation=self.cfg.get('rotation', 0)
        )
        self.display = self.matrix.display
        self.display.brightness = self.cfg['brightness']
        self.display.auto_refresh = False

        self.font = bitmap_font.load_font(self.cfg['font_path'])

        # root holds the offset content group plus the stale dot at true (0, 0)
        self.root = displayio.Group()
        self.group = displayio.Group(x=0, y=self.cfg.get('top_margin', 0))
        self.root.append(self.group)

        def mk(text, x, y, color):
            t = label.Label(self.font, text=text, color=color)
            t.x = x
            t.y = y
            return t

        left_x = self.cfg['left_col_x']
        rows = self.cfg['row_baselines']
        bright = self.cfg['text_color']
        dim = self.cfg['dim_text_color']

        # Left column (left-aligned)
        self.lab_team_l = mk("", left_x, rows[0], bright)
        self.lab_live_l = mk("", left_x, rows[1], bright)
        self.lab_proj_l = mk("", left_x, rows[2], dim)
        self.lab_rank_l = mk("", left_x, rows[3], dim)

        # Right column (right-aligned to the panel edge on render)
        self.lab_team_r = mk("", left_x, rows[0], bright)
        self.lab_live_r = mk("", left_x, rows[1], bright)
        self.lab_proj_r = mk("", left_x, rows[2], dim)
        self.lab_rank_r = mk("", left_x, rows[3], dim)

        self.labels = (
            self.lab_team_l, self.lab_live_l, self.lab_proj_l, self.lab_rank_l,
            self.lab_team_r, self.lab_live_r, self.lab_proj_r, self.lab_rank_r,
        )
        for w in self.labels:
            self.group.append(w)

        # Win probability bar along the bottom edge, drawn in true panel
        # coordinates so the text group's top margin does not shift it
        self.bar_height = self.cfg.get('wp_bar_height', 1)
        self.bar_bitmap = displayio.Bitmap(self.cfg['matrix_width'], self.bar_height, 3)
        self.bar_palette = displayio.Palette(3)
        self.bar_palette[0] = 0x000000
        self.bar_palette[1] = self.cfg['lead_color']
        self.bar_palette[2] = self.cfg['trail_color']
        self.bar_palette.make_transparent(0)
        self.bar = displayio.TileGrid(
            self.bar_bitmap, pixel_shader=self.bar_palette,
            x=0, y=self.cfg.get('wp_bar_y', self.cfg['matrix_height'] - 1)
        )
        self.bar.hidden = True
        self.root.append(self.bar)

        # One dim pixel in the corner: data is old
        dot_bitmap = displayio.Bitmap(1, 1, 1)
        dot_palette = displayio.Palette(1)
        dot_palette[0] = self.cfg.get('stale_color', dim)
        self.dot = displayio.TileGrid(
            dot_bitmap, pixel_shader=dot_palette,
            x=self.cfg['matrix_width'] - 1, y=0
        )
        self.dot.hidden = True
        self.root.append(self.dot)

        # CircuitPython 9+: use root_group
        try:
            self.display.root_group = self.root
        except AttributeError:
            self.display.show(self.root)

        self.display.refresh()

    # ---- helpers ----

    def _clear(self):
        for w in self.labels:
            w.text = ""

    def _right_align_to_edge(self, lbl):
        # place so the right edge of the text is at the last column
        lbl.x = self.cfg['matrix_width'] - 1 - lbl.bounding_box[2]

    def _ordinal(self, n):
        try:
            n = int(n)
        except Exception:
            return "" if n is None else str(n)
        if 10 <= (n % 100) <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return "{}{}".format(n, suffix)

    def _rank_text(self, team):
        rank = team.get('score_rank', None)
        return self._ordinal(rank) if rank is not None else ""

    def _rank_color(self, rank):
        try:
            top_n = int(self.cfg.get('rank_top_n', 5))
            return self.cfg['lead_color'] if int(rank) <= top_n else self.cfg['trail_color']
        except Exception:
            return self.cfg['dim_text_color']

    # ---- screens ----

    def status(self, text, color=None):
        """Single centered line: WIFI..., NO DATA, and friends."""
        self._clear()
        self.bar.hidden = True
        lbl = self.lab_live_l
        lbl.color = color or self.cfg['text_color']
        lbl.text = text
        lbl.x = max(0, (self.cfg['matrix_width'] - lbl.bounding_box[2]) // 2)
        self.display.refresh()

    def render_win_prob(self, left_pct, right_pct):
        """
        Mirror ESPN's FantasyCast bar: each half is a gauge filling outward from
        the center, so the lit block slides toward whoever is favored.

            80% / 20%   ......########|##......
            50% / 50%   ....########|########..

        The favored side is green, the underdog red; a tie is yellow.
        """
        if left_pct is None or right_pct is None:
            if not self.bar.hidden:
                self.bar.hidden = True
                self.display.refresh()
            return

        half = self.cfg['matrix_width'] // 2
        left_len = self._clamp(int(round(left_pct * half / 100.0)), half)
        right_len = self._clamp(int(round(right_pct * half / 100.0)), half)

        if left_pct > right_pct:
            self.bar_palette[1] = self.cfg['lead_color']
            self.bar_palette[2] = self.cfg['trail_color']
        elif right_pct > left_pct:
            self.bar_palette[1] = self.cfg['trail_color']
            self.bar_palette[2] = self.cfg['lead_color']
        else:
            self.bar_palette[1] = self.cfg['tie_color']
            self.bar_palette[2] = self.cfg['tie_color']

        for y in range(self.bar_height):
            for x in range(self.cfg['matrix_width']):
                if half - left_len <= x < half:
                    self.bar_bitmap[x, y] = 1
                elif half <= x < half + right_len:
                    self.bar_bitmap[x, y] = 2
                else:
                    self.bar_bitmap[x, y] = 0

        self.bar.hidden = False
        self.display.refresh()

    def _clamp(self, value, high):
        return 0 if value < 0 else (high if value > high else value)

    def set_stale(self, stale):
        if self.dot.hidden == bool(stale):
            self.dot.hidden = not stale
            self.display.refresh()

    def set_awake(self, awake):
        """Blank the panel during quiet hours without tearing down the display."""
        target = self.cfg['brightness'] if awake else 0
        if self.display.brightness != target:
            self.display.brightness = target

    def _row_two(self, team, other):
        """
        Live points, or the win percentage before anyone has scored.

        Tuesday through Thursday both teams sit on 0.0, which tells you nothing;
        the same row carries the odds until the first player takes the field.
        """
        pregame = not (team.get('live_points') or other.get('live_points'))
        prob = team.get('win_prob')
        if pregame and prob is not None:
            return "{}%".format(int(prob))
        return str(team.get('live_points', ''))

    def render_pair(self, left_team, right_team):
        # --- Left column (left-aligned) ---
        self.lab_team_l.x = self.cfg['left_col_x']
        self.lab_team_l.text = str(left_team.get('team_abbrev', '----'))[:4]
        self.lab_live_l.x = self.cfg['left_col_x']
        self.lab_live_l.text = self._row_two(left_team, right_team)
        self.lab_proj_l.x = self.cfg['left_col_x']
        self.lab_proj_l.text = str(left_team.get('proj_points', ''))
        self.lab_rank_l.x = self.cfg['left_col_x']
        self.lab_rank_l.text = self._rank_text(left_team)

        # --- Right column (right-aligned to the panel edge) ---
        self.lab_team_r.text = str(right_team.get('team_abbrev', '----'))[:4]
        self._right_align_to_edge(self.lab_team_r)
        self.lab_live_r.text = self._row_two(right_team, left_team)
        self._right_align_to_edge(self.lab_live_r)
        self.lab_proj_r.text = str(right_team.get('proj_points', ''))
        self._right_align_to_edge(self.lab_proj_r)
        self.lab_rank_r.text = self._rank_text(right_team)
        self._right_align_to_edge(self.lab_rank_r)

        # --- Colors ---
        bright = self.cfg['text_color']
        self.lab_team_l.color = bright
        self.lab_team_r.color = bright
        self.lab_live_l.color = bright
        self.lab_live_r.color = bright

        # Projected points: color leader and trailer
        try:
            lp = float(left_team.get('proj_points', 0))
            rp = float(right_team.get('proj_points', 0))
        except Exception:
            lp, rp = 0.0, 0.0

        if lp > rp:
            self.lab_proj_l.color = self.cfg['lead_color']
            self.lab_proj_r.color = self.cfg['trail_color']
        elif rp > lp:
            self.lab_proj_l.color = self.cfg['trail_color']
            self.lab_proj_r.color = self.cfg['lead_color']
        else:
            self.lab_proj_l.color = self.cfg['tie_color']
            self.lab_proj_r.color = self.cfg['tie_color']

        # Rank row: green for top-N, else red
        self.lab_rank_l.color = self._rank_color(left_team.get('score_rank'))
        self.lab_rank_r.color = self._rank_color(right_team.get('score_rank'))

        self.render_win_prob(left_team.get('win_prob'), right_team.get('win_prob'))
        self.display.refresh()
