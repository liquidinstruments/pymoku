#
# pymoku example: Waveform Generator Modulation
#
# This example demonstrates how you can use the Waveform Generator instrument
# to generate an amplitude modulated sinewave on Channel 1, and a frequency
# modulated squarewave on Channel 2.
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

    # Generate a sinewave (amp = 1Vpp, freq = 50 kHz) on channel 1. Squarewave
    # (amp = 1 Vpp, freq = 500 Hz) on channel 2.
    i.gen_sinewave(1, amplitude=1.0, frequency=50e3)
    i.gen_squarewave(2, amplitude=1.0, frequency=500)

    # Configure the Moku's front end.
    i._set_frontend(channel=1, fiftyr=True, atten=True, ac=False)
    i._set_frontend(channel=2, fiftyr=True, atten=True, ac=False)

    # Configure amplitude modulation on channel 1. Frequency modulation on
    # channel 2.
    i.gen_modulate(ch=1, mtype='amplitude',
                   source='internal', depth=1.0, frequency=5e3)
    i.gen_modulate(ch=2, mtype='frequency',
                   source='adc2', depth=500, frequency=50)

finally:
    m.close()
