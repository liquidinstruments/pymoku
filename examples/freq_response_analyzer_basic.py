#
# pymoku example: Basic Frequency Response Analyzer
#
# This example demonstrates how you can generate output sweeps using the
# Frequency Response Analyzer instrument, and view transfer function data in real-time.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import FrequencyResponseAnalyzer
import logging

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    # Deploy the Frequency Response Analyzer to your Moku
    i = m.deploy_or_connect(FrequencyResponseAnalyzer)

    # Configure output sweep parameters (100Hz-20MHz)
    i.set_sweep(f_start=100,f_end=20e6,sweep_points=256)

    # Configure output sweep amplitudes
    # Channel 1 - 0.1Vpp
    # Channel 1 - 0.1Vpp
    i.set_output(1, 0.1)
    i.set_output(2, 0.1)

    # Start the sweep
    i.start_sweep(single=True)

    # Get a single sweep frame. This will block until the sweep is complete, beware
    # if your range includes low frequencies!
    frame = i.get_data()

    # Print out the data for Channel 1
    print(frame.ch1.magnitude_dB, frame.ch1.phase, frame.frequency)
finally:
    m.close()
