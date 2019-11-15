import math, string
import logging

from pymoku._instrument import *
from pymoku._oscilloscope import _CoreOscilloscope, VoltsData
from pymoku._pid_controller import PIDController
from . import _instrument
from . import _utils
from pymoku._pid import PID

log = logging.getLogger(__name__)

REG_LIA_PM_BW1 			= 90
REG_LIA_PM_AUTOA1 		= 91
REG_LIA_PM_REACQ		= 92
REG_LIA_PM_RESET		= 93
REG_LIA_PM_OUTDEC 		= 94
REG_LIA_PM_OUTSHIFT 	= 94
REG_LIA_SIG_SELECT		= 95

REG_LIA_ENABLES			= 96

REG_LIA_PIDGAIN1		= 97
REG_LIA_PIDGAIN2		= 98

REG_LIA_INT_IGAIN1		= 99
REG_LIA_INT_IGAIN2		= 100
REG_LIA_INT_IFBGAIN1	= 101
REG_LIA_INT_IFBGAIN2	= 102
REG_LIA_INT_PGAIN1		= 103
REG_LIA_INT_PGAIN2		= 104

REG_LIA_GAIN_STAGE		= 105
REG_LIA_DIFF_DGAIN2		= 106
REG_LIA_DIFF_PGAIN1		= 107
REG_LIA_DIFF_PGAIN2		= 108
REG_LIA_DIFF_IGAIN1		= 109
REG_LIA_DIFF_IGAIN2		= 110
REG_LIA_DIFF_IFBGAIN1	= 111
REG_LIA_DIFF_IFBGAIN2	= 112

REG_LIA_IN_OFFSET1		= 113
REG_LIA_OUT_OFFSET1		= 114

REG_LIA_INPUT_GAIN		= 117

REG_LIA_FREQDEMOD_L		= 118
REG_LIA_FREQDEMOD_H		= 119
REG_LIA_PHASEDEMOD_L	= 120
REG_LIA_PHASEDEMOD_H	= 121

REG_LIA_LO_FREQ_L		= 122
REG_LIA_LO_FREQ_H		= 123
REG_LIA_LO_PHASE_L		= 124
REG_LIA_LO_PHASE_H		= 125

REG_LIA_SINEOUTAMP		= 126
REG_LIA_SINEOUTOFF		= 126

REG_LIA_MONSELECT		= 127

_LIA_INPUT_SMPS = ADC_SMP_RATE
_LIA_CHN_BUFLEN	= CHN_BUFLEN

# Monitor probe locations (for A and B channels)
_LIA_MON_NONE	= 0
_LIA_MON_IN1	= 1
_LIA_MON_I		= 2
_LIA_MON_Q		= 3
_LIA_MON_OUT	= 4
_LIA_MON_AUX	= 5
_LIA_MON_IN2	= 6
_LIA_MON_DEMOD	= 7

# Oscilloscope data sources
_LIA_SOURCE_A		= 0
_LIA_SOURCE_B		= 1
_LIA_SOURCE_IN1		= 2
_LIA_SOURCE_IN2		= 3
_LIA_SOURCE_EXT		= 4

# Input mux selects for Oscilloscope
_LIA_OSC_SOURCES = {
	'a' : _LIA_SOURCE_A,
	'b' : _LIA_SOURCE_B,
	'in1' : _LIA_SOURCE_IN1,
	'in2' : _LIA_SOURCE_IN2,
	'ext' : _LIA_SOURCE_EXT
}

_LIA_CONTROL_FS = 31.25e6
_LIA_FREQSCALE = 1.0e9 / 2**48
_LIA_PHASESCALE = 1.0 / 2**48
_LIA_P_GAINSCALE = 2.0**16
_LIA_ID_GAINSCALE = 2.0**24 - 1

_PID_REG_BASE = 97

_LIA_SIGNALS = ['x', 'y', 'r', 'theta']
# The output signals allowed while non-PLL external demodulation is set
_NON_PLL_ALLOWED_SIGS = ['x','sine','offset','none']

