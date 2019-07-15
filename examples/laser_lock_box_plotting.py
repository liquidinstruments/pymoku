#
# pymoku example: Plotting - Laser Lock Box
#
# This example demonstrates how you can configure the laser lock box
# instrument and monitor signals at each oscilloscope probe point.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import LaserLockBox

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from scipy import signal

def gen_butterworth(corner_frequency):
    """
    Generate coefficients for a second order butterworth low-pass filter.

    Corner frequencies for laser lock box second harmonic filtering should be in the range: 1 kHz < corner frequency < 31.25 MHz.
    """
    sample_rate = 31.25e6
    normalised_corner = corner_frequency / (sample_rate / 2)
    b, a = signal.butter(2, normalised_corner, 'low', analog = False)

    coefficient_array = [[1.0, b[0], b[1], b[2], -a[1], -a[2]],
                        [1.0, 1.0,  0.0,  0.0,  0.0, 0.0]]
    return coefficient_array

# Use Moku.get_by_serial() or get_by_name() if you don't know the IP
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(LaserLockBox)

    # set enables
    i.set_output_enables(1, True)
    i.set_output_enables(2, True)
    i.set_pid_enables(1, True)
    i.set_pid_enables(2, False)
    i.set_channel_pid_enables(1, True)
    i.set_channel_pid_enables(2, True)

    # set local oscillator, auxiliary and scan generators
    i.set_local_oscillator(source='internal', frequency=10e3, phase=0, pll_auto_acq = False)
    i.set_aux_sine(amplitude = 1.0, frequency = 10e3, phase=0, sync_to_lo = False, output = 'out1')
    i.set_scan(frequency=1e3, phase=0, output = 'out2', amplitude=1.0, waveform='triangle')

    # configure PIDs:
    i.set_pid_by_gain(1, g=1, kp=1)
    i.set_pid_by_gain(2, g=1, kp=1)

    # set offsets
    i.set_offsets(position = 'pid_input', offset = 0.1)
    i.set_offsets(position = 'out1', offset = -0.1)
    i.set_offsets(position = 'out2', offset = 0.2)

    # set allowable output range
    i.set_output_range(1, 0.5, -0.5)
    i.set_output_range(2, 0.5, -0.5)

    # configure second harmonic rejection low pass filter
    coef_array = gen_butterworth(1e4)
    i.set_custom_filter(coef_array)

    # Monitor the error signal and fast pid output signal
    i.set_monitor('A', 'pid_fast')
    i.set_monitor('B', 'pid_slow') #green

    # Trigger on rising edge of the scan signal, 0V threshold level with 0.1V hysteresis
    i.set_trigger('scan', 'rising', level = 0, hysteresis = 0.1, trig_on_scan_rising = True)

     # View +- 2 millisecond, i.e. trigger in the centre
    i.set_timebase(-2e-3, 2e-3)

    # Get initial data frame to set up plotting parameters. This can be done once
    # if we know that the axes aren't going to change (otherwise we'd do
    # this in the loop)
    data = i.get_realtime_data()

    # Set up the plotting parameters
    plt.ion()
    plt.show()
    plt.grid(b=True)
    plt.ylim([-2,2])
    plt.xlim([data.time[0], data.time[-1]])

    line1, = plt.plot([])
    line2, = plt.plot([])

    # Configure labels for axes
    ax = plt.gca()
    ax.xaxis.set_major_formatter(FuncFormatter(data.get_xaxis_fmt))
    ax.yaxis.set_major_formatter(FuncFormatter(data.get_yaxis_fmt))
    ax.fmt_xdata = data.get_xcoord_fmt
    ax.fmt_ydata = data.get_ycoord_fmt

    # This loops continuously updates the plot with new data
    while True:
        # Get new data
        data = i.get_realtime_data()

        # Update the plot
        line1.set_ydata(data.ch1)
        line2.set_ydata(data.ch2)
        line1.set_xdata(data.time)
        line2.set_xdata(data.time)
        plt.pause(0.001)
finally:
    # Close the connection to the Moku device
    # This ensures network resources and released correctly
    m.close()

