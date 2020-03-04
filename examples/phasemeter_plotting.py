#
# pymoku example: Plotting Phasemeter
#
# This example demonstrates how you can configure the Phasemeter instrument
# and stream dual-channel samples of the form [fs, f, count, phase, I, Q].
# The signal amplitude is calculated using these samples, and plotted for
# real-time viewing.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku, StreamException
from pymoku.instruments import Phasemeter
import math
import numpy
import matplotlib.pyplot as plt

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(Phasemeter)

    # Set samplerate to slow mode ~30Hz
    i.set_samplerate('slow')

    # Set up signal generator outputs
    # Channel 1 - 5MHz, 0.5Vpp Sinewave
    # Channel 2 - 10MHz, 1.0Vpp Sinewave
    i.gen_sinewave(1, 0.5, 5e6)
    i.gen_sinewave(2, 1.0, 10e6)

    # Restart the phase-lock loop for both channels, and automatically
    # resolve the starting frequency (as opposed to manually setting a seed
    # frequency)
    i.auto_acquire()

    # Stop any existing streaming session and start a new one
    # Logging session:
    #       Duration - 20 sec
    #       Channel 1 - ON, Channel 2 - ON
    i.stop_stream_data()
    i.start_stream_data(duration=20, ch1=True, ch2=True)

    # Set up plotting configuration
    plot_points = 500

    ydata1 = [None] * plot_points
    line1, = plt.plot(ydata1)

    ydata2 = [None] * plot_points
    line2, = plt.plot(ydata2)

    xtent = -1 * (i.get_timestep() * (plot_points - 1))
    xdata = numpy.linspace(xtent, 0, plot_points)

    plt.ion()
    plt.show()
    plt.grid(b=True)
    ax = plt.gca()
    ax.get_yaxis().get_major_formatter().set_useOffset(False)
    plt.xlim([xtent, 0])
    plt.ylabel('Amplitude (V)')
    plt.xlabel('Time (s)')

    # This loop gets and plots the samples being streamed by the Phasemeter
    # over the network
    while True:

        # Get samples off the network
        data = i.get_stream_data()
        # If data is empty then the streaming session has completed
        if not any(data):
            break

        # Process the retrieved samples from both channels
        # Each sample has format [fs, f, count, phase, I, Q]
        # Convert I,Q to amplitude and append to line graph
        ch1_samples = data[0]
        ydata1 += [math.sqrt(s[4]**2 + s[5]**2) for s in data[0]]
        ydata2 += [math.sqrt(s[4]**2 + s[5]**2) for s in data[1]]

        ydata1 = ydata1[-plot_points:]
        ydata2 = ydata2[-plot_points:]

        # Update the plotted line graphs with the new data
        line1.set_ydata(ydata1)
        line1.set_xdata(xdata)

        line2.set_ydata(ydata2)
        line2.set_xdata(xdata)

        ax.relim()
        ax.autoscale_view()
        plt.pause(0.001)
        plt.draw()

    i.stop_stream_data()

except StreamException as e:
    print("Error occured: %s" % e)
finally:
    m.close()
