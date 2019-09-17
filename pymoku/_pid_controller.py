
import logging
import math

from pymoku._instrument import to_reg_bool
from pymoku._instrument import from_reg_bool
from pymoku._instrument import to_reg_unsigned
from pymoku._instrument import from_reg_unsigned
from pymoku._instrument import to_reg_signed
from pymoku._instrument import from_reg_signed
from pymoku._instrument import needs_commit
from pymoku._instrument import ADC_SMP_RATE
from pymoku._instrument import InvalidConfigurationException
from pymoku._instrument import ValueOutOfRangeException
from pymoku._oscilloscope import _CoreOscilloscope
from pymoku import _utils

log = logging.getLogger(__name__)

REG_PID_ENABLES = 96
# CHANNEL 0 REGISTERS
REG_PID_CH0_PIDGAIN1 = 97
REG_PID_CH0_PIDGAIN2 = 98
REG_PID_CH0_INT_IGAIN1 = 99
REG_PID_CH0_INT_IGAIN2_LSB = 99
REG_PID_CH0_INT_IGAIN2_MSB = 100
REG_PID_CH0_INT_IFBGAIN1_LSB = 100
REG_PID_CH0_INT_IFBGAIN1_MSB = 101
REG_PID_CH0_INT_IFBGAIN2 = 101
REG_PID_CH0_INT_PGAIN1 = 102
REG_PID_CH0_INT_PGAIN2_LSB = 102
REG_PID_CH0_INT_PGAIN2_MSB = 103
REG_PID_CH0_DIFF_PGAIN1 = 105
REG_PID_CH0_DIFF_IGAIN1_LSB = 106
REG_PID_CH0_DIFF_IGAIN1_MSB = 107
REG_PID_CH0_DIFF_IFBGAIN1 = 108
REG_PID_CH0_DIFF_IFBGAIN2 = 109
REG_PID_CH0_CH0GAIN_LSB = 108
REG_PID_CH0_CH0GAIN_MSB = 109
REG_PID_CH0_CH1GAIN = 127
REG_PID_CH0_OFFSET1 = 110
REG_PID_CH0_OFFSET2 = 111
# CHANNEL 1 registers
REG_PID_CH1_PIDGAIN1 = 112
REG_PID_CH1_PIDGAIN2 = 113
REG_PID_CH1_INT_IGAIN1 = 114
REG_PID_CH1_INT_IGAIN2_LSB = 114
REG_PID_CH1_INT_IGAIN2_MSB = 115
REG_PID_CH1_INT_IFBGAIN1_LSB = 115
REG_PID_CH1_INT_IFBGAIN1_MSB = 116
REG_PID_CH1_INT_IFBGAIN2 = 116
REG_PID_CH1_INT_PGAIN1 = 117
REG_PID_CH1_INT_PGAIN2_LSB = 117
REG_PID_CH1_INT_PGAIN2_MSB = 118
REG_PID_CH1_DIFF_PGAIN1 = 120
REG_PID_CH1_DIFF_IGAIN1_LSB = 121
REG_PID_CH1_DIFF_IGAIN1_MSB = 122
REG_PID_CH1_DIFF_IFBGAIN1 = 123
REG_PID_CH1_DIFF_IFBGAIN2 = 124
REG_PID_CH1_CH0GAIN_LSB = 123
REG_PID_CH1_CH0GAIN_MSB = 124
REG_PID_CH1_OFFSET1 = 125
REG_PID_CH1_OFFSET2 = 126
REG_PID_CH1_CH1GAIN = 127

REG_PID_MONSELECT = 104

# SIGNAL PRECISION MODES
PID_HIGH_PRECISION = 1
PID_HIGH_RANGE = 0

# Monitor probe locations (for A and B channels)
_PID_MON_NONE = 0
_PID_MON_ADC1 = 1
_PID_MON_IN1 = 2
_PID_MON_OUT1 = 3
_PID_MON_ADC2 = 4
_PID_MON_IN2 = 5
_PID_MON_OUT2 = 6

# Oscilloscope data sources
_PID_SOURCE_A = 0
_PID_SOURCE_B = 1
_PID_SOURCE_IN1 = 2
_PID_SOURCE_IN2 = 3
_PID_SOURCE_EXT = 4

# Input mux selects for Oscilloscope
_PID_OSC_SOURCES = {
    'a': _PID_SOURCE_A,
    'b': _PID_SOURCE_B,
    'in1': _PID_SOURCE_IN1,
    'in2': _PID_SOURCE_IN2,
    'ext': _PID_SOURCE_EXT
}

_PID_INPUT_SMPS = ADC_SMP_RATE / 20
_PID_CHN_BUFLEN = 2**14

_ADC_DEFAULT_CALIBRATION = 3750.0  # Bits/V (No attenuation)
_DAC_DEFAULT_CALIBRATION = _ADC_DEFAULT_CALIBRATION * 2.0**3  # Bits/V


