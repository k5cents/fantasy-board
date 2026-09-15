#!/usr/bin/env python3
"""
Render the board's display to a PNG, without touching the board.

This drives the real board/display.py through a stubbed CircuitPython display
stack, so the output is whatever FantasyBoard actually draws -- layout bugs,
clipping and off-by-one alignment show up here exactly as they would on the
panel.

Geometry matches the physical hardware (Adafruit 2278): 64x32 LEDs on a 4mm
pitch, 255 x 127 mm, with a ~2.1mm emitter in each 4mm cell. Each LED is drawn
as a round dot filling ~53% of its cell, lit dots glowing slightly, unlit dots
left as dark gray so the grid reads like the real panel.

Usage:
    python3 tools/preview.py                     # every scenario, one sheet
    python3 tools/preview.py --scenario live
    python3 tools/preview.py --url http://k5aux.lan:8000/scoreboard.json
    python3 tools/preview.py --json payload.json --scale 16
"""

import argparse
import json
import os
import struct
import sys
import types
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BOARD = os.path.join(ROOT, "board")

# Physical panel (Adafruit 2278)
PITCH_MM = 4.0
EMITTER_MM = 2.1
DOT_RATIO = EMITTER_MM / PITCH_MM

# Where adafruit_display_text puts the baseline relative to a label's y.
# Measured on the board: bitmap_label.Label(font_5x7, text='8').bounding_box
# is (0, -4, 5, 7), so the glyph box runs y-4 .. y+2 and the baseline is y+2.
BASELINE_OFFSET = 2

# Panel appearance
SUBSTRATE = (8, 8, 8)
UNLIT = (18, 18, 18)
GLOW_RATIO = 1.9    # glow radius as a multiple of the dot radius
GLOW_ALPHA = 0.10


# ---------------------- BDF font -------------------------------------------


