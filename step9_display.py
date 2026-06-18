#!/usr/bin/env python3
"""
Guardian — Step 9 + Step 5: Live dB(A) + frequency bands on OLED
Bands: Sub (20-150Hz) and Risk (2-5kHz)

Run: python3 step9_display.py
"""

import numpy as np
import sounddevice as sd
import time, math, collections
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

# ── Config ────────────────────────────────────────────────────────────────────
DEVICE       = 0
FS           = 48000
BLOCK        = 4096
CHANNELS     = 2
MIC_SENS     = -26.0
CAL_OFFSET   = 2.0
EXCHANGE     = 3.0
CRITERION    = 85.0

I2C_ADDRESS  = 0x3C
I2C_PORT     = 1

# ── OLED setup ────────────────────────────────────────────────────────────────
serial = i2c(port=I2C_PORT, address=I2C_ADDRESS)
device = ssd1306(serial)
W, H = 128, 64

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
try:
    font_big   = ImageFont.truetype(FONT_PATH, 20)
    font_med   = ImageFont.truetype(FONT_PATH, 11)
    font_small = ImageFont.truetype(FONT_PATH, 9)
except IOError:
    font_big = font_med = font_small = ImageFont.load_default()

# ── A-weighting ───────────────────────────────────────────────────────────────
freqs  = np.fft.rfftfreq(BLOCK, 1/FS)
f2     = freqs ** 2
ra     = (12194**2 * f2**2) / (
            (f2 + 20.6**2)
            * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2))
            * (f2 + 12194**2))
with np.errstate(divide='ignore'):
    A_DB = 20 * np.log10(ra) + 2.0
A_DB[np.isneginf(A_DB)] = -120

window    = np.hanning(BLOCK)
win_corr  = 1.0 / np.sqrt(np.mean(window ** 2))
BAND_SUB  = (freqs >= 20)   & (freqs < 150)
BAND_RISK = (freqs >= 2000) & (freqs < 5000)

# ── State ─────────────────────────────────────────────────────────────────────
leq_hist = collections.deque(maxlen=12)
dose     = 0.0
t_last   = time.time()

# ── Processing ────────────────────────────────────────────────────────────────
def process(indata):
    global dose, t_last
    x = indata[:, 0].astype(np.float64)
    x -= np.mean(x)
    X       = np.fft.rfft(x * window) * win_corr / (BLOCK / 2)
    p_dbfs  = 20 * np.log10(np.abs(X) + 1e-12)
    p_spl   = p_dbfs - MIC_SENS + 94 + CAL_OFFSET
    p_spl_a = p_spl + A_DB
    dba     = 10 * np.log10(np.sum(10 ** (p_spl_a / 10)) + 1e-12)
    sub_db  = 10 * np.log10(np.sum(10 ** (p_spl[BAND_SUB]  / 10)) + 1e-12)
    risk_db = 10 * np.log10(np.sum(10 ** (p_spl_a[BAND_RISK] / 10)) + 1e-12)
    now = time.time(); dt = now - t_last; t_last = now
    if dba > 80:
        allowed = 8 * 3600 / (2 ** ((dba - CRITERION) / EXCHANGE))
        dose   += 100 * dt / allowed
    leq_hist.append(dba)
    leq1m = 10 * np.log10(np.mean(10 ** (np.array(leq_hist) / 10)))
    if leq1m > 80:
        remain_min = max(0, (100-dose)/100 * 8*3600 / (2**((leq1m-CRITERION)/EXCHANGE)) / 60)
    else:
        remain_min = float('inf')
    return dba, leq1m, dose, remain_min, sub_db, risk_db

def db_to_bar(db, min_db=40, max_db=100, width=44):
    """Convert dB value to bar pixel width."""
    frac = max(0.0, min(1.0, (db - min_db) / (max_db - min_db)))
    return int(frac * width)

# ── OLED display ──────────────────────────────────────────────────────────────
def draw_screen(dba, leq, dose, remain_min, sub_db, risk_db):
    if dba >= 100 or dose >= 100 or risk_db >= 95:
        level = 2
    elif dba >= 85 or dose >= 50:
        level = 1
    else:
        level = 0

    status = ["OK", "WARN", "DANGER"][level]

    if remain_min == float('inf'):
        rem_s = "safe"
    elif remain_min > 60:
        rem_s = f"{remain_min/60:.0f}h"
    else:
        rem_s = f"{remain_min:.0f}m"

    dose_bar = min(127, int(dose / 100 * 127))

    with canvas(device) as draw:
        # ── Title bar ──
        draw.rectangle([(0, 0), (127, 12)], fill="white")
        draw.text((2, 1), "GUARDIAN", font=font_small, fill="black")
        draw.text((80, 1), status, font=font_small, fill="black")

        # ── Big dB(A) ──
        draw.text((2, 13), f"{dba:.1f}", font=font_big, fill="white")
        draw.text((80, 16), "dB(A)", font=font_small, fill="white")
        draw.text((80, 26), f"Leq {leq:.0f}", font=font_small, fill="white")

        # ── Band bars ──
        # Sub label + bar
        draw.text((2, 36), "SUB", font=font_small, fill="white")
        sub_w = db_to_bar(sub_db)
        draw.rectangle([(24, 37), (68, 44)], outline="white")
        if sub_w > 0:
            draw.rectangle([(24, 37), (24 + sub_w, 44)], fill="white")
        draw.text((70, 37), f"{sub_db:.0f}", font=font_small, fill="white")

        # Risk label + bar
        draw.text((2, 47), "2-5k", font=font_small, fill="white")
        risk_w = db_to_bar(risk_db)
        draw.rectangle([(24, 48), (68, 55)], outline="white")
        if risk_w > 0:
            draw.rectangle([(24, 48), (24 + risk_w, 55)], fill="white")
        draw.text((70, 47), f"{risk_db:.0f}", font=font_small, fill="white")

        # ── Dose bar ──
        draw.rectangle([(0, 57), (127, 63)], outline="white")
        if dose_bar > 0:
            draw.rectangle([(0, 57), (dose_bar, 63)], fill="white")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Guardian — live display with frequency bands. Ctrl+C to stop")
    print(f"{'dB(A)':>6}  {'Leq':>6}  {'Dose%':>6}  {'Left':>6}  {'Sub':>5}  {'2-5k':>5}")
    print("-" * 45)

    with sd.InputStream(device=DEVICE, samplerate=FS, blocksize=BLOCK,
                        channels=CHANNELS, dtype='float32') as stream:
        while True:
            data, _ = stream.read(BLOCK)
            dba, leq, d, rem, sub, risk = process(data)
            draw_screen(dba, leq, d, rem, sub, risk)
            rem_s = "safe" if rem == float('inf') else f"{rem:.0f}m"
            print(f"{dba:6.1f}  {leq:6.1f}  {d:6.2f}  {rem_s:>6}  {sub:5.0f}  {risk:5.0f}")

if __name__ == "__main__":
    main()
