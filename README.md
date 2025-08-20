> [!NOTE]  
> Forked from [metro-sign](https://github.com/erikrrodriguez/dc-metro), which was forked from [metro-sign](https://github.com/metro-sign/dc-metro). In the process of making the sign display ESPN fantasy football data instead of WMATA data.

# Fantasy Football Scoreboard
This project contains the source code to create your own ESPN fantasy football scoreboard. It was written using CircuitPython targeting the [Adafruit Matrix Portal](https://www.adafruit.com/product/4745) and is optimized for 64x32 RGB LED matrices.

# How To
## Hardware
- An [Adafruit Matrix Portal Start Kit](https://www.adafruit.com/product/4812) - $69.95
    - An [Adafruit Matrix Portal](https://www.adafruit.com/product/4745)
    - A **64x32 RGB LED matrix** compatible with the _Matrix Portal_
    - A **USB-C power supply**

## Part 1: Prepare the Board

1. Lightly screw in the phillips head screws into the posts on the _Matrix Portal_. These only need to go down about 60% of the way.
2. Using the power cable provided with 64x32 matrix, slide the prong for the **red power cable** between the post and the screw on the port labeled **5v**. Tighten down this screw all the way using your screwdriver. Repeat the same for the **black power cable** and the **GND** port.
3. Connect the _Matrix Portal_ to the large connector on the left-hand side of the back of the 64x32 matrix.
4. Plug one of the power connectors into the right-hand side of the 64x32 matrix.
5. You can use masking tape (or painter's tape) to prevent the cables from flopping around.

## Part 2: Loading the Software
1. Connect the board to your computer using a USB-C cable. Double click the button on the board labeled _RESET_. The board should mount onto your computer as a storage volume, most likely named _MATRIXBOOT_.
2. Flash your _Matrix Portal_ with the latest release of CircuitPython 8.
    - Download the [firmware from Adafruit](https://circuitpython.org/board/matrixportal_m4/).
    - Drag the downloaded `.uf2` file into the root of the _MATRIXBOOT_ volume.
    - The board will automatically flash the version of CircuitPython and remount as _CIRCUITPY_.
    - If something goes wrong, refer to the [Adafruit Documentation](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython).
3. Decompress the `lib.zip` file for from this repository into the root of the _CIRCUITPY_ volume. There should be one folder named `lib/`, with a plethora of files underneath. You can delete `lib.zip` from the _CIRCUITPY_ volume, as it's no longer needed.
    - It has been reported that this step may fail ([Issue #2](https://github.com/metro-sign/dc-metro/issues/2)), most likely due to the storage on the Matrix Portal not being able to handle the decompression. If this happens, unzip the `lib.zip` file on your computer, and copy the `lib/` folder to the Matrix Portal. Command line tools could also be used if the above doesn't work.
4. Copy all of the Python files from `src/` in this repository into the root of the _CIRCUITPY_ volume.
5. The board should now light up with a loading screen, but we've still got some work to do.

## Part 3: Configuring the Board
1. Open the `[config.py](src/config.py)` file located in the root of the _CIRCUITPY_ volume.
2. Fill in your WiFi SSID and password under the **Network Configuration** section.
3. Under the **League Configuration** section:
    1. Set `leagueId` and `teamId` to your league and team.
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
```

5. After you save this file, your board should refresh and connect to ESPN.

> [!TIP]
> If something goes wrong, take a peek at the [Adafruit Documentation](https://learn.adafruit.com/adafruit-matrixportal-m4). Additionally, you can connect to the board using a [serial connection](https://learn.adafruit.com/welcome-to-circuitpython/kattni-connecting-to-the-serial-console) to gain access to its logging.
