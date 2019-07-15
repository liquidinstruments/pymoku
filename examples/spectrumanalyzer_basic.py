#
# pymoku example: Basic Spectrum Analyzer
#
# This example demonstrates how you can use the Spectrum Analyzer instrument to
# to retrieve a single spectrum data frame over a set frequency span.
#
# (c) 2017 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import SpectrumAnalyzer

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

# Deploy the Spectrum Analyzer to your Moku
try:
    i = m.deploy_or_connect(SpectrumAnalyzer)

    # DC to 10MHz span
    i.set_span(0, 10e6)

    # Get the scan results and print them out (power vs frequency, two channels)
    data = i.get_data()
    print(data.ch1, data.ch2, data.frequency)

finally:
    # Close the connection to the Moku.
    m.close()
