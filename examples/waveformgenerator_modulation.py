#
# pymoku example: Basic Waveform Generator
#
# This example demonstrates how you can use the Waveform Generator instrument to
# generate an amplitude modulated sinewave on Channel 1, and un-modulated
# squarewave on Channel 2.
#
# (c) 2017 Liquid Instruments Pty. Ltd.
#
from pymoku import *
from pymoku.instruments import WaveformGenerator

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

# Deploy the Signal Generator to your Moku
i = m.deploy_instrument(WaveformGenerator)

try:
	i.gen_sinewave(1, amplitude = 1.0, frequency = 50e3)
	i.gen_sinewave(2, amplitude = 1.0, frequency = 500)

	i._set_frontend(channel = 1, fiftyr=True, atten=True, ac=False)
	i._set_frontend(channel = 2, fiftyr=True, atten=True, ac=False)

	# modulation:
	i.gen_modulate(ch=1, mtype='phase', source='adc1', depth=180, frequency = 5e3)
	# i.gen_modulate(ch=1, mtype='amplitude', source='internal', depth=1.0, frequency = 50)
	# i.gen_modulate(ch=1, mtype='frequency', source='dac2', depth=31.25e6, frequency = 200)

finally:
	m.close()
