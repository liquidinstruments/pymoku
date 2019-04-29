
import math, time
import logging
from copy import deepcopy
from pymoku._oscilloscope import _CoreOscilloscope
from ._instrument import *
from . import _utils
from ._dec_filter import DecFilter


log = logging.getLogger(__name__)
REG_ENABLE				= 96
REG_MONSELECT			= 111
REG_INPUTOFFSET_CH0		= 112
REG_INPUTOFFSET_CH1		= 113
REG_OUTPUTOFFSET_CH0	= 114
REG_OUTPUTOFFSET_CH1	= 115
REG_CH0_CH0GAIN			= 116
REG_CH0_CH1GAIN			= 117
REG_CH1_CH0GAIN			= 118
REG_CH1_CH1GAIN			= 119
REG_INPUTSCALE_CH0		= 120
REG_INPUTSCALE_CH1		= 121
REG_OUTPUTSCALE_CH0		= 122
REG_OUTPUTSCALE_CH1		= 123
REG_SAMPLINGFREQ		= 124

REG_FILT_RESET 		= 62

_IIR_MON_NONE		= 0
_IIR_MON_ADC1 		= 1
_IIR_MON_IN1		= 2
_IIR_MON_OUT1		= 3
_IIR_MON_ADC2 		= 4
_IIR_MON_IN2 		= 5
_IIR_MON_OUT2 		= 6

# Monitor probe locations (for A and B channels)
_IIR_MON_NONE = 0
_IIR_MON_ADC1 = 1
_IIR_MON_IN1  = 2
_IIR_MON_OUT1 = 3
_IIR_MON_ADC2 = 4
_IIR_MON_IN2  = 5
_IIR_MON_OUT2 = 6

# Oscilloscope data sources
_IIR_SOURCE_A		= 0
_IIR_SOURCE_B		= 1
_IIR_SOURCE_IN1		= 2
_IIR_SOURCE_IN2		= 3
_IIR_SOURCE_EXT		= 4

# Input mux selects for Oscilloscope
_IIR_OSC_SOURCES = {
	'a' : _IIR_SOURCE_A,
	'b' : _IIR_SOURCE_B,
	'in1' : _IIR_SOURCE_IN1,
	'in2' : _IIR_SOURCE_IN2,
	'ext' : _IIR_SOURCE_EXT
}

_IIR_COEFFWIDTH = 48

_IIR_INPUT_SMPS = ADC_SMP_RATE/4
_IIR_CHN_BUFLEN = 2**13

_ADC_DEFAULT_CALIBRATION = 3750.0 # Bits/V (No attenuation)

