# ---- FantasyBoard: 2-column, 4-row scoreboard for 64x32 ----
import displayio
import terminalio
from adafruit_matrixportal.matrix import Matrix
from adafruit_display_text import bitmap_label as label
from adafruit_bitmap_font import bitmap_font

class FantasyBoard:
    """
    Renders two teams with 4 rows:
      Row 1: team_abbrev     team_abbrev
      Row 2: live_points     live_points
      Row 3: proj_points     proj_points
      Row 4: n_unlocked/total  n_unlocked/total
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
        self.lab_team_l = mk("1234567890123", self.cfg['left_col_x'],  self.cfg['row_baselines'][0], self.cfg['text_color'])
        self.lab_live_l = mk("",      self.cfg['left_col_x'],  self.cfg['row_baselines'][1], self.cfg['text_color'])
        self.lab_proj_l = mk("",      self.cfg['left_col_x'],  self.cfg['row_baselines'][2], self.cfg['dim_text_color'])
        self.lab_left_l = mk("",      self.cfg['left_col_x'],  self.cfg['row_baselines'][3], self.cfg['dim_text_color'])

        # Right column labels
        self.lab_team_r = mk("", self.cfg['right_col_x'], self.cfg['row_baselines'][0], self.cfg['text_color'])
        self.lab_live_r = mk("",      self.cfg['right_col_x'], self.cfg['row_baselines'][1], self.cfg['text_color'])
        self.lab_proj_r = mk("",      self.cfg['right_col_x'], self.cfg['row_baselines'][2], self.cfg['dim_text_color'])
        self.lab_left_r = mk("",      self.cfg['right_col_x'], self.cfg['row_baselines'][3], self.cfg['dim_text_color'])

        for w in (
            self.lab_team_l, self.lab_live_l, self.lab_proj_l, self.lab_left_l,
            self.lab_team_r, self.lab_live_r, self.lab_proj_r, self.lab_left_r
        ):
            self.group.append(w)

        # CircuitPython 9+: use root_group
        try:
            self.display.root_group = self.group
        except AttributeError:
            # CP8 fallback
            self.display.show(self.group)

        self.display.refresh()

    def banner(self, left=None, right=None):
        left = left if left is not None else self.cfg.get('banner_left', '')
        right = right if right is not None else self.cfg.get('banner_right', '')
        self.lab_team_l.text = left
        self.lab_team_r.text = right
        self.lab_live_l.text = self.lab_proj_l.text = self.lab_left_l.text = ""
        self.lab_live_r.text = self.lab_proj_r.text = self.lab_left_r.text = ""
        self.display.refresh()

    def _fmt_left(self, team):
        # "yet-to-play / total" where total = n_locked + n_unlocked
        locked = int(team.get('n_locked', 0))
        unlocked = int(team.get('n_unlocked', 0))
        total = locked + unlocked
        return f"{unlocked}/{total}" if total > 0 else f"{unlocked}"

    def _right_align_to_edge(self, lbl):
        # place so the right edge of the text is at the last column (x = width-1)
        w = lbl.bounding_box[2]
        lbl.x = self.cfg['matrix_width'] - 1 - w

    def render_pair(self, left_team: dict, right_team: dict):
        # Left column (left-aligned at left_col_x)
        self.lab_team_l.text = str(left_team.get('team_abbrev', '----'))[:4]
        self.lab_live_l.text = str(left_team.get('live_points', ''))
        self.lab_proj_l.text = str(left_team.get('proj_points', ''))
        self.lab_left_l.text = self._fmt_left(left_team)

        # Right column (right-aligned to panel edge)
        self.lab_team_r.text = str(right_team.get('team_abbrev', '----'))[:4]
        self._right_align_to_edge(self.lab_team_r)

        self.lab_live_r.text = str(right_team.get('live_points', ''))
        self._right_align_to_edge(self.lab_live_r)

        self.lab_proj_r.text = str(right_team.get('proj_points', ''))
        self._right_align_to_edge(self.lab_proj_r)

        self.lab_left_r.text = self._fmt_left(right_team)
        self._right_align_to_edge(self.lab_left_r)

        self.display.refresh()
