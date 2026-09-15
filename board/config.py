# config.py — display and rendering options for the 64x32 matrix.
# Wi-Fi credentials and SCOREBOARD_URL live in settings.toml.

config = {
    # Polling
    'refresh_interval': 30,   # seconds between fetches
    'sleep_interval': 300,    # seconds between fetches while the server says sleep
    'stale_after': 300,       # seconds without fresh data before the stale dot lights

    # Display
    'matrix_width': 64,
    'matrix_height': 32,
    'brightness': 0.2,        # 0.0-1.0
    'rotation': 180,

    # Layout for the 5x7 font on 64x32 (4 rows of 6 lit px + a 1px bar).
    #
    # Measured on the board by reading each label's own bitmap: the glyph's
    # blank row sits at the TOP of the box, so lit pixels run y-3 to y+2 (a
    # descender would reach y+3). With top_margin 2 the rows light 0-5, 8-13,
    # 16-21 and 24-29, leaving row 30 dark as a gap above the bar at y=31.
    # top_margin 3 wastes row 0 and butts the rank row against the bar.
    'left_col_x': 1,
    'top_margin': 2,
    'row_baselines': [1, 9, 17, 25],  # 4 rows, top to bottom

    # Win probability bar: mirrored halves filling outward from the center
    'wp_bar_y': 31,
    'wp_bar_height': 1,

    # Colors
    'text_color': 0xFFFFFF,       # bright rows (team + live)
    'dim_text_color': 0x3b3b3b,   # secondary rows (proj + rank)
    'lead_color':  0x00994C,      # green
    'trail_color': 0xB00020,      # red
    'tie_color':   0xE0C200,      # yellow
    'stale_color': 0x3b3b3b,      # corner dot when data stops updating

    # Bottom row: projected rank at or above this is green, below is red
    'rank_top_n': 5,

    # Font
    'font_path': '/fonts/5x7.bdf',
}
