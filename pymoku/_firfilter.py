import math
import logging
from ._instrument import to_reg_unsigned
from ._instrument import from_reg_unsigned
from ._instrument import to_reg_signed
from ._instrument import from_reg_signed
from ._instrument import to_reg_bool
from ._instrument import from_reg_bool
from ._instrument import ADC_SMP_RATE
from ._instrument import needs_commit
from ._instrument import ValueOutOfRangeException
from ._instrument import struct

from pymoku._oscilloscope import _CoreOscilloscope
from . import _utils

log = logging.getLogger(__name__)

REG_FIR_CONTROL = 96

REG_FIR_IN_SCALE1 = 105
REG_FIR_IN_OFFSET1 = 106
REG_FIR_OUT_SCALE1 = 107
REG_FIR_OUT_OFFSET1 = 108
REG_FIR_MATRIXGAIN_CH1 = 109

REG_FIR_IN_SCALE2 = 110
REG_FIR_IN_OFFSET2 = 111
REG_FIR_OUT_SCALE2 = 112
REG_FIR_OUT_OFFSET2 = 113
REG_FIR_MATRIXGAIN_CH2 = 114

_FIR_NUM_BLOCKS = 29
_FIR_BLOCK_SIZE = 511
_FIR_MMAP_BLOCK_SIZE = 2**17

# Monitor probe locations (for A and B channels)
_FIR_MON_NONE = 0
_FIR_MON_ADC1 = 1
_FIR_MON_IN1 = 2
_FIR_MON_OUT1 = 3
_FIR_MON_ADC2 = 4
_FIR_MON_IN2 = 5
_FIR_MON_OUT2 = 6

# Oscilloscope data sources
_FIR_SOURCE_A = 0
_FIR_SOURCE_B = 1
_FIR_SOURCE_IN1 = 2
_FIR_SOURCE_IN2 = 3
_FIR_SOURCE_EXT = 4

# Input mux selects for Oscilloscope
_FIR_OSC_SOURCES = {
    'a': _FIR_SOURCE_A,
    'b': _FIR_SOURCE_B,
    'in1': _FIR_SOURCE_IN1,
    'in2': _FIR_SOURCE_IN2,
    'ext': _FIR_SOURCE_EXT
}

_FIR_INPUT_SMPS = ADC_SMP_RATE/4
_FIR_CHN_BUFLEN = 2**13

_ADC_DEFAULT_CALIBRATION = 3750.0  # Bits/V (No attenuation)


class _DecFilter(object):
    REG_DECIMATION = 0
    REG_INTERP_WDFRATES = 1
    REG_INTERP_CICRATES = 2
    REG_INTERP_CTRL = 3

    def __init__(self, instr, regbase):
        self._instr = instr
        self.regbase = regbase

    def set_samplerate(self, factor):
        d_wdfmuxsel = 0
        d_outmuxsel = 0
        d_cic1_dec = 0
        d_cic1_bitshift = 0
        d_cic2_dec = 0
        d_cic2_bitshift = 0
        i_muxsel = 0
        i_ratechange_cic2 = 0
        i_interprate_cic2 = 0
        i_bitshift_cic2 = 0
        i_ratechange_cic1 = 0
        i_bitshift_cic1 = 0
        i_interprate_cic1 = 0
        i_highrate_wdf1 = 0
        i_highrate_wdf2 = 0
        if factor == 1:
            d_outmuxsel = 0
            i_muxsel = 0
        elif factor == 2:
            d_wdfmuxsel = 0
            d_outmuxsel = 1
            i_muxsel = 1
            i_highrate_wdf1 = 0
        elif factor == 4:
            d_wdfmuxsel = 0
            d_outmuxsel = 2
            i_muxsel = 2
            i_highrate_wdf1 = factor/2 - 1
            i_highrate_wdf2 = 0
        elif 8 <= factor <= 64:
            d_wdfmuxsel = 1
            d_outmuxsel = 2
            d_cic1_dec = factor/4
            d_cic1_bitshift = 12 - math.log(d_cic1_dec**3, 2)
            i_muxsel = 3
            i_ratechange_cic1 = factor/4
            i_interprate_cic1 = 0
            i_bitshift_cic1 = math.log(i_ratechange_cic1**2, 2)
            i_highrate_wdf1 = factor/2 - 1
            i_highrate_wdf2 = factor/4 - 1
        else:  # 128 <= factor <= 1024
            d_wdfmuxsel = 2
            d_outmuxsel = 2
            d_cic1_dec = 16
            d_cic1_bitshift = 0
            d_cic2_dec = factor/64
            d_cic2_bitshift = math.log(d_cic2_dec**3, 2)
            i_muxsel = 4
            i_ratechange_cic2 = factor/64
            i_interprate_cic2 = 0
            i_bitshift_cic2 = math.log(i_ratechange_cic2**2, 2)
            i_ratechange_cic1 = 16
            i_bitshift_cic1 = 8
            i_interprate_cic1 = i_ratechange_cic2 - 1
            i_highrate_wdf1 = factor/2 - 1
            i_highrate_wdf2 = factor/4 - 1

        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(0, 2),
            d_wdfmuxsel
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(2, 2),
            d_outmuxsel
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(4, 4),
            d_cic1_bitshift)
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(8, 4),
            d_cic2_bitshift)
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(12, 5),
            d_cic1_dec
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(17, 5),
            d_cic2_dec
            )

        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(0, 3),
            i_muxsel
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_WDFRATES,
            to_reg_unsigned(0, 16),
            i_highrate_wdf1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_WDFRATES,
            to_reg_unsigned(16, 16),
            i_highrate_wdf2
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(3, 5),
            i_ratechange_cic1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(8, 5),
            i_ratechange_cic2
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CICRATES,
            to_reg_unsigned(0, 16),
            i_interprate_cic1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CICRATES,
            to_reg_unsigned(16, 16),
            i_interprate_cic2
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(13, 4),
            i_bitshift_cic1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(17, 4),
            i_bitshift_cic2
            )


