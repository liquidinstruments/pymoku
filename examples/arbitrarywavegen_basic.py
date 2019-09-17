"""pymoku example: Arbitrary waveform generator

This example demonstrates how you can generate and output arbitrary
waveforms using Moku:AWG

(c) 2019 Liquid Instruments Pty. Ltd.
"""
from pymoku import Moku
from pymoku.instruments import ArbitraryWaveGen
import numpy as np

# generate a signal the the Arb Waveform Gen should generate on the output
t = np.linspace(0, 1, 100)  # Evaluate our waveform at 100 points

# Simple square wave (can also use scipy.signal)
sq_wave = np.array([-1.0 if x < 0.5 else 1.0 for x in t])

# More interesting waveform. Note that we have to normalize this waveform
# to the range [-1, 1]
not_sq = np.zeros(len(t))
for h in np.arange(1, 15, 2):
    not_sq += (4 / (np.pi * h)) * np.cos(2 * np.pi * h * t)

not_sq = not_sq / max(not_sq)

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

# Prepare the ArbitraryWaveGen instrument
i = m.deploy_or_connect(ArbitraryWaveGen)

try:
    # Load the waveforms to the device. This doesn't yet generate an output as
    # we haven't set the amplitude, frequency etc; this only defines the shape.
    i.write_lut(1, not_sq)
    i.write_lut(2, sq_wave)

    # We have configurable on-device linear interpolation between LUT points.
    # Normally interpolation is a good idea, but for sharp edges like square
    # waves it will improve jitter but reduce rise-time. Configure whatever's
    # suitable for your application.
    i.gen_waveform(1, period=1e-6, amplitude=1, interpolation=True)
    i.gen_waveform(2, period=1e-6, amplitude=2, interpolation=False)
finally:
    m.close()
