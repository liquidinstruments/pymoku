#
# pymoku example: Basic Spectrum Analyser
#
# This example demonstrates how you can use the Spectrum Analyser instrument to
# to retrieve a single spectrum data frame over a set frequency span.
#
# (c) 2017 Liquid Instruments Pty. Ltd.
#
from pymoku import *
from pymoku.instruments import SpectrumAnalyser

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

# Prepare the Spectrum Analyser instrument
i = SpectrumAnalyser()

# Deploy the Spectrum Analyser to your Moku
m.deploy_instrument(i)

try:
	# DC to 10MHz span
	i.set_span(0, 10e6)

	# Get the scan results and print them out (power vs frequency, two channels)
	data = i.get_data()
	print(data.ch1, data.ch2, data.frequency)

finally:
	# Close the connection to the Moku.
	m.close()
