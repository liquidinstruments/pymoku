
import math
import logging
import re
import os

from ._instrument import *
from . import _frame_instrument
from . import _waveform_generator
from pymoku._oscilloscope import _CoreOscilloscope
from . import _utils
from ._trigger import Trigger
from ._sweep_generator import SweepGenerator

log = logging.getLogger(__name__)

REG_ARB_SETTINGS1 = 88
REG_ARB_LUT_LENGTH1 = 105
REG_ARB_AMPLITUDE1 = 106
REG_ARB_OFFSET1 = 107

REG_ARB_SETTINGS2 = 108
REG_ARB_LUT_LENGTH2 = 125
REG_ARB_AMPLITUDE2 = 126
REG_ARB_OFFSET2 = 127

_ARB_MODE_1000 = 0x0
_ARB_MODE_500 = 0x1
_ARB_MODE_250 = 0x2
_ARB_MODE_125 = 0x3

_ARB_LUT_LENGTH = 8192
_ARB_LUT_LSB = 2.0**32
_ARB_LUT_INTERPLOATION_LENGTH = 2**32

_ARB_TRIG_SRC_CH1 = 0
_ARB_TRIG_SRC_CH2 = 1
_ARB_TRIG_SRC_EXT = 4

_ARB_TRIG_LVL_MIN = -5.0
_ARB_TRIG_LVL_MAX = 5.0

_ARB_TRIG_TYPE_SINGLE 	= 0
_ARB_TRIG_TYPE_CONT		= 2

_ARB_SMPL_RATE = 1.0e9

# In-built monitor constants
_ARB_INPUT_SMPS = ADC_SMP_RATE
_ARB_CHN_BUFLEN = 2**13