class FIRFilter(_CoreOscilloscope):
    """

    The FIR Filter Box instrument implements two Finite Impulse Response (FIR)
    filter channels with kernels consisting of over 14,000 coefficients.
    The transfer function can be written:

    .. math::
        H(z) = sum_{k=1}^{N} b_k * z^{-k}

    where :math:`N` is the number of coefficients and :math:`b_k` is the
    k-th coefficient.

    To configure a filter kernel, call the :py:meth:
    `~pymoku.instruments.FIRFilter.set_filter` function with a 1-D coefficient
    array containing all coefficients in your filter kernel.
    Note that the array does not need to be zero-padded to the maximum kernel
    length, and the coefficients must be normalised to the range [-1.0, 1.0].
    i.e.

    .. math::
        [b_1, b_2, b_3, ... b_N] = [ 0.3, -0.2, 0.12, ... 0.5 ]

    Internally, the coefficients are represented as signed 25-bit fixed-point
    numbers.
    Filter coefficients can be computed using signal processing toolboxes in
    e.g. MATLAB or SciPy.

    Each filter channel can run at one of eight sampling rates, as summarised
    in the table below. These sample rates correspond to a division of the
    125 MHz clock by powers
    of 2 between 3-10. Sample rates are configured in the :py:meth:
    `~pymoku.instruments.FIRFilter.set_filter` function by specifying
    the power of 2 exponent as the `decimation_factor` function argument.

    The maximum number of kernel coefficients that can be implemented
    follows the following formula:

    .. math::
        N_{max} = min(29 * 2^{decimation_factor}, 14819)

    +-------------+--------------------+---------------------+
    | Sample rate | Decimation Factor  | Max # Coefficients  |
    +=============+====================+=====================+
    | 15.625 MHz  | 3                  | 232                 |
    +-------------+--------------------+---------------------+
    | 7.8125 MHz  | 4                  | 464                 |
    +-------------+--------------------+---------------------+
    | ~3.906 MHz  | 5                  | 928                 |
    +-------------+--------------------+---------------------+
    | ~1.953 MHz  | 6                  | 1856                |
    +-------------+--------------------+---------------------+
    | ~976.6 kHz  | 7                  | 3712                |
    +-------------+--------------------+---------------------+
    | ~488.3 kHz  | 8                  | 7424                |
    +-------------+--------------------+---------------------+
    | ~244.2 kHz  | 9                  | 14819               |
    +-------------+--------------------+---------------------+
    | ~122.1 kHz  | 10                 | 14819               |
    +-------------+--------------------+---------------------+

    .. warning::
        The overall output gain of the instrument is the product of the gain
        of the filter, set in the coefficient kernel array. To avoid clipping
        with full-range input signals, you should ensure that the sum of all
        coefficients in the kernel is <= 1.0.

    To run a new FIR Filter Box instrument, this class should be instantiated
    and deployed via a connected
    :any:`Moku` object using :any:`deploy_instrument`.
    Alternatively, a pre-configured instrument object can be obtained by
    discovering an already running FIR Filter Box instrument on a Moku:Lab
    device via :any:`deploy_or_connect`.

    .. automethod:: pymoku.instruments.FIRFilter.__init__

    .. attribute:: type
        :annotation: = "firfilter"

        Name of this instrument.

    """
    def __init__(self):
        super(FIRFilter, self).__init__()
        self._register_accessors(_fir_reg_handlers)
        self.id = 10
        self.type = "firfilter"

        # Monitor samplerate
        self._input_samplerate = _FIR_INPUT_SMPS
        self._chn_buffer_len = _FIR_CHN_BUFLEN

        self._decfilter1 = _DecFilter(self, 97)
        self._decfilter2 = _DecFilter(self, 101)

        self.monitor_a = 'none'
        self.monitor_b = 'none'

        # Initialise all local configuration variables
        # These remember user settings prior to on-commit reg calculations
        self._matrixscale_ch1_ch1 = 0
        self._matrixscale_ch1_ch2 = 0
        self._matrixscale_ch2_ch1 = 0
        self._matrixscale_ch2_ch2 = 0

        self._input_scale1 = 0
        self._output_scale1 = 0
        self._input_offset1 = 0
        self._output_offset1 = 0
        self._input_scale2 = 0
        self._output_scale2 = 0
        self._input_offset2 = 0
        self._output_offset2 = 0

    @needs_commit
    def set_defaults(self):
        super(FIRFilter, self).set_defaults()

        # We only allow looking at the monitor signals in the embedded scope
        self._set_source(1, _FIR_SOURCE_A)
        self._set_source(2, _FIR_SOURCE_B)

        self.set_gains_offsets(1)
        self.set_gains_offsets(2)

        self.input_en1 = True
        self.input_en2 = True

        # Plotting script defaults:
        self.set_control_matrix(1, 1.0, 0.0)
        self.set_control_matrix(2, 0.0, 1.0)

        self.set_monitor('a', 'in1')
        self.set_monitor('b', 'in2')

        self.set_trigger('a', 'rising', 0, mode='auto')
        self.set_timebase(-1e-3, 1e-3)
        self._set_samplerate(1, 8)
        self._set_samplerate(2, 8)

    @needs_commit
    def set_control_matrix(self, ch, scale_in1, scale_in2):
        """
        Configure the input control matrix specifying the input signal mixing
        for the specified filter channel.

        Input mixing allows a filter channel to act on a linear combination of
        the two input signals.

        :type ch: int, {1, 2}
        :param ch: target filter channel

        :type scale_in1: float, [-20, 20]
        :param scale_in1: linear scale factor of input 1 signal added to target
         filter channel input.
            To avoid quantization, use at most one decimal place.

        :type scale_in2: float, [-20, 20]
        :param scale_in2: linear scale factor of input 2 signal added to target
         filter channel input.
            To avoid quantization, use at most one decimal place.
        """
        _utils.check_parameter_valid('set', ch, [1, 2], 'filter channel')
        _utils.check_parameter_valid('range', scale_in1, [-20, 20],
                                     'control matrix scale (ch1)',
                                     'linear scalar')
        _utils.check_parameter_valid('range', scale_in2, [-20, 20],
                                     'control matrix scale (ch2)',
                                     'linear scalar')
        if (scale_in1 / 0.1) % 1 or (scale_in2 / 0.1) % 1:
            log.warning("Control matrix scalars should contain one decimal "
                        "place to avoid quantization effects.")

        if ch == 1:
            self._matrixscale_ch1_ch1 = scale_in1
            self._matrixscale_ch1_ch2 = scale_in2
        else:
            self._matrixscale_ch2_ch1 = scale_in1
            self._matrixscale_ch2_ch2 = scale_in2

    def _update_control_matrix_regs(self):
        # Used to update regs at commit time with correct frontend
        # settings.
        self.matrixscale_ch1_ch1 = self._matrixscale_ch1_ch1
        self.matrixscale_ch1_ch2 = self._matrixscale_ch1_ch2
        self.matrixscale_ch2_ch1 = self._matrixscale_ch2_ch1
        self.matrixscale_ch2_ch2 = self._matrixscale_ch2_ch2

    def _sync_control_matrix_regs(self):
        # sync local variables when connecting to an existing instrument
        self._matrixscale_ch1_ch1 = self.matrixscale_ch1_ch1
        self._matrixscale_ch1_ch2 = self.matrixscale_ch1_ch2
        self._matrixscale_ch2_ch1 = self.matrixscale_ch2_ch1
        self._matrixscale_ch2_ch2 = self.matrixscale_ch2_ch2

    @needs_commit
    def set_gains_offsets(self, ch, input_gain=1.0, output_gain=1.0,
                          input_offset=0, output_offset=0):
        """
        Configure pre- and post-filter scales and offsets for a given filter
        channel.

        .. note::
            The overall output gain of the instrument is the product of the
            gain of the filter, set by the filter coefficients,
            and the input/output stage gain set here.

        :type ch: int, {1,2}
        :param ch: target filter channel

        :type input_gain, output_gain: float, linear scalar, [-100,100]
        :param input_gain, output_gain: channel scalars before and after the
        FIR filter

        :type input_offset: float, volts, [-1.0,1.0]
        :param input_offset: channel offset before the FIR filter

        :type output_offset: float, volts, [-2.0,2.0]
        :param output_offset: channel offset after the FIR filter
        """
        _utils.check_parameter_valid('set', ch, [1, 2], 'filter channel')
        _utils.check_parameter_valid('range', input_gain, [-100, 100],
                                     'input gain', 'linear scalar')
        _utils.check_parameter_valid('range', output_gain, [-100, 100],
                                     'output gain', 'linear scalar')
        _utils.check_parameter_valid('range', input_offset, [-1.0, 1.0],
                                     'input offset', 'Volts')
        _utils.check_parameter_valid('range', output_offset, [-2.0, 2.0],
                                     'output offset', 'Volts')

        if ch == 1:
            self._input_scale1 = input_gain
            self._output_scale1 = output_gain
            self._input_offset1 = input_offset
            self._output_offset1 = output_offset
        else:
            self._input_scale2 = input_gain
            self._output_scale2 = output_gain
            self._input_offset2 = input_offset
            self._output_offset2 = output_offset

        # Reset the channel's filtering loop for new settings to take effect
        # immediately
        self._channel_reset(ch)

    def _update_gains_offsets_regs(self):
        # Used to update regs at commit time with correct frontend settings.
        self.input_scale1 = self._input_scale1
        self.output_scale1 = self._output_scale1
        self.input_offset1 = self._input_offset1
        self.output_offset1 = self._output_offset1
        self.input_scale2 = self._input_scale2
        self.output_scale2 = self._output_scale2
        self.input_offset2 = self._input_offset2
        self.output_offset2 = self._output_offset2

    def _sync_gains_offsets_regs(self):
        # sync local variables when connecting to an existing instrument
        self._input_scale1 = self.input_scale1
        self._output_scale1 = self.output_scale1
        self._input_offset1 = self.input_offset1
        self._output_offset1 = self.output_offset1
        self._input_scale2 = self.input_scale2
        self._output_scale2 = self.output_scale2
        self._input_offset2 = self.input_offset2
        self._output_offset2 = self.output_offset2

    def set_filter(self, ch, decimation_factor, filter_coefficients):
        """
        Set FIR filter sample rate and kernel coefficients for the specified
        filter channel. This will enable the specified channel output.
        See class documentation for information on the `filter_coefficients`
        array formatting and how
        `decimation_factor` relates to instrument sample rate.

        :type ch: int; {1,2}
        :param ch: Filter channel.

        :type decimation_factor: int; [3,10]
        :param decimation_factor: the binary exponent *n* specifying the
         filter sample rate: :math:`Fs = 125 MHz / 2^n`.

        :type filter_coefficients: array(float)
        :param filter_coefficients: array of FIR filter coefficients. The
         length of the array must not exceed :math:`N = min(29*2^n, 14819)`.
        """
        _utils.check_parameter_valid('set', ch, [1, 2], 'filter channel')
        _utils.check_parameter_valid('set', decimation_factor, range(3, 11),
                                     'decimation factor')
        _utils.check_parameter_valid(
            'range', len(filter_coefficients),
            [0, _FIR_NUM_BLOCKS * min(2**decimation_factor, 2**9 - 1)],
            'filter coefficient array length')
        # Check that all coefficients are between -1.0 and 1.0
        if not all(map(lambda x: abs(x) <= 1.0, filter_coefficients)):
            raise ValueOutOfRangeException("set_filter filter coefficients "
                                           "must be in the range "
                                           "[-1.0, 1.0].")

        """ IMPORTANT: The decimation filter samplerate must be set before the
                       coefficients are written
                       this is because the mmap access bit appropriately resets
                       the other decimation blocks.
        """
        self._set_samplerate(ch, 2.0**decimation_factor)

        self._write_coeffs(ch, filter_coefficients)

        if ch == 1:
            self.filter_en1 = True
            self.output_en1 = True
            self.input_en1 = True
        else:
            self.filter_en2 = True
            self.output_en2 = True
            self.input_en2 = True

        self._channel_reset(ch)

        # Manually commit all outstanding registers as this function does not
        # use needs_commit
        # This is because the mmap_access register muts be committed when
        # writing coefficients.
        self.commit()

    @needs_commit
    def set_monitor(self, monitor_ch, source, clip=False):
        """
        Configures the specified monitor channel to view the desired filterbox
        signal.

        There are two 12-bit monitoring channels available, 'a' and 'b'; each
        of these can be assigned to source signals from any of the internal
        filterbox monitoring points.
        Signals larger than 12-bits must be either truncated or clipped to the
        allowed size.

        The source is one of:
            - **adc1**  : Channel 1 ADC input
            - **in1**   : Filter Channel 1 input (after mixing, offset and
                          scaling)
            - **out1**  : Filter Channel 1 output
            - **adc2**  : Channel 2 ADC Input
            - **in2**   : Filter Channel 2 input (after mixing, offset and
                          scaling)
            - **out2**  : Filter Channel 2 output

        :type monitor_ch: str; {'a','b'}
        :param monitor_ch: Monitor channel

        :type source: str; {'adc1', 'in1', 'out1', 'adc2', 'in2', 'out2'}
        :param source: Signal to connect to the monitor channel

        :type clip: bool;
        :param clip: Enable signal clipping to the allowed size (truncate is
         default).
        """
        _utils.check_parameter_valid('string', monitor_ch,
                                     desc="monitor channel")
        _utils.check_parameter_valid('string', source,
                                     desc="monitor signal")

        monitor_sources = {
            'none': _FIR_MON_NONE,
            'adc1': _FIR_MON_ADC1,
            'in1':  _FIR_MON_IN1,
            'out1': _FIR_MON_OUT1,
            'adc2': _FIR_MON_ADC2,
            'in2':  _FIR_MON_IN2,
            'out2': _FIR_MON_OUT2
        }
        monitor_ch = monitor_ch.lower()
        source = source.lower()

        _utils.check_parameter_valid('set', monitor_ch, allowed=['a', 'b'],
                                     desc="monitor channel")
        _utils.check_parameter_valid('set', source,
                                     allowed=['none', 'adc1', 'in1', 'out1',
                                              'adc2', 'in2', 'out2'],
                                     desc="monitor source")

        if monitor_ch == 'a':
            self.monitor_a = source
            self.mon1_source = monitor_sources[source]
            self.mon1_clip = clip
        elif monitor_ch == 'b':
            self.monitor_b = source
            self.mon2_source = monitor_sources[source]
            self.mon2_clip = clip
        else:
            raise ValueOutOfRangeException("Invalid channel %d", monitor_ch)

    @needs_commit
    def set_trigger(self, source, edge, level, minwidth=None, maxwidth=None,
                    hysteresis=10e-3, hf_reject=False, mode='auto'):
        """
        Set the trigger source for the monitor channel signals. This can be
        either of the input or
        monitor signals, or the external input.

        :type source: string, {'in1','in2','A','B','ext'}
        :param source: Trigger Source. May be either an input or monitor
                       channel (as set by :py:meth:`~pymoku.instruments.
                       FIRFilter.set_monitor`), or external. External refers
                       to the back-panel connector of the same name, allowing
                       triggering from an externally-generated digital [LV]TTL
                       or CMOS signal.

        :type edge: string, {'rising','falling','both'}
        :param edge: Which edge to trigger on. In Pulse Width modes this
                     specifies whether the pulse is positive (rising) or
                     negative (falling), with the 'both' option being invalid.

        :type level: float, [-10.0, 10.0] volts
        :param level: Trigger level

        :type minwidth: float, seconds
        :param minwidth: Minimum Pulse Width.
                         0 <= minwidth < (2^32/samplerate).
                         Can't be used with maxwidth.

        :type maxwidth: float, seconds
        :param maxwidth: Maximum Pulse Width.
                         0 <= maxwidth < (2^32/samplerate).
                         Can't be used with minwidth.

        :type hysteresis: float, [100e-6, 1.0] volts
        :param hysteresis: Hysteresis around trigger point.

        :type hf_reject: bool
        :param hf_reject: Enable high-frequency noise rejection

        :type mode: string, {'auto', 'normal'}
        :param mode: Trigger mode.
        """
        # Define the trigger sources appropriate to the LockInAmp instrument
        source = _utils.str_to_val(_FIR_OSC_SOURCES, source, 'trigger source')

        # This function is the portion of set_trigger shared among instruments
        # with embedded scopes.
        self._set_trigger(source, edge, level, minwidth, maxwidth, hysteresis,
                          hf_reject, mode)

    @needs_commit
    def disable_output(self, ch):
        """
        Disables the output of the specified FIR filter channel.

        :type ch: int; {1,2}
        :param ch: target channel
        """
        if ch == 1:
            self.output_en1 = False
        else:
            self.output_en2 = False

    def _set_samplerate(self, ch, factor):
        if ch == 1:
            self._decfilter1.set_samplerate(factor)
        else:
            self._decfilter2.set_samplerate(factor)

    def _channel_reset(self, ch):
        if ch == 1:
            self.reset_ch1 = True
        else:
            self.reset_ch2 = True

    def _write_coeffs(self, ch, coeffs):
        assert ch in [1, 2], "Invalid channel"
        assert len(coeffs) <= _FIR_NUM_BLOCKS * _FIR_BLOCK_SIZE, \
            "Invalid number of filter coefficients."

        coeffs = list(coeffs)

        # Create a list of coefficients in each FIR block
        n = int(math.ceil(len(coeffs)/float(_FIR_NUM_BLOCKS)))
        blocks = [coeffs[x:x+n] for x in range(0, len(coeffs), n)]
        blocks += [[]] * (_FIR_NUM_BLOCKS - len(blocks))

        # Construct a bytearray from the FIR block contents
        coeff_bytes = bytearray()
        for b in blocks:
            b.reverse()
            coeff_bytes += bytearray(struct.pack('<I', len(b)))
            coeff_bytes += bytearray(struct.pack('<' + 'i'*len(b),
                                     *[int(round((2.0**24-1) * c))
                                     for c in b]))
            coeff_bytes += bytearray(b'\x00'*4*(_FIR_BLOCK_SIZE-len(b)))

        # Sanity check the coefficient byte array length
        assert len(coeff_bytes) == (_FIR_BLOCK_SIZE+1) * _FIR_NUM_BLOCKS * 4, \
            "Invalid length for FIR coefficient memory map."

        # Write the coefficients to the FIR coefficient memory map
        self._set_mmap_access(True)
        self._moku._send_file_bytes('j', '', coeff_bytes,
                                    offset=_FIR_MMAP_BLOCK_SIZE*(ch-1))
        self._set_mmap_access(False)

        # Release the memory map "file" to other resources
        self._moku._fs_finalise('j', '', _FIR_MMAP_BLOCK_SIZE*2)

    def _signal_source_volts_per_bit(self, source, scales, trigger=False):
        """
            Converts volts to bits depending on the signal source
        """
        # Decimation gain is applied only when using precision mode data
        if (not trigger and self.is_precision_mode()) or \
           (trigger and self.trig_precision):
            deci_gain = self._deci_gain()
        else:
            deci_gain = 1.0

        if (source == _FIR_SOURCE_A):
            level = self._monitor_source_volts_per_bit(
                self.monitor_a, scales) / deci_gain
        elif (source == _FIR_SOURCE_B):
            level = self._monitor_source_volts_per_bit(
                self.monitor_b, scales) / deci_gain
        elif (source == _FIR_SOURCE_IN1):
            level = scales['gain_adc1'] * (
                10.0 if scales['atten_ch1'] else 1.0) / deci_gain
        elif (source == _FIR_SOURCE_IN2):
            level = scales['gain_adc2'] * (
                10.0 if scales['atten_ch2'] else 1.0) / deci_gain
        else:
            level = 1.0
        return level

    def _monitor_source_volts_per_bit(self, source, scales):
        # Calculates the volts to bits conversion for the given monitor port
        # signal

        monitor_source_gains = {
            'none': 1.0,
            'adc1':
                scales['gain_adc1'] / (10.0 if scales['atten_ch1'] else 1.0),
            'in1':
                1.0 / _ADC_DEFAULT_CALIBRATION / (10.0 if scales['atten_ch1']
                                                  else 1.0),
            'out1': scales['gain_dac1']*(2.0**4),
            'adc2':
                scales['gain_adc2'] / (10.0 if scales['atten_ch2'] else 1.0),
            'in2':
                1.0/_ADC_DEFAULT_CALIBRATION / (10.0 if scales['atten_ch2']
                                                else 1.0),
            'out2': scales['gain_dac2']*(2.0**4)
        }
        return monitor_source_gains[source]

    def _update_dependent_regs(self, scales):
        super(FIRFilter, self)._update_dependent_regs(scales)
        self._update_control_matrix_regs()
        self._update_gains_offsets_regs()

    def _on_reg_sync(self):
        super(FIRFilter, self)._on_reg_sync()
        # Update local variables with device variables
        self._sync_gains_offsets_regs()
        self._sync_control_matrix_regs()


