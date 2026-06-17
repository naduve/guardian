#!/usr/bin/env python3
"""
Guardian — Step 3: Measurement Engine
Gate: dB(A) numbers respond logically to sound (loud = up, quiet = down ~30-40)
No new hardware — runs on mic from Step 2.

Run: python3 step3_engine.py
"""

import numpy as np
import sounddevice as sd
import time, math, collections

# ── Config ────────────────────────────────────────────────────────────────────
DEVICE       = 0          # googlevoicehat (from query_devices())
FS           = 48000      # sample rate
BLOCK        = 4096       # ~85ms per block
CHANNELS     = 2          # hardware needs 2ch; we use left channel only
MIC_SENS     = -26.0      # INMP441 sensitivity dBFS @ 94dB SPL
CAL_OFFSET   = 2.0        # rough cal vs NIOSH app — refine with UT353 in Step 4
EXCHANGE     = 3.0        # NIOSH 3dB exchange rate
CRITERION    = 85.0       # 85 dB(A) / 8h = 100% dose

# ── A-weighting (IEC 61672) ───────────────────────────────────────────────────
freqs  = np.fft.rfftfreq(BLOCK, 1/FS)
f2     = freqs ** 2
ra     = (12194**2 * f2**2) / (
            (f2 + 20.6**2)
            * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2))
            * (f2 + 12194**2))
with np.errstate(divide='ignore'):
    A_DB = 20 * np.log10(ra) + 2.0
A_DB[np.isneginf(A_DB)] = -120

window   = np.hanning(BLOCK)
win_corr = 1.0 / np.sqrt(np.mean(window ** 2))

# Frequency bands
BAND_SUB  = (freqs >= 20)   & (freqs < 150)
BAND_RISK = (freqs >= 2000) & (freqs < 5000)

# ── State ─────────────────────────────────────────────────────────────────────
leq_hist = collections.deque(maxlen=12)   # ~1 min of 5s blocks
dose     = 0.0
t_last   = time.time()

# ── Processing ────────────────────────────────────────────────────────────────
def process(indata):
    global dose, t_last

    x = indata[:, 0].astype(np.float64)   # left channel only
    x -= np.mean(x)                        # remove DC offset

    # FFT spectrum
    X       = np.fft.rfft(x * window) * win_corr / (BLOCK / 2)
    p_dbfs  = 20 * np.log10(np.abs(X) + 1e-12)

    # dBFS → dB SPL
    p_spl   = p_dbfs - MIC_SENS + 94 + CAL_OFFSET
    p_spl_a = p_spl + A_DB

    # Overall dB(A)
    dba = 10 * np.log10(np.sum(10 ** (p_spl_a / 10)) + 1e-12)

    # Band energies
    sub_db  = 10 * np.log10(np.sum(10 ** (p_spl[BAND_SUB]  / 10)) + 1e-12)
    risk_db = 10 * np.log10(np.sum(10 ** (p_spl_a[BAND_RISK] / 10)) + 1e-12)

    # NIOSH dose
    now = time.time()
    dt  = now - t_last
    t_last = now
    if dba > 80:
        allowed = 8 * 3600 / (2 ** ((dba - CRITERION) / EXCHANGE))
        dose   += 100 * dt / allowed

    # Leq over last ~1 min
    leq_hist.append(dba)
    leq1m = 10 * np.log10(np.mean(10 ** (np.array(leq_hist) / 10)))

    # Time remaining at current Leq
    if leq1m > 80:
        remain = (100 - dose) / 100 * 8 * 3600 / (2 ** ((leq1m - CRITERION) / EXCHANGE))
        remain_min = max(0, remain / 60)
    else:
        remain_min = float('inf')

    return dba, leq1m, dose, remain_min, sub_db, risk_db


def alert_level(dba, dose, risk_db):
    if dba >= 100 or dose >= 100 or risk_db >= 95:
        return "🔴 DANGER"
    if dba >= 85 or dose >= 50:
        return "🟡 WARN  "
    return "🟢 OK    "


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Guardian measurement engine — Ctrl+C to stop")
    print("Speak or clap near the mic. Quiet room should read ~35-45 dB(A)\n")
    print(f"{'Level':<10} {'dB(A)':>6} {'Leq1m':>6} {'Dose%':>6} {'Left':>8} {'Sub':>5} {'2-5k':>5}")
    print("-" * 55)

    with sd.InputStream(device=DEVICE, samplerate=FS, blocksize=BLOCK,
                        channels=CHANNELS, dtype='float32') as stream:
        while True:
            data, _ = stream.read(BLOCK)
            dba, leq, d, rem, sub, risk = process(data)
            lvl = alert_level(dba, d, risk)
            rem_s = "inf" if rem == float('inf') else f"{rem:.0f}m"
            print(f"{lvl}  {dba:6.1f}  {leq:6.1f}  {d:6.2f}  {rem_s:>8}  {sub:5.0f}  {risk:5.0f}")


if __name__ == "__main__":
    main()
