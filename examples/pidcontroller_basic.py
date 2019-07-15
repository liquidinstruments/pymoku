# pymoku example: Basic PID Controller
#
# This script demonstrates how to configure one of the two PID Controllers
# in the PID Controller instrument. Configuration is done by specifying
# frequency response characteristics of the controller.
#
# (c) 2019 Liquid Instruments Pty. Ltd.
#

from pymoku import Moku
from pymoku.instruments import PIDController

def from_dB(dB):
    # Helper function that converts from dB to linear scale
    return 10**(dB/20.0)

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name("Moku")

try:
    i = m.deploy_instrument(PIDController)

    # Configure the PID Controller using frequency response characteristics
    #   P = -10dB
    #   I Crossover = 100Hz
    #   D Crossover = 10kHz
    #   I Saturation = 10dB
    #   D Saturation = 10dB
    #   Double-I = OFF
    # Note that gains must be converted from dB first
    i.set_by_frequency(1, kp=from_dB(-10), i_xover=1e2, ii_xover=None, d_xover =1e4, si=from_dB(10), sd=from_dB(10))
    i.enable_output(1, True)

finally:
    # Close the connection to the Moku:Lab
    m.close()