class BDFFont:
    """Minimal BDF reader: enough to rasterize the board's 5x7 font."""

    def __init__(self, path):
        self.glyphs = {}  # codepoint -> dict(w, h, xoff, yoff, advance, rows)
        self._parse(path)

    def _parse(self, path):
        code = advance = None
        bbx = None
        rows = []
        reading = False
        with open(path) as handle:
            for line in handle:
                line = line.strip()
                if line.startswith("ENCODING "):
                    code = int(line.split()[1])
                elif line.startswith("DWIDTH "):
                    advance = int(line.split()[1])
                elif line.startswith("BBX "):
                    bbx = [int(v) for v in line.split()[1:5]]
                elif line == "BITMAP":
                    reading, rows = True, []
                elif line == "ENDCHAR":
                    if reading and code is not None and bbx:
                        w, h, xoff, yoff = bbx
                        self.glyphs[code] = {
                            "w": w, "h": h, "xoff": xoff, "yoff": yoff,
                            "advance": advance if advance is not None else w,
                            "rows": rows,
                        }
                    reading, code, bbx, advance = False, None, None, None
                elif reading and line:
                    rows.append(int(line, 16))

    def glyph(self, char):
        return self.glyphs.get(ord(char)) or self.glyphs.get(ord("?"))

    def text_width(self, text):
        """Total advance, which is what adafruit_display_text reports as width."""
        return sum(self.glyph(c)["advance"] for c in text if self.glyph(c))

    def vertical_extent(self, text):
        """(top, bottom) of the text box, relative to the baseline, y down."""
        tops, bottoms = [], []
        for char in text:
            g = self.glyph(char)
            if not g:
                continue
            top = -(g["h"] + g["yoff"])
            tops.append(top)
            bottoms.append(top + g["h"] - 1)
        if not tops:
            return 0, 0
        return min(tops), max(bottoms)

    def draw(self, frame, text, x, y, color):
        """
        Draw `text` the way adafruit_display_text places it.

        A label's box is not centered on y: measured on the board itself, a 5x7
        glyph reports bounding_box (0, -4, w, 7), so the box runs y-4 to y+2 and
        the baseline sits at y + BASELINE_OFFSET.
        """
        baseline = y + BASELINE_OFFSET
        pen = x
        for char in text:
            g = self.glyph(char)
            if not g:
                continue
            gy = baseline - (g["h"] + g["yoff"])
            for row_index, bits in enumerate(g["rows"]):
                for col in range(g["w"]):
                    # BDF packs each row MSB first, padded to whole bytes
                    byte_bits = ((g["w"] + 7) // 8) * 8
                    if bits & (1 << (byte_bits - 1 - col)):
                        frame.set(pen + col + g["xoff"], gy + row_index, color)
            pen += g["advance"]


# ---------------------- framebuffer ----------------------------------------


class Frame:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.pixels = {}
        self.clipped = 0  # pixels the renderer tried to draw off-panel

    def set(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[(x, y)] = color
        else:
            self.clipped += 1

    def get(self, x, y):
        return self.pixels.get((x, y))


def rgb(value):
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


# ---------------------- CircuitPython stubs --------------------------------


class StubBitmap:
    def __init__(self, width, height, colors):
        self.width, self.height, self.data = width, height, {}

    def __setitem__(self, xy, value):
        self.data[xy] = value

    def __getitem__(self, xy):
        return self.data.get(xy, 0)


class StubPalette(list):
    def __init__(self, n):
        super().__init__([0] * n)
        self.transparent = set()

    def make_transparent(self, i):
        self.transparent.add(i)


class StubGroup(list):
    def __init__(self, x=0, y=0):
        super().__init__()
        self.x, self.y, self.hidden = x, y, False


class StubTileGrid:
    def __init__(self, bitmap, pixel_shader=None, x=0, y=0):
        self.bitmap, self.palette = bitmap, pixel_shader
        self.x, self.y, self.hidden = x, y, False


class StubLabel:
    font_ref = None  # set once the BDF is loaded

    def __init__(self, font, text="", color=0):
        self.text, self.color = text, color
        self.x = self.y = 0
        self.hidden = False

    @property
    def bounding_box(self):
        return (0, 0, StubLabel.font_ref.text_width(self.text), 7)


class StubDisplay:
    def __init__(self):
        self.brightness, self.auto_refresh, self.root_group = 0.0, True, None

    def refresh(self):
        pass


class StubMatrix:
    def __init__(self, **kwargs):
        self.display = StubDisplay()


def install_stubs():
    displayio = types.ModuleType("displayio")
    displayio.Bitmap, displayio.Palette = StubBitmap, StubPalette
    displayio.Group, displayio.TileGrid = StubGroup, StubTileGrid

    matrix_mod = types.ModuleType("adafruit_matrixportal.matrix")
    matrix_mod.Matrix = StubMatrix
    portal = types.ModuleType("adafruit_matrixportal")
    portal.matrix = matrix_mod

    label_mod = types.ModuleType("adafruit_display_text.bitmap_label")
    label_mod.Label = StubLabel
    text_pkg = types.ModuleType("adafruit_display_text")
    text_pkg.bitmap_label = label_mod

    font_mod = types.ModuleType("adafruit_bitmap_font.bitmap_font")
    font_mod.load_font = lambda path: path
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


# ---------------------- compositing ----------------------------------------


def composite(node, frame, font, ox=0, oy=0):
    """Walk the display tree the way displayio would, drawing into `frame`."""
    if getattr(node, "hidden", False):
        return
    x, y = ox + getattr(node, "x", 0), oy + getattr(node, "y", 0)

    if isinstance(node, StubGroup):
        for child in node:
            composite(child, frame, font, x, y)
    elif isinstance(node, StubTileGrid):
        for (px, py), index in node.bitmap.data.items():
            if index in node.palette.transparent:
                continue
            frame.set(x + px, y + py, rgb(node.palette[index]))
    elif isinstance(node, StubLabel):
        if node.text:
            font.draw(frame, node.text, x, y, rgb(node.color))


# ---------------------- PNG ------------------------------------------------


def write_png(path, width, height, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(png)


def render_leds(frames, scale, gap_cells=2):
    """
    Draw one or more 64x32 frames as physical LED dots, stacked vertically.

    Returns (width, height, rows) with rows as flat RGB byte lists.
    """
    width_cells = frames[0].width
    height_cells = sum(f.height for f in frames) + gap_cells * (len(frames) - 1)
    width, height = width_cells * scale, height_cells * scale

    canvas = [[SUBSTRATE] * width for _ in range(height)]

    radius = DOT_RATIO * scale / 2.0
    glow = radius * GLOW_RATIO

    y_offset = 0
    for frame in frames:
        for cy in range(frame.height):
            for cx in range(frame.width):
                color = frame.get(cx, cy) or UNLIT
                center_x = cx * scale + scale / 2.0
                center_y = (cy + y_offset) * scale + scale / 2.0
                lit = frame.get(cx, cy) is not None

                span = int(glow) + 2
                for py in range(int(center_y - span), int(center_y + span) + 1):
                    if not 0 <= py < height:
                        continue
                    for px in range(int(center_x - span), int(center_x + span) + 1):
                        if not 0 <= px < width:
                            continue
                        dx, dy = px + 0.5 - center_x, py + 0.5 - center_y
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist <= radius - 0.5:
                            canvas[py][px] = color
                        elif dist <= radius + 0.5:
                            blend(canvas, px, py, color, radius + 0.5 - dist)
                        elif lit and dist <= glow:
                            falloff = (glow - dist) / (glow - radius)
                            blend(canvas, px, py, color, GLOW_ALPHA * falloff)
        y_offset += frame.height + gap_cells

    rows = []
    for row in canvas:
        flat = []
        for pixel in row:
            flat.extend(pixel)
        rows.append(flat)
    return width, height, rows


def blend(canvas, x, y, color, alpha):
    alpha = max(0.0, min(1.0, alpha))
    base = canvas[y][x]
    canvas[y][x] = tuple(
        int(base[i] + (color[i] - base[i]) * alpha) for i in range(3)
    )


# ---------------------- scenarios ------------------------------------------


def team(abbrev, live, proj, rank, prob):
    return {
        "team_abbrev": abbrev, "live_points": live, "proj_points": proj,
        "score_rank": rank, "win_prob": prob,
    }


SCENARIOS = {
    "pregame": ("Tue-Thu: nobody has played", lambda b: b.render_pair(
        team("KIER", 0.0, 102.3, 1, 54), team("BILL", 0.0, 95.9, 8, 46))),
    "live": ("Sunday afternoon, mid-slate", lambda b: b.render_pair(
        team("KIER", 44.7, 81.5, 9, 38), team("COMP", 94.9, 100.6, 4, 62))),
    "tie": ("dead heat", lambda b: b.render_pair(
        team("KIER", 61.2, 98.0, 5, 50), team("BILL", 61.2, 98.0, 5, 50))),
    "blowout": ("lopsided", lambda b: b.render_pair(
        team("KIER", 132.8, 141.0, 1, 93), team("ANUS", 58.1, 71.4, 10, 7))),
    "final": ("after the Monday night game", lambda b: b.render_pair(
        team("KIER", 118.6, 118.6, 3, 88), team("BILL", 101.2, 101.2, 7, 12))),
    "stale": ("server unreachable, last frame held", lambda b: (
        b.render_pair(team("KIER", 44.7, 81.5, 9, 38), team("COMP", 94.9, 100.6, 4, 62)),
        b.set_stale(True))),
    "nodata": ("no payload yet", lambda b: b.status("NO DATA", 0xB00020)),
    "wifi": ("connecting", lambda b: b.status("WIFI")),
}

SHEET_ORDER = ["pregame", "live", "tie", "blowout", "final", "stale", "nodata"]


def payload_scenario(payload):
    """Render a real server payload the way code.py would."""
    def render(board):
        if payload.get("status") == "sleep":
            board.status("SLEEP")
            return
        if payload.get("status") != "ok":
            board.status("NO DATA", 0xB00020)
            return
        left, right = payload["scoreboard"]
        board.render_pair(left, right)
        if payload.get("stale"):
            board.set_stale(True)
    return render


# ---------------------- main -----------------------------------------------


def load_board():
    """Install the stubs and import the board's own config and renderer."""
    install_stubs()
    for name in ("display", "config"):
        sys.modules.pop(name, None)
    if BOARD not in sys.path:
        sys.path.insert(0, BOARD)
    from config import config as cfg
    from display import FantasyBoard

    font = BDFFont(os.path.join(BOARD, "fonts", "5x7.bdf"))
    StubLabel.font_ref = font
    return cfg, FantasyBoard, font


def render_frame(render, font, cfg, FantasyBoard):
    board = FantasyBoard(cfg)
    render(board)
    frame = Frame(cfg["matrix_width"], cfg["matrix_height"])
    composite(board.display.root_group, frame, font)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="render one scenario")
    parser.add_argument("--url", help="render a live payload from the server")
    parser.add_argument("--json", help="render a payload from a file")
    parser.add_argument("--scale", type=int, default=12, help="pixels per LED (default 12)")
    parser.add_argument("--out", default=os.path.join(ROOT, "preview.png"))
    args = parser.parse_args()

    cfg, FantasyBoard, font = load_board()

    if args.url or args.json:
        if args.url:
            import urllib.request
            with urllib.request.urlopen(args.url, timeout=10) as resp:
                payload = json.loads(resp.read())
        else:
            with open(args.json) as handle:
                payload = json.load(handle)
        renders = [(args.url or args.json, payload_scenario(payload))]
    elif args.scenario:
        caption, render = SCENARIOS[args.scenario]
        renders = [(args.scenario + ": " + caption, render)]
    else:
        renders = [(name + ": " + SCENARIOS[name][0], SCENARIOS[name][1])
                   for name in SHEET_ORDER]

    frames = [render_frame(render, font, cfg, FantasyBoard) for _, render in renders]
    width, height, rows = render_leds(frames, args.scale)
    write_png(args.out, width, height, rows)

    clipped = sum(f.clipped for f in frames)
    if clipped:
        print("WARNING: %d pixel(s) drawn off-panel -- the layout clips" % clipped)

    mm_w = cfg["matrix_width"] * PITCH_MM
    mm_h = cfg["matrix_height"] * PITCH_MM
    print("wrote %s  (%dx%d px, %d panel%s at %.0f x %.0f mm each)" % (
        args.out, width, height, len(frames), "" if len(frames) == 1 else "s", mm_w, mm_h))
    for label, _ in renders:
        print("  -", label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
