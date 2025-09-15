# ---- FantasyBoard: 2-column, 4-row scoreboard for 64x32 ----
import displayio
import terminalio
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
    Expects numbers already rounded on the data source (Pi).
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

        FONT = bitmap_font.load_font(self.cfg['font_path'])
        self.group = displayio.Group(x=0, y=self.cfg.get('top_margin', 0))

        def mk(text, x, y, color):
            t = label.Label(FONT, text=text, color=color)
            t.x = x
            t.y = y
            return t

        # Left column labels
        self.lab_team_l = mk("TEAM", self.cfg['left_col_x'],  self.cfg['row_baselines'][0], self.cfg['text_color'])
        self.lab_live_l = mk("",     self.cfg['left_col_x'],  self.cfg['row_baselines'][1], self.cfg['text_color'])
        self.lab_proj_l = mk("",     self.cfg['left_col_x'],  self.cfg['row_baselines'][2], self.cfg['dim_text_color'])
        self.lab_rank_l = mk("",     self.cfg['left_col_x'],  self.cfg['row_baselines'][3], self.cfg['dim_text_color'])

        # Right column labels
        self.lab_team_r = mk("",     self.cfg['right_col_x'], self.cfg['row_baselines'][0], self.cfg['text_color'])
        self.lab_live_r = mk("",     self.cfg['right_col_x'], self.cfg['row_baselines'][1], self.cfg['text_color'])
        self.lab_proj_r = mk("",     self.cfg['right_col_x'], self.cfg['row_baselines'][2], self.cfg['dim_text_color'])
        self.lab_rank_r = mk("",     self.cfg['right_col_x'], self.cfg['row_baselines'][3], self.cfg['dim_text_color'])

        for w in (
            self.lab_team_l, self.lab_live_l, self.lab_proj_l, self.lab_rank_l,
            self.lab_team_r, self.lab_live_r, self.lab_proj_r, self.lab_rank_r
        ):
            self.group.append(w)

        # CircuitPython 9+: use root_group
        try:
            self.display.root_group = self.group
        except AttributeError:
            self.display.show(self.group)

        self.display.refresh()

    def banner(self, left=None, right=None):
        left = left if left is not None else self.cfg.get('banner_left', '')
        right = right if right is not None else self.cfg.get('banner_right', '')
        self.lab_team_l.text = left
        self.lab_team_r.text = right
        self.lab_live_l.text = self.lab_proj_l.text = self.lab_rank_l.text = ""
        self.lab_live_r.text = self.lab_proj_r.text = self.lab_rank_r.text = ""
        self.display.refresh()

    def _right_align_to_edge(self, lbl):
        # place so the right edge of the text is at the last column (x = width-1)
        w = lbl.bounding_box[2]
        lbl.x = self.cfg['matrix_width'] - 1 - w

    def _ordinal(self, n):
        try:
            n = int(n)
        except Exception:
            return "" if n is None else str(n)
        if 10 <= (n % 100) <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    def _rank_text(self, team: dict):
        r = team.get('score_rank', None)
        return self._ordinal(r) if r is not None else ""

    def _rank_color(self, rank):
        good = self.cfg.get('lead_color', 0x00FF00)    # green default
        bad  = self.cfg.get('trail_color', 0xFF4040)   # red-ish default
        top_n = int(self.cfg.get('rank_top_n', 5))
        try:
            return good if int(rank) <= top_n else bad
        except Exception:
            return self.cfg['dim_text_color']

    def render_pair(self, left_team: dict, right_team: dict):
        # --- Text values ---
        # Left column (left-aligned)
        self.lab_team_l.text = str(left_team.get('team_abbrev', '----'))[:4]
        self.lab_live_l.text = str(left_team.get('live_points', ''))
        self.lab_proj_l.text = str(left_team.get('proj_points', ''))
        self.lab_rank_l.text = self._rank_text(left_team)

        # Right column (right-aligned to panel edge)
        self.lab_team_r.text = str(right_team.get('team_abbrev', '----'))[:4]
        self._right_align_to_edge(self.lab_team_r)

        self.lab_live_r.text = str(right_team.get('live_points', ''))
        self._right_align_to_edge(self.lab_live_r)

        self.lab_proj_r.text = str(right_team.get('proj_points', ''))
        self._right_align_to_edge(self.lab_proj_r)

        self.lab_rank_r.text = self._rank_text(right_team)
        self._right_align_to_edge(self.lab_rank_r)

        # --- Colors ---
        base = self.cfg['text_color']
        dim  = self.cfg['dim_text_color']
        lead_color  = self.cfg.get('proj_lead_color',  self.cfg.get('lead_color',  base))
        trail_color = self.cfg.get('proj_trail_color', self.cfg.get('trail_color', dim))
        tie_color   = self.cfg.get('proj_tie_color',   self.cfg.get('tie_color',   base))

        # Keep team names and LIVE neutral
        self.lab_team_l.color = base
        self.lab_team_r.color = base
        self.lab_live_l.color = base
        self.lab_live_r.color = base

        # Projected points: color leader/trailer
        try:
            lp = float(left_team.get('proj_points', 0))
            rp = float(right_team.get('proj_points', 0))
        except Exception:
            lp, rp = 0.0, 0.0

        if lp > rp:
            self.lab_proj_l.color = lead_color
            self.lab_proj_r.color = trail_color
        elif rp > lp:
            self.lab_proj_l.color = trail_color
            self.lab_proj_r.color = lead_color
        else:
            self.lab_proj_l.color = tie_color
            self.lab_proj_r.color = tie_color

        # Bottom row (rank): green for top-N, else red
        self.lab_rank_l.color = self._rank_color(left_team.get('score_rank'))
        self.lab_rank_r.color = self._rank_color(right_team.get('score_rank'))

        self.display.refresh()