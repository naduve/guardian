"""
Guardian — Step 1: OLED Test
Gate: text visible on screen → git commit -m "step1: OLED works"

Wiring (I2C):
  VCC → Pin 1  (3.3V)
  GND → Pin 6  (GND)
  SDA → Pin 3  (GPIO2)
  SCL → Pin 5  (GPIO3)

Setup (once):
  sudo raspi-config        # Interface Options → I2C → Enable → reboot
  sudo apt install -y i2c-tools
  i2cdetect -y 1           # should show 0x3c
  pip3 install luma.oled --break-system-packages
"""

import time
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

# ── Config ──────────────────────────────────────────────────────────────────
I2C_ADDRESS = 0x3C   # change to 0x3D if i2cdetect shows that instead
I2C_PORT    = 1      # always 1 on Pi 3/4/5/Zero 2W

# ── Init ─────────────────────────────────────────────────────────────────────
serial = i2c(port=I2C_PORT, address=I2C_ADDRESS)
device = ssd1306(serial)          # 128×64

def draw_screen(db_value=None):
    """Draw the Guardian UI. Pass a float for dB, or None for placeholder."""
    with canvas(device) as draw:
        # Title bar
        draw.rectangle([(0, 0), (127, 14)], fill="white")
        draw.text((4, 2), "◆ GUARDIAN", fill="black")

        # dB reading (big)
        if db_value is not None:
            label = f"{db_value:.1f} dB(A)"
        else:
            label = "-- dB(A)"
        draw.text((10, 20), label, fill="white")

        # Sub-labels (will be wired up in later steps)
        draw.text((0, 40), "Dose: --%", fill="white")
        draw.text((0, 52), "Step 1 OK", fill="white")

        # Right side: I2C address confirmation
        draw.text((80, 52), f"0x{I2C_ADDRESS:02X}", fill="white")


print("Guardian OLED test — press Ctrl+C to stop")
print(f"Connecting to SSD1306 at I2C port {I2C_PORT}, address 0x{I2C_ADDRESS:02X} ...")

try:
    t = 0
    while True:
        draw_screen()           # static placeholder; swap in real dB later
        time.sleep(0.5)
        t += 0.5
        if int(t) % 10 == 0:
            print(f"  {int(t)}s — screen alive")
except KeyboardInterrupt:
    device.cleanup()
    print("\nDone. If you saw text on the display → Gate 1 ✅")
    print("Next: git commit -m 'step1: OLED works'")
