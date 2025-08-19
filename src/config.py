# config.py — Fantasy Scoreboard (local file mode, exactly two teams)

config = {
    # Wi-Fi
    'wifi_ssid': 'k24wifi',
    'wifi_password': 'dork.hardware.sled',

    # Data source
    'mode': 'FANTASY_LOCAL',
    'local_json_path': '/scoreboard.json',
    'refresh_interval': 2,   # seconds; adjust as you like

    # Display
    'matrix_width': 64,
    'matrix_height': 32,
    'brightness': 0.1,      # 0.0–1.0

    # Layout for terminalio 8px font on 64x32 (4 rows)
    'left_col_x': 1,
    'right_col_x': 40,
    # 'row_baselines': [1, 9, 17, 25],

    # Colors & banner
    'text_color': 0xFFFFFF,       # bright rows (team + live)
    'dim_text_color': 0x3b3b3b,   # secondary rows (proj + yet-to-play)
    'banner_left': '123456789012',
    'banner_right': '',

    # Font information
    'font_path': '/lib/5x7.bdf',  # same tiny bitmap font as the WMATA repo
    'top_margin': 0,              # push everything down to avoid top clipping

    # Row baselines inside the group (we’re adding +3 via top_margin, so keep last row safe)
    'row_baselines': [5, 13, 21, 28],  # 4 rows, top → bottom

    'rotation': 180
}
