"""
Guardian — OLED Fun Animation
Bouncing title (big font) + pulsing bar + scrolling ticker
"""

import time
import math
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

I2C_ADDRESS = 0x3C
I2C_PORT    = 1

serial = i2c(port=I2C_PORT, address=I2C_ADDRESS)
device = ssd1306(serial)

W, H = 128, 64

# Load fonts — falls back to default if DejaVu not installed
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
try:
    font_big    = ImageFont.truetype(FONT_PATH, 16)   # title
    font_small  = ImageFont.truetype(FONT_PATH, 10)   # ticker
    print("Using DejaVu font")
except IOError:
    font_big   = ImageFont.load_default()
    font_small = ImageFont.load_default()
    print("DejaVu not found — using default font")
    print("Install with: sudo apt install -y fonts-dejavu-core")

TICKER = "  GUARDIAN  |  noise protection  |  step 1 done  |  mic incoming  "
ticker_x = float(W)
TICKER_CHAR_W = 7   # approx px per char at size 10

print("Animation running -- Ctrl+C to stop")

try:
    while True:
        t = time.time()

        bounce_y = int(2 + 6 * abs(math.sin(t * 2.5)))
        bar_w    = int(10 + 100 * abs(math.sin(t * 1.5)))

        with canvas(device) as draw:
            # Big bouncing title
            draw.text((4, bounce_y), "GUARDIAN", font=font_big, fill="white")

            # Divider
            draw.line([(0, 22), (W, 22)], fill="white")

            # Pulsing bar
            draw.rectangle([(0, 26), (bar_w, 34)], fill="white")

            # Divider
            draw.line([(0, 38), (W, 38)], fill="white")

            # Scrolling ticker
            draw.text((int(ticker_x), 42), TICKER, font=font_small, fill="white")

        ticker_x -= 2
        if ticker_x < -(len(TICKER) * TICKER_CHAR_W):
            ticker_x = float(W)

        time.sleep(0.04)

except KeyboardInterrupt:
    device.cleanup()
    print("Done.")