class IIRFilterBox(_CoreOscilloscope):
	r"""

	The IIR Filter Box implements infinite impulse response (IIR) filters using 4 cascaded Direct Form 1 second-order stages
	with a final output gain stage. The total transfer function can be written:

	.. math::
		H(z) = G * \prod_{k=1}^4 s_k * \frac{b_0k + b_1k * z^-1 + b_2k * z^-2}{1 + a_1k * z^-1 + a_2k * z^-2}

	To specify a filter, you must supply an array containing the filter coefficients. The array should contain five rows and six columns.
	The first row has one column entry, corresponding to the overall gain factor G. The following four rows have six entries each, corresponding
	to the s, b0, b1, b2, a1 and a2 coefficients of the four cascaded SOS filters.

	Example array dimensions:

	+----------+------+------+------+------+-------+
	| G        |      |      |      |      |       |
	+==========+======+======+======+======+=======+
	| s1       | b0.1 | b1.1 | b2.1 | a1.1 |  a2.1 |
	+----------+------+------+------+------+-------+
	| s2       | b0.2 | b1.2 | b2.2 | a1.2 |  a2.2 |
	+----------+------+------+------+------+-------+
	| s3       | b0.3 | b1.3 | b2.3 | a1.3 |  a2.3 |
	+----------+------+------+------+------+-------+
	| s4       | b0.4 | b1.4 | b2.4 | a1.4 |  a2.4 |
	+----------+------+------+------+------+-------+

	Each 'a' coefficient must be a float in the range [-4.0, +4.0). 's' coefficients are multiplied into each 'b' coefficient before being sent to the device. These products (sN x b0.N, sN x b1.N, sN x b2.N) 
	must also fall in the range [-4.0, +4.0). Internally, the 'a' and 'b' coefficients are represented as signed 48-bit fixed-point numbers, with 45 fractional bits. The gain coefficient G must 
	be a float in the range [-8e6, 8e6 - 2^-24]. It is represented internally as a signed 48-bit fixed-point with 24 fractional bits. 
	
	Filter coefficients can be computed using signal processing toolboxes in e.g. MATLAB or SciPy.

	.. note::
		The overall output gain of the instrument is the product of the gain of the filter, set in the coefficient matrix, and the output stage
		gain set using :any:`set_gains_offsets`.

	.. warning::
		Some coefficients may result in overflow or underflow, which degrade filter performance. Filter responses should be checked prior to use.

	"""
	def __init__(self):
		"""Create a new IIR FilterBox instrument, ready to be attached to a Moku."""
		super(IIRFilterBox, self).__init__()
		self._register_accessors(_iir_reg_handlers)

		self.id = 6
		self.type = "iirfilterbox"

		# Monitor samplerate
		self._input_samplerate = _IIR_INPUT_SMPS
		self._chn_buffer_len = _IIR_CHN_BUFLEN

		# Remembers monitor source choice
		self.monitor_a = 'none'
		self.monitor_b = 'none'

		self._decfilter1 = DecFilter(self, 103)
		self._decfilter2 = DecFilter(self, 107)

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

		# TODO: Read these back on_reg_sync
		self.filter_ch1 = [[0,0,0,0,0,0]]*4
		self.filter_ch2 = [[0,0,0,0,0,0]]*4

	@needs_commit
	def set_defaults(self):
		""" Reset the IIR to sane defaults. """
		super(IIRFilterBox, self).set_defaults()

		# We only allow looking at the monitor signals in the embedded scope
		self._set_source(1, _IIR_SOURCE_A)
		self._set_source(2, _IIR_SOURCE_B)

		# Default values
		self.input_en1 = True
		self.output_en1 = False
		self.input_en2 = True
		self.output_en2 = False

		self.set_control_matrix(1, 1.0, 0.0)
		self.set_control_matrix(2, 0.0, 1.0)

		self.filter_reset = 0

		# initialize filter coefficient arrays as all pass filters
		b = [1.0,1.0,0.0,0.0,0.0,0.0]
		self.filter_ch1 = [b,b,b,b]
		self.filter_ch2 = [b,b,b,b]

		# do we want to set here?
		self.set_frontend(1,fiftyr=True, atten=False, ac=False)
		self.set_frontend(2,fiftyr=True, atten=False, ac=False)

		# Default unity gain, zero offset, identity mixing matrix.
		self.set_gains_offsets(1)
		self.set_gains_offsets(2)

		# Set default settings to plotting script values that have been tested thoroughly
		self.set_monitor('a', 'in1')
		self.set_monitor('b', 'in2')
		self.set_trigger('a', 'rising', 0)
		self._decfilter1.set_samplerate(8)
		self._decfilter2.set_samplerate(8)
		self.set_timebase(-1e-3, 1e-3)

	@needs_commit
	def set_control_matrix(self, ch, scale_in1, scale_in2):
		"""
		Configure the input control matrix specifying the input signal mixing for the specified filter channel.

		Input mixing allows a filter channel to act on a linear combination of the two input signals.

		:type ch: int, {1, 2}
		:param ch: target filter channel

		:type scale_in1: float, [-20, 20]
		:param scale_in1: linear scale factor of input 1 signal added to target filter channel input.
			To avoid quantization, use at most one decimal place.

		:type scale_in2: float, [-20, 20] 
		:param scale_in2: linear scale factor of input 2 signal added to target filter channel input.
			To avoid quantization, use at most one decimal place.
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'filter channel')
		_utils.check_parameter_valid('range', scale_in1, [-20, 20], 'control matrix scale (ch1)', 'linear scalar')
		_utils.check_parameter_valid('range', scale_in2, [-20, 20], 'control matrix scale (ch2)', 'linear scalar')
		if (scale_in1/0.1)%1 or (scale_in2/0.1)%1:
			log.warning("Control matrix scalars should contain one decimal place to avoid quantization effects.")

		if ch == 1:
			self._matrixscale_ch1_ch1 = scale_in1
			self._matrixscale_ch1_ch2 = scale_in2
		else:
			self._matrixscale_ch2_ch1 = scale_in1
			self._matrixscale_ch2_ch2 = scale_in2

	def _update_control_matrix_regs(self):
			# Used to update regs at commit time with correct frontend settings.
			self.matrixscale_ch1_ch1 = self._matrixscale_ch1_ch1
			self.matrixscale_ch1_ch2 = self._matrixscale_ch1_ch2
			self.matrixscale_ch2_ch1 = self._matrixscale_ch2_ch1
			self.matrixscale_ch2_ch2 = self._matrixscale_ch2_ch2

	def _sync_control_matrix_regs(self):
			# Used to sync local variabels when connecting to an existing moku.
			self._matrixscale_ch1_ch1 = self.matrixscale_ch1_ch1
			self._matrixscale_ch1_ch2 = self.matrixscale_ch1_ch2
			self._matrixscale_ch2_ch1 = self.matrixscale_ch2_ch1
			self._matrixscale_ch2_ch2 = self.matrixscale_ch2_ch2

	# NOTE: This function avoids @needs_commit because it calls _set_mmap_access which requires an immediate commit
	def set_filter(self, ch, sample_rate, filter_coefficients):
		"""
		Set SOS filter sample rate and filter coefficients. This also enables the input and outputs of the specified Moku:Lab channel.

		:type ch: int; {1,2}
		:param ch: target channel

		:type sample_rate: string; {'high','low'}
		:param sample_rate: filter sample rate where 'high' ~ 15.625 MHz and 'low' ~ 122.070 kHz.

		:type filter_coefficients: array;
		:param filter_coefficients: array containing SOS filter coefficients. Format is described in class documentation above.
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'filter channel')
		_utils.check_parameter_valid('set', sample_rate, ['high', 'low'], 'filter sample rate')

		# Set the filter input samplerate
		factor = (8 if sample_rate == 'high' else 1024)
		if ch == 1:
			self._decfilter1.set_samplerate(factor)
		else:
			self._decfilter2.set_samplerate(factor)

		# Conversion of input array (typically generated by Scipy/Matlab) to HDL memory map format
		if filter_coefficients != None:

			# Deep copy to avoid modifying user's original input array 
			intermediate_filter = deepcopy(filter_coefficients)

			# Array dimension check
			if len(filter_coefficients) != 5:
				_utils.check_parameter_valid('set', len(filter_coefficients), [5],'number of coefficient array rows')
			for m in range(4):
				if m == 0:
					if len(filter_coefficients[0]) != 1:
						_utils.check_parameter_valid('set', len(filter_coefficients[0]), [1],'number of columns in coefficient array row 0')
				else:
					if len(filter_coefficients[m]) != 6:
						_utils.check_parameter_valid('set', len(filter_coefficients[m]), [6],("number of columns in coefficient array row %s"%(m)))

			# Array values check
			_utils.check_parameter_valid('range', filter_coefficients[0][0], [-8e6,8e6 - 2**(-24)],("coefficient array entry m = %s, n = %s"%(0,0)))
			for m in range(1, 5):
				for n in range(6):
					_utils.check_parameter_valid('range', filter_coefficients[m][n], [-4.0,4.0 - 2**(-45)],("coefficient array entry m = %s, n = %s"%(0,0)))


			# multiply S coefficients into B coefficients and replace all S coefficients with 1.0
			for n in range(1,5):
				intermediate_filter[n][1] *= intermediate_filter[n][0]
				intermediate_filter[n][2] *= intermediate_filter[n][0]
				intermediate_filter[n][3] *= intermediate_filter[n][0]
				intermediate_filter[n][0] = 1.0

			# place gain factor G into S coefficient position 4 to comply with HDL requirements:
			intermediate_filter[4][0] = intermediate_filter[0][0]
			intermediate_filter = intermediate_filter[1:5]

			if ch == 1:
				self.filter_ch1 = intermediate_filter
			else:
				self.filter_ch2 = intermediate_filter

		# combine both filter arrays:
		filter_coeffs = [[0.0]*6]*4
		coeff_list = [ [ [0 for k in range(2)] for x in range(6)] for y in range(8) ]
		for n in range(4):
		 	filter_coeffs[n] = self.filter_ch1[n] + self.filter_ch2[n]

		for k in range(2):
			for x in range(4):
					for y in range(6):
						if y == 0:
							coeff_list[x][y][k] = int(round( 2**(_IIR_COEFFWIDTH - 24) * filter_coeffs[x][y + k*6]))
						else:
							coeff_list[x][y][k] = int(round( 2**(_IIR_COEFFWIDTH - 3) * filter_coeffs[x][y + k*6]))
		coeff_bytes = bytearray()
		for k in range(2):
			for y in range(6):
				for x in range(4):
					coeff_bytes += bytearray(struct.pack('<q', coeff_list[x][y][k]))

		self._set_mmap_access(True)
		self._moku._send_file_bytes('j', '', coeff_bytes)
		self._set_mmap_access(False)

		# Release the memory map "file" to other resources
		self._moku._fs_finalise('j', '', len(coeff_bytes))

		# Enable the output and input of the set channel
		if ch==1:
			self.output_en1 = True
			self.input_en1 = True
		else:
			self.output_en2 = True
			self.input_en2 = True

		# Manually commit the above register settings as @needs_commit is not used in this function
		self.commit()

	@needs_commit
	def disable_output(self, ch):
		"""
		Disables the output of the specified IIR filter channel.

		:type ch: int; {1,2}
		:param ch: target channel
		"""
		if ch == 1:
			self.output_en1 = False
		else:
			self.output_en2 = False

	@needs_commit
	def set_gains_offsets(self, ch, input_gain=1.0, output_gain=1.0, input_offset=0, output_offset=0):
		"""
		Configure pre- and post-filter scales and offsets for a given filter channel.

		.. note::
			The overall output gain of the instrument is the product of the gain of the filter, set by the filter coefficients,
			and the input/output stage gain set here.

		:type ch: int, {1,2}
		:param ch: target filter channel

		:type input_gain, output_gain: float, [-100,100] scalar
		:param input_gain, output_gain: channel scalars before and after the FIR filter

		:type input_offset: float, [-1.0,1.0] Volts
		:param input_offset: channel offset before the FIR filter

		:type output_offset: float, [-2.0,2.0] Volts
		:param output_offset: channel offset after the FIR filter
		"""
		_utils.check_parameter_valid('set', ch, [1,2],'filter channel')
		_utils.check_parameter_valid('range', input_gain, [-100,100],'input scale','linear scalar')
		_utils.check_parameter_valid('range', output_gain, [-100,100],'output scale','linear scalar')
		_utils.check_parameter_valid('range', input_offset, [-1.0,1.0],'input offset','Volts')
		_utils.check_parameter_valid('range', output_offset, [-2.0,2.0],'output offset','Volts')

		# Calculate input/output offset values
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

	def _update_gains_offsets_regs(self):
		# Used to update regs at commit time with correct frontend settings.
		self.input_scale1   = self._input_scale1
		self.output_scale1  = self._output_scale1
		self.input_offset1  = self._input_offset1
		self.output_offset1 = self._output_offset1
		self.input_scale2   = self._input_scale2
		self.output_scale2  = self._output_scale2
		self.input_offset2  = self._input_offset2
		self.output_offset2 = self._output_offset2

	def _sync_gains_offsets_regs(self):
		# Used to update regs at commit time with correct frontend settings.
		self._input_scale1   = self.input_scale1
		self._output_scale1  = self.output_scale1
		self._input_offset1  = self.input_offset1
		self._output_offset1 = self.output_offset1
		self._input_scale2   = self.input_scale2
		self._output_scale2  = self.output_scale2
		self._input_offset2  = self.input_offset2
		self._output_offset2 = self.output_offset2

	@needs_commit
	def set_monitor(self, monitor_ch, source):
		"""
		Configures the specified monitor channel to view the desired IIR Filter Box signal.

		There are two 12-bit monitoring channels available, 'a' and 'b'; each of these can 
		be assigned to source signals from any of the internal filterbox monitoring points. 
		Signals larger than 12-bits must be either truncated or clipped to the allowed size.

		The source is one of:
			- **adc1**	: Channel 1 ADC input
			- **in1**	: Filter Channel 1 input (after mixing, offset and scaling)
			- **out1**	: Filter Channel 1 output
			- **adc2**	: Channel 2 ADC Input
			- **in2**	: Filter Channel 2 input (after mixing, offset and scaling)
			- **out2**	: Filter Channel 2 output

		:type monitor_ch: str; {'a','b'}
		:param monitor_ch: Monitor channel

		:type source: str; {'adc1', 'in1', 'out1', 'adc2', 'in2', 'out2'}
		:param source: Signal to connect to the monitor channel
		"""
		_utils.check_parameter_valid('string', monitor_ch, desc="monitor channel")
		_utils.check_parameter_valid('string', source, desc="monitor signal")

		monitor_sources = {
			'none': _IIR_MON_NONE,
			'adc1': _IIR_MON_ADC1,
			'in1':	_IIR_MON_IN1,
			'out1': _IIR_MON_OUT1,
			'adc2': _IIR_MON_ADC2,
			'in2':	_IIR_MON_IN2,
			'out2':	_IIR_MON_OUT2
		}
		monitor_ch = monitor_ch.lower()
		source = source.lower()

		_utils.check_parameter_valid('set', monitor_ch, allowed=['a','b'], desc="monitor channel")
		_utils.check_parameter_valid('set', source, allowed=['none', 'adc1', 'in1', 'out1', 'adc2', 'in2', 'out2'], desc="monitor source")

		if monitor_ch == 'a':
			self.monitor_a = source
			self.mon1_source = monitor_sources[source]
		elif monitor_ch == 'b':
			self.monitor_b = source
			self.mon2_source = monitor_sources[source]
		else:
			raise ValueOutOfRangeException("Invalid channel %d", monitor_ch)

	@needs_commit
	def set_trigger(self, source, edge, level, minwidth=None, maxwidth=None, hysteresis=10e-3, hf_reject=False, mode='auto'):
		""" 
		Set the trigger source for the monitor channel signals. This can be either of the input or
		monitor signals, or the external input.

		:type source: string, {'in1','in2','A','B','ext'}
		:param source: Trigger Source. May be either an input or monitor channel (as set by 
				:py:meth:`~pymoku.instruments.IIRFilterBox.set_monitor`), or external. External refers 
				to the back-panel connector of the same	name, allowing triggering from an 
				externally-generated digital [LV]TTL or CMOS signal.

		:type edge: string, {'rising','falling','both'}
		:param edge: Which edge to trigger on. In Pulse Width modes this specifies whether the pulse is positive (rising)
				or negative (falling), with the 'both' option being invalid.

		:type level: float, [-10.0, 10.0] volts
		:param level: Trigger level

		:type minwidth: float, seconds
		:param minwidth: Minimum Pulse Width. 0 <= minwidth < (2^32/samplerate). Can't be used with maxwidth.

		:type maxwidth: float, seconds
		:param maxwidth: Maximum Pulse Width. 0 <= maxwidth < (2^32/samplerate). Can't be used with minwidth.

		:type hysteresis: float, [100e-6, 1.0] volts
		:param hysteresis: Hysteresis around trigger point.

		:type hf_reject: bool
		:param hf_reject: Enable high-frequency noise rejection

		:type mode: string, {'auto', 'normal'}
		:param mode: Trigger mode.
		"""
		# Define the trigger sources appropriate to the LockInAmp instrument
		source = _utils.str_to_val(_IIR_OSC_SOURCES, source, 'trigger source')

		# This function is the portion of set_trigger shared among instruments with embedded scopes. 
		self._set_trigger(source, edge, level, minwidth, maxwidth, hysteresis, hf_reject, mode)

	def _signal_source_volts_per_bit(self, source, scales, trigger=False):
		"""
			Converts volts to bits depending on the signal source
		"""
		# Decimation gain is applied only when using precision mode data
		if (not trigger and self.is_precision_mode()) or (trigger and self.trig_precision):
			deci_gain = self._deci_gain()
		else:
			deci_gain = 1.0

		if (source == _IIR_SOURCE_A):
			level = self._monitor_source_volts_per_bit(self.monitor_a, scales)/deci_gain
		elif (source == _IIR_SOURCE_B):
			level = self._monitor_source_volts_per_bit(self.monitor_b, scales)/deci_gain
		elif (source == _IIR_SOURCE_IN1):
			level = scales['gain_adc1']*(10.0 if scales['atten_ch1'] else 1.0)/deci_gain
		elif (source == _IIR_SOURCE_IN2):
			level = scales['gain_adc2']*(10.0 if scales['atten_ch2'] else 1.0)/deci_gain
		else:
			level = 1.0
		return level

	def _monitor_source_volts_per_bit(self, source, scales):
		# Calculates the volts to bits conversion for the given monitor port signal

		monitor_source_gains = {
			'none': 1.0,
			'adc1': scales['gain_adc1']/(10.0 if scales['atten_ch1'] else 1.0),
			'in1':	1.0/_ADC_DEFAULT_CALIBRATION/(10.0 if scales['atten_ch1'] else 1.0),
			'out1': scales['gain_dac1']*(2.0**4),
			'adc2': scales['gain_adc2']/(10.0 if scales['atten_ch2'] else 1.0),
			'in2':	1.0/_ADC_DEFAULT_CALIBRATION/(10.0 if scales['atten_ch2'] else 1.0),
			'out2':	scales['gain_dac2']*(2.0**4)
		}
		return monitor_source_gains[source]

	def _update_dependent_regs(self, scales):
		super(IIRFilterBox, self)._update_dependent_regs(scales)
		self._update_control_matrix_regs()
		self._update_gains_offsets_regs()

	def _on_reg_sync(self):
		super(IIRFilterBox, self)._on_reg_sync()
		# Update local variables with device variables
		self._sync_control_matrix_regs()
		self._sync_gains_offsets_regs()

		# TODO: Sync previous IIR filter coefficients to local coefficient variables
		# self.filter_ch1 = ...
		# self.filter_ch2 = ...