_fir_reg_handlers = {
    'reset_ch1':
        (REG_FIR_CONTROL,
            to_reg_bool(0),
            from_reg_bool(0)),
    'reset_ch2':
        (REG_FIR_CONTROL,
            to_reg_bool(1),
            from_reg_bool(1)),
    'filter_en1':
        (REG_FIR_CONTROL,
            to_reg_bool(2),
            from_reg_bool(2)),
    'filter_en2':
        (REG_FIR_CONTROL,
            to_reg_bool(3),
            from_reg_bool(3)),
    'link':
        (REG_FIR_CONTROL,
            to_reg_bool(4),
            from_reg_bool(4)),
    'input_en1':
        (REG_FIR_CONTROL,
            to_reg_bool(5),
            from_reg_bool(5)),
    'input_en2':
        (REG_FIR_CONTROL,
            to_reg_bool(6),
            from_reg_bool(6)),
    'mon1_source':
        (REG_FIR_CONTROL,
            to_reg_unsigned(8, 3),
            from_reg_unsigned(8, 3)),
    'mon2_source':
        (REG_FIR_CONTROL,
            to_reg_unsigned(12, 3),
            from_reg_unsigned(12, 3)),
    'mon1_clip':
        (REG_FIR_CONTROL,
            to_reg_bool(11),
            from_reg_bool(11)),
    'mon2_clip':
        (REG_FIR_CONTROL,
            to_reg_bool(15),
            from_reg_bool(15)),
    'output_en1':
        (REG_FIR_CONTROL,
            to_reg_bool(16),
            from_reg_bool(16)),
    'output_en2':
        (REG_FIR_CONTROL,
            to_reg_bool(17),
            from_reg_bool(17)),

    'input_scale1':
        (REG_FIR_IN_SCALE1,
            to_reg_signed(0, 18, xform=lambda obj, x: x * 2.0**9),
            from_reg_signed(0, 18, xform=lambda obj, x: x / (2.0**9))),

    'input_scale2':
        (REG_FIR_IN_SCALE2,
            to_reg_signed(0, 18, xform=lambda obj, x: x * 2.0**9),
            from_reg_signed(0, 18, xform=lambda obj, x: x / (2.0**9))),

    'input_offset1':
        (REG_FIR_IN_OFFSET1,
            to_reg_signed(0, 32,
                          xform=lambda obj, x: x * 2.0**12 * 2.0 *
                          (_ADC_DEFAULT_CALIBRATION /
                           (10.0 if obj.get_frontend(1)[1] else 1.0) *
                           obj._adc_gains()[0])),
            from_reg_signed(0, 32,
                            xform=lambda obj, x: x /
                            (_ADC_DEFAULT_CALIBRATION /
                             (10.0 if obj.get_frontend(1)[1] else 1.0) *
                             obj._adc_gains()[0]) / 2.0**12 / 2.0)),

    'input_offset2':
        (REG_FIR_IN_OFFSET2,
            to_reg_signed(0, 32,
                          xform=lambda obj, x: x * 2.0**12 * 2.0 *
                          (_ADC_DEFAULT_CALIBRATION /
                           (10.0 if obj.get_frontend(2)[1] else 1.0) *
                           obj._adc_gains()[1])),
            from_reg_signed(0, 32,
                            xform=lambda obj, x: x /
                            (_ADC_DEFAULT_CALIBRATION /
                             (10.0 if obj.get_frontend(2)[1] else 1.0) *
                             obj._adc_gains()[1]) / 2.0**12 / 2.0)),

    'output_scale1':
        (REG_FIR_OUT_SCALE1,
            to_reg_signed(0, 18,
                          xform=lambda obj, x:
                          int(round(x * 2.0**9 /
                              (_ADC_DEFAULT_CALIBRATION * 2**3 *
                               obj._dac_gains()[0])))),
            from_reg_signed(0, 18,
                            xform=lambda obj, x: x *
                            (_ADC_DEFAULT_CALIBRATION * 2**3 *
                             obj._dac_gains()[0]) / 2.0**9)),

    'output_scale2':
        (REG_FIR_OUT_SCALE2,
            to_reg_signed(0, 18,
                          xform=lambda obj, x:
                          int(round(x * 2.0**9 / (_ADC_DEFAULT_CALIBRATION *
                              2**3 * obj._dac_gains()[1])))),
            from_reg_signed(0, 18,
                            xform=lambda obj, x: x *
                            (_ADC_DEFAULT_CALIBRATION * 2**3 *
                             obj._dac_gains()[1]) / 2.0**9)),

    'output_offset1':
        (REG_FIR_OUT_OFFSET1,
            to_reg_signed(0, 17,
                          xform=lambda obj, x:
                          int(round(x / obj._dac_gains()[0]))),
            from_reg_signed(0, 17,
                            xform=lambda obj, x:
                            x * obj._dac_gains()[0])),

    'output_offset2':
        (REG_FIR_OUT_OFFSET2,
            to_reg_signed(0, 17,
                          xform=lambda obj, x:
                          int(round(x / obj._dac_gains()[1]))),
            from_reg_signed(0, 17,
                            xform=lambda obj, x: x * obj._dac_gains()[1])),

    'matrixscale_ch1_ch1':
        (REG_FIR_MATRIXGAIN_CH1,
            to_reg_signed(0, 16,
                          xform=lambda obj, x:
                          int(round(x * (_ADC_DEFAULT_CALIBRATION /
                              (10.0 if obj.get_frontend(1)[1] else 1.0)) *
                           obj._adc_gains()[0] * 2.0**10))),
            from_reg_signed(0, 16,
                            xform=lambda obj, x:
                            x * ((10.0 if obj.get_frontend(1)[1] else 1.0) /
                                 _ADC_DEFAULT_CALIBRATION) /
                            obj._adc_gains()[0] / 2.0**10)),

    'matrixscale_ch1_ch2':
        (REG_FIR_MATRIXGAIN_CH1,
            to_reg_signed(16, 16,
                          xform=lambda obj, x:
                          int(round(x * (_ADC_DEFAULT_CALIBRATION /
                              (10.0 if obj.get_frontend(2)[1] else 1.0)) *
                              obj._adc_gains()[1] * 2.0**10))),
            from_reg_signed(16, 16,
                            xform=lambda obj, x:
                            x * ((10.0 if obj.get_frontend(2)[1] else 1.0) /
                                 _ADC_DEFAULT_CALIBRATION) /
                            obj._adc_gains()[1] / 2.0**10)),

    'matrixscale_ch2_ch1':
        (REG_FIR_MATRIXGAIN_CH2,
            to_reg_signed(0, 16,
                          xform=lambda obj, x:
                          int(round(x * (_ADC_DEFAULT_CALIBRATION /
                              (10.0 if obj.get_frontend(1)[1] else 1.0)) *
                              obj._adc_gains()[0] * 2.0**10))),
            from_reg_signed(0, 16,
                            xform=lambda obj, x:
                            x * ((10.0 if obj.get_frontend(2)[1] else 1.0) /
                                 _ADC_DEFAULT_CALIBRATION) /
                            obj._adc_gains()[1] / 2.0**10)),

    'matrixscale_ch2_ch2':
        (REG_FIR_MATRIXGAIN_CH2,
            to_reg_signed(16, 16,
                          xform=lambda obj, x:
                          int(round(x * (_ADC_DEFAULT_CALIBRATION /
                              (10.0 if obj.get_frontend(2)[1] else 1.0)) *
                              obj._adc_gains()[1] * 2.0**10))),
            from_reg_signed(16, 16,
                            xform=lambda obj, x:
                            x * ((10.0 if obj.get_frontend(1)[1] else 1.0) /
                                 _ADC_DEFAULT_CALIBRATION) /
                            obj._adc_gains()[0] / 2.0**10))
}
