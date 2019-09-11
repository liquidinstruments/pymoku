"""pymoku example: Plotting IIR Filter Box

This example demonstrates how you can configure the IIR Filter instrument,
configure real-time monitoring of the input and output signals.

(c) 2019 Liquid Instruments Pty. Ltd.
"""
from pymoku import Moku
from pymoku.instruments import IIRFilterBox

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# This script provides a basic example showing how to load coefficients from an
# array into the IIRFilterBox and how to set up oscilloscope probes to monitor
# time domain signals at different points in the instrument.

# The following example array produces an 8th order Direct-form 1 Chebyshev
# type 2 IIR filter with a normalized stopband frequency of 0.2 pi rad/sample
# and a stopband attenuation of 40 dB. Output gain is set to 1.0. See the
# IIRFilterBox documentation for array dimension specifics.
filt_coeff = [
    [
        1.0000000000
    ], [
        1.0000000000, 0.6413900006, -1.0290561741,
        0.6413900006, -1.6378425857, 0.8915664128
    ], [
        1.0000000000, 0.5106751138, -0.7507394931,
        0.5106751138, -1.4000444473, 0.6706551819
    ], [
        1.0000000000, 0.3173108134, -0.3111365531,
        0.3173108134, -1.0873085012, 0.4107935750
    ], [
        1.0000000000, 0.1301131088, 0.1223154629,
        0.1301131088, -0.7955572476, 0.1780989281
    ]
]

m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(IIRFilterBox)

    i.set_frontend(1, fiftyr=True, atten=False, ac=False)
    i.set_frontend(2, fiftyr=True, atten=False, ac=False)

    # Both filters have the same coefficients, but the different sampling rates
    # mean the resultant transfer functions will be different by a factor of
    # 128 (the ratio of sampling rates)
    i.set_filter(1, sample_rate='high', filter_coefficients=filt_coeff)
    i.set_filter(2, sample_rate='low', filter_coefficients=filt_coeff)

    # Filter channel 1 acts solely on the data from ADC CH1. Filter channel 2
    # acts solely on ADC CH 2.
    i.set_control_matrix(1, scale_in1=1.0, scale_in2=0.0)
    i.set_control_matrix(2, scale_in1=0.0, scale_in2=1.0)

    # Set up monitoring on the input and output of the first filter channel.
    i.set_monitor('a', 'in1')
    i.set_monitor('b', 'out1')

    # Trigger on monitor channel 'a', rising edge, 0V with 0.1V hysteresis
    i.set_trigger('a', 'rising', 0)

    # View +/- 1 microsecond with the trigger point centered
    i.set_timebase(-1e-3, 1e-3)

    # Get initial data frame to set up plotting parameters.
    data = i.get_realtime_data()

    # Set up the plotting parameters
    plt.ion()
    plt.show()
    plt.grid(b=True, which='both', axis='both')
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
    m.close()