class PIDController(_CoreOscilloscope):
    """ PIDController instrument object. This should be instantiated and
        attached to a :any:`Moku` instance.

    .. automethod:: pymoku.instruments.PIDController.__init__

    .. attribute:: hwver

        Hardware Version

    .. attribute:: hwserial

        Hardware Serial Number

    .. attribute:: framerate
        :annotation: = 10

        Frame Rate, range 1 - 30.

    .. attribute:: type
        :annotation: = "pidcontroller"

        Name of this instrument.

    """
    def __init__(self):
        super(PIDController, self).__init__()
        self._register_accessors(_PID_reg_hdl)

        self.id = 5
        self.type = "pidcontroller"

        # Monitor samplerate
        self._input_samplerate = _PID_INPUT_SMPS
        self._chn_buffer_len = _PID_CHN_BUFLEN

        self.monitor_a = 'none'
        self.monitor_b = 'none'

    @needs_commit
    def set_defaults(self):
        """ Reset the lockinamp to sane defaults. """
        super(PIDController, self).set_defaults()

        # We only allow looking at the monitor signals in the embedded scope
        self._set_source(1, _PID_SOURCE_A)
        self._set_source(2, _PID_SOURCE_B)

        self.set_monitor('a', 'out1')
        self.set_monitor('b', 'out2')

        self.set_trigger('a', 'rising', 0, mode='auto')
        self.set_timebase(-1e-3, 1e-3)

        self.set_control_matrix(1, 1, 0)
        self.set_control_matrix(2, 1, 0)
        self.set_by_gain(1, 1, 1)
        self.set_by_gain(2, 1, 1)
        # Enable inputs/outputs
        self.ch1_input_en = True
        self.ch1_output_en = False
        self.ch2_input_en = True
        self.ch2_output_en = False

    def _calculate_gains_by_frequency(self, kp, i_xover, d_xover,
                                      ii_xover, si, sd):
        # Particularly high or low I or D crossover frequencies (<1Hz, >1MHz)
        # require that some of their gain is pushed to the overall gain on
        # the end due to dynamic range limitations
        fs = _PID_INPUT_SMPS / (2 * math.pi)
        cross_over_gain = kp if kp else 1

        i_gmin = d_gmin = 1
        i_gmax = d_gmax = 1
        if i_xover:
            i_unity = i_xover * cross_over_gain
            i_gmin = min(i_unity, 1)
            i_gmax = max(i_unity / 1e6, 1)

        if d_xover:
            d_unity = d_xover * (2 * math.pi) * fs / d_xover
            d_gmin = sd if sd is not None and sd < 1 \
                else max(1.0e6 / d_unity, 1.0)
            d_gmax = max(1 / d_unity, 1)

        g_min = min(i_gmin, d_gmin)
        g_max = max(i_gmax, d_gmax)

        if g_min < 1 and g_max == 1:
            best_gain = g_min
        elif g_max > 1 and g_min == 1:
            best_gain = g_max
        elif g_min < 1 and g_max > 1:
            best_gain = math.sqrt(g_min * g_max)
        else:
            best_gain = 1

        cross_over_gain /= best_gain

        ii_xover = None if i_xover is None else ii_xover
        si = None if i_xover is None else si
        sd = None if d_xover is None else sd

        if ii_xover:
            if i_xover:
                ki = cross_over_gain * i_xover
                kii = ii_xover  # math.sqrt(cross_over_gain) * ii_xover
            else:
                ki = kii = 0
        else:
            if i_xover:
                ki = cross_over_gain * i_xover
            else:
                ki = 0
            kii = 0

        kd = cross_over_gain / d_xover if d_xover else 0
        si = si / best_gain if si else None

        # if ii_xover :
        #   si = math.sqrt(si)

        sd = sd / best_gain if sd else None

        return best_gain, kp, ki, kd, kii, si, sd

    def _calculate_regs_by_gain(self, ch, g, kp, ki, kd, kii, si, sd):
        # Calculate register gain values for PID controller blocks

        # overall gain is:
        #  - 1/1000 to undo gain from control matrix to optimise rounding
        #    strategy
        #  - 1/16 to convert from ADC bits to DAC bits
        #  - DAC gain to convert from bits to output volts
        #  - user-supplied factor so they can optimise the rounding strategy
        #    too

        # Check if double integrator stage is enabled
        double_integrator = kii != 0

        gain_factor = g * 2.0**4 / 31.25

        p_gain = kp

        if double_integrator:
            gain_factor = math.sqrt(gain_factor)

        gain_factor = gain_factor / self._dac_gains()[ch - 1]

        fs = _PID_INPUT_SMPS / (2 * math.pi)

        # I gain and corner. Factors of FS convert essentially from S-
        # to Z-plane
        i_gain = ki / fs
        ii_gain = kii / fs

        if si is None:
            i_c = 0
        else:
            i_c = math.sqrt(ki * kii / si) if kii else ki / si
            if i_c < fs / (2**24 - 1):
                si_max = (g * ki / (2 * fs / (2**24 - 1)))
                raise InvalidConfigurationException("Integrator corner below"
                                                    " minimum. Decrease "
                                                    "integrator saturation "
                                                    "below %.3f dB." %
                                                    (20 * math.log(si_max,
                                                                   10)))
        i_fb = 1.0 - (i_c / fs)

        d_gain = 4 * sd if sd else 4 * 1000

        # Calculate the differentiator feedback gain and ensure saturation
        # corner doesn't exceed 1MHz.
        if sd:
            if kd > 0:
                fc_coeff = sd / (kd * (fs))
            else:
                fc_coeff = 1
        else:
            # Set the differentiator corner to 1MHz
            fc_coeff = 1e6 / 12.5e6 * math.pi

        if fc_coeff > (1e6 / 12.5e6 * math.pi):
            raise InvalidConfigurationException("Differentiator saturation "
                                                "corner above maximum. Reduce"
                                                " differentiator saturation "
                                                "below %.3f."
                                                % (fc_coeff * kd * fs))

        d_fb = 1.0 - (fc_coeff)

        return p_gain, i_gain, d_gain, gain_factor, ii_gain, i_fb, d_fb

    @needs_commit
    def set_by_frequency(self, ch, kp=1, i_xover=None, d_xover=None,
                         ii_xover=None, si=None, sd=None, in_offset=0,
                         out_offset=0):
        """

        Configure the selected PID controller using crossover frequencies.

        :type ch: int; [1,2]
        :param ch: Channel of PID controller to  configure

        :type kp: float; [-1e3,1e3]
        :param kp: Proportional gain factor

        :type i_xover: float; [1e-3,1e6] Hz
        :param i_xover: Integrator crossover frequency

        :type d_xover: float; [1,10e6] Hz
        :param d_xover: Differentiator crossover frequency

        :type ii_xover: float; [1, 1e6] Hz
        :param ii_xover: Second integrator crossover frequency

        :type si: float; float; [-1e3,1e3]
        :param si: Integrator gain saturation

        :type sd: float; [-1e3,1e3]
        :param sd: Differentiator gain saturation

        :type in_offset: float; [-1.0,1.0] V
        :param in_offset: Input signal offset

        :type out_offset: float; [-1.0, 1.0] V
        :type out_offset: Output signal offset

        :raises InvalidConfigurationException: if the configuration of
                PID gains is not possible.
        """

        g, kp, ki, kd, kii, si, sd = self._calculate_gains_by_frequency(
            kp, i_xover, d_xover, ii_xover, si, sd)
        self._set_by_gain(ch, g, kp, ki, kd, kii, si, sd, in_offset,
                          out_offset, touch_ii=True, dac=ch)

    @needs_commit
    def set_by_gain(self, ch, g, kp=0, ki=0, kd=0, kii=0, si=None, sd=None,
                    in_offset=0, out_offset=0):
        """

        Configure the selected PID controller using gain coefficients.

        :type ch: int; [1,2]
        :param ch: Channel of the PID controller to be configured.

        :type g: float; [0,2^16 - 1]
        :param g: Gain

        :type kp: float; [-1e3,1e3]
        :param kp: Proportional gain factor

        :type ki: float;
        :param ki: Integrator gain factor

        :type kd: float;
        :param kd: Differentiator gain factor

        :type kii: float;
        :param kii: Second integrator gain factor

        :type si: float; float; [-1e3,1e3]
        :param si: Integrator gain saturation

        :type sd: float; [-1e3,1e3]
        :param sd: Differentiator gain saturation

        :type in_offset: float; [-1.0,1.0] V
        :param in_offset: Input signal offset

        :type out_offset: float; [-1.0, 1.0] V
        :type out_offset: Output signal offset

        :raises InvalidConfigurationException: if the configuration of PID
                gains is not possible.
        """
        self._set_by_gain(ch, g, kp, ki, kd, kii, si, sd, in_offset,
                          out_offset, touch_ii=True, dac=ch)

    def _set_by_gain(self, ch, g, kp, ki, kd, kii, si, sd,
                     in_offset, out_offset, touch_ii, dac):

        # The gain calculations depend on the output DAC, not the PID channel.
        p_gain, i_gain, d_gain, gain_factor, ii_gain, i_fb, d_fb = \
            self._calculate_regs_by_gain(dac, g, kp, ki, kd, kii, si, sd)

        double_integrator = kii != 0

        if ch == 1:

            # PID1 Enable components (PID/IS/DS stage)
            self.ch1_pid1_bypass = False
            self.ch1_pid1_en = True
            self.ch1_pid1_pen = p_gain > 0
            self.ch1_pid1_ien = ki > 0
            self.ch1_pid1_den = kd > 0
            self.ch1_pid1_pidgain = gain_factor
            # Set gain factors
            self.ch1_pid1_int_i_gain = i_gain
            self.ch1_pid1_int_p_gain = p_gain
            self.ch1_pid1_int_ifb_gain = i_fb
            self.ch1_pid1_int_dc_pole = si is None

            self.ch1_pid1_diff_p_gain = 0
            self.ch1_pid1_diff_i_gain = d_gain
            self.ch1_pid1_diff_ifb_gain = d_fb

            self.ch1_pid1_in_offset = in_offset
            self.ch1_pid1_out_offset = out_offset if not double_integrator \
                else 0

            if touch_ii:
                # PID2 Enable components (Additional I stage)
                self.ch1_pid2_bypass = not double_integrator
                self.ch1_pid2_en = True
                self.ch1_pid2_pen = double_integrator
                self.ch1_pid2_ien = ki > 0 and double_integrator
                self.ch1_pid2_den = False
                self.ch1_pid2_pidgain = gain_factor

                self.ch1_pid2_int_i_gain = ii_gain
                self.ch1_pid2_int_p_gain = 1
                self.ch1_pid2_int_ifb_gain = i_fb
                self.ch1_pid2_int_dc_pole = si is None

                # Input offset should be applied on the first PID, output
                # offset should be on the last /enabled/ pid.
                self.ch1_pid2_in_offset = 0
                self.ch1_pid2_out_offset = out_offset if double_integrator \
                    else 0

        if ch == 2:

            # PID1 Enable components (PID/IS/DS stage)
            self.ch2_pid1_bypass = False
            self.ch2_pid1_en = True
            self.ch2_pid1_pen = p_gain > 0
            self.ch2_pid1_ien = ki > 0
            self.ch2_pid1_den = kd > 0
            self.ch2_pid1_pidgain = gain_factor
            # Set gain factors
            self.ch2_pid1_int_i_gain = i_gain
            self.ch2_pid1_int_p_gain = p_gain
            self.ch2_pid1_int_ifb_gain = i_fb
            self.ch2_pid1_int_dc_pole = si is None

            self.ch2_pid1_diff_p_gain = 0
            self.ch2_pid1_diff_i_gain = d_gain
            self.ch2_pid1_diff_ifb_gain = d_fb

            self.ch2_pid1_in_offset = in_offset
            self.ch2_pid1_out_offset = out_offset if not double_integrator \
                else 0

            if touch_ii:
                # PID2 Enable components (Additional I stage)
                self.ch2_pid2_bypass = not double_integrator
                self.ch2_pid2_en = True
                self.ch2_pid2_pen = double_integrator
                self.ch2_pid2_ien = ki > 0 and double_integrator
                self.ch2_pid2_den = False
                self.ch2_pid2_pidgain = gain_factor

                self.ch2_pid2_int_i_gain = ii_gain
                self.ch2_pid2_int_p_gain = 1
                self.ch2_pid2_int_ifb_gain = i_fb
                self.ch2_pid2_int_dc_pole = si is None

                # Input offset should be applied on the first PID, output
                # offset should be on the last /enabled/ pid.
                self.ch2_pid2_in_offset = 0
                self.ch2_pid2_out_offset = out_offset if double_integrator \
                    else 0

    @needs_commit
    def set_control_matrix(self, ch, self_gain, cross_gain):
        """
        Set the linear combination of ADC input signals for a given PID
        channel.

        :type ch: int; [1,2]
        :param ch: PID Channel

        :type self_gain: float; [-20,20]
        :param self_gain: ADC input gain for same PID channel

        :type cross_gain: float; [-20, 20]
        :param cross_gain:

        """
        # We chuck in a factor of 1000 here then take it off again in the
        # controller gain. This optimises the rounding strategy, as the
        # control matrix itself doesn't have many fractional bits.
        if ch == 1:
            self.ch1_ch1_gain = self_gain * 1000 * 4
            self.ch1_ch2_gain = cross_gain * 1000 * 4
        elif ch == 2:
            self.ch2_ch1_gain = cross_gain * 1000 * 4
            self.ch2_ch2_gain = self_gain * 1000 * 4

        if self.ch1_ch1_gain == self.ch2_ch1_gain == 0:
            self.ch1_input_light = False
        else:
            self.ch1_input_light = True

        if self.ch1_ch2_gain == self.ch2_ch2_gain == 0:
            self.ch1_input_light = False
        else:
            self.ch2_input_light = True

    @needs_commit
    def set_trigger(self, source, edge, level, minwidth=None, maxwidth=None,
                    hysteresis=10e-3, hf_reject=False, mode='auto'):
        """
        Set the trigger source for the monitor channel signals. This can be
        either of the input or monitor signals, or the external input.

        :type source: string, {'in1','in2','A','B','ext'}
        :param source: Trigger Source. May be either an input or monitor
                channel (as set by :py:meth:`~pymoku.instruments.
                PIDController.set_monitor`), or external. External refers to
                the back-panel connector of the same name, allowing triggering
                from an externally-generated digital [LV]TTL or CMOS signal.

        :type edge: string, {'rising','falling','both'}
        :param edge: Which edge to trigger on. In Pulse Width modes this
                specifies whether the pulse is positive (rising)
                or negative (falling), with the 'both' option being invalid.

        :type level: float, [-10.0, 10.0] volts
        :param level: Trigger level

        :type minwidth: float, seconds
        :param minwidth: Minimum Pulse Width.
            0 <= minwidth < (2^32/samplerate). Can't be used with maxwidth.

        :type maxwidth: float, seconds
        :param maxwidth: Maximum Pulse Width.
            0 <= maxwidth < (2^32/samplerate). Can't be used with minwidth.

        :type hysteresis: float, [100e-6, 1.0] volts
        :param hysteresis: Hysteresis around trigger point.

        :type hf_reject: bool
        :param hf_reject: Enable high-frequency noise rejection

        :type mode: string, {'auto', 'normal'}
        :param mode: Trigger mode.
        """
        # Define the trigger sources appropriate to the LockInAmp instrument
        source = _utils.str_to_val(_PID_OSC_SOURCES, source, 'trigger source')

        # This function is the portion of set_trigger shared among
        # instruments with embedded scopes.
        self._set_trigger(source, edge, level, minwidth, maxwidth, hysteresis,
                          hf_reject, mode)

    @needs_commit
    def set_monitor(self, monitor_ch, source):
        """
        Configures the specified monitor channel to view the desired PID
        instrument signal.

        There are two 12-bit monitoring channels available, 'a' and 'b';
        each of these can be assigned to source signals from any of the
        internal PID instrument monitoring points. Signals larger than 12-bits
        must be either truncated or clipped to the allowed size.

        The source is one of:
            - **adc1** : Channel 1 ADC input
            - **in1** : PID Channel 1 input (after mixing, offset and scaling)
            - **out1** : PID Channel 1 output
            - **adc2** : Channel 2 ADC Input
            - **in2** : PID Channel 2 input (after mixing, offset and scaling)
            - **out2** : PID Channel 2 output

        :type monitor_ch: str; {'a','b'}
        :param monitor_ch: Monitor channel

        :type source: str; {'adc1', 'in1', 'out1', 'adc2', 'in2', 'out2'}
        :param source: Signal to connect to the monitor channel

        """
        _utils.check_parameter_valid(
            'string', monitor_ch, desc="monitor channel")
        _utils.check_parameter_valid(
            'string', source, desc="monitor signal")

        monitor_sources = {
            'none': _PID_MON_NONE,
            'adc1': _PID_MON_ADC1,
            'in1': _PID_MON_IN1,
            'out1': _PID_MON_OUT1,
            'adc2': _PID_MON_ADC2,
            'in2': _PID_MON_IN2,
            'out2': _PID_MON_OUT2
        }
        monitor_ch = monitor_ch.lower()
        source = source.lower()

        _utils.check_parameter_valid(
            'set', monitor_ch, allowed=['a', 'b'], desc="monitor channel")
        _utils.check_parameter_valid('set', source,
                                     allowed=['none',
                                              'adc1',
                                              'in1',
                                              'out1',
                                              'adc2',
                                              'in2',
                                              'out2'],
                                     desc="monitor source")

        if monitor_ch == 'a':
            self.monitor_a = source
            self.mon1_source = monitor_sources[source]
        elif monitor_ch == 'b':
            self.monitor_b = source
            self.mon2_source = monitor_sources[source]
        else:
            raise ValueOutOfRangeException("Invalid channel %d", monitor_ch)

    def _signal_source_volts_per_bit(self, source, scales, trigger=False):
        """
            Converts volts to bits depending on the signal source
        """
        # Decimation gain is applied only when using precision mode data
        if (not trigger and self.is_precision_mode()) or (trigger and (
                self.trig_precision)):
            deci_gain = self._deci_gain()
        else:
            deci_gain = 1.0

        if (source == _PID_SOURCE_A):
            level = self._monitor_source_volts_per_bit(
                self.monitor_a, scales) / deci_gain
        elif (source == _PID_SOURCE_B):
            level = self._monitor_source_volts_per_bit(
                self.monitor_b, scales) / deci_gain
        elif (source == _PID_SOURCE_IN1):
            level = scales['gain_adc1'] * (10.0 if scales['atten_ch1']
                                           else 1.0) / deci_gain
        elif (source == _PID_SOURCE_IN2):
            level = scales['gain_adc2'] * (10.0 if scales['atten_ch2']
                                           else 1.0) / deci_gain
        else:
            level = 1.0
        return level

    def _monitor_source_volts_per_bit(self, source, scales):
        # Calculates the volts to bits conversion for the given monitor
        # port signal

        monitor_source_gains = {
            'none': 1.0,
            'adc1': scales['gain_adc1'] / (10.0 if scales['atten_ch1']
                                           else 1.0),
            'in1': 1.0 / _ADC_DEFAULT_CALIBRATION,
            'out1': scales['gain_dac1'] * (2.0 ** 4),
            'adc2': scales['gain_adc2'] / (10.0 if scales['atten_ch2']
                                           else 1.0),
            'in2': 1.0 / _ADC_DEFAULT_CALIBRATION,
            'out2': scales['gain_dac2'] * (2.0 ** 4)
        }
        return monitor_source_gains[source]

    @needs_commit
    def enable_output(self, ch=None, en=True):
        """ Enable or disable the PID channel output(s).

        If *ch* is None (the default), both channels will be acted upon,
        otherwise just the one specified by the argument.

        :type ch: int; {1,2} or None
        :param ch: Output channel, or both.

        :type en: bool
        :param en: Enable the specified output channel(s).

        :raises InvalidParameterException: Invalid parameters
        """
        _utils.check_parameter_valid(
            'set', ch, [1, 2, None], 'output channel')
        _utils.check_parameter_valid('bool', en, 'output enable')

        if ch is None or ch == 1:
            self.ch1_output_en = en
        if ch is None or ch == 2:
            self.ch2_output_en = en

    @needs_commit
    def enable_input(self, ch=None, en=True):
        """ Enable or disable the PID channel input(s).

        If *ch* is None (the default), both channels will be acted upon,
        otherwise just the one specified by the argument.

        :type ch: int; {1,2} or None
        :param ch: Output channel, or both.

        :type en: bool
        :param en: Enable the specified input channel(s).

        :raises InvalidParameterException: Invalid parameters
        """
        _utils.check_parameter_valid('set', ch, [1, 2, None], 'input channel')
        _utils.check_parameter_valid('bool', en, desc='enable input')

        if ch is None or ch == 1:
            self.ch1_input_en = en
        if ch is None or ch == 2:
            self.ch2_input_en = en