_iir_reg_handlers = {
	'mon1_source':	(REG_MONSELECT,		to_reg_unsigned(0,3), from_reg_unsigned(0,3)),
	'mon2_source':	(REG_MONSELECT,		to_reg_unsigned(3,3), from_reg_unsigned(3,3)),

	'input_en1':		(REG_ENABLE,			to_reg_unsigned(0,1), from_reg_unsigned(0,1)),
	'input_en2':		(REG_ENABLE,			to_reg_unsigned(1,1), from_reg_unsigned(1,1)),
	'output_en1':		(REG_ENABLE,			to_reg_unsigned(2,1), from_reg_unsigned(2,1)),
	'output_en2':		(REG_ENABLE,			to_reg_unsigned(3,1), from_reg_unsigned(3,1)),

	'matrixscale_ch1_ch1':	(REG_CH0_CH0GAIN,	to_reg_signed(0, 16, 
															xform=lambda obj, x: int(round(x * (_ADC_DEFAULT_CALIBRATION / (10.0 if obj.get_frontend(1)[1] else 1.0)) * obj._adc_gains()[0] * 2.0**10))), 
														from_reg_signed(0, 16,
															xform=lambda obj, x: x * ((10.0 if obj.get_frontend(1)[1] else 1.0) / _ADC_DEFAULT_CALIBRATION) / obj._adc_gains()[0] / 2.0**10)),
	'matrixscale_ch1_ch2':	(REG_CH0_CH1GAIN,	to_reg_signed(0, 16, 
															xform=lambda obj, x: int(round(x * (_ADC_DEFAULT_CALIBRATION / (10.0 if obj.get_frontend(2)[1] else 1.0)) * obj._adc_gains()[1] * 2.0**10))), 
														from_reg_signed(0, 16,
															xform=lambda obj, x: x * ((10.0 if obj.get_frontend(2)[1] else 1.0) / _ADC_DEFAULT_CALIBRATION) / obj._adc_gains()[1] / 2.0**10)),
	'matrixscale_ch2_ch1':	(REG_CH1_CH0GAIN,	to_reg_signed(0, 16, 
															xform=lambda obj, x: int(round(x * (_ADC_DEFAULT_CALIBRATION / (10.0 if obj.get_frontend(1)[1] else 1.0)) * obj._adc_gains()[0] * 2.0**10))), 
														from_reg_signed(0, 16,
															xform=lambda obj, x: x * ((10.0 if obj.get_frontend(1)[1] else 1.0) / _ADC_DEFAULT_CALIBRATION) / obj._adc_gains()[0] / 2.0**10)),
	'matrixscale_ch2_ch2':	(REG_CH1_CH1GAIN,	to_reg_signed(0, 16, 
															xform=lambda obj, x: int(round(x * (_ADC_DEFAULT_CALIBRATION / (10.0 if obj.get_frontend(2)[1] else 1.0)) * obj._adc_gains()[1] * 2.0**10))), 
														from_reg_signed(0, 16,
															xform=lambda obj, x: x * ((10.0 if obj.get_frontend(2)[1] else 1.0) / _ADC_DEFAULT_CALIBRATION) / obj._adc_gains()[1] / 2.0**10)),
	
	'ch1_sampling_freq':	(REG_SAMPLINGFREQ,		to_reg_unsigned(0, 1), from_reg_unsigned(0, 1)),
	'ch2_sampling_freq':	(REG_SAMPLINGFREQ,		to_reg_unsigned(1, 1), from_reg_unsigned(1, 1)),

	'filter_reset':		(REG_FILT_RESET, 		to_reg_bool(0), from_reg_bool(0)),

	'input_scale1':			(REG_INPUTSCALE_CH0, to_reg_signed(0, 18, xform=lambda obj, x: x * 2.0**9), 
														from_reg_signed(0, 18, xform=lambda obj, x : x / (2.0 **9))),
	'input_scale2':			(REG_INPUTSCALE_CH1, to_reg_signed(0, 18, xform=lambda obj, x: x * 2.0**9), 
														from_reg_signed(0, 18, xform=lambda obj, x : x / (2.0 **9))),

	'output_scale1':		(REG_OUTPUTSCALE_CH0,		to_reg_signed(0, 18, xform=lambda obj, x: int(round(x * 2.0**9 / (_ADC_DEFAULT_CALIBRATION * 2**3 * obj._dac_gains()[0])))), 
														from_reg_signed(0, 18, xform=lambda obj, x: x * (_ADC_DEFAULT_CALIBRATION * 2**3 * obj._dac_gains()[0]) / 2.0**9)),

	'output_scale2':		(REG_OUTPUTSCALE_CH1,		to_reg_signed(0, 18, xform=lambda obj, x: int(round(x * 2.0**9 / (_ADC_DEFAULT_CALIBRATION * 2**3 * obj._dac_gains()[1])))), 
														from_reg_signed(0, 18, xform=lambda obj, x: x * (_ADC_DEFAULT_CALIBRATION * 2**3 * obj._dac_gains()[1]) / 2.0**9)),

	'input_offset1':	(REG_INPUTOFFSET_CH0,	to_reg_signed(0, 14, 
													xform=lambda obj, x: int(round(2.0 * x * _ADC_DEFAULT_CALIBRATION / (10.0 if obj.get_frontend(1)[1] else 1.0)))), 
												from_reg_signed(0, 14,
													xform=lambda obj, x: x * ((10.0 if obj.get_frontend(1)[1] else 1.0) / 2.0 / _ADC_DEFAULT_CALIBRATION))),
	'input_offset2':	(REG_INPUTOFFSET_CH1,	to_reg_signed(0, 14, 
													xform=lambda obj, x: int(round(2.0 * x * _ADC_DEFAULT_CALIBRATION / (10.0 if obj.get_frontend(2)[1] else 1.0)))), 
												from_reg_signed(0, 14,
													xform=lambda obj, x: x * ((10.0 if obj.get_frontend(2)[1] else 1.0) / 2.0 / _ADC_DEFAULT_CALIBRATION))),
	'output_offset1':	(REG_OUTPUTOFFSET_CH0,	to_reg_signed(0, 17,
													xform=lambda obj, x: int(round(x / obj._dac_gains()[0]))), 
												from_reg_signed(0, 17,
													xform=lambda obj, x: x * obj._dac_gains()[0])),
	'output_offset2':	(REG_OUTPUTOFFSET_CH1,	to_reg_signed(0, 17,
													xform=lambda obj, x: int(round(x / obj._dac_gains()[1]))), 
												from_reg_signed(0, 17,
													xform=lambda obj, x: x * obj._dac_gains()[1]))
	}