class ArbitraryWaveGen(_CoreOscilloscope):
	"""
	.. automethod:: pymoku.instruments.WaveformGenerator.__init__
	"""

	def __init__(self):
		super(ArbitraryWaveGen, self).__init__()
		self._register_accessors(_arb_reg_handlers)
		self.id = 15
		self.type = "arbitrarywavegen"

		self._sweep1 = SweepGenerator(self, 96)
		self._sweep2 = SweepGenerator(self, 116)

		self._trigger1 = Trigger(self, 89)
		self._trigger2 = Trigger(self, 109)

		# Locally store the trigger level
		self.trig_level1 = 0 # Volts
		self.trig_level2 = 0 # Volts

		# Monitor configuration
		# TODO: Implement monitor functions? Is there a use-case?
		# TODO: Check this rate is correct for the AWG
		self._input_samplerate	= _ARB_INPUT_SMPS
		self._chn_buffer_len	= _ARB_CHN_BUFLEN

		self.mode1 = _ARB_MODE_125
		self.mode2 = _ARB_MODE_125


	@needs_commit
	def set_defaults(self):
		"""Sets the Arbitrary Waveform Generator instrument to sane defaults
		"""
		super(ArbitraryWaveGen, self).set_defaults()

		self.set_frontend(1, fiftyr=True, atten=True, ac=False)
		self.set_frontend(1, fiftyr=True, atten=True, ac=False)

		self.gen_waveform(1, 1, 0, en=False)
		self.gen_waveform(2, 1, 0, en=False)

		self.set_waveform_trigger(1, 'in1', 'rising', 0)
		self.set_waveform_trigger(2, 'in2', 'rising', 0)

		self.set_waveform_trigger_output(1, False)
		self.set_waveform_trigger_output(2, False)

	def _set_mode(self, ch, mode, length):
		if mode is _ARB_MODE_1000:
			_utils.check_parameter_valid('range', length, [1,2**13], desc='length for lookup table')
		if mode is _ARB_MODE_500:
			_utils.check_parameter_valid('range', length, [1,2**14], desc='length for lookup table')
		if mode is _ARB_MODE_250:
			_utils.check_parameter_valid('range', length, [1,2**15], desc='length for lookup table')
		if mode is _ARB_MODE_125:
			_utils.check_parameter_valid('range', length, [1,2**16], desc='length for lookup table')

		if ch == 1:
			self.mode1 = mode
			self.lut_length1 = length-1
		elif ch ==2:
			self.mode2 = mode
			self.lut_length2 = length-1

	# Can't use nested needs_commit because mmap access bit must be set in this function
	def write_lut(self, ch, data, mode=None):
		"""Writes the signal lookup table to memory in the Moku:Lab.

		You can also choose the output rate of the AWG, which influences the
		maximum length of the look-up table as follows:

		- 1000MSPS: 8192 points per channel
		- 500MSPS: 16384 points per channel
		- 250MSPS: 32768 points per channel
		- 125MSPS: 65536 points per channel

		If you don't specify a mode, the fastest output rate for the given data
		length will be automatically chosen. This is correct in almost all
		circumstances.

		If you specify a particular mode along with a data array too big for
		that mode, the behaviour is undefined.

		To avoid unexpected output signals during write, disable the outputs
		by using the :any:`enable_output` function.

		:type ch: int; {1,2}
		:param ch: Output channel to load the LUT to

		:type data: float array;
		:param data: Lookup table coefficients normalised to range [-1.0, 1.0].

		:type mode: int; {125, 250, 500, 1000} MSmps
		:param mode: defines the output sample rate of the AWG.

		:raises ValueError: if the channel is invalid
		:raises ValueOutOfRangeException: if wave parameters are out of range
		"""
		_utils.check_parameter_valid('set', ch, [1, 2],'output channel')
		_utils.check_parameter_valid('set', mode, [125, 250, 500, 1000], desc='output sample rate', units="MSmps", allow_none=True)

		# Check that all coefficients are between -1.0 and 1.0
		if not all(map(lambda x: abs(x) <= 1.0, data)):
			raise ValueOutOfRangeException("Lookup table coefficients must be in the range [-1.0, 1.0].")

		n_points = len(data)

		if n_points <= 2**13:
			max_lut_samplerate = 1000
		elif n_points <= 2**14:
			max_lut_samplerate = 500
		elif n_points <= 2**15:
			max_lut_samplerate = 250
		elif n_points <= 2**16:
			max_lut_samplerate = 125
		else:
			raise ValueOutOfRangeException("Maximum data length is 65535 samples")

		if not mode:
			mode = max_lut_samplerate

		if mode > max_lut_samplerate:
			raise InvalidConfigurationException("Maximum samplerate for {} lookup table coefficients is {}Msmps.".format(n_points,max_lut_samplerate))

		_str_to_mode = {
			'1000' 	: _ARB_MODE_1000,
			'500' 	: _ARB_MODE_500,
			'250'	: _ARB_MODE_250,
			'125'	: _ARB_MODE_125
		}

		mode = _utils.str_to_val(_str_to_mode, str(mode), "operating mode")

		self._set_mode(ch, mode, len(data))
		self.commit()

		# picks the stepsize and the steps based in the mode
		steps, stepsize = [(8, 8192), (4, 8192 * 2), (2, 8192 * 4), (1, 8192 * 8)][mode]

		byte_data = bytearray()
		for step in range(steps):
			byte_data += bytearray(b''.join([struct.pack('<hh', int(math.ceil((2.0 ** 15 - 1) * d)), 0) for d in data]))
			byte_data += bytearray(b'\0' * (stepsize * 4 - (len(data) * 4)))

		# Write the data to AWG memory map
		self._set_mmap_access(True)
		self._moku._send_file_bytes('j', '', byte_data, offset=_ARB_LUT_LENGTH * 8 * 4 * (ch - 1))
		self._set_mmap_access(False)

		# Release the memory map "file" to other resources
		self._moku._fs_finalise('j', '', _ARB_LUT_LENGTH * 8 * 4 * 2)

	@needs_commit
	def gen_waveform(self, ch, period, amplitude, phase=0, offset=0, interpolation=True, dead_time=0, dead_voltage=0, en=True):
		""" Configure and enable the Arbitrary Waveform on the given output channel.

		The look-up table for this channel's output waveform should have been loaded beforehand using :any:`write_lut`.

		The Arbitrary Waveform Generator has the ability to insert a deadtime between cycles of the look-up
		table. This time is specified in cycles of the waveform. During this time, the output will be held
		at the given *dead_voltage*.  This allows the user to, for example, generate infrequent pulses without
		using space in the LUT to specify the time between, keeping the full LUT size to provide a high-resolution
		pulse shape.

		Where the period and look-up table contents are set such that there isn't exactly one LUT point per output
		sample, the AWG instrument can optionally provide a linear interpolation between LUT points.

		This function enables the output channel by default. If you wish to enable the outputs simultaneously, you
		should set the `en` parameter to False and enable both when desired using :any:`enable_output`.

		:type ch: int; {1,2}
		:param ch: Channel on which to generate the wave

		:type period: float, [4e-9, 1];
		:param period: period of the signal in seconds

		:type amplitude: float, [0.0,2.0] Vpp
		:param amplitude: Waveform peak-to-peak amplitude

		:type phase: float, [0-360] degrees
		:param phase: Phase offset of the wave

		:type offset: float, [-1.0,1.0] Volts
		:param offset: DC offset applied to the waveform

		:type interpolation: bool [True, False]
		:param interpolation: Enable linear interpolation of LUT entries

		:type dead_time: float [0, 2e18] cyc
		:param dead_time: number of cycles which show the dead voltage. Use 0 for no dead time

		:type dead_voltage: float [-2.0,2.0] V
		:param dead_voltage: signal level during dead time in Volts

		:type en: bool
		:param en: Enable output

		:raises ValueError: if the parameters  is invalid
		:raises ValueOutOfRangeException: if wave parameters are out of range
		:raises InvalidParameterException: if the parameters are the wrong types
		"""
		_utils.check_parameter_valid('set', ch, [1,2], desc='output channel')
		_utils.check_parameter_valid('range', period, [4e-9, 1000], desc='period of the signal')
		_utils.check_parameter_valid('range', amplitude, [0.0,2.0], desc='peak to peak amplitude', units='volts')
		_utils.check_parameter_valid('bool', interpolation, desc='linear interpolation')
		_utils.check_parameter_valid('range', dead_time, [0.0, 2e18], desc='signal dead time', units='cycles')
		_utils.check_parameter_valid('range', dead_voltage, [-2.0, 2.0], desc='dead value', units='volts')
		_utils.check_parameter_valid('range', phase, [0, 360], desc='phase offset', units='degrees')
		_utils.check_parameter_valid('bool', en, 'output enable')

		upper_voltage = offset + (amplitude/2.0)
		lower_voltage = offset - (amplitude/2.0)

		if (upper_voltage > 1.0) or (lower_voltage < -1.0):
			raise ValueOutOfRangeException("Waveform offset limited by amplitude (max output range 2.0Vpp).")

		# Ensure that dead voltage does not exceed the amplitude of the waveform
		if dead_voltage > upper_voltage or dead_voltage < lower_voltage:
			raise ValueOutOfRangeException("Dead voltage must not exceed custom waveform voltage range of [%.2f, %.2f] Volts." \
				% (lower_voltage, upper_voltage))

		if(ch == 1):
			freq = 1.0/period
			self.interpolation1 = interpolation
			phase_modulo = (self.lut_length1 + 1) * _ARB_LUT_INTERPLOATION_LENGTH
			self._sweep1.step = freq / _ARB_SMPL_RATE * phase_modulo
			phase_modulo = phase_modulo * (1 + dead_time)
			self._sweep1.stop = phase_modulo
			self._sweep1.start = (phase / 360.0) * phase_modulo
			self.dead_value1 = 0.0 if not amplitude else 2.0 * (dead_voltage - lower_voltage)/(upper_voltage - lower_voltage) - 1.0
			self.amplitude1 = amplitude
			self.offset1 = offset
			self.enable1 = en

		if(ch == 2):
			freq = 1.0/period
			self.interpolation2 = interpolation
			phase_modulo = (self.lut_length2 + 1) * _ARB_LUT_INTERPLOATION_LENGTH
			self._sweep2.step = freq / _ARB_SMPL_RATE * phase_modulo
			phase_modulo = phase_modulo * (1 + dead_time)
			self._sweep2.stop = phase_modulo
			self._sweep2.start = (phase / 360.0) * phase_modulo
			self.dead_value2 = 0.0 if not amplitude else 2.0 * (dead_voltage - lower_voltage)/(upper_voltage - lower_voltage) - 1.0
			self.amplitude2 = amplitude
			self.offset2 = offset
			self.enable2 = en

	@needs_commit
	def set_waveform_trigger(self, ch, source, edge, level, minwidth=None, maxwidth=None, hysteresis=False):
		""" Specify what constitutes a trigger event for the given output channel.
		This takes effect only when the channel has triggered output mode enabled (see :any:`set_waveform_trigger_output <pymoku.instruments.ArbitraryWaveGen.set_waveform_trigger_output>`
		).

		:type ch: int; {1,2}
		:param ch: Output channel to set triggering on

		:type source: string, {'in1','in2','ext'}
		:param source: Trigger source. May be either input channel, or the external 'Trig' back-panel connector
			allowing triggering from an externally-generated digital [LV]TTL or CMOS signal.

		:type edge: string, {'rising','falling','both'}
		:param edge: Which edge to trigger on. In 'Pulse Width' mode this specifies whether the pulse is positive (rising)
				or negative (falling), with the 'both' option being invalid.

		:type level: float, [-5.0, 5.0] volts
		:param level: Trigger level. Ignored in 'ext' mode.

		:type minwidth: float, seconds
		:param minwidth: Minimum Pulse Width. 0 <= minwidth < (2^32/samplerate). Can't be used with maxwidth.

		:type maxwidth: float, seconds
		:param maxwidth: Maximum Pulse Width. 0 <= maxwidth < (2^32/samplerate). Can't be used with minwidth.

		:type hysteresis: bool
		:param hysteresis: Enable hysteresis around trigger point.

		"""
		_utils.check_parameter_valid('set', ch, [1,2], 'channel')
		_utils.check_parameter_valid('set', source, ['in1', 'in2', 'ext'], 'trigger source')
		_utils.check_parameter_valid('set', edge, ['rising', 'falling', 'both'])
		_utils.check_parameter_valid('range', level, [_ARB_TRIG_LVL_MIN, _ARB_TRIG_LVL_MAX], 'trigger level', 'Volts')

		if not (maxwidth is None or minwidth is None):
			raise InvalidConfigurationException("Can't set both 'minwidth' and 'maxwidth' for Pulse Width trigger mode. Choose one.")
		if (maxwidth or minwidth) and (edge is 'both'):
			raise InvalidConfigurationException("Can't set trigger edge type 'both' in Pulse Width trigger mode. Choose one of {'rising','falling'}.")

		# External trigger source is only available on Moku 20
		if (self._moku.get_hw_version() == 1.0) and source == 'ext':
			raise InvalidConfigurationException('External trigger source is not available on your hardware.')
		if source=='ext' and level:
			log.warning("Trigger level ignored when triggering from source 'ext'.")

		# TODO: Add timer source
		_str_to_source = {
			'in1' : _ARB_TRIG_SRC_CH1,
			'in2' : _ARB_TRIG_SRC_CH2,
			'ext' : _ARB_TRIG_SRC_EXT
		}
		_str_to_edge = {
			'rising' : Trigger.EDGE_RISING,
			'falling' : Trigger.EDGE_FALLING,
			'both'	: Trigger.EDGE_BOTH
		}
		source = _utils.str_to_val(_str_to_source, source, 'trigger source')
		edge = _utils.str_to_val(_str_to_edge, edge, 'edge type')

		if ch == 1:
			self.trig_source1 = source
			self.trig_level1 = level
		elif ch == 2:
			self.trig_source2 = source
			self.trig_level2 = level
		else:
			raise ValueOutOfRangeException("Incorrect channel number %d", ch)

		trig_channels = [self._trigger1, self._trigger2]

		# AKA: Normal trigger mode only (HG-2598)
		trig_channels[ch-1].timer = 0.0
		trig_channels[ch-1].auto_holdoff = 0

		trig_channels[ch-1].edge = edge
		trig_channels[ch-1].duration = minwidth or maxwidth or 0.0
		# TODO: Enable setting hysteresis level. For now we use the iPad LSB values for ON/OFF.
		trig_channels[ch-1].hysteresis = 25 if hysteresis else 0

		if maxwidth:
			trig_channels[ch-1].trigtype = Trigger.TYPE_PULSE
			trig_channels[ch-1].pulsetype = Trigger.PULSE_MAX
		elif minwidth:
			trig_channels[ch-1].trigtype = Trigger.TYPE_PULSE
			trig_channels[ch-1].pulsetype = Trigger.PULSE_MIN
		else:
			trig_channels[ch-1].trigtype = Trigger.TYPE_EDGE

	@needs_commit
	def set_waveform_trigger_output(self, ch, trig_en=True, single=False, duration=0, hold_last=False):
		""" Enables triggered output mode on the specified channel and configures 'how' to output the set waveform on a trigger event.

		:type ch: int; {1,2}
		:param ch: Output channel to configure

		:type trig_en: bool;
		:param trig_en: Enables triggering mode on the specified output channel

		:type single: bool;
		:param single: Enables single mode. Outputs a single waveform (vs continuous) per trigger event.

		:type duration: float; [0.0, 1e11] seconds
		:param duration: Total time that the triggered output should be generated (leave 0 for continuous).
			Note the duration resolution is 8ns.

		:type hold_last: bool
		:param hold_last: Hold the last value of the waveform for the duration of the triggered output.
		"""
		# Convert the input parameter strings to bit-value mappings
		_utils.check_parameter_valid('set', ch, [1,2], 'channel')
		_utils.check_parameter_valid('bool', trig_en, 'trigger enable')
		_utils.check_parameter_valid('bool', single, 'single trigger enable')
		_utils.check_parameter_valid('range', duration, [0, 1e11], 'duration', 'seconds')
		_utils.check_parameter_valid('bool', hold_last, 'hold_last')

		sweep_channels = [self._sweep1, self._sweep2]

		sweep_channels[ch-1].wait_for_trig = trig_en
		sweep_channels[ch-1].waveform = _ARB_TRIG_TYPE_SINGLE if single else _ARB_TRIG_TYPE_CONT
		sweep_channels[ch-1].hold_last = hold_last

		if single and not duration:
			# Duration must be set to ~equal the waveform period otherwise we can never retrigger
			sweep_channels[ch-1].duration = _ARB_SMPL_RATE / 8.0 / self.get_frequency(ch)
		else:
			sweep_channels[ch-1].duration = int(round(duration * 1.0e9 / 8))

	def _update_dependent_regs(self, scales):
		super(ArbitraryWaveGen, self)._update_dependent_regs(scales)
		self._trigger1.level = int(round(self.trig_level1 / self._signal_source_volts_per_bit(self.trig_source1, scales)))
		self._trigger2.level = int(round(self.trig_level2 / self._signal_source_volts_per_bit(self.trig_source2, scales)))

	@needs_commit
	def sync_phase(self):
		""" Resets the phase accumulator of both output waveforms.
		"""
		self.reset_phase(1)
		self.reset_phase(2)

	@needs_commit
	def reset_phase(self, ch):
		""" resets the channels phase accumulator to zero

		:type ch: int; {1,2}
		:param ch: Channel on which the reset is performed

		:raises ValueError: if the channel number is invalid
		"""
		_utils.check_parameter_valid('set', ch, [1,2],'output channel')

		if ch == 1:
			self.phase_rst1 = True
		elif ch ==2:
			self.phase_rst2 = True

	def get_frequency(self, ch):
		""" Returns the frequency of the output waveform on the selected channel.

		:type ch: int; {1,2}
		:param ch: Output channel

		:raises ValueError: if the channel number is invalid
		"""
		_utils.check_parameter_valid('set', ch, [1,2],'output channel')

		if ch == 1:
			return (float(self._sweep1.step) / self._sweep1.stop) * _ARB_SMPL_RATE
		if ch == 2:
			return (float(self._sweep2.step) / self._sweep2.stop) * _ARB_SMPL_RATE

	@needs_commit
	@deprecated(category='method', message="'gen_off' has been deprecated, use 'enable_output' instead.")
	def gen_off(self, ch=None):
		""" Turn ArbitraryWaveGen output(s) off.

		The channel will be turned on when configuring the waveform type but can be turned off
		using this function. If *ch* is None (the default), both channels will be turned off,
		otherwise just the one specified by the argument.

		:type ch: int; {1,2} or None
		:param ch: Channel to turn off, or both.

		:raises ValueError: Invalid parameters
		"""
		self.enable_output(ch, en=False)

	@needs_commit
	def enable_output(self, ch=None, en=True):
		""" Enable or disable the ArbitraryWaveGen output(s).

		If *ch* is None (the default), both channels will be acted upon,
		otherwise just the one specified by the argument.

		:type ch: int; {1,2} or None
		:param ch: Output channel, or both.

		:type en: bool
		:param en: Enable the specified output channel(s).

		:raises ValueError: Invalid parameters
		"""
		_utils.check_parameter_valid('set',ch, [1,2], 'output channel', allow_none=True)
		_utils.check_parameter_valid('bool',en,'output enable')
		if not ch or ch==1:
			self.enable1 = en
		if not ch or ch==2:
			self.enable2 = en

	def _signal_source_volts_per_bit(self, source, scales, trigger=False):
		"""
			Converts volts to bits depending on the signal source.
			To do: complete this function when osc functionality added to awg, stubbed for now.
		"""
		if (source == _ARB_TRIG_SRC_CH1):
			level = scales['gain_adc1']
		elif (source == _ARB_TRIG_SRC_CH2):
			level = scales['gain_adc2']
		elif (source == _ARB_TRIG_SRC_EXT):
			level = 1.0
		else:
			level = 1.0

		return level