_PID_reg_hdl = {
    'ch1_pid1_bypass':
        (REG_PID_ENABLES,
            to_reg_bool(0),
            from_reg_bool(0)),
    'ch1_pid2_bypass':
        (REG_PID_ENABLES,
            to_reg_bool(1),
            from_reg_bool(1)),
    'ch1_pid1_int_dc_pole':
        (REG_PID_ENABLES,
            to_reg_bool(2),
            from_reg_bool(2)),
    'ch1_pid2_int_dc_pole':
        (REG_PID_ENABLES,
            to_reg_bool(3),
            from_reg_bool(3)),
    'ch2_pid1_bypass':
        (REG_PID_ENABLES,
            to_reg_bool(4),
            from_reg_bool(4)),
    'ch2_pid2_bypass':
        (REG_PID_ENABLES,
            to_reg_bool(5),
            from_reg_bool(5)),
    'ch2_pid1_int_dc_pole':
        (REG_PID_ENABLES,
            to_reg_bool(6),
            from_reg_bool(6)),
    'ch2_pid2_int_dc_pole':
        (REG_PID_ENABLES,
            to_reg_bool(7),
            from_reg_bool(7)),
    'ch1_pid1_en':
        (REG_PID_ENABLES,
            to_reg_bool(8),
            from_reg_bool(8)),
    'ch1_pid2_en':
        (REG_PID_ENABLES,
            to_reg_bool(9),
            from_reg_bool(9)),
    'ch2_pid1_en':
        (REG_PID_ENABLES,
            to_reg_bool(10),
            from_reg_bool(10)),
    'ch2_pid2_en':
        (REG_PID_ENABLES,
            to_reg_bool(11),
            from_reg_bool(11)),
    'ch1_pid1_ien':
        (REG_PID_ENABLES,
            to_reg_bool(12),
            from_reg_bool(12)),
    'ch1_pid2_ien':
        (REG_PID_ENABLES,
            to_reg_bool(13),
            from_reg_bool(13)),
    'ch2_pid1_ien':
        (REG_PID_ENABLES,
            to_reg_bool(14),
            from_reg_bool(14)),
    'ch2_pid2_ien':
        (REG_PID_ENABLES,
            to_reg_bool(15),
            from_reg_bool(15)),
    'ch1_pid1_pen':
        (REG_PID_ENABLES,
            to_reg_bool(16),
            from_reg_bool(16)),
    'ch1_pid2_pen':
        (REG_PID_ENABLES,
            to_reg_bool(17),
            from_reg_bool(17)),
    'ch2_pid1_pen':
        (REG_PID_ENABLES,
            to_reg_bool(18),
            from_reg_bool(18)),
    'ch2_pid2_pen':
        (REG_PID_ENABLES,
            to_reg_bool(19),
            from_reg_bool(19)),
    'ch1_pid1_den':
        (REG_PID_ENABLES,
            to_reg_bool(20),
            from_reg_bool(20)),
    'ch1_pid2_den':
        (REG_PID_ENABLES,
            to_reg_bool(21),
            from_reg_bool(21)),
    'ch2_pid1_den':
        (REG_PID_ENABLES,
            to_reg_bool(22),
            from_reg_bool(22)),
    'ch2_pid2_den':
        (REG_PID_ENABLES,
            to_reg_bool(23),
            from_reg_bool(23)),
    'ch1_output_en':
        (REG_PID_ENABLES,
            to_reg_bool(24),
            from_reg_bool(24)),
    'ch2_output_en':
        (REG_PID_ENABLES,
            to_reg_bool(25),
            from_reg_bool(25)),
    'ch1_input_en':
        (REG_PID_MONSELECT,
            to_reg_bool(6),
            from_reg_bool(6)),
    'ch2_input_en':
        (REG_PID_MONSELECT,
            to_reg_bool(7),
            from_reg_bool(7)),
    'ch1_input_light':
        (REG_PID_MONSELECT,
            to_reg_bool(8),
            from_reg_bool(8)),
    'ch2_input_light':
        (REG_PID_MONSELECT,
            to_reg_bool(9),
            from_reg_bool(9)),
    'ch1_ch1_gain':
        ((REG_PID_CH0_CH0GAIN_MSB, REG_PID_CH0_CH0GAIN_LSB),
            to_reg_signed(24, 16,
                          xform=lambda obj,
                          x: x * 2.0**8 * obj._adc_gains()[0]),
            from_reg_signed(24, 16,
                            xform=lambda obj,
                            x: x / 2.0**8 / obj._adc_gains()[0])),

    'ch1_ch2_gain':
        (REG_PID_CH0_CH1GAIN,
            to_reg_signed(0, 16,
                          xform=lambda obj,
                          x: x * 2.0**8 * obj._adc_gains()[0]),
            from_reg_signed(0, 16,
                            xform=lambda obj,
                            x: x / 2.0**8 / obj._adc_gains()[0])),

    'ch2_ch1_gain':
        ((REG_PID_CH1_CH0GAIN_MSB, REG_PID_CH1_CH0GAIN_LSB),
            to_reg_signed(24, 16,
                          xform=lambda obj,
                          x: x * 2.0**8 * obj._adc_gains()[1]),
            from_reg_signed(24, 16,
                            xform=lambda obj,
                            x: x / 2.0**8 / obj._adc_gains()[1])),

    'ch2_ch2_gain':
        (REG_PID_CH1_CH1GAIN,
            to_reg_signed(16, 16,
                          xform=lambda obj,
                          x: x * 2.0**8 * obj._adc_gains()[1]),
            from_reg_signed(16, 16,
                            xform=lambda obj,
                            x: x / 2.0**8 / obj._adc_gains()[1])),

    'ch1_pid1_in_offset':
        (REG_PID_CH0_OFFSET1,
            to_reg_signed(0, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[0]),
            from_reg_signed(0, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[0])),

    'ch1_pid2_in_offset':
        (REG_PID_CH0_OFFSET2,
            to_reg_signed(0, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[0]),
            from_reg_signed(0, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[0])),

    'ch1_pid1_out_offset':
        (REG_PID_CH0_OFFSET1,
            to_reg_signed(16, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[0]),
            from_reg_signed(16, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[0])),

    'ch1_pid2_out_offset':
        (REG_PID_CH0_OFFSET2,
            to_reg_signed(16, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[0]),
            from_reg_signed(16, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[0])),

    'ch1_pid1_pidgain':
        (REG_PID_CH0_PIDGAIN1,
            to_reg_signed(0, 32, xform=lambda obj, x: x),
            from_reg_signed(0, 32, xform=lambda obj, x: x)),

    'ch1_pid2_pidgain':
        (REG_PID_CH0_PIDGAIN2,
            to_reg_signed(0, 32, xform=lambda obj, x: x),
            from_reg_signed(0, 32, xform=lambda obj, x: x)),

    'ch1_pid1_int_i_gain':
        (REG_PID_CH0_INT_IGAIN1,
         to_reg_unsigned(0, 24, xform=lambda obj, x: x * (2.0 ** 24 - 1)),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    # TODO: This concerns me, not sure if its writing to the registers as
    # expected
    'ch1_pid2_int_i_gain':
        ((REG_PID_CH0_INT_IGAIN2_MSB, REG_PID_CH0_INT_IGAIN2_LSB),
            to_reg_unsigned(24, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(24, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'ch1_pid1_int_ifb_gain':
        ((REG_PID_CH0_INT_IFBGAIN1_MSB, REG_PID_CH0_INT_IFBGAIN1_LSB),
            to_reg_unsigned(16, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(16, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'ch1_pid2_int_ifb_gain':
        (REG_PID_CH0_INT_IFBGAIN2,
         to_reg_unsigned(8, 24, xform=lambda obj, x: x * (2.0 ** 24 - 1)),
         from_reg_unsigned(8, 24, xform=lambda obj, x: x / (2.0 ** 24 - 1))),

    'ch1_pid1_int_p_gain':
        (REG_PID_CH0_INT_PGAIN1,
            to_reg_unsigned(0, 24, xform=lambda obj, x: x * 2.0**11),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / 2.0**11)),

    'ch1_pid2_int_p_gain':
        ((REG_PID_CH0_INT_PGAIN2_MSB, REG_PID_CH0_INT_PGAIN2_LSB),
            to_reg_unsigned(24, 24, xform=lambda obj, x: x * 2.0**11),
            from_reg_unsigned(24, 24, xform=lambda obj, x: x / 2.0**11)),

    'ch1_pid1_diff_p_gain':
        (REG_PID_CH0_DIFF_PGAIN1,
            to_reg_unsigned(0, 24, xform=lambda obj, x: x * 2.0**11),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / 2.0**11)),

    'ch1_pid1_diff_i_gain':
        ((REG_PID_CH0_DIFF_IGAIN1_MSB, REG_PID_CH0_DIFF_IGAIN1_LSB),
            to_reg_unsigned(16, 24),
            from_reg_unsigned(16, 24)),

    'ch1_pid1_diff_ifb_gain':
        (REG_PID_CH0_DIFF_IFBGAIN1,
            to_reg_unsigned(0, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'ch2_pid1_in_offset':
        (REG_PID_CH1_OFFSET1,
            to_reg_signed(0, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[1]),
            from_reg_signed(0, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[1])),

    'ch2_pid2_in_offset':
        (REG_PID_CH1_OFFSET2,
            to_reg_signed(0, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[1]),
            from_reg_signed(0, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[1])),

    'ch2_pid1_out_offset':
        (REG_PID_CH1_OFFSET1,
            to_reg_signed(16, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[1]),
            from_reg_signed(16, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[1])),

    'ch2_pid2_out_offset':
        (REG_PID_CH1_OFFSET2,
            to_reg_signed(16, 16,
                          xform=lambda obj, x: x / obj._dac_gains()[1]),
            from_reg_signed(16, 16,
                            xform=lambda obj, x: x * obj._dac_gains()[1])),

    'ch2_pid1_pidgain':
        (REG_PID_CH1_PIDGAIN1,
            to_reg_signed(0, 32, xform=lambda obj, x: x),
            from_reg_signed(0, 32, xform=lambda obj, x: x)),

    'ch2_pid2_pidgain':
        (REG_PID_CH1_PIDGAIN2,
            to_reg_signed(0, 32, xform=lambda obj, x: x),
            from_reg_signed(0, 32, xform=lambda obj, x: x)),

    'ch2_pid1_int_i_gain':
        (REG_PID_CH1_INT_IGAIN1,
            to_reg_unsigned(0, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'ch2_pid2_int_i_gain':
        ((REG_PID_CH1_INT_IGAIN2_MSB, REG_PID_CH1_INT_IGAIN2_LSB),
            to_reg_unsigned(24, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(24, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'ch2_pid1_int_ifb_gain':
        ((REG_PID_CH1_INT_IFBGAIN1_MSB, REG_PID_CH1_INT_IFBGAIN1_LSB),
            to_reg_unsigned(16, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(16, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'ch2_pid2_int_ifb_gain':
        (REG_PID_CH1_INT_IFBGAIN2,
            to_reg_unsigned(8, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(8, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'ch2_pid1_int_p_gain':
        (REG_PID_CH1_INT_PGAIN1,
            to_reg_unsigned(0, 24, xform=lambda obj, x: x * 2.0**11),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / 2.0**11)),

    'ch2_pid2_int_p_gain':
        ((REG_PID_CH1_INT_PGAIN2_MSB, REG_PID_CH1_INT_PGAIN2_LSB),
            to_reg_unsigned(24, 24, xform=lambda obj, x: x * 2.0**11),
            from_reg_unsigned(24, 24, xform=lambda obj, x: x / 2.0**11)),

    'ch2_pid1_diff_p_gain':
        (REG_PID_CH1_DIFF_PGAIN1,
            to_reg_unsigned(0, 24, xform=lambda obj, x: x * 2.0**11),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / 2.0**11)),

    'ch2_pid1_diff_i_gain':
        ((REG_PID_CH1_DIFF_IGAIN1_MSB, REG_PID_CH1_DIFF_IGAIN1_LSB),
            to_reg_unsigned(16, 24),
            from_reg_unsigned(16, 24)),

    'ch2_pid1_diff_ifb_gain':
        (REG_PID_CH1_DIFF_IFBGAIN1,
            to_reg_unsigned(0, 24, xform=lambda obj, x: x * (2.0**24 - 1)),
            from_reg_unsigned(0, 24, xform=lambda obj, x: x / (2.0**24 - 1))),

    'mon1_source':
        (REG_PID_MONSELECT,
            to_reg_unsigned(0, 3),
            from_reg_unsigned(0, 3)),

    'mon2_source':
        (REG_PID_MONSELECT,
            to_reg_unsigned(3, 3),
            from_reg_unsigned(3, 3)),

}
