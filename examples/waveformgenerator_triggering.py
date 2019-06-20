#
# pymoku example: Waveform Generator Triggering
#
# This example demonstrates how you can use the Waveform Generator instrument to
# generate a gated sinewave on Channel 1, and a swept frequency squarewave on Channel 2.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#
from pymoku import Moku
from pymoku.instruments import WaveformGenerator

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
	# Deploy the Signal Generator to your Moku
	i = m.deploy_instrument(WaveformGenerator)

	# Generate a sinewave (amp = 1Vpp, freq = 10 Hz) on channel 1. Squarewave (amp = 1 Vpp, freq = 500 Hz) on channel 2.
	i.gen_sinewave(1, amplitude=1.0, frequency=10)
	i.gen_squarewave(2, amplitude=1.0, frequency=500)

	# Configure the Moku's frontend
	i._set_frontend(channel=1, fiftyr=True, atten=True, ac=False)
	i._set_frontend(channel=2, fiftyr=True, atten=True, ac=False)

	# Configure gated trigger mode on channel 1. Sweep trigger mode on channel 2.
	i.set_trigger(1, mode='gated', trigger_source='internal', internal_trig_period=2.0, internal_trig_high=0.5)
	i.set_trigger(2, mode='sweep', trigger_source='adc1', sweep_end_freq=10.0, sweep_duration=2.0, trigger_threshold=0.1)

finally:
	m.close()