_arb_reg_handlers = {
	'enable1':			(REG_ARB_SETTINGS1,		to_reg_bool(0),	from_reg_bool(0)),
	'phase_rst1':		(REG_ARB_SETTINGS1,		to_reg_bool(1),	from_reg_bool(1)),
	'mode1':			(REG_ARB_SETTINGS1,		to_reg_unsigned(2, 2, allow_set=[_ARB_MODE_125, _ARB_MODE_250, _ARB_MODE_500, _ARB_MODE_1000]),
												from_reg_unsigned(2, 2)),
	'interpolation1':	(REG_ARB_SETTINGS1,		to_reg_bool(4),	from_reg_bool(4)),
	'trig_source1':		(REG_ARB_SETTINGS1,		to_reg_unsigned(5, 5, allow_set=[_ARB_TRIG_SRC_CH1, _ARB_TRIG_SRC_CH2, _ARB_TRIG_SRC_EXT]),
												from_reg_unsigned(5, 5)),
	'lut_length1':		(REG_ARB_LUT_LENGTH1,	to_reg_unsigned(0, 16), from_reg_unsigned(0, 16)),
	'dead_value1':		(REG_ARB_LUT_LENGTH1,	to_reg_signed(16, 16, xform=lambda obj, r: r * (2.0**15)),
												from_reg_signed(16, 16, xform=lambda obj, r: r / (2.0**15))),
	'amplitude1':		(REG_ARB_AMPLITUDE1,	to_reg_signed(0, 18, xform=lambda obj, r: r / obj._dac_gains()[0]),
	                                            from_reg_signed(0, 18, xform=lambda obj, r: r * obj._dac_gains()[0])),
	'offset1':			(REG_ARB_OFFSET1,		to_reg_signed(0, 16, xform=lambda obj, r: r / obj._dac_gains()[0]),
	                                            from_reg_signed(0, 16, xform=lambda obj, r: r * obj._dac_gains()[0])),
	'enable2':			(REG_ARB_SETTINGS2,		to_reg_bool(0), from_reg_bool(0)),
	'phase_rst2':		(REG_ARB_SETTINGS2,		to_reg_bool(1),	from_reg_bool(1)),
	'mode2':			(REG_ARB_SETTINGS2,		to_reg_unsigned(2, 2, allow_set=[_ARB_MODE_125, _ARB_MODE_250, _ARB_MODE_500, _ARB_MODE_1000]),
												from_reg_unsigned(2, 2)),
	'interpolation2':	(REG_ARB_SETTINGS2,		to_reg_bool(4),	from_reg_bool(4)),
	'trig_source2':		(REG_ARB_SETTINGS2,		to_reg_unsigned(5, 5, allow_set=[_ARB_TRIG_SRC_CH1, _ARB_TRIG_SRC_CH2, _ARB_TRIG_SRC_EXT]),
												from_reg_unsigned(5, 5)),
	'lut_length2':		(REG_ARB_LUT_LENGTH2,	to_reg_unsigned(0, 16), from_reg_unsigned(0, 16)),
	'dead_value2':		(REG_ARB_LUT_LENGTH2,	to_reg_signed(16, 16, xform=lambda obj, r: r * 2.0**15),
												from_reg_signed(16, 16, xform=lambda obj, r: r / (2.0**15))),
	'amplitude2':		(REG_ARB_AMPLITUDE2,	to_reg_signed(0, 18, xform=lambda obj, r: r / obj._dac_gains()[1]),
	                                            from_reg_signed(0, 18, xform=lambda obj, r: r * obj._dac_gains()[1])),
	'offset2':			(REG_ARB_OFFSET2,		to_reg_signed(0, 16, xform=lambda obj, r: r / obj._dac_gains()[1]),
	                                            from_reg_signed(0, 16, xform=lambda obj, r: r * obj._dac_gains()[1]))
}
