# config.py — Fantasy Scoreboard (local file mode, exactly two teams)

config = {
    # Data source
    'mode': 'FANTASY_HTTP',
    "http_url": "http://192.168.0.109:8000/scoreboard.json",
    'local_json_path': '/scoreboard.json',
    'refresh_interval': 30,   # seconds; adjust as you like

    # Display
    'matrix_width': 64,
    'matrix_height': 32,
    'brightness': 0.2,      # 0.0–1.0

    # Layout for terminalio 8px font on 64x32 (4 rows)
    'left_col_x': 1,
    'right_col_x': 40,

    # Colors
    'text_color': 0xFFFFFF,       # bright rows (team + live)
    'dim_text_color': 0x3b3b3b,   # secondary rows (proj + yet-to-play)
    'lead_color':  0x00994C,  # green
    'trail_color': 0xB00020,  # red
    'tie_color':   0xE0C200,  # yellow

    # Banners
    'banner_left': '123456789012',
    'banner_right': '',

    # Font information
    'font_path': '/lib/5x7.bdf',  # same tiny bitmap font as the WMATA repo
    'top_margin': 3,              # push everything down to avoid top clipping
    'row_baselines': [1, 9, 17, 25],  # 4 rows, top → bottom

    'rotation': 180
}
