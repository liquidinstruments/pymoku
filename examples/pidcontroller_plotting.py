# pymoku example: PID Controller Plotting Example
#
# This script demonstrates how to configure both PID Controllers
# in the PID Controller instrument. Configuration on the Channel 1
# PID is done by specifying frequency response characteristics,
# while Channel 2 specifies the gain characteristics.
#
# The output response of each PID Controller channel is plotted
# in real-time.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import PIDController

import math
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

def from_dB(dB):
    # Helper function that converts from dB to linear scale
    return 10**(dB/20.0)

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(PIDController)

    # Configure the Channel 1 PID Controller using frequency response characteristics
    #   P = -10dB
    #   I Crossover = 100Hz
    #   D Crossover = 10kHz
    #   I Saturation = 10dB
    #   D Saturation = 10dB
    #   Double-I = OFF
    # Note that gains must be converted from dB first
    i.set_by_frequency(1, kp=from_dB(-10), i_xover=1e2, ii_xover=None, d_xover =1e4, si=from_dB(10), sd=from_dB(10))

    # Configure the Channel 2 PID Controller using gain characteristics
    #   Overall Gain = 6dB
    #   I Gain       = 20dB
    #   I Saturation = 40dB
    # Note that gains must be converted from dB first
    i.set_by_gain(2, g=from_dB(6.0), ki=from_dB(20), si=from_dB(25))

    # Set which signals to view on each monitor channel, and the timebase on
    # which to view them.
    i.set_monitor('a', 'out1')
    i.set_monitor('b', 'out2')

    # +- 1msec
    i.set_timebase(-1e-3, 1e-3)
    i.set_trigger('a', 'rising', 0)

    i.enable_output(1, True)
    i.enable_output(2, True)

    # Get initial data frame to set up plotting parameters. This can be done once
    # if we know that the axes aren't going to change (otherwise we'd do
    # this in the loop)
    data = i.get_realtime_data()

    # Set up the plotting parameters
    plt.ion()
    plt.show()
    plt.grid(b=True)
    plt.ylim([-1,1])
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
    m.close()
