#
# pymoku example: Plotting Lock-in Amplifier
#
# This example demonstrates how you can configure the lock-in amplifier
# instrument and monitor the signals in real-time
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import LockInAmp

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(LockInAmp)

    # Output a 1MHz sine wave but demodulate at a harmonic (2MHz)
    i.set_demodulation('internal', 2e6)
    i.set_lo_output(1.0, 1e6, 0)

    # Output the 'X' (I) signal and the local-oscillator sine wave on the two
    # DAC channels. Configure a PID controller on the main 'X' output with
    # a proportional gain of 10x, integrator cross-over of 10Hz and integrator
    # saturation at 100x
    i.set_outputs('X', 'sine')
    i.set_pid_by_frequency('main', kp=10, i_xover=10, si=100)

    # Monitor the I and Q signals from the mixer, before filtering
    i.set_monitor('A', 'I')
    i.set_monitor('B', 'Q')

    # Trigger on Monitor 'B' ('Q' signal), rising edge, 0V with 0.1V hysteresis
    i.set_trigger('B', 'rising', 0)

    # View +- 0.1 second, i.e. trigger in the centre
    i.set_timebase(-1e-6, 1e-6)

    # Get initial data frame to set up plotting parameters. This can be done
    # once if we know that the axes aren't going to change (otherwise we'd do
    # this in the loop)
    data = i.get_realtime_data()

    # Set up the plotting parameters
    plt.ion()
    plt.show()
    plt.grid(b=True)
    plt.ylim([-1, 1])
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
