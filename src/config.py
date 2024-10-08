#from adafruit_bitmap_font import bitmap_font

config = {
	#########################
	# Network Configuration #
	#########################

	# WIFI Network SSID
	'wifi_ssid': '',

	# WIFI Password
	'wifi_password': '',

	##########################
	# League Configuration   #
	##########################

	'league_id': 42654852,
	'season_id': 2024,
	'team_id': 4,
  'slot_id_bench': 20,
  
	'refresh_interval': 60,

	#############################
	# Off Hours Configuration   #
	#############################

	# adafruit io settings, necessary for determining current time to sleep
	# An account is free to set up, instructions below
	# https://learn.adafruit.com/adafruit-magtag/getting-the-date-time
	'aio_username': '',
	'aio_key': '',

	# Time of day to turn board on and off - must be 24 hour "HH:MM"
	'display_on_time': "08:00",
	'display_off_time': "23:59",

	#########################
	# Display Configuration #
	#########################
	'matrix_width': 64,
	# 'font': bitmap_font.load_font('lib/5x7.bdf'),

	'character_width': 5,
	'character_height': 6,
	'text_padding': 2,
	'text_color': 0xFF7500,

	'loading_destination_text': 'Loading',
	'loading_min_text': '---',
	'loading_line_color': 0xFF00FF, # Something something Purple Line joke

	'heading_text': 'LN DEST   MIN',
	'heading_color': 0xFF0000,

	'train_line_height': 6,
	'train_line_width': 4

}

config.update(
  {"espn_api_url": f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{config['season_id']}/segments/0/leagues/{config['league_id']}?view=mScoreboard&view=mRoster"}
)