class LockInAmp(PIDController, _CoreOscilloscope):
	def __init__(self):
		super(LockInAmp, self).__init__()
		self._register_accessors(_lia_reg_hdl)

		self.id = 8
		self.type = "lockinamp"

		# Monitor samplerate
		self._input_samplerate = _LIA_INPUT_SMPS
		self._chn_buffer_len 	= _LIA_CHN_BUFLEN

		# Remember some user settings for when swapping channels
		# Need to initialise these to valid values so set_defaults can be run.
		self.monitor_a = 'none'
		self.monitor_b = 'none'
		self.demod_mode = 'internal'
		self.main_source = 'none'
		self.aux_source = 'none'
		self._pid_channel = 'main'
		self.r_theta_mode = False
		# self._pid_gains = {'g': 1.0, 'kp': 1.0, 'ki': 0, 'kd': 0, 'si': None,
		#                    'sd': None, 'in_offset': 0, 'out_offset': 0}

		self.pid = PID(self, reg_base=_PID_REG_BASE, fs=_LIA_CONTROL_FS)
		self._lo_amp = 1.0
		self.gainstage_gain = 1.0
		self._demod_amp = 0.5
		self.r_theta_input_range = 0
		self.gain_user = {'main': 1.0, 'aux': 1.0}
		self.ch_scaling = {'main': 1.0, 'aux': 1.0}

	@needs_commit
	def set_defaults(self):
		""" Reset the lockinamp to sane defaults. """

		# Avoid calling the PID controller set_defaults
		_CoreOscilloscope.set_defaults(self)

		# We only allow looking at the monitor signals in the embedded scope
		self._set_source(1, _LIA_SOURCE_A)
		self._set_source(2, _LIA_SOURCE_B)

		self.set_filter(1e3, 1)
		self.set_gain('aux', 1.0)
		self.set_pid_by_gain('main', 1.0)
		self.set_lo_output(0.5, 1e6, 0)
		self.set_demodulation('internal', 0)
		self.set_outputs('x', 'sine')

		self.set_monitor('a', 'in1')
		self.set_monitor('b', 'main')
		self.set_trigger('b', 'rising', 0)
		self.set_timebase(-1e-6, 1e-6)
		self.set_input_range_r_theta(0)

	@needs_commit
	def set_outputs(self, main, aux, main_offset=0.0, aux_offset=0.0):
		"""
		Configures the main (Channel 1) and auxiliary (Channel 2) output
		signals of the Lock-In.

		.. note::
		  When 'external' demodulation is used (that is, without a PLL),
		  the Lock-in Amplifier doesn't know the frequency and therefore
		  can't form the quadrature for full I/Q demodulation. This in
		  turn means it can't distinguish I from Q, X from Y, or form R/Theta.
		  This limits the choices for signals that can be output on the AUX
		  channel to ones not from the Lock-in logic (e.g. demodulation
		  source, auxiliary sine wave etc).

		  An exception will be raised if you attempt to set the auxiliary
		  channel to view aa signal from the Lock-in logic while
		  external demodulation is enabled.

		:type main: string; {'x', 'y', 'r', 'theta', 'offset', 'none'}
		:param main: Main output signal

		:type aux: string; {'x', 'y', 'r', theta', 'sine', 'demod',
							'offset', 'none'}
		:param aux: auxiliary output signal

		:type main_offset: float; [-1.0, 1.0] V
		:param main_offset: Main output offset

		:type aux_offset: float; [-1.0, 1.0] V
		:param aux_offset: auxiliary output offset
		"""
		_utils.check_parameter_valid(
			'string', main, desc="main output signal")
		_utils.check_parameter_valid(
			'string', aux, desc="auxiliary output signal")

		# Allow uppercase options
		main = main.lower()
		aux = aux.lower()

		_utils.check_parameter_valid('set', main,
									 allowed=['x',
											  'y',
											  'r',
											  'theta',
											  'offset',
											  'none'],
									 desc="main output signal")
		_utils.check_parameter_valid('set', aux,
									 allowed=['x',
											  'y',
											  'r',
											  'theta',
											  'sine',
											  'demod',
											  'offset',
											  'none'],
									 desc="auxiliary output signal")

		if self.demod_mode == 'external' and (
				aux not in _NON_PLL_ALLOWED_SIGS and main not in
				_NON_PLL_ALLOWED_SIGS):
			raise InvalidConfigurationException(
				"Can't use quadrature-related outputs when using external "
				"demodulation without a PLL. Allowed outputs are " + str(
					_NON_PLL_ALLOWED_SIGS))

		if main in ['r', 'theta'] and aux in ['x', 'y']:
			raise InvalidConfigurationException(
				"Can't use r/theta outputs in conjunction with x/y outputs. "
				"Please select  r/theta or x/y  for both outputs.")

		if main in ['x', 'y'] and aux in ['r', 'theta']:
			raise InvalidConfigurationException(
				"Can't use x/y outputs in conjunction with r/theta outputs."
				"Please select r/theta or x/y for both outputs.")

		self.ch_scaling['main'] = 1.0 / 1.4 if main == 'theta' else 1.0
		self.ch_scaling['aux'] = 1.0 / 1.4 if aux == 'theta' else 1.0

		# Update locking mode
		self._set_r_theta_mode(main in ['r', 'theta'] or aux in ['r', 'theta'])

		# Main output enables
		self.main_offset = main_offset
		self.main_source = main
		self.ch1_signal_en = main in _LIA_SIGNALS
		self.ch1_out_en = main != 'none'

		# auxiliary output enables
		self.aux_offset = aux_offset
		self.aux_source = aux
		self.ch2_signal_en = aux in (_LIA_SIGNALS) or aux in ['sine', 'demod']
		self.ch2_out_en = aux != 'none'
		# Defaults to local oscillator i.e. 'sine'
		self.aux_select = 1 if aux in _LIA_SIGNALS else (
			2 if aux == 'demod' else 0)

		# PID/Gain stage selects are updated on commit

	def _update_pid_gain_selects(self):
		# Update the PID/Gain signal inputs / channel select outputs to
		# match the set main/aux source signals

		def _signal_select(sig):
			return 0 if (sig not in _LIA_SIGNALS) else [i for i, x in
														enumerate(_LIA_SIGNALS)
														if x == sig][0]

		if self._pid_channel=='main':
			self.pid_sig_select = _signal_select(self.main_source)
			self.pid_ch_select = 0
			self.gain_sig_select = _signal_select(self.aux_source)
		else:
			self.pid_sig_select = _signal_select(self.aux_source)
			self.pid_ch_select = 1
			self.gain_sig_select = _signal_select(self.main_source)

	@needs_commit
	def set_pid_by_frequency(self, lia_ch, kp=1, i_xover=None, d_xover=None, si=None, sd=None, in_offset=0, out_offset=0):
		"""
		Set which lock-in channel the PID is on and configure it using frequency domain parameters.

		This sets the gain stage to be on the opposite channel.

		:type lia_ch: string; {'main','aux'}
		:param lia_ch: Lock-in channel name to put PID on.

		:type kp: float; [-1e3,1e3]
		:param kp: Proportional gain factor

		:type i_xover: float; [1e-3,1e6] Hz
		:param i_xover: Integrator crossover frequency

		:type d_xover: float; [1,10e6] Hz
		:param d_xover: Differentiator crossover frequency

		:type si: float; float; [-1e3,1e3]
		:param si: Integrator gain saturation

		:type sd: float; [-1e3,1e3]
		:param sd: Differentiator gain saturation

		:type in_offset: float; [-1.0,1.0] V
		:param in_offset: Input signal offset

		:type out_offset: float; [-1.0, 1.0] V
		:param out_offset: Output signal offset

		:raises InvalidConfigurationException: if the configuration of PID
				gains is not possible.
		"""

		# Locally store these settings, and update the instrument registers on
		# commit
		# This ensures all dependent register values are updated at the same
		# time, and the correct
		# DAC scaling is used.

		# gain filter
		f = {'main': 0.0, 'aux': 0.0}
		# gain output
		o = {'main': 0.0, 'aux': 0.0}
		# gain filter select
		s = {'main': 0.0, 'aux': 0.0}

		_pid_ch = self._pid_channel
		if lia_ch != _pid_ch:
			self.gain_user[_pid_ch] = self.gain_user[lia_ch]
			f[_pid_ch], o[_pid_ch], s[_pid_ch] = self._distribute_gain(
				self.gain_user[_pid_ch])
			o[_pid_ch] = self._apply_dac_gain(_pid_ch, o[_pid_ch])
			self._set_filt_gain(_pid_ch, f[_pid_ch])
			self._set_filt_gain_select(s[_pid_ch], _pid_ch)
			self._set_output_scaling(_pid_ch, o[_pid_ch])

		self._pid_channel = lia_ch

		f[lia_ch], o[lia_ch], s[lia_ch] = self._distribute_gain(kp)
		gain_dsp = self._calculate_filt_dsp_gain()
		o[lia_ch] = self._apply_dac_gain(lia_ch, o[lia_ch])
		self._set_filt_gain(lia_ch, f[lia_ch])
		self._set_filt_gain_select(s[lia_ch], lia_ch)

		self.gain_user[lia_ch] = 1.0
		self.pid.set_reg_by_frequency(
			kp,
			i_xover,
			d_xover,
			si,
			sd,
			overall_scaling=o[lia_ch] * 2.0**16 / f[lia_ch] / gain_dsp)
		self.pid.input_offset = in_offset
		self.pid.output_offset = out_offset

		d1, d2 = self._dac_gains()
		a1, a2 = self._adc_gains()
		adc = a1 * 2**12	#a1 * a2 * 2**24 if self.ext_demod == 1 else a1 * 2**12
		self.pid.input_offset = (in_offset * adc / 2) / (d1 if lia_ch == 'main' else d2)
		self.pid.output_offset = out_offset / (d1 if lia_ch == 'main' else d2)

	@needs_commit
	def set_pid_by_gain(self, lia_ch, g, kp=1.0, ki=0, kd=0, si=None, sd=None, in_offset=0, out_offset=0):
		"""
		Set which lock-in channel the PID is on and configure it using gain parameters.

		This sets the gain stage to be on the opposite channel.

		:type lia_ch: string; {'main','aux'}
		:param lia_ch: Lock-in channel name to put PID on

		:type g: float; [0,2^16 - 1]
		:param g: Gain

		:type kp: float; [-1e3,1e3]
		:param kp: Proportional gain factor

		:type ki: float;
		:param ki: Integrator gain factor

		:type kd: float;
		:param kd: Differentiator gain factor

		:type si: float; float; [-1e3,1e3]
		:param si: Integrator gain saturation

		:type sd: float; [-1e3,1e3]
		:param sd: Differentiator gain saturation

		:type in_offset: float; [-1.0,1.0] V
		:param in_offset: Input signal offset

		:type out_offset: float; [-1.0, 1.0] V
		:param out_offset: Output signal offset

		:raises InvalidConfigurationException: if the configuration of PID
				gains is not possible.
		"""
		# Locally store these settings, and update the instrument registers
		# on commit
		# This ensures all dependent register values are updated at the same
		# time, and the correct
		# DAC scaling is used.

		# gain filter
		f = {'main': 0.0, 'aux': 0.0}
		# gain output
		o = {'main': 0.0, 'aux': 0.0}
		# gain select filter
		s = {'main': 0.0, 'aux': 0.0}

		# Greq = kp
		# Gfilt, Gout, filt_gain_select = self._distribute_gain(Greq)
		# Gdsp = self._calculate_filt_dsp_gain()
		# Gout = self._apply_dac_gain(lia_ch, Gout)
		# self._set_filt_gain(lia_ch, Gfilt)
		# self._set_filt_gain_select(filt_gain_select, lia_ch)
		_pid_ch = self._pid_channel
		if lia_ch != _pid_ch:
			self.gain_user[_pid_ch] = self.gain_user[lia_ch]
			f[_pid_ch], o[_pid_ch], s[_pid_ch] = self._distribute_gain(
				self.gain_user[_pid_ch])
			self._set_filt_gain(_pid_ch, f[_pid_ch])
			self._set_filt_gain_select(s[_pid_ch], _pid_ch)
			o[_pid_ch] = self._apply_dac_gain(_pid_ch, o[_pid_ch])
			self._set_output_scaling(_pid_ch, o[_pid_ch])

		self._pid_channel = lia_ch
		self.gain_user[lia_ch] = g

		f[lia_ch], o[lia_ch], s[lia_ch] = self._distribute_gain(g)
		self._set_filt_gain(lia_ch, f[lia_ch])
		self._set_filt_gain_select(s[lia_ch], lia_ch)
		o[lia_ch] = self._apply_dac_gain(lia_ch, o[lia_ch])

		self.pid.set_reg_by_gain(o[lia_ch] * 2.0**16, kp, ki, kd, si, sd)
		self.pid.input_offset = in_offset
		self.pid.output_offset = out_offset

	@needs_commit
	def set_gain(self, lia_ch, g):
		"""
		Sets the gain stage to be on the specified lock-in channel, and
		configures its gain.

		This sets the PID stage to be on the opposite channel.

		:type lia_ch: string; {'main','aux'}
		:param lia_ch: Channel name

		:type g: float; [0, 2^16 - 1]
		:param g: Gain
		"""
		_utils.check_parameter_valid(
			'set', lia_ch, allowed=['main', 'aux'], desc="lock-in channel")
		_utils.check_parameter_valid(
			'range', g, allowed=[0, 2**16 - 1], desc="gain")

		# gain filter
		f = {'main': 0.0, 'aux': 0.0}
		# gain output
		o = {'main': 0.0, 'aux': 0.0}
		# gain select filter
		s = {'main': 0.0, 'aux': 0.0}

		_pid_ch = self._pid_channel
		if lia_ch == _pid_ch:
			self.gain_user[_pid_ch] = self.gain_user[lia_ch]
			f[_pid_ch], o[_pid_ch], s[_pid_ch] = self._distribute_gain(
				self.gain_user[_pid_ch])
			self._set_filt_gain(_pid_ch, f[_pid_ch])
			self._set_filt_gain_select(s[_pid_ch], _pid_ch)
			o[_pid_ch] = self._apply_dac_gain(_pid_ch, o[_pid_ch])
			self._set_output_scaling(_pid_ch, o[_pid_ch])

		if lia_ch == 'main':
			self._pid_channel = 'aux'
		else:
			self._pid_channel = 'main'

		self.gain_user[lia_ch] = g
		f[lia_ch], o[lia_ch], s[lia_ch] = self._distribute_gain(g)
		self._set_filt_gain(lia_ch, f[lia_ch])
		self._set_filt_gain_select(s[lia_ch], lia_ch)
		o[lia_ch] = self._apply_dac_gain(lia_ch, o[lia_ch])

		# Store selected gain locally. Update on commit with correct DAC
		# scaling.
		self._set_output_scaling(lia_ch, o[lia_ch])

	@needs_commit
	def set_demodulation(self, mode, frequency=1e6, phase=0, output_amplitude=0.5):
		"""
		Configure the demodulation stage.

		The mode is one of:
			- **internal** : for an internally set local oscillator
			- **external** : to directly use an external signal for demodulation (Note: Q is not selectable in this mode)
			- **external_pll** : to use an external signal for demodulation after running it through an internal PLL.

		.. note::
		  When 'external' is used (that is, without a PLL), the Lock-in Amplifier doesn't know the frequency and therefore
		  can't form the quadrature for full I/Q demodulation. This in turn means it can't distinguish I from Q, X from Y,
		  or form R/Theta. This limits the choices for signals that can be output on the Main and AUX channels to ones not
		  formed from the quadrature signal.

		  An exception will be raised if you attempt to set the demodulation to 'external' while viewing one of these signals.

		:type mode: string; {'internal', 'external', 'external_pll'}
		:param mode: Demodulation mode

		:type frequency: float; [0, 200e6] Hz
		:param frequency: Internal demodulation signal frequency (ignored for all 'external' modes)

		:type phase: float; [0, 360] deg
		:param phase: Internal demodulation signal phase (ignored in 'external' mode)

		:type output_amplitude: float; [0.0, 2.0] Vpp
		:param output_amplitude: Output amplitude of the demodulation
		signal when auxiliary channel set to output `demod`.

		"""
		_utils.check_parameter_valid('range', frequency, allowed=[0,200e6], desc="demodulation frequency", units="Hz")
		_utils.check_parameter_valid('range', phase, allowed=[0,360], desc="demodulation phase", units="degrees")
		_utils.check_parameter_valid('set', mode, allowed=['internal', 'external', 'external_pll'] )

		if mode == 'external' and (
				self.aux_source not in _NON_PLL_ALLOWED_SIGS and (
				self.main_source not in _NON_PLL_ALLOWED_SIGS)):
			raise InvalidConfigurationException(
				"Can't use external demodulation source without a PLL with "
				"quadrature-related outputs. Allowed outputs are " + str(
					_NON_PLL_ALLOWED_SIGS))

		self.autoacquire = 1
		self.bandwidth = 0
		self.lo_PLL_reset = 0
		self.lo_reacquire = 0

		# Store the desired output amplitude in the case that 'set_outputs'
		# is called with 'demod' for the auxiliary channel output. We can't
		# set the register here because it is shared with the local oscillator
		# amplitude. It will be updated on commit.
		self._demod_amp = output_amplitude
		if mode == 'external' and (self.demod_mode == 'internal' or self.demod_mode == 'external_pll'):
			self.pid.gain = self.pid.gain * (1.0 / 3750 / self._adc_gains()[1])
			self.gainstage_gain = self.gainstage_gain * (1.0 / 3750 / self._adc_gains()[1])
		elif mode != 'external' and self.demod_mode == 'external':
			self.pid.gain = self.pid.gain / (1.0 / 3750 / self._adc_gains()[1])
			self.gainstage_gain = self.gainstage_gain / (1.0 / 3750 / self._adc_gains()[1])

		if mode == 'internal':
			self.ext_demod = 0
			self.lo_PLL = 0
			self.frequency_demod = frequency
			self.phase_demod = phase
			self.demod_mode = mode
		elif mode == 'external':
			self.ext_demod = 1
			self.lo_PLL = 0
			self.demod_mode = mode
		elif mode == 'external_pll':
			self.ext_demod = 0
			self.lo_PLL = 1
			self.lo_reacquire = 1
			self.phase_demod = phase
			self.demod_mode = mode
		else :
			# Should not happen
			raise ValueOutOfRangeException('Demodulation mode must be one of "internal", "external" or "external_pll", not %s', mode)

	@needs_commit
	def set_filter(self, f_corner, order):
		"""
		Set the low-pass filter parameters.

		:type f_corner: float; [300.0e-3, 5.0e6]
		:param f_corner: Corner frequency of the low-pass filter (Hz)

		:type order: int; [1, 2, 3, 4]
		:param order: filter order; 0 (bypass), first- or second-order.

		"""
		_utils.check_parameter_valid('range', f_corner,
									 allowed=[300.0e-3, 5.0e6],
									 desc="filter corner frequency",
									 units="Hz")

		_utils.check_parameter_valid('set', order, allowed=[1, 2, 3, 4],
									 desc="filter order")

		# filter gain
		f = [0, 0]
		# new gain
		n = [0, 0]
		# filter gain select
		s = [0, 0]

		self.filt_select = order - 1

		self.lpf_int_ifb_gain = 1.0 - 2.0 * (
			math.pi * f_corner) / _LIA_CONTROL_FS

		self.lpf_following_stage_gain = 2**24 - (self.lpf_int_ifb_gain * _LIA_ID_GAINSCALE)

		f[0], n[0], s[0] = self._distribute_gain(self.gain_user['main'])
		f[1], n[1], s[1] = self._distribute_gain(self.gain_user['aux'])

		self._set_filt_gain_select(s[0], 'main')
		self._set_filt_gain_select(s[1], 'aux')

		self._set_filt_gain('main', f[0])
		self._set_filt_gain('aux', f[1])
		self._set_output_scaling('main', n[0])
		self._set_output_scaling('aux', n[1])

	@needs_commit
	def set_lo_output(self, amplitude, frequency, phase):
		"""
		Configure local oscillator output.

		This output is available on Channel 2 of the Moku:Lab.

		:type amplitude: float; [0.0, 2.0] Vpp
		:param amplitude: Amplitude

		:type frequency: float; [0, 200e6] Hz
		:param frequency: Frequency

		:type phase: float; [0, 360] deg
		:param phase: Phase
		"""
		_utils.check_parameter_valid('range', amplitude, allowed=[0, 2.0], desc="local oscillator amplitude", units="Vpp")
		_utils.check_parameter_valid('range', frequency, allowed=[0,200e6], desc="local oscillator frequency", units="Hz")
		_utils.check_parameter_valid('range', phase, allowed=[0,360], desc="local oscillator phase", units="degrees")

		# The sine amplitude register also scales the LIA signal outputs
		# (eek!), so it must only be updated
		# if the auxiliary output is set to a non-filtered signal.
		self._lo_amp = amplitude
		self.lo_frequency = frequency
		self.lo_phase = phase

	@needs_commit
	def set_monitor(self, monitor_ch, source, high_sensitivity_en=False):
		"""
		Select the point inside the lockin amplifier to monitor.

		There are two monitoring channels available, 'A' and 'B'; you can mux any of the internal
		monitoring points to either of these channels.

		The source is one of:
			- **none**: Disable monitor channel
			- **in1**, **in2**: Input Channel 1/2
			- **main**: Lock-in output (Output Channel 1)
			- **aux**: auxiliary output (Output Channel 2)
			- **demod**: Demodulation signal input to mixer
			- **i**, **q**: Mixer I and Q channels respectively.

		:type monitor_ch: string; {'A','B'}
		:param monitor_ch: Monitor channel
		:type source: string; {'none','in1','in2','main','aux','demod','i','q'}
		:param source: Signal to monitor
		:type high_sensitivity_en: bool
		:param high_sensitivity_en: Enable high-sensitivity mode (for signals smaller than 25 mVpp)
		"""
		_utils.check_parameter_valid('string', monitor_ch, desc="monitor channel")
		_utils.check_parameter_valid('string', source, desc="monitor signal")

		monitor_ch = monitor_ch.lower()
		source = source.lower()

		_utils.check_parameter_valid('set', monitor_ch, allowed=['a','b'], desc="monitor channel")
		_utils.check_parameter_valid('set', source, allowed=['none', 'in1', 'in2', 'main', 'aux', 'demod', 'i','q'], desc="monitor source")

		monitor_sources = {
			'none'	: _LIA_MON_NONE,
			'in1'	: _LIA_MON_IN1,
			'in2'	: _LIA_MON_IN2,
			'main'	: _LIA_MON_OUT,
			'aux'	: _LIA_MON_AUX,
			'demod'	: _LIA_MON_DEMOD,
			'i'		: _LIA_MON_I,
			'q'		: _LIA_MON_Q,
		}

		if monitor_ch == 'a':
			self.monitor_a = source
			self.monitor_select0 = monitor_sources[source]
			self.monitor_a_sensitivity_en = high_sensitivity_en
		elif monitor_ch == 'b':
			self.monitor_b = source
			self.monitor_select1 = monitor_sources[source]
			self.monitor_b_sensitivity_en = high_sensitivity_en
		else:
			raise ValueOutOfRangeException("Invalid channel %d", monitor_ch)

	@needs_commit
	def set_trigger(self, source, edge, level, minwidth=None, maxwidth=None, hysteresis=10e-3, hf_reject=False, mode='auto'):
		"""
		Set the trigger source for the monitor channel signals. This can be either of the input or
		monitor signals, or the external input.

		:type source: string, {'in1','in2','A','B','ext'}
		:param source: Trigger Source. May be either an input or monitor channel (as set by
				:py:meth:`~pymoku.instruments.LockInAmp.set_monitor`), or external. External refers
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
		source = _utils.str_to_val(_LIA_OSC_SOURCES, source, 'trigger source')

		# This function is the portion of set_trigger shared among instruments with embedded scopes.
		self._set_trigger(source, edge, level, minwidth, maxwidth, hysteresis, hf_reject, mode)

	@needs_commit
	def set_input_range_r_theta(self, i_range=0):
		"""
		Sets the Rect-to-polar conversion range for r theta mode.

		Three scaling ranges are available: 2 Vpp, 7.5 mVpp and 25 uVpp

		:type i_range: integer, [0, 1, 2]
		:param i_range: range selection, 0 = 2 Vpp, 1 = 7.5 mVpp, 2 = 25 uVpp
		"""
		_utils.check_parameter_valid('set', i_range,
									 allowed=[0, 1, 2],
									 desc="range scale select")
		gain_filter, filt_gain_select = self._calculate_r_theta_gain(i_range)

		self._set_filt_gain_select(filt_gain_select)

		self._set_filt_gain('main', gain_filter)
		self._set_filt_gain('aux', gain_filter)

	def _signal_source_volts_per_bit(self, source, scales, trigger=False):
		"""
			Converts volts to bits depending on the signal source
		"""
		# Decimation gain is applied only when using precision mode data
		if (not trigger and self.is_precision_mode()) or (trigger and self.trig_precision):
			deci_gain = self._deci_gain()
		else:
			deci_gain = 1.0

		if source == _LIA_SOURCE_A:
			return self._monitor_source_volts_per_bit(
				self.monitor_a, scales) / deci_gain / (16.0 if self.monitor_a_sensitivity_en else 1.0)
		elif source == _LIA_SOURCE_B:
			return self._monitor_source_volts_per_bit(
				self.monitor_b, scales) / deci_gain / (16.0 if self.monitor_b_sensitivity_en else 1.0)
		elif source == _LIA_SOURCE_IN1:
			return scales['gain_adc1'] * (10.0 if scales['atten_ch1']
										  else 1.0) / deci_gain
		elif source == _LIA_SOURCE_IN2:
			return scales['gain_adc2'] * (10.0 if scales['atten_ch2']
										  else 1.0) / deci_gain
		else:
			return 1.0

	def _monitor_source_volts_per_bit(self, source, scales):
		# Calculates the volts to bits conversion for the given monitor port signal

		def _demod_mode_to_gain(mode):
			if mode in ['internal', 'external_pll']:
				return 1.0 / 2**11
			else:
				return 1.0

		monitor_source_gains = {
			'none': 1.0,
			'in1': scales['gain_adc1'] / (
				10.0 if scales['atten_ch1'] else 1.0),
			'in2': scales['gain_adc2'] / (
				10.0 if scales['atten_ch2'] else 1.0),
			'main': scales['gain_dac1'] * (2.0**4),  # 12bit ADC - 16bit DAC
			'aux': scales['gain_dac2'] * (2.0**4),
			'demod': _demod_mode_to_gain(self.demod_mode),
			'i': scales['gain_adc1'] / (10.0 if scales['atten_ch1'] else 1.0),
			'q': scales['gain_adc1'] / (10.0 if scales['atten_ch1'] else 1.0)
		}
		return monitor_source_gains[source]

	def _update_dependent_regs(self, scales):
		super(LockInAmp, self)._update_dependent_regs(scales)

		# Update PID/Gain stage input/output selects as they may have swapped channels
		self._update_pid_gain_selects()

		if self.aux_source in _LIA_SIGNALS:
			# If aux is set to a filtered signal, set this to maximum gain
			# setting.
			# If you don't do this, the filtered signal is scaled by < 1.0.
			self.sineout_amp = 2**16 - 1
		else:
			# If aux is set to LO or demod, set the sine amplitude as desired.
			# Only ever output on Channel 2.
			self.sineout_amp = (self._lo_amp if self.aux_source == 'sine'
								else self._demod_amp) / self._dac_gains()[1]

	@deprecated(category='method', message="Deprecated.")
	def set_control_matrix(self):
		pass

	def _calculate_filt_dsp_gain(self):
		return 1.0 / (1.0 - self.lpf_int_ifb_gain)

	def _get_filt_gain(self, ch):
		if ch == 'main':
			return self._remove_adc_gain(self.lpf_int_i_gain_ch1)
		else:
			return self._remove_adc_gain(self.lpf_int_i_gain_ch2)

	def _set_filt_gain(self, ch, gain):
		if self.r_theta_mode is True:
			self.lpf_int_i_gain_ch1 = self._apply_adc_gain(gain)
			self.lpf_int_i_gain_ch2 = self._apply_adc_gain(gain)
		elif ch == 'main':
			self.lpf_int_i_gain_ch1 = self._apply_adc_gain(gain)
		elif ch == 'aux':
			self.lpf_int_i_gain_ch2 = self._apply_adc_gain(gain)

	def _set_output_scaling(self, ch, gain):
		if self._pid_channel == ch:
			self.pid.gain = self._apply_dac_gain(ch, gain * 2**16) * self.ch_scaling[ch]
		else:
			self.gainstage_gain = self._apply_dac_gain(ch, gain) * self.ch_scaling[ch]

	def _get_output_scaling(self, ch):
		if self._pid_channel == ch:
			return self._remove_dac_gain(ch, self.pid.gain) / 2.0**16
		else:
			return self._remove_dac_gain(ch, self.gainstage_gain)

	def _apply_adc_gain(self, gain):
		attenuation_on = self.get_frontend(1)[1]
		if attenuation_on is True:
			return gain * self._adc_gains()[0] * 2**12 / 10
		else:
			return gain * self._adc_gains()[0] * 2**12

	def _remove_adc_gain(self, gain):
		attenuation_on = self.get_frontend(1)[1]
		if attenuation_on is True:
			return 10 * gain / self._adc_gains()[0] / 2.0**12
		else:
			return gain / self._adc_gains()[0] / 2.0**12

	def _apply_dac_gain(self, ch, gain):
		ch_number = 0 if ch == 'main' else 1
		return gain / self._dac_gains()[ch_number] / 2.0**15

	def _remove_dac_gain(self, ch, gain):
		ch_number = 0 if ch == 'main' else 1
		return gain * self._dac_gains()[ch_number] * 2.0**15

	def _distribute_gain(self, required_gain, i_range=0):
		dsp_gain = self._calculate_filt_dsp_gain()
		if self.r_theta_mode is False:
			return self._calculate_distributed_gain(required_gain / dsp_gain)
		elif self.r_theta_mode is True:
			filter_gain, filter_gain_select = self._calculate_r_theta_gain(
				i_range)
			out_gain = required_gain
			return filter_gain, out_gain, filter_gain_select

	@staticmethod
	def _calculate_distributed_gain(required_gain):
		gain_threshold = (2**31 - 1) / 2**24
		if required_gain > (2**15):
			filter_gain_select = 1
			filter_gain = gain_threshold
			out_gain = required_gain / 2**8 / filter_gain
		elif required_gain > gain_threshold:
			filter_gain_select = 1
			filter_gain = required_gain / 2**8
			out_gain = 1
		elif required_gain > 2**(-24):
			filter_gain_select = 0
			filter_gain = required_gain
			out_gain = 1
		else:
			filter_gain_select = 0
			filter_gain = 2**(-24)
			out_gain = required_gain / filter_gain

		return filter_gain, out_gain, filter_gain_select

	def _calculate_r_theta_gain(self, input_range):
		gain_dsp = self._calculate_filt_dsp_gain()
		if input_range == 0:
			return 1.0 / gain_dsp, 0
		elif input_range == 1:
			return 2.0**8 / gain_dsp, 0
		elif input_range == 2:
			return 2.0**8 / gain_dsp, 1
		else:
			return 1.0 / gain_dsp, 0

	def _get_required_gain(self, ch):
		return self._get_output_scaling(ch) * self._get_filt_gain(
			ch) * self._calculate_filt_dsp_gain()

	def _set_r_theta_mode(self, mode):
		if self.r_theta_mode != mode:
			gain_filter = 1.0 / self._calculate_filt_dsp_gain()
			self.lpf_int_i_gain_ch1 = self.lpf_int_i_gain_ch2 = gain_filter
			self.set_pid_by_gain('main', 1)
			self.set_gain('aux', 1)
			if mode is False:
				log.info('Switched to x/y mode please check gain settings')
			else:
				log.info('Switched to r/theta mode please check gain settings')
		self.r_theta_mode = mode

	def _set_filt_gain_select(self, gain_select, ch=None):
		if self.r_theta_mode is True or ch is None:
			self.filt_gain_select_ch1 = gain_select
			self.filt_gain_select_ch2 = gain_select
		elif ch == 1:
			self.filt_gain_select_ch1 = gain_select
		elif ch == 2:
			self.filt_gain_select_ch2 = gain_select

_lia_reg_hdl = {

	'bandwidth':
		(90,
		 to_reg_signed(0, 5, xform=lambda obj, b: b),
		 from_reg_signed(0, 5, xform=lambda obj, b: b)),

	'autoacquire':
		(91,
		 to_reg_bool(0),
		 from_reg_bool(0)),

	'lo_reacquire':
		(92,
		 to_reg_bool(0),
		 from_reg_bool(0)),

	'lo_PLL_reset':
		(93,
		 to_reg_bool(31),
		 from_reg_bool(31)),

	'monitor_a_sensitivity_en':
		(113,
		 to_reg_bool(0),
		 from_reg_bool(0)),

	'monitor_b_sensitivity_en':
		(113,
		 to_reg_bool(1),
		 from_reg_bool(1)),

	'ch1_out_en':
		(96,
		 to_reg_bool(2),
		 from_reg_bool(2)),

	'ch1_signal_en':
		(96,
		 to_reg_bool(3),
		 from_reg_bool(3)),

	'ch2_out_en':
		(96,
		 to_reg_bool(4),
		 from_reg_bool(4)),

	'ch2_signal_en':
		(96,
		 to_reg_bool(5),
		 from_reg_bool(5)),

	'ext_demod':
		(96,
		 to_reg_bool(6),
		 from_reg_bool(6)),

	'lo_PLL':
		(96,
		 to_reg_bool(7),
		 from_reg_bool(7)),

	'filt_select':
		(96,
		 to_reg_unsigned(8, 2),
		 from_reg_unsigned(8, 2)),

	'aux_select':
		(96,
		 to_reg_unsigned(10, 2),
		 from_reg_unsigned(10, 2)),

	'filt_gain_select_ch1':
		(96,
		 to_reg_bool(12),
		 from_reg_bool(12)),

	'filt_gain_select_ch2':
		(96,
		 to_reg_bool(13),
		 from_reg_bool(13)),

	'pid_ch_select':
		(96,
		 to_reg_bool(14),
		 from_reg_bool(14)),

	'pid_sig_select':
		(96,
		 to_reg_unsigned(15, 2),
		 from_reg_unsigned(15, 2)),

	'gain_sig_select':
		(96,
		 to_reg_unsigned(17, 2),
		 from_reg_unsigned(17, 2)),

	'lpf_int_ifb_gain':
		(106,
		 to_reg_signed(0, 25,
					   xform=lambda obj, x: x * _LIA_ID_GAINSCALE),
		 from_reg_signed(0, 25,
						 xform=lambda obj, x: x / _LIA_ID_GAINSCALE)),

	'lpf_int_i_gain_ch1':
		(107,
		 to_reg_signed(0, 32,
					   xform=lambda obj, x: x * 2.0**24),
		 from_reg_signed(0, 32,
						 xform=lambda obj, x: x / 2.0**24)),

	'lpf_following_stage_gain':
		(108,
		 to_reg_signed(0, 32),
		 from_reg_signed(0, 32)),

	'lpf_int_i_gain_ch2':
		(109,
		 to_reg_signed(0, 32,
					   xform=lambda obj, x: x * 2.0**24),
		 from_reg_signed(0, 32,
						 xform=lambda obj, x: x / 2.0**24)),

	'gainstage_gain':
		(110,
		 to_reg_signed(0, 32, xform=lambda obj, x: x * 2.0**16),
		 from_reg_signed(0, 32, xform=lambda obj, x: x / 2.0**16)),

	'main_offset':
		(111,
		 to_reg_signed(0, 16,
					   xform=lambda obj, x: x / obj._dac_gains()[0]),
		 from_reg_signed(0, 16,
						 xform=lambda obj, x: x * obj._dac_gains()[0])),

	'aux_offset':
		(112,
		 to_reg_signed(0, 16,
					   xform=lambda obj, x: x / obj._dac_gains()[1]),
		 from_reg_signed(0, 16,
						 xform=lambda obj, x: x * obj._dac_gains()[1])),

	'frequency_demod':
		((119, 118),
		 to_reg_unsigned(0, 48,
						 xform=lambda obj, x: x / _LIA_FREQSCALE),
		 from_reg_unsigned(0, 48,
						   xform=lambda obj, x: x * _LIA_FREQSCALE)),

	'phase_demod':
		((121, 120),
		 to_reg_unsigned(0, 48,
						 xform=lambda obj, x: x / (360.0 * _LIA_PHASESCALE)),
		 from_reg_unsigned(0, 48, xform=lambda obj, x: x * (
						   360.0 * _LIA_PHASESCALE))),

	'lo_frequency':
		((123, 122),
		 to_reg_unsigned(0, 48, xform=lambda obj, x: x / _LIA_FREQSCALE),
		 from_reg_unsigned(0, 48, xform=lambda obj, x: x * _LIA_FREQSCALE)),

	'lo_phase':
		((125, 124),
		 to_reg_unsigned(0, 48,
						 xform=lambda obj, x: x / (360.0 * _LIA_PHASESCALE)),
		 to_reg_unsigned(0, 48,
						 xform=lambda obj, x: x * (360.0 * _LIA_PHASESCALE))),

	'sineout_amp':
		(126,
		 to_reg_unsigned(0, 16, xform=lambda obj, x: x),
		 from_reg_unsigned(0, 16, xform=lambda obj, x: x)),

	'monitor_select0':
		(127,
		 to_reg_unsigned(0, 3, allow_set=[_LIA_MON_NONE,
										  _LIA_MON_IN1,
										  _LIA_MON_I,
										  _LIA_MON_Q,
										  _LIA_MON_OUT,
										  _LIA_MON_AUX,
										  _LIA_MON_IN2,
										  _LIA_MON_DEMOD]),
		 from_reg_unsigned(0, 3)),

	'monitor_select1':
		(127,
		 to_reg_unsigned(3, 3, allow_set=[_LIA_MON_NONE,
										  _LIA_MON_IN1,
										  _LIA_MON_I,
										  _LIA_MON_Q,
										  _LIA_MON_OUT,
										  _LIA_MON_AUX,
										  _LIA_MON_IN2,
										  _LIA_MON_DEMOD]),
		 from_reg_unsigned(0, 3))
}
