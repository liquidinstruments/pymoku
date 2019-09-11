"""pymoku example: Basic Laser Lock Box

This example demonstrates how you can configure the laser lock box
instrument

(c) 2019 Liquid Instruments Pty. Ltd.
"""
from pymoku import Moku
from pymoku.instruments import LaserLockBox

from scipy import signal


def gen_butterworth(corner_frequency):
    """
    Generate coefficients for a second order butterworth low-pass filter.

    Corner frequencies for laser lock box second harmonic filtering should be
    in the range: 1 kHz < corner frequency < 31.25 MHz.
    """
    sample_rate = 31.25e6
    normalised_corner = corner_frequency / (sample_rate / 2)
    b, a = signal.butter(2, normalised_corner, 'low', analog=False)

    coefficient_array = [[1.0, b[0], b[1], b[2], -a[1], -a[2]],
                         [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]]
    return coefficient_array


# Use Moku.get_by_serial() or get_by_name() if you don't know the IP
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(LaserLockBox)

    # set local oscillator, auxiliary and scan generators
    i.set_local_oscillator(source='internal', frequency=0, phase=90,
                           pll_auto_acq=False)
    i.set_aux_sine(amplitude=1.0, frequency=10e3, phase=0, sync_to_lo=False,
                   output='out1')
    i.set_scan(frequency=1e3, phase=0, output='out2', amplitude=1.0,
               waveform='triangle')

    # configure PIDs:
    i.set_pid_by_gain(1, g=1, kp=1)
    i.set_pid_by_gain(2, g=1, kp=1)

    # configure second harmonic rejection low pass filter
    coef_array = gen_butterworth(1e4)
    i.set_custom_filter(coef_array)

finally:
    # Close the connection to the Moku device
    # This ensures network resources and released correctly
    m.close()
