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
	def _set_gain_range(self, range=0):
		"""
		Set the main input gain (Input Channel 1).

		:type gain: int; {0, 24} dB
		:param gain: Input gain

		"""

		if range == 0:
			self.gain_select = 0
		else:
			self.gain_select = 1

	@needs_commit
	def set_outputs(self, main, aux, main_offset=0.0, aux_offset=0.0):
		"""
		Configures the main (Channel 1) and auxillary (Channel 2) output signals of the Lock-In.

		.. note::
		  When 'external' demodulation is used (that is, without a PLL), the Lock-in Amplifier doesn't know the frequency and therefore
		  can't form the quadrature for full I/Q demodulation. This in turn means it can't distinguish I from Q, X from Y,
		  or form R/Theta. This limits the choices for signals that can be output on the AUX channel to ones not from the
		  Lock-in logic (e.g. demodulation source, auxilliary sine wave etc).

		  An exception will be raised if you attempt to set the auxilliary channel to view aa signal from the Lock-in logic while
		  external demodulation is enabled.

		:type main: string; {'x', 'y', 'r', 'theta', 'offset', 'none'}
		:param main: Main output signal

		:type aux: string; {'x', 'y', 'r', theta', 'sine', 'demod', 'offset', 'none'}
		:param aux: Auxillary output signal

		:type main_offset: float; [-1.0, 1.0] V
		:param main_offset: Main output offset

		:type aux_offset: float; [-1.0, 1.0] V
		:param aux_offset: Auxillary output offset
		"""
		_utils.check_parameter_valid('string', main, desc="main output signal")
		_utils.check_parameter_valid('string', aux, desc="auxillary output signal")

		# Allow uppercase options
		main = main.lower()
		aux = aux.lower()

		_utils.check_parameter_valid('set', main, allowed=['x','y','r','theta','offset','none'], desc="main output signal")
		_utils.check_parameter_valid('set', aux, allowed=['x', 'y','r','theta','sine','demod','offset','none'], desc="auxillary output signal")

		if self.demod_mode == 'external' and not (aux in _NON_PLL_ALLOWED_SIGS and main in _NON_PLL_ALLOWED_SIGS):
			raise InvalidConfigurationException("Can't use quadrature-related outputs when using external demodulation without a PLL. " \
				"Allowed outputs are " + str(_NON_PLL_ALLOWED_SIGS))


		if main in ['r', 'theta'] and aux in ['x', 'y']:
			raise InvalidConfigurationException("Can't use "
													 "r/theta outputs"
													 " in conjunction"
													 " with x/y"
													 " outputs."
													 " Please select"
													 " r/theta or x/y"
													 " for both outputs."
													)

		if main in ['x', 'y'] and aux in ['r', 'theta']:
			raise InvalidConfigurationException("Can't use "
													 "x/y outputs"
													 " in conjunction"
													 " with r/theta"
													 " outputs."
													 " Please select"
													 " r/theta or x/y"
													 " for both outputs."
													)

		# Update locking mode
		self._set_r_theta_mode(main in ['r', 'theta'] or aux in ['r', 'theta'])

		# Main output enables
		self.main_offset = main_offset
		self.main_source = main
		self.ch1_signal_en = main in _LIA_SIGNALS
		self.ch1_out_en = not (main == 'none')

		# Auxillary output enables
		self.aux_offset = aux_offset
		self.aux_source = aux
		self.ch2_signal_en = aux in (_LIA_SIGNALS + ['sine', 'demod'])
		self.ch2_out_en = not (aux == 'none')
		# Defaults to local oscillator i.e. 'sine'
		self.aux_select = 1 if aux in (_LIA_SIGNALS) else \
			(2 if aux == 'demod' else 0)

		# PID/Gain stage selects are updated on commit

	def _set_r_theta_mode(self, r_theta_en):
		if self.r_theta_mode == r_theta_en:
			if r_theta_en is False:
				log.info('Switched to x/y mode please check gain settings')
			else:
				log.info('Switched to r/theta mode please check gain settings')
		self.r_theta_mode = r_theta_en

	def _update_pid_gain_selects(self):
		# Update the PID/Gain signal inputs / channel select ouputs to
		# match the set main/aux source signals

		def _signal_select(sig):
			return 0 if not(sig in _LIA_SIGNALS) else [i for i,x in enumerate(_LIA_SIGNALS) if x==sig][0]

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
		Greq = kp
		Gfilt, Gout, filt_gain_select = self._distribute_gain(Greq)
		Gdsp = self._calculate_filt_dsp_gain()
		Gout = self._apply_dac_gain(lia_ch, Gout)
		self._set_filt_gain(lia_ch, Gfilt)
		self._set_filt_gain_select(filt_gain_select, lia_ch)

		if lia_ch != self._pid_channel:
			gainstage_scaling = self._get_output_scaling(lia_ch)
			new_gainstage_ch = self._pid_channel
			self._pid_channel = lia_ch
			self._set_output_scaling(new_gainstage_ch, gainstage_scaling)

		output_channel = 0 if lia_ch == 'main' else 1

		self.pid.set_reg_by_frequency(kp, i_xover, d_xover, si, sd, overall_scaling=Gout * 2.0**16 / Gfilt / Gdsp)
		self.pid.input_offset = in_offset
		self.pid.output_offset = out_offset

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
		Greq = g
		Gfilt, Gout, filt_gain_select = self._distribute_gain(Greq)
		self._set_filt_gain(lia_ch, Gfilt)
		print('in set by gain', filt_gain_select, Gfilt, Gout)
		self._set_filt_gain_select(filt_gain_select, lia_ch)
		# if self.r_theta_mode is False:
		#     Gfilt, Gout = self._balance_gains(Greq / Gdsp)
		#     if lia_ch == 'main':
		#         self.lpf_int_i_gain_ch1 = Gfilt
		#     elif lia_ch == 'aux':
		#         self.lpf_int_i_gain_ch2 = Gfilt
		#     else:
		#         self.lpf_int_i_gain_ch1 = Gfilt
		# elif self.r_theta_mode is True:
		#     Gout = Greq
		#     Gfilt = 1.0 / Gdsp
		#     self.lpf_int_i_gain_ch1 = self.lpf_int_i_gain_ch2 = Gfilt
		Gout = self._apply_dac_gain(lia_ch, Gout)

		if lia_ch != self._pid_channel:
			gainstage_scaling = self._get_output_scaling(lia_ch)
			new_gainstage_ch = self._pid_channel
			self._pid_channel = lia_ch
			self._set_output_scaling(new_gainstage_ch, gainstage_scaling)

		output_channel = 0 if lia_ch == 'main' else 1
		self.pid.set_reg_by_gain(Gout * 2.0**16,
								 kp, ki, kd, si, sd)
		# print('kd', kd)
		self.pid.input_offset = in_offset
		self.pid.output_offset = out_offset

	# @needs_commit
	# def _set_input_range(self, input_range=0):
	#     """
	#     Sets the input range whilst in r theta mode. This setting is not
	#     available in x/y mode.

	#     :type input_range: string; {"smallest", "small", "high"}
	#     :param input_range: input singal range in r/theta mode

	#     """

	#     Greq = [0, 0]
	#     Gdsp = [0, 0]
	#     Gnew = [0, 0]

	#     Greq[0] = self._get_required_gain(1)
	#     Greq[1] = self._get_required_gain(2)
	#     print('Greq in set input range', Greq[0])
	#     print('Greq in set input range', Greq[1])

	#     if self.r_theta_mode is True or input_range == 0:
	#         self.r_theta_input_range = input_range
	#     else:
	#         raise InvalidConfigurationException("Input gains only used in "
	#                                             "r/theta mode.")
	#     if self._pid_channel == 'main':
	#         self.set_pid_by_gain('main', Greq[0])
	#         self.set_gain('aux', Greq[1])
	#     else:
	#         self.set_gain('main', Greq[0])
	#         self.set_pid_by_gain('aux', Greq[1])



	@needs_commit
	def set_gain(self, lia_ch, g):
		"""
		Sets the gain stage to be on the specified lock-in channel, and configures its gain.

		This sets the PID stage to be on the opposite channel.

		:type lia_ch: string; {'main','aux'}
		:param lia_ch: Channel name

		:type g: float; [0, 2^16 - 1]
		:param g: Gain
		"""
		_utils.check_parameter_valid(
			'set', lia_ch, allowed=['main','aux'], desc="lock-in channel")
		_utils.check_parameter_valid(
			'range', g, allowed=[0, 2**16 - 1], desc="gain")

		new_pid_ch = 'main' if lia_ch=='aux' else 'aux'

		if new_pid_ch == self._pid_channel:
			pid_scaling = self._get_output_scaling(self._pid_channel)
			print('in set gain output scaling', pid_scaling)
			self._pid_channel = new_pid_ch
			self._set_output_scaling(new_pid_ch, pid_scaling)




		# print('in gain settings',  self.r_theta_input_range)
		Greq = g
		Gfilt, Gout, filt_gain_select = self._distribute_gain(Greq)
		Gout = self._apply_dac_gain(lia_ch, Gout)
		# print('in set gain', Gfilt, Gout)
		self._set_filt_gain(lia_ch, Gfilt)
		self._set_filt_gain_select(filt_gain_select, lia_ch)
		# if self.r_theta_mode is False:
		#     Gfilt, Gout = self._balance_gains(Greq / Gdsp)
		#     if lia_ch == 'main':
		#         self.lpf_int_i_gain_ch1 = Gfilt
		#     elif lia_ch == 'aux':
		#         self.lpf_int_i_gain_ch2 = Gfilt
		#     else:
		#         self.lpf_int_i_gain_ch1 = Gfilt
		# elif self.r_theta_mode is True:
		#     Gout = Greq
		#     Gfilt = 1.0 / Gdsp
		#     self.lpf_int_i_gain_ch1 = self.lpf_int_i_gain_ch2 = Gfilt

		# Store selected gain locally. Update on commit with correct DAC
		# scaling.
		self.gainstage_gain = Gout

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
		:param output_amplitude: Output amplitude of the demodulation signal when auxillary channel set to output `demod`.

		"""
		_utils.check_parameter_valid('range', frequency, allowed=[0,200e6], desc="demodulation frequency", units="Hz")
		_utils.check_parameter_valid('range', phase, allowed=[0,360], desc="demodulation phase", units="degrees")
		_utils.check_parameter_valid('set', mode, allowed=['internal', 'external', 'external_pll'] )

		if mode == 'external' and not (self.aux_source in _NON_PLL_ALLOWED_SIGS and self.main_source in _NON_PLL_ALLOWED_SIGS):
			raise InvalidConfigurationException("Can't use external demodulation source without a PLL with quadrature-related outputs. " \
				"Allowed outputs are " + str(_NON_PLL_ALLOWED_SIGS))

		self.autoacquire = 1
		self.bandwidth = 0
		self.lo_PLL_reset = 0
		self.lo_reacquire = 0

		# Store the desired output amplitude in the case that 'set_outputs' is called with
		# 'demod' for the auxillary channel output. We can't set the register here because
		# it is shared with the local oscillator amplitude. It will be updated on commit.
		self._demod_amp = output_amplitude

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

		:type f_corner: float
		:param f_corner: Corner frequency of the low-pass filter (Hz)

		:type order: int; [1, 2, 3, 4]
		:param order: filter order; 0 (bypass), first- or second-order.

		"""
		_utils.check_parameter_valid('set', order, allowed=[1, 2, 3, 4],
									 desc="filter order")

		Greq = [0, 0]
		Gfilt = [0, 0]
		Gnew = [0, 0]
		filt_gain_select = [0, 0]

		Greq[0] = self._get_required_gain('main')
		Greq[1] = self._get_required_gain('aux')
		# print('in set filter', Greq)
		self.lpf_den = 0

		self.filt_select = order - 1

		self.input_gain = 1.0

		ifb = (1.0 - 2.0 * (math.pi * f_corner)
							  / _LIA_CONTROL_FS)
		self.lpf_int_ifb_gain = ifb

		Gfilt[0], Gnew[0], filt_gain_select[0] = self._distribute_gain(Greq[0])
		Gfilt[1], Gnew[1], filt_gain_select[1] = self._distribute_gain(Greq[1])

		self._set_filt_gain_select(filt_gain_select[0], 'main')
		self._set_filt_gain_select(filt_gain_select[1], 'aux')

		self._set_filt_gain('main', Gfilt[0])
		self._set_filt_gain('aux', Gfilt[1])
		# self.lpf_pidgain = Gnew[0]
		self._set_output_scaling('main', Gnew[0])
		self._set_output_scaling('aux', Gnew[1])

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

		# The sine amplitude register also scales the LIA signal outputs (eek!), so it must only be updated
		# if the auxillary output is set to a non-filtered signal.
		self._lo_amp = amplitude
		self.lo_frequency = frequency
		self.lo_phase = phase

	@needs_commit
	def set_monitor(self, monitor_ch, source, high_sensitvity_en=False):
		"""
		Select the point inside the lockin amplifier to monitor.

		There are two monitoring channels available, 'A' and 'B'; you can mux any of the internal
		monitoring points to either of these channels.

		The source is one of:
			- **none**: Disable monitor channel
			- **in1**, **in2**: Input Channel 1/2
			- **main**: Lock-in output (Output Channel 1)
			- **aux**: Auxillary output (Output Channel 2)
			- **demod**: Demodulation signal input to mixer
			- **i**, **q**: Mixer I and Q channels respectively.

		:type monitor_ch: string; {'A','B'}
		:param monitor_ch: Monitor channel
		:type source: string; {'none','in1','in2','main','aux','demod','i','q'}
		:param source: Signal to monitor
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
			self.monitor_a_sensitivity_en = high_sensitvity_en
		elif monitor_ch == 'b':
			self.monitor_b = source
			self.monitor_select1 = monitor_sources[source]
			self.monitor_b_sensitivity_en = high_sensitvity_en
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

	def _signal_source_volts_per_bit(self, source, scales, trigger=False):
		"""
			Converts volts to bits depending on the signal source
		"""
		# Decimation gain is applied only when using precision mode data
		if (not trigger and self.is_precision_mode()) or (trigger and self.trig_precision):
			deci_gain = self._deci_gain()
		else:
			deci_gain = 1.0

		if (source == _LIA_SOURCE_A):
			level = self._monitor_source_volts_per_bit(self.monitor_a, scales)/deci_gain
		elif (source == _LIA_SOURCE_B):
			level = self._monitor_source_volts_per_bit(self.monitor_b, scales)/deci_gain
		elif (source == _LIA_SOURCE_IN1):
			level = scales['gain_adc1']*(10.0 if scales['atten_ch1'] else 1.0)/deci_gain
		elif (source == _LIA_SOURCE_IN2):
			level = scales['gain_adc2']*(10.0 if scales['atten_ch2'] else 1.0)/deci_gain
		else:
			level = 1.0
		return level

	def _monitor_source_volts_per_bit(self, source, scales):
		# Calculates the volts to bits conversion for the given monitor port signal

		def _demod_mode_to_gain(mode):
			if mode == 'internal' or 'external_pll':
				return 1.0/2**11
			else:
				return 1.0

		monitor_source_gains = {
			'none': 1.0,
			'in1': scales['gain_adc1'] / (10.0 if scales['atten_ch1'] else 1.0),
			'in2': scales['gain_adc2'] / (10.0 if scales['atten_ch2'] else 1.0),
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

		# Set the PID gains using the correct output DAC channel
		# gs = self._pid_gains

		pid_ch = 1 if self._pid_channel == 'main' else 2
		# self._set_by_gain(1, gs['g'], gs['kp'], gs['ki'], gs['kd'], 0,
		#                   gs['si'], gs['sd'], gs['in_offset'],
		#                   gs['out_offset'], touch_ii=False, dac=pid_ch)

		# Set gainstage gain with correct output DAC channel scaling
		# self.gainstage_gain = self._gainstage_gain / \
		#     self._dac_gains()[1 if self._pid_channel == 'main' else 0] \
		#     / 2**14

		if self.aux_source in _LIA_SIGNALS:
			# If aux is set to a filtered signal, set this to maximum gain setting.
			# If you don't do this, the filtered signal is scaled by < 1.0.
			self.sineout_amp = 2**16 - 1
		else:
			# If aux is set to LO or demod, set the sine amplitude as desired.
			# Only ever output on Channel 2.
			self.sineout_amp = (self._lo_amp if self.aux_source=='sine' else self._demod_amp) / self._dac_gains()[1]

	@deprecated(category='method', message="Deprecated.")
	def set_control_matrix(self):
		# This function is merely here because LIA inherits PID which has a control matrix
		# We need to rethink PID inheritance.
		pass

	# def _balance_gains(self, Greq):
	#     if Greq > 2**4:
	#         Gfilt = 2**4
	#         Gout = Greq / 2**4
	#     elif Greq < 1 / 2**25:
	#         Gfilt = 1 / 2**25
	#         Gout = Greq * 2**25
	#     else:
	#         Gout = 1
	#         Gfilt = Greq
	#     return (Gfilt, Gout)

	# def _get_balanced_gains(self, ch):
	#     Gdsp = 1.0 / ( 1.0 - self.lpf_int_ifb_gain)

	#     if ch == 1:
	#         if self._pid_channel == 'main':
	#             Gout = self.ch1_pid1_pidgain * self._dac_gains()[
	#                 ch - 1] * 31.25 /  2.0**4
	#             print('ch1 Gout for pid', Gout)
	#         else:
	#             Gout = self._gainstage_gain #* self._dac_gains()[ch - 1] * 31.25 /  2.0**4
	#             print('ch1 Gout for gainstage', Gout)
	#         Gfilt = self.lpf_int_i_gain_ch1
	#     elif ch == 2:
	#         if self._pid_channel == 'main':
	#             Gout = self._gainstage_gain# * self._dac_gains()[ch - 1] * 31.25 /  2.0**4
	#             print('ch2 Gout for gainstage', Gout)
	#         else:
	#             Gout = self.ch1_pid1_pidgain * self._dac_gains()[
	#                 ch - 1] * 31.25 /  2.0**4
	#             print('ch2 Gout for pid', Gout)
	#         Gfilt = self.lpf_int_i_gain_ch1

	#     print(Gout, Gfilt, Gdsp)
	#     print(Gout * Gfilt * Gdsp)

	#     return Gout * Gfilt * Gdsp

	def _calculate_filt_dsp_gain(self):
		G = 1.0 / ( 1.0 - self.lpf_int_ifb_gain)
		return G

	def _get_filt_gain(self, ch):
		if ch == 'main':
			G = self._remove_adc_gain(ch, self.lpf_int_i_gain_ch1)
		else:
			G = self._remove_adc_gain(ch, self.lpf_int_i_gain_ch2)
		return G

	def _set_filt_gain(self, ch, G):
		if self.r_theta_mode is True:
			self.lpf_int_i_gain_ch1 = self._apply_adc_gain(G)
			self.lpf_int_i_gain_ch2 = self._apply_adc_gain(G)
		elif ch == 'main':
			self.lpf_int_i_gain_ch1 = self._apply_adc_gain(G)
		elif ch == 'aux':
			self.lpf_int_i_gain_ch2 = self._apply_adc_gain(G)

	def _set_output_scaling(self, ch, G):
		if self._pid_channel == ch:
			self.pid.gain = self._apply_dac_gain(ch, G * 2**16)
		else:
			self.gainstage_gain = self._apply_dac_gain(ch, G)

	def _get_output_scaling(self, ch):
		if self._pid_channel == ch:
			G = self._remove_dac_gain(ch, self.pid.gain) / 2.0**16
		else:
			G = self._remove_dac_gain(ch, self.gainstage_gain)
		print('get output scaling, G, ch', G, ch)
		print('get output scaling pid gain, gainstage gain', self.pid.gain, self.gainstage_gain)
		return G

	def _apply_adc_gain(self, gain):
		atten_on = self.get_frontend(1)[1]
		if atten_on is True:
			Gcal = gain * self._adc_gains()[0] * 2**12 / 10
		else:
			Gcal = gain * self._adc_gains()[0] * 2**12
		# print('gain, Gcal', gain, Gcal)
		return Gcal

	def _remove_adc_gain(self, ch, gain):
		if ch == 'main':
			ch_number = 0
		else:
			ch_number = 1
		atten_on = self.get_frontend(1)[1]
		if atten_on is True:
			Guncal = 10 * gain / self._adc_gains()[0] / 2.0**12
		else:
			Guncal = gain / self._adc_gains()[0] / 2.0**12
		return Guncal

	def _apply_dac_gain(self, ch, gain):
		if ch == 'main':
			ch_number = 0
		else:
			ch_number = 1

		Gcal = gain / self._dac_gains()[ch_number] / 2.0**15
		return Gcal

	def _remove_dac_gain(self, ch, gain):
		if ch == 'main':
			ch_number = 0
		else:
			ch_number = 1
		print('in remove dac gain', gain, ch)
		Guncal = gain * self._dac_gains()[ch_number -1] * 2.0**15
		return Guncal

	def _distribute_gain(self, Greq, input_range=0):
		Gdsp = self._calculate_filt_dsp_gain()

		if self.r_theta_mode is False:
			Gfilt, Gout , filt_gain_select = (
				self._calculate_distributed_gain(Greq / Gdsp))
		elif self.r_theta_mode is True:
			Gfilt, filt_gain_select = self._calculate_r_theta_gain(input_range)
			Gout = Greq / 2.0
		# print('in distribute gain, Greq', Greq)
		# print('in distribute gain, Gfilt, Gout, filt_select', Gfilt, Gout, filt_gain_select, Gdsp)
		return (Gfilt, Gout, filt_gain_select)

	def _calculate_distributed_gain(self, Greq):
		gain_threshold = (2**31 - 1) / 2**24
		if Greq > (2**15):
			filt_gain_select = 1
			Gfilt = gain_threshold
			Gout = Greq / 2**8 / Gfilt
		elif Greq > (gain_threshold):
			filt_gain_select = 1
			Gfilt = Greq / 2**8
			Gout = 1
		elif Greq > 2**(-24):
			filt_gain_select = 0
			Gfilt = Greq
			Gout = 1
		else:
			filt_gain_select = 0
			Gfilt = 2**(-24)
			Gout = Greq / Gfilt

		# print('calculate distributed gain Gfilt, Gout, filt_gain_select', Gfilt, Gout, filt_gain_select)
		return (Gfilt, Gout, filt_gain_select)
	def _calculate_r_theta_gain(self, input_range):
		Gdsp = self._calculate_filt_dsp_gain()
		if input_range == 0:
			Gfilt = 1.0 / Gdsp
			filt_gain_select = 0
		elif input_range == 1:
			Gfilt = 2.0**(8) / Gdsp
			filt_gain_select = 0
		elif input_range == 2:
			Gfilt = 2.0**(8) / Gdsp
			filt_gain_select = 1
		else:
			Gfilt = 1.0 / Gdsp
			filt_gain_select = 0

		return (Gfilt, filt_gain_select)

	def _get_required_gain(self, ch):
		Gdsp = self._calculate_filt_dsp_gain()
		Gfilt = self._get_filt_gain(ch)
		Gout = self._get_output_scaling(ch)
		print('in get required gain', Gdsp, Gfilt, Gout)
		Greq = Gout * Gfilt * Gdsp
		return Greq

	def _set_r_theta_mode(self, mode):
		if self.r_theta_mode != mode:
			Gfilt = 1.0 / self._calculate_filt_dsp_gain()
			self.lpf_int_i_gain_ch1 = self.lpf_int_i_gain_ch2 = Gfilt
			self.set_pid_by_gain('main', 1)
			self.set_gain('aux', 1)
		self.r_theta_mode = mode


	def _set_filt_gain_select(self, gain_select, ch=None):
		# print('in filt select gain select', gain_select)
		if self.r_theta_mode is True or ch is None:
			self.filt_gain_select_ch1 = gain_select
			self.filt_gain_select_ch2 = gain_select
		elif ch == 1:
			self.filt_gain_select_ch1 = gain_select
		elif ch == 2:
			self.filt_gain_select_ch2 = gain_select

	# def _set_r_theta_input_range(self, input_range=0):
	#     Gfilt = 2**(8 * input_range) / self._calculate_filt_dsp_gain()
	#     self._set_filt_gain('main', Gfilt)
	#     self._set_filt_gain('aux', Gfilt)
	#     print('input range settings', Gfilt, input_range)
		# self._set_output_scaling('main', Gmain)

	def set_input_range_r_theta(self, input_range=0):

		Gfilt, filt_gain_select = self._calculate_r_theta_gain(input_range)

		self._set_filt_gain_select(filt_gain_select)

		self._set_filt_gain('main', Gfilt)
		self._set_filt_gain('aux', Gfilt)

	# def _set_filter_gains(self, ch, r_theta, Greq, Gdsp):
	#     if r_theta is False:
	#         Gfilt, Gout = self._balance_gains(Greq / Gdsp)
	#         if ch == 'main':
	#             self.lpf_int_i_gain_ch1 = Gfilt
	#         elif ch == 'aux':
	#             self.lpf_int_i_gain_ch2 = Gfilt
	#         else:
	#             self.lpf_int_i_gain_ch1 = Gfilt
	#     elif r_theta is True:

	#         Gfilt = 2**(self.r_theta_input_range * 8) * 1.0 / Gdsp
	#         self.lpf_int_i_gain_ch1 = self.lpf_int_i_gain_ch2 = Gfilt
	#         if ch == 'main':
	#             Gout = Greq /  2**(self.r_theta_input_range * 8)
	#         else:
	#             Gout = Greq
	#         print('in set filter gains')
	#         print(ch, self.r_theta_input_range, Gout, Gfilt)
	#     return Gout

_lia_reg_hdl = {
	'lpf_en':			(REG_LIA_ENABLES,		to_reg_bool(0),
												from_reg_bool(0)),

	'monitor_a_sensitivity_en':
		(REG_LIA_ENABLES,
			to_reg_bool(4),
			from_reg_bool(4)),

	'monitor_b_sensitivity_en':
		(REG_LIA_ENABLES,
			to_reg_bool(5),
			from_reg_bool(5)),

	'ch1_out_en':
		(REG_LIA_ENABLES,
			to_reg_bool(8),
			from_reg_bool(8)),

	'ch2_out_en': 		(REG_LIA_ENABLES, 		to_reg_bool(9),
												from_reg_bool(9)),

	'lpf_den':			(REG_LIA_ENABLES,		to_reg_bool(10),
												from_reg_bool(10)),

	'ch1_signal_en':
		(REG_LIA_ENABLES,
			to_reg_bool(14),
			from_reg_bool(14)),

	'ch2_signal_en':
		(REG_LIA_ENABLES,
			to_reg_bool(17),
			from_reg_bool(17)),

	'ext_demod':		(REG_LIA_ENABLES, 		to_reg_bool(18),
												from_reg_bool(18)),

	'lo_PLL':			(REG_LIA_ENABLES, 		to_reg_bool(19),
												from_reg_bool(19)),

	'filt_select':
		(REG_LIA_ENABLES,
			to_reg_unsigned(21, 2),
			from_reg_unsigned(21, 2)),

	'pid_ch_select':	(REG_LIA_ENABLES, 		to_reg_bool(23),
												from_reg_bool(23)),

	'aux_select':		(REG_LIA_ENABLES, 		to_reg_unsigned(26, 2),
												from_reg_unsigned(26, 2)),

	'gain_select':
		(REG_LIA_ENABLES,
			to_reg_unsigned(28, 2),
			from_reg_unsigned(28, 2)),

	'filt_gain_select_ch1':
		(REG_LIA_ENABLES,
			 to_reg_bool(29),
			 from_reg_bool(29)),

	'filt_gain_select_ch2':
		(REG_LIA_ENABLES,
			 to_reg_bool(30),
			 from_reg_bool(30)),

	'main_offset': 		(REG_LIA_OUT_OFFSET1, 	to_reg_signed(0, 16, xform=lambda obj, x: x / obj._dac_gains()[0]),
												  	from_reg_signed(0, 16, xform=lambda obj, x: x * obj._dac_gains()[0])),

	'lpf_pidgain':		(REG_LIA_PIDGAIN1,			to_reg_signed(0, 32, xform=lambda obj, x : x * 2**15),
													from_reg_signed(0, 32, xform=lambda obj, x: x / 2**15)),

	# 'ch1_pid1_pidgain':
	#     (REG_LIA_PIDGAIN2,
	#         to_reg_signed(0, 32, xform=lambda obj, x: x),
	#         from_reg_signed(0, 32, xform=lambda obj, x: x)),

	'r_theta_input_range':
		(97,
			to_reg_unsigned(0, 2),
			from_reg_unsigned(0, 2)),

	'lpf_int_i_gain_ch1':
		(107,
			to_reg_signed(0, 32,
						  xform=lambda obj, x: x * 2.0**24),
			from_reg_signed(0, 32,
							xform=lambda obj, x: x / 2.0**24)),

	'lpf_int_i_gain_ch2':
		(109,
			to_reg_signed(0, 32,
						  xform=lambda obj, x: x *  2.0**24),
			from_reg_signed(0, 32,
							xform=lambda obj, x: x / 2.0**24)),

	'lpf_int_ifb_gain':
		(106,
			to_reg_signed(0, 25,
						  xform=lambda obj, x: x * _LIA_ID_GAINSCALE),
			from_reg_signed(0, 25,
							xform=lambda obj, x: x / _LIA_ID_GAINSCALE)),

	'gainstage_gain':
		(110,
			to_reg_signed(0, 32, xform=lambda obj, x: x * 2.0**16),
			from_reg_signed(0, 32, xform=lambda obj, x: x / 2.0**16)),


	'frequency_demod':	((REG_LIA_FREQDEMOD_H, REG_LIA_FREQDEMOD_L),
												to_reg_unsigned(0, 48, xform=lambda obj, x: x / _LIA_FREQSCALE),
												from_reg_unsigned(0, 48, xform=lambda obj, x: x * _LIA_FREQSCALE)),

	'phase_demod':		((REG_LIA_PHASEDEMOD_H, REG_LIA_PHASEDEMOD_L),
												to_reg_unsigned(0, 48, xform=lambda obj, x: x / (360.0 * _LIA_PHASESCALE)),
												from_reg_unsigned(0, 48, xform=lambda obj, x: x * (360.0 * _LIA_PHASESCALE))),

	'lo_frequency':		((REG_LIA_LO_FREQ_H, REG_LIA_LO_FREQ_L),
												to_reg_unsigned(0, 48, xform=lambda obj, x: x / _LIA_FREQSCALE),
												from_reg_unsigned(0, 48, xform=lambda obj, x: x * _LIA_FREQSCALE)),

	'lo_phase':			((REG_LIA_LO_PHASE_H, REG_LIA_LO_PHASE_L),
												to_reg_unsigned(0, 48, xform=lambda obj, x: x / (360.0 * _LIA_PHASESCALE)),
												to_reg_unsigned(0, 48, xform=lambda	obj, x: x * (360.0 * _LIA_PHASESCALE))),

	'monitor_select0':	(REG_LIA_MONSELECT,		to_reg_unsigned(0, 3, allow_set=[_LIA_MON_NONE, _LIA_MON_IN1, _LIA_MON_I, _LIA_MON_Q, _LIA_MON_OUT, _LIA_MON_AUX, _LIA_MON_IN2, _LIA_MON_DEMOD]),
												from_reg_unsigned(0, 3)),

	'monitor_select1':	(REG_LIA_MONSELECT,		to_reg_unsigned(3, 3, allow_set=[_LIA_MON_NONE, _LIA_MON_IN1, _LIA_MON_I, _LIA_MON_Q, _LIA_MON_OUT, _LIA_MON_AUX, _LIA_MON_IN2, _LIA_MON_DEMOD]),
												from_reg_unsigned(0, 3)),

	'sineout_amp':		(REG_LIA_SINEOUTAMP,	to_reg_unsigned(0, 16, xform=lambda obj, x: x),
												from_reg_unsigned(0, 16, xform=lambda obj, x: x)),

	'aux_offset':	(REG_LIA_SINEOUTOFF,		to_reg_signed(16, 16, xform=lambda obj, x: x / obj._dac_gains()[1]),
												from_reg_signed(16, 16, xform=lambda obj, x: x * obj._dac_gains()[1])),

	'input_gain':		(REG_LIA_INPUT_GAIN,	to_reg_signed(0,32, xform=lambda obj, x: x * 2**15),
												from_reg_signed(0,32, xform=lambda obj, x: x / 2**15)),

	'bandwidth':		(REG_LIA_PM_BW1, 	to_reg_signed(0,5, xform=lambda obj, b: b),
											from_reg_signed(0,5, xform=lambda obj, b: b)),

	'lo_PLL_reset':		(REG_LIA_PM_RESET, 	to_reg_bool(31),
											from_reg_bool(31)),

	'lo_reacquire':		(REG_LIA_PM_REACQ, 	to_reg_bool(0),
											from_reg_bool(0)),

	'pid_sig_select':	(REG_LIA_SIG_SELECT, to_reg_unsigned(0,2),
											from_reg_unsigned(0,2)),

	'gain_sig_select':	(REG_LIA_SIG_SELECT, to_reg_unsigned(2,2),
											 from_reg_unsigned(2,2)),

	'output_decimation':	(REG_LIA_PM_OUTDEC,	to_reg_unsigned(0,17),
												from_reg_unsigned(0,17)),

	'output_shift':			(REG_LIA_PM_OUTSHIFT, 	to_reg_unsigned(17,5),
													from_reg_unsigned(17,5)),

	'autoacquire':		(REG_LIA_PM_AUTOA1, to_reg_bool(0),
											from_reg_bool(0))
}
