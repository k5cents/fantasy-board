> [!NOTE]  
> Forked from [metro-sign](https://github.com/erikrrodriguez/dc-metro), which was forked from [metro-sign](https://github.com/metro-sign/dc-metro). In the process of making the sign display ESPN fantasy football data instead of WMATA data.

# Fantasy Football Scoreboard
This project contains the source code to create your own ESPN fantasy football scoreboard. It was written using CircuitPython targeting the [Adafruit Matrix Portal](https://www.adafruit.com/product/4745) and is optimized for 64x32 RGB LED matrices.

![Board Showing Train Arriving](img/board.gif)

# How To
## Hardware
- An [Adafruit Matrix Portal](https://www.adafruit.com/product/4745) - $24.99
- A **64x32 RGB LED matrix** compatible with the _Matrix Portal_ - $39.99 _to_ $84.99
    - [64x32 RGB LED Matrix - 3mm pitch](https://www.adafruit.com/product/2279)
    - [64x32 RGB LED Matrix - 4mm pitch](https://www.adafruit.com/product/2278)
    - [64x32 RGB LED Matrix - 5mm pitch](https://www.adafruit.com/product/2277)
    - [64x32 RGB LED Matrix - 6mm pitch](https://www.adafruit.com/product/2276)
- A **USB-C power supply** (15w phone adapters should work fine for this code, but the panels can theoretically pull 20w if every pixel is on white)
- A **USB-C cable** that can connect your computer/power supply to the board

## Tools
- A small phillips head screwdriver
- A hot glue gun _(optional)_
- Tape _(optional)_

## Part 1: Prepare the Board
1. Use a hot glue gun to cover the sharp screws on the right-hand side of the 64x32 LED matrix. This step is optional, but it will prevent wire chafing later on.

    ![64x32 Matrix with Hot Glue on Screws](img/base-board.jpg)

2. Lightly screw in the phillips head screws into the posts on the _Matrix Portal_. These only need to go down about 60% of the way.

    ![Matrix Portal with Screws](img/wiring.jpg)

3. Using the power cable provided with 64x32 matrix, slide the prong for the **red power cable** between the post and the screw on the port labeled **5v**. Tighten down this screw all the way using your screwdriver. Repeat the same for the **black power cable** and the **GND** port.

    ![Matrix Portal with Separate Cables](img/cables.jpg)
    ![Matrix Portal with Connected Cables](img/portal-setup.jpg)

4. Connect the _Matrix Portal_ to the large connector on the left-hand side of the back of the 64x32 matrix.

    ![64x32 Matrix with Connector Highlighted](img/port.jpg)

5. Plug one of the power connectors into the right-hand side of the 64x32 matrix.

    ![64x32 Matrix with Power Connected](img/connected-board.jpg)

6. You can use masking tape (or painter's tape) to prevent the cables from flopping around.

    ![64x32 Matrix with Cable Management](img/cable-management.jpg)

## Part 2: Loading the Software
1. Connect the board to your computer using a USB C cable. Double click the button on the board labeled _RESET_. The board should mount onto your computer as a storage volume, most likely named _MATRIXBOOT_.
    
    ![Matrix Connected via USB](img/usb-connected.jpg)

2. Flash your _Matrix Portal_ with the latest release of CircuitPython 8.
    - Download the [firmware from Adafruit](https://circuitpython.org/board/matrixportal_m4/).
    - Drag the downloaded _.uf2_ file into the root of the _MATRIXBOOT_ volume.
    - The board will automatically flash the version of CircuitPython and remount as _CIRCUITPY_.
    - If something goes wrong, refer to the [Adafruit Documentation](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython).

3. Decompress the _lib.zip_ file for 8.x from this repository into the root of the _CIRCUITPY_ volume. There should be one folder named _lib_, with a plethora of files underneath. You can delete _lib.zip_ from the _CIRCUITPY_ volume, as it's no longer needed.

    - It has been reported that this step may fail ([Issue #2](https://github.com/metro-sign/dc-metro/issues/2)), most likely due to the storage on the Matrix Portal not being able to handle the decompression. If this happens, unzip the _lib.zip_ file on your computer, and copy the _lib_ folder to the Matrix Portal. Command line tools could also be used if the above doesn't work.

    ![Lib Decompressed](img/lib.png)

4. Copy all of the Python files from _src_ in this repository into the root of the _CIRCUITPY_ volume.

    ![Source Files](img/source.png)

5. The board should now light up with a loading screen, but we've still got some work to do.

    ![Loading Sign](img/loading.jpg)

## Part 3: No need for an ESPN API key

## Part 4: (Optional) Obtain adafruit IO Key for Off Hours.
If you'd like to configure your board to turn the display off for certain hours of the day, you'll need to set up a free account with Adafruit to make requests for the local time. You may skip this if you are not interested in this feature.

1. Follow steps 1-3 outlined [here](https://learn.adafruit.com/adafruit-magtag/getting-the-date-time).
2. Make note of your username and your Adafruit IO key.

## Part 5: Configuring the Board
1. Open the [config.py](src/config.py) file located in the root of the _CIRCUITPY_ volume.
2. Fill in your WiFi SSID and password under the **Network Configuration** section.
3. Under the **League Configuration** section:
    1. Set `leagueId` and `teamId` to your league and team.
4. (Optional) Under the **Off Hours Configuration** section:
    1. Set _aio_username_ to the username you created with Adafruit in [Part 4]((optional)-obtain-adafruit-io-key-for-off-hours).
    2. Set _aio_key_ to the api key associated with your Adafruit account.
    3. Set the _display_on_time_ and _display_off_time_ variables to the time of day you would like the sign to be turned off and on. Note that they must be of the format "HH:MM" and use a 24 hour clock.
4. At the end, the first part of your configuration file should look similar this:

```python
#########################
# Network Configuration #
#########################

# WIFI Network SSID
'wifi_ssid': 'My Wireless Network',

# WIFI Password
'wifi_password': 'MyWirelessPassword',

#########################
# leagueId Configuration   #
#########################
'leagueId': '42654852'
'teamId': '6'

...
...
...

#############################
# Off Hours Configuration   #
#############################

# adafruit io settings, necessary for determining current time to sleep
# An account is free to set up, instructions below
# https://learn.adafruit.com/adafruit-magtag/getting-the-date-time
'aio_username': 'aio_username',
'aio_key': 'jf9834f983hf98h434',

# Time of day to turn board on and off - must be 24 hour "HH:MM"
'display_on_time': "07:00",
'display_off_time': "22:00",
```

5. After you save this file, your board should refresh and connect to ESPN.

> [!TIP]
> If something goes wrong, take a peek at the [Adafruit Documentation](https://learn.adafruit.com/adafruit-matrixportal-m4). Additionally, you can connect to the board using a [serial connection](https://learn.adafruit.com/welcome-to-circuitpython/kattni-connecting-to-the-serial-console) to gain access to its logging.
