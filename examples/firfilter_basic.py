"""pymoku example: Basic FIR Filter Box

This example demonstrates how to run the FIR Filter Box and configure its
individual filter channel coefficients.

(c) 2019 Liquid Instruments Pty. Ltd.
"""
from pymoku import Moku
from pymoku.instruments import FIRFilter

# The following two example arrays are simple rectangular FIR kernels with 50
# and 400 taps respectively. A rectangular kernel produces a sinc shaped
# transfer function with width inversely proportional to the length of the
# kernel. FIR kernels must have a normalised power of <= 1.0, so the value of
# each tap is the inverse of the total number of taps.
filt_coeff1 = [1.0 / 50.0] * 50
filt_coeff2 = [1.0 / 400.0] * 400

# Connect to your Moku by its device name
# Alternatively, use Moku.get_by_serial('#####') or Moku('192.168.###.###')
m = Moku.get_by_name('Moku')

try:
    i = m.deploy_or_connect(FIRFilter)

    # Configure the Moku:Lab's frontend settings
    i.set_frontend(1, fiftyr=True, atten=False, ac=False)
    i.set_frontend(2, fiftyr=True, atten=False, ac=False)

    # Load the coefficients for each FIR filter channel.
    #
    # The channel's decimation factor determines the filter sample rate (Fs)
    # and the maximum number of filter kernel coefficients (N) for the channel.
    # The defining equations are given by:
    #
    #   3 <= decimation_factor <= 10,
    #   Fs = 125 MHz / 2^decimation_factor,
    #   N  = 2^(decimation_factor) * 29.
    #
    # To implement 50 FIR taps, N = 2^(3) * 29 = 232 > 50
    i.set_filter(1, decimation_factor=3, filter_coefficients=filt_coeff1)
    # To implement 400 FIR taps, N = 2^(4) * 29 = 464 > 400
    i.set_filter(2, decimation_factor=4, filter_coefficients=filt_coeff2)

    # Both channels have unity gain and no offsets
    i.set_gains_offsets(1, input_gain=1.0, output_gain=1.0, input_offset=0,
                        output_offset=0)
    i.set_gains_offsets(2, input_gain=1.0, output_gain=1.0, input_offset=0,
                        output_offset=0)

finally:
    m.close()
