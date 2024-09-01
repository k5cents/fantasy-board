import time
from config import config
from score_board import ScoreBoard
from espn_api import FantasyApi, FantasyApiOnFireException
from secrets import secrets
import busio
import board
from digitalio import DigitalInOut
import neopixel
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager

# New network setup
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# Get our username, key and desired timezone
aio_username = secrets.get("aio_username")
aio_key = secrets.get("aio_key")
location = secrets.get("timezone", None)
TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s" % (aio_username, aio_key)
TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L+%25j+%25u+%25z+%25Z"

OFF_HOURS_ENABLED = aio_username and aio_key and config.get("display_on_time") and config.get("display_off_time")

REFRESH_INTERVAL = config['refresh_interval']

# Initialize FantasyApi and ScoreBoard
fantasy_api = FantasyApi()
score_board = ScoreBoard(fantasy_api.fetch_data)

def is_off_hours() -> bool:
    try:
        now = wifi.get(TIME_URL, timeout=1).text
        now_hour = int(now[11:13])
        now_minute = int(now[14:16])
        after_end = now_hour > config['display_off_time'][:2] or (now_hour == config['display_off_time'][:2] and now_minute > config['display_off_time'][3:])
        before_start = now_hour < config['display_on_time'][:2] or (now_hour == config['display_on_time'][:2] and now_minute < config['display_on_time'][3:])
        return before_start or after_end
    except:
        return False

while True:
    if OFF_HOURS_ENABLED and is_off_hours():
        print("OFF HOURS")
        score_board.hide()
        time.sleep(60)  # Sleep for a minute before checking again
        continue

    try:
        print("Updating Fantasy Football Scores")
        score_board.refresh()
    except FantasyApiOnFireException:
        print("ESPN API is on fire! Skipping this update.")

    time.sleep(REFRESH_INTERVAL)
