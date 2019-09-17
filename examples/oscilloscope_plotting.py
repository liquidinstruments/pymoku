"""pymoku example: Plotting Oscilloscope

This example demonstrates how you can configure the Oscilloscope instrument,
and view triggered time-voltage data frames in real-time.

(c) 2019 Liquid Instruments Pty. Ltd.
"""

from pymoku import Moku
from pymoku.instruments import Oscilloscope

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(Oscilloscope)

    # Trigger on input Channel 1, rising edge, 0V with 0.1V hysteresis
    i.set_trigger('in1', 'rising', 0, hysteresis=0.1)

    # View +-5usec, i.e. trigger in the centre
    i.set_timebase(-5e-6, 5e-6)

    # Generate an output sinewave on Channel 2, 500mVpp, 1MHz, 0V offset
    i.gen_sinewave(2, 0.5, 1e6, 0)

    # Set the data source of Channel 1 to be Input 1
    i.set_source(1, 'in1')

    # Set the data source of Channel 2 to the generated output sinewave
    i.set_source(2, 'out2')

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
