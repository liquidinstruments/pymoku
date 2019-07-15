# pymoku example: FIR Filter Box Plotting Example
#
# This script demonstrates how to generate an FIR filter kernel with specified
# parameters using the scipy library, and how to configure settings of the FIR
# instrument.
#
# NOTE: FIR kernels should have a normalised power of <= 1.0. Scipy's firwin
# function conforms to this requirement.
#
# (c) 2019 Liquid Instruments
#
from pymoku import Moku
from pymoku.instruments import FIRFilter
from scipy.signal import firwin
from scipy import fft
import math
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Specify nyquist and cutoff (-3dB) frequencies
nyq_rate = 125e6 / 2**10 / 2.0
cutoff_hz = 1e3

# Calculate FIR kernel using 1000 taps and a chebyshev window with -60dB
# stop-band attenuation
taps = firwin(1000, cutoff_hz/nyq_rate, window='hamming')

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(FIRFilter)

    # Configure the Moku:Lab frontend settings
    i.set_frontend(1, fiftyr = True, atten = False, ac = False)
    i.set_frontend(2, fiftyr = True, atten = False, ac = False)

    # Both filter channels are configured with the same FIR kernel. A decimation
    # factor of 10 is used to achieve the desired nyquist rate and FIR kernel
    # length of 1000.
    i.set_filter(1, decimation_factor = 10, filter_coefficients = taps)
    i.set_filter(2, decimation_factor = 10, filter_coefficients = taps)

    # Channel 1 has unity input/output gain and acts solely on ADC1.
    # Channel 2 has an input gain of 0.5, output gain of 2.0, input offset of
    # -0.1V and acts on signal 0.5 * ADC1 + 0.5 * ADC2.
    i.set_gains_offsets(1, input_gain = 1.0, output_gain = 1.0)
    i.set_gains_offsets(2, input_gain = 0.5, input_offset = -0.1,
        output_gain = 1.0)
    i.set_control_matrix(1, 1.0, 0.0)
    i.set_control_matrix(2, 0.5, 0.5)

    # Set which signals to view on each monitor channel, and the timebase on
    # which to view them.
    i.set_timebase(-5e-3, 5e-3)
    i.set_monitor('a', 'in1')
    i.set_monitor('b', 'out1')

    # Calculate and plot the quantized FIR kernel and transfer function for
    # reference.
    taps_quantized = \
     [round(taps[x]*2.0**24-1) / (2**24 - 1) for x in range(0,len(taps))]
    fft_taps = fft(taps_quantized)
    fft_mag = [abs(fft_taps[x]) for x in range(0,len(fft_taps[0:499]))]
    fft_db = [20*math.log10(fft_mag[x]) for x in range(0,len(fft_mag))]

    plt.subplot(221)
    plt.plot(taps)
    plt.title('Filter Kernel')
    plt.ylabel('Normalised Value')
    plt.grid(True, which = 'major')
    plt.xlabel('Kernel Tap Number')
    plt.subplot(222)
    plt.semilogx(fft_db)
    plt.title('Filter Transfer Function')
    plt.ylabel('Magnitude (dB)')
    plt.xlabel('Frequency (Hz)')
    plt.grid(True, which = 'major')

    # Set up the live FIR Filter Box monitor signal plot
    plt.subplot(212)
    plt.title("Monitor Signals")
    plt.suptitle("FIR Filter Box", fontsize=16)
    plt.grid(b=True, which='both', axis='both')
    data = i.get_realtime_data() # Get data to determine the signal timebase
    plt.xlim([data.time[0], data.time[-1]])
    plt.ylim([-1.0,1.0]) # View up to +-1V

    line1, = plt.plot([], label='Channel A')
    line2, = plt.plot([], label='Channel B')

    ax = plt.gca()
    ax.legend(loc="lower right")
    ax.xaxis.set_major_formatter(FuncFormatter(data.get_xaxis_fmt))
    ax.yaxis.set_major_formatter(FuncFormatter(data.get_yaxis_fmt))
    ax.fmt_xdata = data.get_xcoord_fmt
    ax.fmt_ydata = data.get_ycoord_fmt

    # Continually update the monitor signal data being displayed
    while True:
        data = i.get_realtime_data()
        line1.set_ydata(data.ch1)
        line2.set_ydata(data.ch2)
        line1.set_xdata(data.time)
        line2.set_xdata(data.time)
        plt.pause(0.001)

finally:
    m.close()
