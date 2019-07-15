#
# pymoku example: Basic Oscilloscope
#
# This script demonstrates how to use the Oscilloscope instrument
# to retrieve a single frame of dual-channel voltage data.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import Oscilloscope

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(Oscilloscope)

    # Span from -1s to 1s i.e. trigger point centred
    i.set_timebase(-1, 1)

    # Get and print a single frame worth of data (time series
    # of voltage per channel)
    data = i.get_data(timeout=10)
    print(data.ch1, data.ch2, data.time)

finally:
    m.close()
