import math
import logging
import warnings
warnings.simplefilter('always', DeprecationWarning)

from ._instrument import *
from ._instrument import _usgn, _sgn, deprecated
from . import _utils
from ._trigger import Trigger
from ._sweep_generator import SweepGenerator

log = logging.getLogger(__name__)

REG_BASE_MOD_0       = 43
REG_BASE_MOD_1       = 60
REG_BASE_WAV_0       = 80
REG_BASE_WAV_1       = 104

REG_GATETHRESH_L_CH1 = 76
REG_GATETHRESH_H_CH1 = 77
REG_GATETHRESH_L_CH2 = 78
REG_GATETHRESH_H_CH2 = 79

_WG_WAVE_SINE        = 0
_WG_WAVE_SQUARE      = 1

_WG_MOD_NONE         = 0
_WG_MOD_AMPL         = 1
_WG_MOD_FREQ         = 2
_WG_MOD_PHASE        = 4

_WG_MODSOURCE_INT    = 0
_WG_MODSOURCE_ADC    = 1
_WG_MODSOURCE_DAC    = 2

_WG_FREQSCALE        = 1.0e9 / 2**64
_WG_FREQSCALE_SQR    = 1.0e9 / 2**48
_WG_PERIODSCALE_SQR  = 2**48 - 1
_WG_RISESCALE        = 2**24

_WG_MAX_RISE         = 1.0/(2**39 - 1)
_WG_TIMESCALE        = 1.0 / (2**32 - 1) # Doesn't wrap

_WG_MOD_FREQ_MAX     = 62.5e6
_WG_MOD_DEPTH_MAX    = 2.0**31-1 # 100% modulation depth in bits

_WG_TRIG_ADC1        = 0
_WG_TRIG_ADC2        = 1
_WG_TRIG_DAC1        = 2
_WG_TRIG_DAC2        = 3
_WG_TRIG_EXT         = 4
_WG_TRIG_INTER       = 5

_WG_MOD_ADC1         = 0
_WG_MOD_ADC2         = 1
_WG_MOD_DAC1         = 2
_WG_MOD_DAC2         = 3
_WG_MOD_INTER        = 4
_WG_MOD_GATE         = 5

_WG_GATE_ADC         = 0
_WG_GATE_DAC         = 1
_WG_GATE_SWEEP       = 2
_WG_GATE_EXT         = 3

_WG_TRIG_MODE_OFF    = 0
_WG_TRIG_MODE_GATE   = 1
_WG_TRIG_MODE_START  = 2
_WG_TRIG_MODE_NCYCLE = 3
_WG_TRIG_MODE_SWEEP  = 4

_WG_TRIGLVL_ADC_MAX  = 5.0
_WG_TRIGLVL_ADC_MIN  = -5.0

_WG_TRIGLVL_DAC_MAX  = 1.0
_WG_TRIGLVL_DAC_MIN  = -1.0

class BasicWaveformGenerator(MokuInstrument):
	"""
	.. automethod:: pymoku.instruments.WaveformGenerator.__init__
	"""
	def __init__(self):
		""" Create a new WaveformGenerator instance, ready to be attached to a Moku."""
		super(BasicWaveformGenerator, self).__init__()
		self._register_accessors(_wavegen_reg_handlers)
		self.id = 4
		self.type = "signal_generator"
		self._sweep1 = SweepGenerator(self, REG_BASE_WAV_0 + 3)
		self._sweep2 = SweepGenerator(self, REG_BASE_WAV_1 + 3)
		self.enable_reset_ch1 = False
		self.enable_reset_ch2 = False

	@needs_commit
	def set_defaults(self):
		super(BasicWaveformGenerator, self).set_defaults()
		self.enable_ch1 = True
		self.enable_ch2 = True
		self.out1_amplitude = 0
		self.out2_amplitude = 0
		self.adc1_statuslight = False
		self.adc2_statuslight = False

		# Init channel sweep gens:
		self._set_sweepgenerator(self._sweep1, 0, 0, 0, 0, 0, 0, 0)
		self._set_sweepgenerator(self._sweep2, 0, 0, 0, 0, 0, 0, 0)

		# Disable inputs on hardware that supports it
		self.en_in_ch1 = True
		self.en_in_ch2 = True

		# Configure front end:
		self._set_frontend(channel = 1, fiftyr=True, atten=False, ac=False)
		self._set_frontend(channel = 2, fiftyr=True, atten=False, ac=False)

	def _set_sweepgenerator(self, sweepgen, waveform=None, waitfortrig=None,
		                    frequency=None, offset=None, logsweep=None,
		                    duration=None, holdlast = None):
		sweepgen.waveform = 2
		sweepgen.stop = (2**64 - 1)
		sweepgen.direction = 0

		if waitfortrig != None:
			sweepgen.waitfortrig = waitfortrig

		if offset != None:
			sweepgen.start = offset / 360.0 * (2**64 - 1)

		if frequency != None:
			sweepgen.step = frequency/_WG_FREQSCALE

		if duration != None:
			sweepgen.duration = duration * 125.0e6

		if logsweep != None:
			sweepgen.logsweep = logsweep

		if holdlast != None:
			sweepgen.holdlast = holdlast

	@needs_commit
	def gen_sinewave(self, ch, amplitude, frequency, offset = 0, phase = 0.0):
		""" Generate a Sine Wave with the given parameters on the given channel.

		:type ch: int; {1,2}
		:param ch: Channel on which to generate the wave

		:type amplitude: float, [0.0,2.0] Vpp
		:param amplitude: Waveform peak-to-peak amplitude

		:type frequency: float, [0,250e6] Hz
		:param frequency: Frequency of the wave

		:type offset: float, [-1.0,1.0] Volts
		:param offset: DC offset applied to the waveform

		:type phase: float, [0-360] degrees
		:param phase: Phase offset of the wave

		"""
		_utils.check_parameter_valid('set', ch, [1,2],'output channel')
		_utils.check_parameter_valid('range', amplitude, [0.0, 2.0],'sinewave amplitude','Volts')
		_utils.check_parameter_valid('range', frequency, [0, 250e6],'sinewave frequency', 'Hz')
		_utils.check_parameter_valid('range', offset, [-1.0, 1.0],'sinewave offset', 'Volts')
		_utils.check_parameter_valid('range', phase, [0, 360], 'sinewave phase', 'degrees')

		# Ensure offset does not cause signal to exceed allowable 2.0Vpp range
		upper_voltage = offset + (amplitude / 2.0)
		lower_voltage = offset - (amplitude / 2.0)
		if (upper_voltage > 1.0) or (lower_voltage < -1.0):
			raise ValueOutOfRangeException("Sinewave offset limited by amplitude (max output range 2.0Vpp).")

		if ch == 1:
			self.enable_ch1 = True
			self._set_sweepgenerator(sweepgen = self._sweep1, frequency = frequency, offset = phase)
			self.amplitude_ch1 = amplitude
			self.offset_ch1 = offset
			self.waveform_type_ch1 = _WG_WAVE_SINE
			self.phase_dly_ch1 = (11 * frequency / 125e6) % 1 * 2**32
		elif ch == 2:
			self.enable_ch2 = True
			self._set_sweepgenerator(sweepgen = self._sweep2, frequency = frequency, offset = phase)
			self.amplitude_ch2 = amplitude
			self.offset_ch2 = offset
			self.waveform_type_ch2 = _WG_WAVE_SINE
			self.phase_dly_ch2 = (11 * frequency / 125e6) % 1 * 2**32

	@needs_commit
	def gen_squarewave(self, ch, amplitude, frequency, offset=0.0, duty=0.5, risetime=0.0, falltime=0.0, phase=0.0):
		""" Generate a Square Wave with given parameters on the given channel.

		:type ch: int; {1,2}
		:param ch: Channel on which to generate the wave

		:type amplitude: float, [0, 2.0] volts
		:param amplitude: Waveform peak-to-peak amplitude

		:type frequency: float, [0, 100e6] hertz
		:param frequency: Frequency of the wave

		:type offset: float, [-1.0, 1.0] volts
		:param offset: DC offset applied to the waveform

		:type duty: float, [0, 1.0]
		:param duty: Fractional duty cycle

		:type risetime: float, [0, 1.0]
		:param risetime: Fraction of a cycle taken for the waveform to rise

		:type falltime: float [0, 1.0]
		:param falltime: Fraction of a cycle taken for the waveform to fall

		:type phase: float, degrees 0-360
		:param phase: Phase offset of the wave
		"""
		_utils.check_parameter_valid('set', ch, [1, 2],'output channel')
		_utils.check_parameter_valid('range', amplitude, [0.0, 2.0],'squarewave amplitude','Volts')
		_utils.check_parameter_valid('range', frequency, [0, 100e6],'squarewave frequency', 'Hz')
		_utils.check_parameter_valid('range', offset, [-1.0, 1.0], 'squarewave offset', 'Volts')
		_utils.check_parameter_valid('range', duty, [0, 1.0], 'squarewave duty', 'cycles')
		_utils.check_parameter_valid('range', risetime, [0, 1.0], 'squarewave risetime', 'cycles')
		_utils.check_parameter_valid('range', falltime, [0, 1.0], 'squarewave falltime', 'cycles')
		_utils.check_parameter_valid('range', phase, [0, 360], 'squarewave phase', 'degrees')

		# Ensure offset does not cause signal to exceed allowable 2.0Vpp range
		upper_voltage = offset + (amplitude / 2.0)
		lower_voltage = offset - (amplitude / 2.0)
		if (upper_voltage > 1.0) or (lower_voltage < -1.0):
			raise ValueOutOfRangeException("Squarewave offset limited by amplitude (max output range 2.0Vpp).")

		frequency = float(frequency)

		if duty < risetime:
			raise ValueOutOfRangeException("Squarewave duty too small for given rise time.")
		elif duty + falltime > 1:
			raise ValueOutOfRangeException("Squarewave duty and fall time too big.")

		# ensure duty cycle and fall/rise time combinations don't overflow
		if frequency != 0:

			minedgetime = 4.0e-9 * frequency

			if risetime < minedgetime:
				risetime = minedgetime
				log.warning("WARNING: Risetime restricted to minimum value of 4 ns.")

			if falltime < minedgetime:
				falltime = minedgetime
				log.warning("WARNING: Falltime restricted to minimum value of 4 ns.")

			if duty < minedgetime:
				duty = minedgetime
				log.warning("WARNING: Duty cycle restricted to %s" % duty)

			if duty > 1 - minedgetime:
				duty = 1 - minedgetime
				log.warning("WARNING: Duty cycle restricted to %s" % duty)

			if risetime > 1 - minedgetime:
				risetime = 1 - minedgetime
				log.warning("WARNING: Risetime restricted to maximum value.")

			if falltime > 1 - minedgetime:
				falltime = 1 - minedgetime
				log.warning("WARNING: Falltime restricted to maximum value.")

		else:
			falltime = _WG_MAX_RISE
			risetime = _WG_MAX_RISE

		# Set rise/fall rate and t0, t1 and t2
		t0 = risetime
		t1 = duty
		t2 = duty + falltime

		phase_dly = 0

		if ch == 1:
			self.waveform_type_ch1 = _WG_WAVE_SQUARE
			self.enable_ch1 = True
			self._set_sweepgenerator(sweepgen=self._sweep1, frequency=frequency, offset=phase, holdlast=0)
			self.amplitude_ch1 = amplitude
			self.offset_ch1 = offset

			# This is overdefined, but saves the FPGA doing a tricky division
			self.t0_ch1 = t0
			self.t1_ch1 = t1
			self.t2_ch1 = t2
			self.riserate_ch1 = risetime
			self.fallrate_ch1 = -falltime
			self.phase_dly_ch1 = phase_dly

		elif ch == 2:
			self.waveform_type_ch2 = _WG_WAVE_SQUARE
			self.enable_ch2 = True
			self._set_sweepgenerator(sweepgen=self._sweep2, frequency=frequency, offset=phase, holdlast=0)
			self.amplitude_ch2 = amplitude
			self.offset_ch2 = offset
			self.t0_ch2 = t0
			self.t1_ch2 = t1
			self.t2_ch2 = t2
			self.riserate_ch2 = risetime
			self.fallrate_ch2 = -falltime
			self.phase_dly_ch2 = phase_dly

	@needs_commit
	def gen_rampwave(self, ch, amplitude, frequency, offset=0, symmetry=0.5, phase= 0.0):
		""" Generate a Ramp with the given parameters on the given channel.

		This is a wrapper around the Square Wave generator, using the *riserate* and *fallrate*
		parameters to form the ramp.

		:type ch: int; {1,2}
		:param ch: Channel on which to generate the wave

		:type amplitude: float, [0, 2.0] volts
		:param amplitude: Waveform peak-to-peak amplitude

		:type frequency: float, [0, 100e6] hertz
		:param frequency: Frequency of the wave

		:type offset: float, [-1.0, 1.0] volts
		:param offset: DC offset applied to the waveform

		:type symmetry: float, [0, 1.0]
		:param symmetry: Fraction of the cycle rising.

		:type phase: float, degrees [0, 360]
		:param phase: Phase offset of the wave
		"""
		_utils.check_parameter_valid('set', ch, [1, 2],'output channel')
		_utils.check_parameter_valid('range', amplitude, [0.0, 2.0],'rampwave amplitude','Volts')
		_utils.check_parameter_valid('range', frequency, [0, 100e6],'rampwave frequency', 'Hz')
		_utils.check_parameter_valid('range', offset, [-1.0, 1.0], 'rampwave offset', 'cycles')
		_utils.check_parameter_valid('range', symmetry, [0, 1.0], 'rampwave symmetry', 'fraction')
		_utils.check_parameter_valid('range', phase, [0, 360], 'rampwave phase', 'degrees')

		# Ensure offset does not cause signal to exceed allowable 2.0Vpp range
		upper_voltage = offset + (amplitude / 2.0)
		lower_voltage = offset - (amplitude / 2.0)
		if (upper_voltage > 1.0) or (lower_voltage < -1.0):
			raise ValueOutOfRangeException("Rampwave offset limited by amplitude (max output range 2.0Vpp).")

		self.gen_squarewave(ch, amplitude, frequency,
			offset = offset, duty = symmetry,
			risetime = symmetry,
			falltime = 1 - symmetry,
			phase = phase)

	@needs_commit
	def sync_phase(self):
		"""	Synchronize the phase of both output channels.

		The phase of both channels is reset to their respestive phase offset values.
		"""
		self.enable_reset_ch1 = True
		self.enable_reset_ch2 = True

	@needs_commit
	def gen_off(self, ch=None):
		""" Turn Waveform Generator output(s) off.

		The channel will be turned on when configuring the waveform type but can be turned off
		using this function. If *ch* is None (the default), both channels will be turned off,
		otherwise just the one specified by the argument.

		:type ch: int; {1,2} or None
		:param ch: Channel to turn off, or both.
		"""
		_utils.check_parameter_valid('set', ch, [1,2],'output channel', allow_none=True)

		if ch is None or ch == 1:
			self.enable_ch1 = False

		if ch is None or ch == 2:
			self.enable_ch2 = False


class WaveformGenerator(BasicWaveformGenerator):
	""" Waveform Generator instrument object.

	To run a new Waveform Generator instrument, this should be instantiated and deployed via a connected
	:any:`Moku` object using :any:`deploy_instrument`. Alternatively, a pre-configured instrument object
	can be obtained by discovering an already running Waveform Generator instrument on a Moku:Lab device via
	:any:`discover_instrument`.

	.. automethod:: pymoku.instruments.WaveformGenerator.__init__

	.. attribute:: type
		:annotation: = "signal_generator"

		Name of this instrument.
	"""
	def __init__(self):
		""" Create a new WaveformGenerator instance, ready to be attached to a Moku."""
		super(WaveformGenerator, self).__init__()
		self._register_accessors(_wavegen_mod_reg_handlers)

		# Define any (non-register-mapped) properties that are used when committing
		# as a commit is called when the instrument is set running
		self.trig_volts_ch1 = 0.0
		self.trig_volts_ch2 = 0.0
		self._trigger1 = Trigger(self, 28)
		self._trigger2 = Trigger(self, 45)
		self._sweepmod1 = SweepGenerator(self, 34)
		self._sweepmod2 = SweepGenerator(self, 51)

	@needs_commit
	def set_defaults(self):
		super(WaveformGenerator, self).set_defaults()
		self._init_trig_modulation(1)
		self._init_trig_modulation(2)
		self.phasedly_en_ch1 = 1
		self.phasedly_en_ch2 = 1
		self.sine_trigdly_ch1 = 0
		self.sine_trigdly_ch2 = 0

	def _init_trig_modulation(self, ch):
		# initialise the state of all modules used in modulation/trigger/sweep modes

		if ch == 1:
			# Set AM/FM/PM and sweep enable to zero:
			self.amod_enable_ch1 = False
			self.fmod_enable_ch1 = False
			self.pmod_enable_ch1 = False
			self.sweep_enable_ch1 = False

			# Default trigger module values:
			self._trigger1.trigtype = 0
			self._trigger1.edge = 0
			self._trigger1.pulsetype = 0
			self._trigger1.hysteresis = 0
			self._trigger1.timer = 0
			self._trigger1.holdoff = 0
			self._trigger1.auto_holdoff = 0
			self._trigger1.ntrigger = 0
			self._trigger1.ntrigger_mode = 0
			self._trigger1.level = 0
			self._trigger1.duration = 0

			# Default modulating sweep generator values:
			self._sweepmod1.waveform = 0
			self._sweepmod1.waitfortrig = 0
			self._sweepmod1.holdlast = 0
			self._sweepmod1.direction = 0
			self._sweepmod1.logsweep = 0
			self._sweepmod1.start = 0
			self._sweepmod1.stop = 0
			self._sweepmod1.step = 0
			self._sweepmod1.duration = 0

			# Trigger/modulation/gate source/threshold default values:
			self.trig_source_ch1 = _WG_TRIG_ADC1
			self.mod_source_ch1 = _WG_MOD_ADC1
			self.gate_thresh_ch1 = 0
			self.mod_depth_ch1 = 0

			# Default waveform sweep generator values that are touched in modulation/trigger/sweep modes:
			self._sweep1.waitfortrig = 0
			self._sweep1.duration = 0
			self._sweep1.holdlast = 0

			# Gated mode flag used to toggle amplitude division by 2 on the FPGA
			self.gate_mode_ch1 = 0

			# Trigger mode flag to enable calibration calculations in _update_dependent_regs function
			self.trig_sweep_mode_ch1 = 0

			# Phase delay flag, trig delay flag
			self.phasedly_en_ch1 = 1
			self.sine_trigdly_ch1 = 0

		else:
			# Set AM/FM/PM and sweep enable to zero:
			self.amod_enable_ch2 = False
			self.fmod_enable_ch2 = False
			self.pmod_enable_ch2 = False
			self.sweep_enable_ch2 = False

			# Default trigger module values:
			self._trigger2.trigtype = 0
			self._trigger2.edge = 0
			self._trigger2.pulsetype = 0
			self._trigger2.hysteresis = 0
			self._trigger2.timer = 0
			self._trigger2.holdoff = 0
			self._trigger2.auto_holdoff = 0
			self._trigger2.ntrigger = 0
			self._trigger2.ntrigger_mode = 0
			self._trigger2.level = 0
			self._trigger2.duration = 0

			# Default modulating sweep generator values:
			self._sweepmod2.waveform = 0
			self._sweepmod2.waitfortrig = 0
			self._sweepmod2.holdlast = 0
			self._sweepmod2.direction = 0
			self._sweepmod2.logsweep = 0
			self._sweepmod2.start = 0
			self._sweepmod2.stop = 0
			self._sweepmod2.step = 0
			self._sweepmod2.duration = 0

			# Trigger/modulation/gate source/threshold default values:
			self.trig_source_ch2 = _WG_TRIG_ADC2
			self.mod_source_ch2 = _WG_MOD_ADC2
			self.gate_thresh_ch2 = 0
			self.mod_depth_ch2 = 0

			# Default waveform sweep generator values that are touched in modulation/trigger/sweep modes:
			self._sweep2.waitfortrig = 0
			self._sweep2.duration = 0
			self._sweep2.holdlast = 0

			# Gated mode flag used to toggle amplitude division by 2 on the FPGA
			self.gate_mode_ch2 = 0

			# Trigger mode flag to enable calibration calculations in _update_dependent_regs function
			self.trig_sweep_mode_ch2 = 0

			# Phase delay flag, trig delay flag
			self.phasedly_en_ch2 = 1
			self.sine_trigdly_ch2 = 0

	@needs_commit
	@deprecated(category='param', message="'in' and 'out' trigger sources have been deprecated. Use 'adc1', 'adc2', 'dac1' or 'dac2' instead.")
	def set_trigger(self, ch, mode, ncycles = 1, sweep_start_freq = None, sweep_end_freq = 0,
		            sweep_duration = 1.0e-3, trigger_source = 'adc1', trigger_threshold = 0.0,
		            internal_trig_period = 1.0, internal_trig_high = 0.5):
		""" Configure gated, start, ncycle or sweep trigger mode on target channel.

		The trigger event can come from an ADC input channel, the opposite generated waveform, the external
		trigger input (for hardware that supports that) or a internally-generated clock of configurable
		period.

		The trigger event can be used in several different ways:
		- *gated*: The output waveform is only generated while the trigger is asserted
		- *start*: The output waveform is enabled once the trigger event fires
		- *ncycle*: The output waveform starts at a trigger event and completes the given number of cycles, before turning off and re-arming
		- *sweep*: The trigger event starts the waveform generation at the *sweep_start_freq*, before automatically sweeping the
		frequency to *sweep_end_freq* over the course of *sweep_duration* seconds.

		:type ch: int
		:param ch: target channel.

		:type mode: string, {'gated', 'start', 'ncycle', 'sweep', 'off'}
		:param mode: Select the mode in which the trigger is operated.

		:type ncycles: int, [1, 1e6]
		:param ncycles: integer number of signal repetitions in ncycle mode.

		:type sweep_start_freq: float, [0.0,250.0e6], hertz
		:param sweep_start_freq: starting sweep frequency, set to current waveform frequency if not specified. Value range may vary for different waveforms.

		:type sweep_end_freq: float, [0.0,250.0e6], hertz
		:param sweep_end_freq: finishing sweep frequency. Value range may vary for different waveforms.

		:type sweep_duration: float, [1.0e-3,1000.0], seconds
		:param sweep_duration: sweep duration in seconds.

		:type trigger_source: string {'adc1','adc2', 'dac1', 'dac2', 'external', 'internal', 'in', 'out'}
		:param trigger_source: defines which source should be used as triggering signal. In and out sources are deprecated.

		:type trigger_threshold: float, [-5, 5], volts
		:param trigger_threshold: The threshold value range dependes on the source and the attenution used. Values ranges might be less for different settings.

		:type internal_trig_period: float, [0,1e11], seconds
		:param internal_trig_period: period of the internal trigger clock, if used.

		:type internal_trig_high: float, [0,1e11], seconds
		:param internal_trig_high: High time of the internal trigger clock, if used. Must be less than the internal trigger period.
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'output channel')
		_utils.check_parameter_valid('set', mode, ['gated', 'start', 'ncycle', 'sweep'],'trigger mode')
		_utils.check_parameter_valid('set', trigger_source, ['adc1','adc2', 'dac1', 'dac2', 'external', 'internal', 'in', 'out'], 'trigger source')
		_utils.check_parameter_valid('range', ncycles, [1, 1e6],'ncycles')
		_utils.check_parameter_valid('range', sweep_duration, [0.001, 1000.0],'sweep duration', 'seconds')
		_utils.check_parameter_valid('range', internal_trig_period, [100.0e-9, 1000.0],'internal trigger period', 'seconds')
		_utils.check_parameter_valid('range', internal_trig_high, [10.0e-9, 1000.0],'internal trigger high time', 'seconds')

		if trigger_source in ['in', 'out']:
			warnings.warn(
				message="'in' and 'out' trigger sources have been deprecated. Use 'adc1', 'adc2', 'dac1' or 'dac2' instead.",
				category=DeprecationWarning,
				stacklevel=1
			)

		#'in' and 'out' trigger sources are deprecated sources. Convert to adc/dac source type:
		if ch == 1:
			if trigger_source == 'in':
				trigger_source = 'adc1'
			elif trigger_source == 'out':
				trigger_source = 'dac2'
		if ch == 2:
			if trigger_source == 'in':
				trigger_source = 'adc2'
			elif trigger_source == 'out':
				trigger_source = 'dac1'

		# Can't use current channel as trigger mode source:
		if ch == 1 and trigger_source == 'dac1':
			raise ValueOutOfRangeException("dac1 cannot be used as the trigger source for trigger mode on channel 1.")
		elif ch == 2 and trigger_source == 'dac2':
			raise ValueOutOfRangeException("dac2 cannot be used as the trigger source for trigger mode on channel 2.")

		# Can't use modulation with trigger/sweep modes
		self.set_modulate_trig_off(ch)

		### Configure trigger and source settings:
		if ch == 1 :
			_WG_TRIG_ADC = _WG_TRIG_ADC2
			_WG_TRIG_DAC = _WG_TRIG_DAC1
		else :
			_WG_TRIG_ADC = _WG_TRIG_ADC1
			_WG_TRIG_DAC = _WG_TRIG_DAC2


		_str_to_trigger_source = {
			'adc1'     : _WG_TRIG_ADC1,
			'adc2'     : _WG_TRIG_ADC2,
			'dac1'     : _WG_TRIG_DAC1,
			'dac2'     : _WG_TRIG_DAC2,
			'external' : _WG_TRIG_EXT,
			'internal' : _WG_TRIG_INTER
		}

		trigger_source = _utils.str_to_val(_str_to_trigger_source, trigger_source, 'trigger source')

		if trigger_source is _WG_TRIG_ADC:
			_utils.check_parameter_valid('range', trigger_threshold, [_WG_TRIGLVL_ADC_MIN, _WG_TRIGLVL_ADC_MAX], 'trigger threshold', 'Volts')
		elif trigger_source is _WG_TRIG_DAC:
			_utils.check_parameter_valid('range', trigger_threshold, [_WG_TRIGLVL_DAC_MIN, _WG_TRIGLVL_DAC_MAX], 'trigger threshold', 'Volts')

		# The internal trigger's duty cycle is only used in gated burst mode. Duty cycle is limited such that the duty period is not
		# less than 8 ns and not greater than the trigger period minus 8 ns.

		if internal_trig_high > internal_trig_period:
			raise ValueOutOfRangeException("Internal trigger high must be less than or equal to the internal trigger period.")

		if (internal_trig_period - internal_trig_high) <= 8.0e-9:
			internal_trig_high = internal_trig_period - 10.0e-9

		if ch == 1:
			self._trigger1.trigtype = 0
			self._trigger1.edge = 0
			self.trig_sweep_mode_ch1 = 1
		elif ch == 2:
			self._trigger1.trigtype = 0
			self._trigger1.edge = 0
			self.trig_sweep_mode_ch2 = 1

		#### Configure trigger mode settings:

		_str_to_trigger_mode = {
			'gated' : _WG_TRIG_MODE_GATE,
			'start' : _WG_TRIG_MODE_START,
			'ncycle' : _WG_TRIG_MODE_NCYCLE,
			'sweep'	: _WG_TRIG_MODE_SWEEP
		}
		mode = _utils.str_to_val(_str_to_trigger_mode, mode, 'trigger mode')

		# set status light register
		if ch == 1:
			self.adc1_statuslight = True if trigger_source == _WG_TRIG_ADC1 else False
		else:
			self.adc2_statuslight = True if trigger_source == _WG_TRIG_ADC2 else False

		if sweep_start_freq is None or mode != _WG_TRIG_MODE_SWEEP:
			channel_frequency = (self._sweep1.step * _WG_FREQSCALE) if ch == 1 else (self._sweep2.step * _WG_FREQSCALE)
		else:
			channel_frequency = sweep_start_freq

		waveform = self.waveform_type_ch1 if ch == 1 else self.waveform_type_ch2

		#if waveform is a sinewave certain ranges do change
		if waveform == _WG_WAVE_SINE:
			_utils.check_parameter_valid('range', sweep_end_freq, [0.0, 250.0e6],'sweep finishing frequency','frequency')
			_utils.check_parameter_valid('range', channel_frequency, [0.0, 250.0e6],'sweep starting frequency','frequency')
		else:
			_utils.check_parameter_valid('range', sweep_end_freq, [0.0, 100.0e6],'sweep finishing frequency','frequency')
			_utils.check_parameter_valid('range', channel_frequency, [0.0, 100.0e6],'sweep starting frequency','frequency')

		# minimum frequency deviation in sweep mode is 1 mHz
		if abs(channel_frequency - sweep_end_freq) < 1.0e-3:
			raise ValueOutOfRangeException("Frequency deviation in sweep mode is restricted to values greater than 1 mHz.")

		if mode == _WG_TRIG_MODE_GATE:
			self._set_trigger_gated(ch, waveform, trigger_source, trigger_threshold, internal_trig_period, internal_trig_high)
		elif mode == _WG_TRIG_MODE_START:
			self._set_trigger_start(ch, trigger_source, trigger_threshold)
		elif mode == _WG_TRIG_MODE_NCYCLE:
			self._set_trigger_ncycle(ch, channel_frequency, ncycles, trigger_threshold, trigger_source, internal_trig_period)
		elif mode == _WG_TRIG_MODE_SWEEP:
			self._set_trigger_sweep(ch, waveform, trigger_source, sweep_end_freq, channel_frequency, sweep_duration, trigger_threshold)

	def _set_trigger_gated(self, ch, waveform, trigger_source, trigger_threshold, internal_trig_period, internal_trig_high):

		# Threshold calculations. Calibration is applied in _update_dependent_regs
		if trigger_source == _WG_TRIG_EXT:
			trigger_threshold = 0
		elif trigger_source == _WG_TRIG_INTER:
			trigger_threshold = -2**47 + (1.0 - internal_trig_high / internal_trig_period) * (2**48-1)
			if ch == 1:
				self._sweepmod1.step = 1/internal_trig_period / _WG_FREQSCALE
				self._sweepmod1.waveform = 2
				self._sweepmod1.direction = 1
			else:
				self._sweepmod2.step = 1/internal_trig_period / _WG_FREQSCALE
				self._sweepmod2.waveform = 2
				self._sweepmod2.direction = 1

		if ch == 1:
			self.amod_enable_ch1 = True
			self.mod_source_ch1 = _WG_MOD_GATE
			self.mod_depth_uncalibrated_ch1 = 1.0
			self._sweep1.waitfortrig = 0
			self.trig_source_ch1 = trigger_source
			self.gate_thresh_uncalibrated_ch1 = trigger_threshold
			self.gate_mode_ch1 = 1
		elif ch == 2:
			self.amod_enable_ch2 = True
			self.mod_source_ch2 = _WG_MOD_GATE
			self.mod_depth_uncalibrated_ch2 = 1.0
			self._sweep2.waitfortrig = 0
			self.trig_source_ch2 = trigger_source
			self.gate_thresh_uncalibrated_ch2 = trigger_threshold
			self.gate_mode_ch2 = 1

	def _set_trigger_start(self, ch, trigger_source, trigger_threshold):
		# Internal trigger source cannot be used for burst start mode:
		if trigger_source == _WG_TRIG_INTER:
			raise ValueOutOfRangeException("The internal trigger source cannot be used in start burst mode.")

		# Calculate threshold level and configure modulating sweep generator. Calibration is added to threshold in _set_dependent_regs.
		if trigger_source == _WG_TRIG_EXT:
			trigger_threshold = 0
			if ch == 1:
				self._sweepmod1.direction = 1
			elif ch == 2:
				self._sweepmod2.direction = 1

		if ch == 1:
			self.trigger_threshold_uncalibrated_ch1 = trigger_threshold
			self.trig_source_ch1 = trigger_source
			self._sweep1.waitfortrig = 1
			self._sweep1.duration = 0
			self.enable_reset_ch1 = True
			self.phasedly_en_ch1 = 0
			self.sine_trigdly_ch1 = 1 if self.waveform_type_ch1 == _WG_WAVE_SINE else 0

		elif ch == 2:
			self.trigger_threshold_uncalibrated_ch2 = trigger_threshold
			self.trig_source_ch2 = trigger_source
			self._sweep2.waitfortrig = 1
			self._sweep2.duration = 0
			self.enable_reset_ch2 = True
			self.phasedly_en_ch2 = 0
			self.sine_trigdly_ch2 = 1 if self.waveform_type_ch2 == _WG_WAVE_SINE else 0

	def _set_trigger_ncycle(self, ch, channel_frequency, ncycles, trigger_threshold, trigger_source, internal_trig_period):
		# Waveform frequencies are restricted to <= 10 MHz in Ncycle burst mode:
		if channel_frequency > 10.0e6:
			raise ValueOutOfRangeException("Waveform frequencies are restricted to 10 MHz or less in Ncycle burst mode.")

		# Calculate threshold level and configure modulating sweep generator. Calibration is added to threshold in _set_dependent_regs.
		if trigger_source == _WG_TRIG_EXT:
			trigger_threshold = 0
		elif trigger_source == _WG_TRIG_INTER:
			trigger_threshold = 0
			if ch == 1:
				self._set_sweepgenerator(sweepgen=self._sweepmod1, waveform=2,
					waitfortrig=0, frequency=1.0/internal_trig_period, offset=0, logsweep=0, duration=0, holdlast=0)
				self._sweepmod1.direction = 1
			elif ch == 2:
				self._set_sweepgenerator(sweepgen=self._sweepmod2, waveform=2,
					waitfortrig=0, frequency=1.0/internal_trig_period, offset=0, logsweep=0, duration=0, holdlast=0)
				self._sweepmod2.direction = 1

		# ensure combination of signal frequency and Ncycles doesn't cause 64 bit register overflow:
		FPGA_cycles = (math.floor(125e6 / channel_frequency * ncycles) - 1) if channel_frequency != 0.0 else 0
		if FPGA_cycles > 2**63-1:
			raise ValueOutOfRangeException("NCycle Register Overflow")

		if ch == 1:
			self.trigger_threshold_uncalibrated_ch1 = trigger_threshold
			self.trig_source_ch1 = trigger_source
			self._sweep1.waitfortrig = 1
			self._sweep1.duration = FPGA_cycles
			self._sweep1.holdlast = 0
			self.enable_reset_ch1 = True
			self.phasedly_en_ch1 = 0
			self.sine_trigdly_ch1 = 1 if self.waveform_type_ch1 == _WG_WAVE_SINE else 0

		elif ch == 2:
			self.trigger_threshold_uncalibrated_ch2 = trigger_threshold
			self.trig_source_ch2 = trigger_source
			self._sweep2.waitfortrig = 1
			self._sweep2.duration = FPGA_cycles
			self._sweep2.holdlast = 0
			self.enable_reset_ch2 = True
			self.phasedly_en_ch2 = 0
			self.sine_trigdly_ch2 = 1 if self.waveform_type_ch2 == _WG_WAVE_SINE else 0

	def _set_trigger_sweep(self, ch, waveform, trigger_source, sweep_end_freq, channel_frequency, sweep_duration, trigger_threshold):

		# Calculate threshold level and enable/disable continuous sweep. Calibration is added to threshold in _set_dependent_regs.
		if trigger_source == _WG_TRIG_EXT:
			trigger_threshold = 0
			mod_continuous_sweep = 1
		elif trigger_source == _WG_TRIG_INTER:
			trigger_threshold = 1
			mod_continuous_sweep = 0
		else:
			mod_continuous_sweep = 1

		# calculate sweep parameters:
		mod_start_freq = 0
		range_shift = 0
		deltafreq_persecond = (sweep_end_freq - channel_frequency)/sweep_duration
		mod_step = abs(2.0**64 / 1e18 * deltafreq_persecond)
		mod_duration_FPGAcycles = math.floor(sweep_duration * 125e6)
		mod_stop_freq = mod_step * 1e9 * sweep_duration

		range_shift = min(math.floor(abs(math.log(max(mod_step / 2.0**64, mod_stop_freq / 2.0**64), 2))), 63)
		mod_step *= 2**range_shift
		mod_stop_freq *= 2**range_shift

		# check if reverse sweep:
		if (sweep_end_freq - channel_frequency) < 0:
			mod_direction = 1
		else:
			mod_direction = 0

		if ch == 1:
			self._set_sweepgenerator(sweepgen=self._sweep1, frequency=channel_frequency, waitfortrig=0)
			self._sweepmod1.waitfortrig = mod_continuous_sweep
			self._sweepmod1.start = mod_start_freq
			self._sweepmod1.stop = mod_stop_freq
			self._sweepmod1.step = mod_step
			self._sweepmod1.duration = mod_duration_FPGAcycles
			self._sweepmod1.direction = 0
			self.reverse_sweep_ch1 = mod_direction
			self._sweepmod1.waveform = 2
			self._sweepmod1.holdlast = 0
			self.amod_enable_ch1 = False
			self.pmod_enable_ch1 = False
			self.fmod_enable_ch1 = False
			self.sweep_enable_ch1 = True
			self.trig_source_ch1 = trigger_source
			self.trigger_threshold_uncalibrated_ch1 = trigger_threshold

			self.range_shift_ch1 = range_shift
		else:
			self._set_sweepgenerator(sweepgen=self._sweep2, frequency=channel_frequency, waitfortrig=0)
			self._sweepmod2.waitfortrig = mod_continuous_sweep
			self._sweepmod2.start = mod_start_freq
			self._sweepmod2.stop = mod_stop_freq
			self._sweepmod2.step = mod_step
			self._sweepmod2.duration = mod_duration_FPGAcycles
			self._sweepmod2.direction = 0
			self.reverse_sweep_ch2 = mod_direction
			self._sweepmod2.waveform = 2
			self._sweepmod2.holdlast = 0
			self.amod_enable_ch2 = False
			self.pmod_enable_ch2 = False
			self.fmod_enable_ch2 = False
			self.sweep_enable_ch2 = True
			self.trig_source_ch2 = trigger_source
			self.trigger_threshold_uncalibrated_ch2 = trigger_threshold

			self.range_shift_ch2 = range_shift

	@needs_commit
	@deprecated(category='method', message="'gen_modulate_off' has been deprecated. Use set_modulate_trig_off instead.")
	def gen_modulate_off(self, ch=None):
		"""
		'gen_modulate_off' has been deprecated. Use set_modulate_trig_off instead.

		Turn off modulation for the specified output channel.

		If *ch* is None (the default), both channels will be turned off,
		otherwise just the one specified by the argument.

		:type ch: int; {1,2} or None
		:param ch: Output channel to turn modulation off.
		"""
		# warnings.warn("'gen_modulate_off' has been deprecated. Use set_modulate_trig_off instead.", DeprecationWarning)
		self.set_modulate_trig_off(ch)

	@needs_commit
	@deprecated(category='method', message="'gen_trigger_off' has been deprecated. Use set_modulate_trig_off instead.")
	def gen_trigger_off(self, ch=None):
		"""
		'gen_trigger_off' has been deprecated. Use set_modulate_trig_off instead."

		Turn off trigger/sweep mode for the specified output channel.

		If *ch* is None (the default), both channels will be turned off,
		otherwise just the one specified by the argument.

		:type ch: int; {1,2} or None
		:param ch: Output channel to turn trigger/sweep mode off
		"""
		# warnings.warn("'gen_trigger_off' has been deprecated. Use set_modulate_trig_off instead.", DeprecationWarning)
		self.set_modulate_trig_off(ch)

	@needs_commit
	def set_modulate_trig_off(self, ch=None):
		"""
		Turn off modulation and trigger modes for the specified output channel.

		If *ch* is None (the default), both channels will be turned off,
		otherwise just the one specified by the argument.

		:type ch: int; {1,2} or None
		:param ch: Output channel to turn modulation off.
		"""
		_utils.check_parameter_valid('set', ch, [1, 2],'output channel', allow_none=True)

		self._init_trig_modulation(ch)

	@needs_commit
	@deprecated(category='param', message="'in' and 'out' modulation sources have been deprecated. Use 'adc1', 'adc2', 'dac1' or 'dac2' instead.")
	def gen_modulate(self, ch, mtype, source, depth, frequency=0.0):
		"""
		Set up modulation on an output channel.

		:type ch: int; {1,2}
		:param ch: Channel to modulate

		:type mtype: string, {'amplitude', 'frequency', 'phase'}
		:param mtype:  Modulation type. Respectively Off, Amplitude, Frequency and Phase modulation.

		:type source: string, {'adc1', 'adc2', 'dac1', 'dac2', 'internal', 'in', 'out'}
		:param source: Modulation source. Respectively Internal Sinewave, associated input channel or opposite output channel. In and out sources are deprecated.

		:type depth: float 0-1, 0-125MHz or 0 - 360 deg
		:param depth: Modulation depth (depends on modulation type): Fractional modulation depth, Frequency Deviation/Volt or +/- phase shift/Volt

		:type frequency: float
		:param frequency: Frequency of internally-generated sine wave modulation. This parameter is ignored if the source is set to ADC or DAC.

		:raises ValueOutOfRangeException: if the channel number is invalid or modulation parameters can't be achieved
		"""
		_utils.check_parameter_valid('set', ch, [1, 2],'modulation channel')
		_utils.check_parameter_valid('range', frequency, [0, 250e6],'internal modulation frequency')
		_utils.check_parameter_valid('set', mtype, ['amplitude', 'frequency', 'phase'],'modulation type')
		_utils.check_parameter_valid('set', source, ['adc1', 'adc2', 'dac1', 'dac2', 'internal', 'in', 'out'],'modulation source')

		if source in ['in', 'out']:
			warnings.warn(
				message="'in' and 'out' modulation sources have been deprecated. Use 'adc1', 'adc2', 'dac1' or 'dac2' instead.",
				category=DeprecationWarning,
				stacklevel=1
			)

		#'in' and 'out' sources are deprecated sources. Convert to adc/dac source type:
		if ch == 1:
			if source == 'in':
				source = 'adc1'
			elif source == 'out':
				source = 'dac2'
		if ch == 2:
			if source == 'in':
				source = 'adc2'
			elif source == 'out':
				source = 'dac1'

		# Can't use current channel as trigger mode source:
		if ch == 1 and source == 'dac1':
			raise ValueOutOfRangeException("dac1 cannot be used as the modulation source for channel 1.")
		elif ch == 2 and source == 'dac2':
			raise ValueOutOfRangeException("dac2 cannot be used as the modulation source for channel 2.")

		_str_to_modsource = {
			'adc1'     : _WG_MOD_ADC1,
			'adc2'     : _WG_MOD_ADC2,
			'dac1'     : _WG_MOD_DAC1,
			'dac2'     : _WG_MOD_DAC2,
			'internal' : _WG_MOD_INTER
		}

		_str_to_modtype = {
			'amplitude' : _WG_MOD_AMPL,
			'frequency' : _WG_MOD_FREQ,
			'phase'     : _WG_MOD_PHASE
		}
		source = _utils.str_to_val(_str_to_modsource, source, 'modulation source')
		mtype = _utils.str_to_val(_str_to_modtype, mtype, 'modulation source')

		# Maximum achievable modulation depth is limited when frontend attenuation is not enabled
		if self.atten_compensate_ch1 == 0:
			logging.warning("+/- 0.5 V voltage range is selected on input channel 1. Maximum achievable modulation depth may be limited.")
		if self.atten_compensate_ch2 == 0:
			logging.warning("+/- 0.5 V voltage range is selected on input channel 2. Maximum achievable modulation depth may be limited.")

		# Calculate the depth value depending on modulation source and type. Calibration calculations for frontend variations done in _update_dependent_regs.
		depth_parameter = 0.0
		if mtype == _WG_MOD_AMPL:
			_utils.check_parameter_valid('range', depth, [0.0, 1.0], 'amplitude modulation depth', 'fraction')
			depth_parameter = depth

		elif mtype == _WG_MOD_FREQ:
			_utils.check_parameter_valid('range', depth, [0.0,_WG_MOD_FREQ_MAX], 'frequency modulation depth', 'Hz/V')
			depth_parameter = depth / (DAC_SMP_RATE / 8.0)

		elif mtype == _WG_MOD_PHASE:
			_utils.check_parameter_valid('range', depth, [0.0, 360.0], 'phase modulation depth', 'degrees/V')
			depth_parameter = depth / 360.0

		# Can't use trigger/sweep modes at the same time as modulation
		self.set_modulate_trig_off(ch)

		if ch == 1:
			self.mod_depth_uncalibrated_ch1 = depth_parameter
			self.mod_source_ch1 = source
			self.amod_enable_ch1 = True if mtype == _WG_MOD_AMPL else False
			self.fmod_enable_ch1 = True if mtype == _WG_MOD_FREQ else False
			self.pmod_enable_ch1 = True if mtype == _WG_MOD_PHASE else False
			self.sweep_enable_ch1 = False
			if source == _WG_MOD_INTER:
				self._set_sweepgenerator(sweepgen=self._sweepmod1, waveform=2, waitfortrig=0,
					frequency=frequency, offset=0, logsweep=0, duration=0)
			self.adc1_statuslight = True if source == _WG_MODSOURCE_ADC else False
		elif ch == 2:
			self.mod_depth_uncalibrated_ch2 = depth_parameter
			self.mod_source_ch2 = source
			self.amod_enable_ch2 = True if mtype == _WG_MOD_AMPL else False
			self.fmod_enable_ch2 = True if mtype == _WG_MOD_FREQ else False
			self.pmod_enable_ch2 = True if mtype == _WG_MOD_PHASE else False
			self.sweep_enable_ch2 = False
			if source == _WG_MOD_INTER:
				self._set_sweepgenerator(sweepgen=self._sweepmod2, waveform=2, waitfortrig=0, frequency=frequency, offset=0, logsweep=0, duration=0)
			self.adc2_statuslight = True if source == _WG_MODSOURCE_ADC else False

	def _get_mod_depth_uncalibrated(self, ch):
		# Calculate mod depth based on instrument state. Used when connecting to running device.

		dac1, dac2 = self._dac_gains()
		adc1, adc2 = self._adc_gains()

		mod_source_scalers = [2.0**11 / (8.0 if self.atten_compensate_ch1 else 1.0) * adc1,
		                      2.0**11 / (8.0 if self.atten_compensate_ch2 else 1.0) * adc2,
		                      2.0**14 * dac1,
		                      2.0**14 * dac2,
		                      1.0,
		                      1.0]

		if ch == 1:
			mod_depth_uncalibrated = self.mod_depth_ch1 / mod_source_scalers[self.mod_source_ch1] / _WG_MOD_DEPTH_MAX
		else:
			mod_depth_uncalibrated = self.mod_depth_ch2 / mod_source_scalers[self.mod_source_ch2] / _WG_MOD_DEPTH_MAX
		return mod_depth_uncalibrated

	def _get_gate_thresh_uncalibrated(self, ch):
		# Calculate gate threshold based on instrument state. Used when connecting to running device.

		dac1, dac2 = self._dac_gains()
		adc1, adc2 = self._adc_gains()

		gate_source_scalers = [adc1, adc2, dac1 * 16, dac2 * 16, 1.0, 1.0]

		if ch == 1:
			gate_thresh_uncalibrated = self.gate_thresh_ch1 * gate_source_scalers[self.trig_source_ch1]
		else:
			gate_thresh_uncalibrated = self.gate_thresh_ch2 * gate_source_scalers[self.trig_source_ch2]
		return gate_thresh_uncalibrated

	def _get_trig_thresh_uncalibrated(self, ch):
		# Calculate trig threshold based on instrument state. Used when connecting to running device.

		dac1, dac2 = self._dac_gains()
		adc1, adc2 = self._adc_gains()

		trig_source_scalers = [adc1, adc2, dac1 * 16, dac2 * 16, 1.0, 1.0]

		if ch == 1:
			trig_threshold_uncalibrated = self._trigger1.level * trig_source_scalers[self.trig_source_ch1]
		else:
			trig_threshold_uncalibrated = self._trigger2.level * trig_source_scalers[self.trig_source_ch2]
		return trig_threshold_uncalibrated


	def _update_dependent_regs(self):
		# Get the calibration coefficients of the front end
		dac1, dac2 = self._dac_gains()
		adc1, adc2 = self._adc_gains()

		# Frontend attenuation flag for modulation
		self.atten_compensate_ch1 = 1 if self._get_frontend(1)[1] else 0
		self.atten_compensate_ch2 = 1 if self._get_frontend(2)[1] else 0

		# Scaling source parameter arrays for each trigger/modulation mode.
		mod_source_scalers = [2.0**11 / (8.0 if self.atten_compensate_ch1 else 1.0) * adc1,
		                      2.0**11 / (8.0 if self.atten_compensate_ch2 else 1.0) * adc2,
		                      2.0**14 * dac1,
		                      2.0**14 * dac2,
		                      1.0,
		                      1.0]
		gate_source_scalers = [adc1, adc2, dac1 * 16, dac2 * 16, 1.0, 1.0]
		trig_source_scalers = [adc1, adc2, dac1 * 16, dac2 * 16, 1.0, 1.0]

		# Channel 1 modulation depth
		if (self.amod_enable_ch1 == True or self.pmod_enable_ch1 == True or self.fmod_enable_ch1 == True):

			try:
				self.mod_depth_uncalibrated_ch1
			except AttributeError:
				self.mod_depth_uncalibrated_ch1 = self._get_mod_depth_uncalibrated(1)

			self.mod_depth_ch1 = self.mod_depth_uncalibrated_ch1 * mod_source_scalers[self.mod_source_ch1] * _WG_MOD_DEPTH_MAX

		# Channel 2 modulation depth
		if (self.amod_enable_ch2 == True or self.pmod_enable_ch2 == True or self.fmod_enable_ch2 == True):

			try:
				self.mod_depth_uncalibrated_ch2
			except AttributeError:
				self.mod_depth_uncalibrated_ch2 = self._get_mod_depth_uncalibrated(2)

			self.mod_depth_ch2 = self.mod_depth_uncalibrated_ch2 * mod_source_scalers[self.mod_source_ch2] * _WG_MOD_DEPTH_MAX

		# Channel 1 gate threshold
		if self.gate_mode_ch1 == 1:
			try:
				self.gate_thresh_uncalibrated_ch1
			except AttributeError:
				self.gate_thresh_uncalibrated_ch1 = self._get_gate_thresh_uncalibrated(1)

			self.gate_thresh_ch1 = self.gate_thresh_uncalibrated_ch1 / gate_source_scalers[self.trig_source_ch1]

		# Channel 2 gate threshold
		if self.gate_mode_ch2 == 1:

			try:
				self.gate_thresh_uncalibrated_ch2
			except AttributeError:
				self.gate_thresh_uncalibrated_ch2 = self._get_gate_thresh_uncalibrated(2)

			self.gate_thresh_ch2 = self.gate_thresh_uncalibrated_ch2 / gate_source_scalers[self.trig_source_ch2]

		# Channel 1 N cycle/start/sweep mode trigger threshold
		if (self.trig_sweep_mode_ch1 == 1 and self.gate_mode_ch1 != 1):

			try:
				self.trigger_threshold_uncalibrated_ch1
			except AttributeError:
				self.trigger_threshold_uncalibrated_ch1 = self._get_trig_thresh_uncalibrated(1)

			self._trigger1.level = self.trigger_threshold_uncalibrated_ch1 / trig_source_scalers[self.trig_source_ch1]

		# Channel 2 N cycle/start/sweep mode trigger threshold
		if (self.trig_sweep_mode_ch2 == 1 and self.gate_mode_ch2 != 1):

			try:
				self.trigger_threshold_uncalibrated_ch2
			except AttributeError:
				self.trigger_threshold_uncalibrated_ch2 = self._get_trig_thresh_uncalibrated(2)

			self._trigger2.level = self.trigger_threshold_uncalibrated_ch2 / trig_source_scalers[self.trig_source_ch2]


	def commit(self):
		self._update_dependent_regs()

		# Commit the register values to the device
		super(WaveformGenerator, self).commit()

	# Bring in the docstring from the superclass for our docco.
	commit.__doc__ = MokuInstrument.commit.__doc__

_wavegen_reg_handlers = {
	# channel 1 control:

	# modulation controls
	'adc1_statuslight':     (REG_BASE_MOD_0, to_reg_unsigned(0,1),  from_reg_unsigned(0,1)),
	'amod_enable_ch1':      (REG_BASE_MOD_0, to_reg_unsigned(1,1),  from_reg_unsigned(1,1)),
	'fmod_enable_ch1':      (REG_BASE_MOD_0, to_reg_unsigned(2,1),  from_reg_unsigned(2,1)),
	'pmod_enable_ch1':      (REG_BASE_MOD_0, to_reg_unsigned(3,1),  from_reg_unsigned(3,1)),
	'sweep_enable_ch1':     (REG_BASE_MOD_0, to_reg_unsigned(4,1),  from_reg_unsigned(4,1)),
	'reverse_sweep_ch1':    (REG_BASE_MOD_0, to_reg_unsigned(5,1),  from_reg_unsigned(5,1)),
	'mod_source_ch1':       (REG_BASE_MOD_0, to_reg_unsigned(6,3),  from_reg_unsigned(6,3)),
	'atten_compensate_ch1': (REG_BASE_MOD_0, to_reg_unsigned(9,1),  from_reg_unsigned(9,1)),
	'trig_source_ch1':      (REG_BASE_MOD_0, to_reg_unsigned(10,3), from_reg_unsigned(10,3)),
	'range_shift_ch1':      (REG_BASE_MOD_0, to_reg_unsigned(13,6), from_reg_unsigned(13,6)),
	'sine_trigdly_ch1':     (REG_BASE_MOD_0, to_reg_unsigned(19,1), from_reg_unsigned(19,1)),
	'phasedly_en_ch1':      (REG_BASE_MOD_0, to_reg_unsigned(20,1), from_reg_unsigned(20,1)),
	'trig_sweep_mode_ch1':  (REG_BASE_MOD_0, to_reg_unsigned(29,1), from_reg_unsigned(29,1)),
	'gate_mode_ch1':        (REG_BASE_MOD_0, to_reg_unsigned(30,1), from_reg_unsigned(30,1)),
	'mod_depth_ch1':        (REG_BASE_MOD_0 + 1, to_reg_unsigned(0,32), from_reg_unsigned(0,32)),
	'gate_thresh_ch1':     ((REG_GATETHRESH_H_CH1, REG_GATETHRESH_L_CH1),
	                           to_reg_signed(16,48), from_reg_signed(16,48)),

	# waveform controls
	'enable_ch1':        (REG_BASE_WAV_0, to_reg_unsigned(0,1), from_reg_unsigned(0,1)),
	'waveform_type_ch1': (REG_BASE_WAV_0, to_reg_unsigned(1,1), from_reg_unsigned(1,1)),

	'amplitude_ch1':     (REG_BASE_WAV_0 + 1,
	                        to_reg_signed(0, 18, xform=lambda obj, a: 2 * a / obj._dac_gains()[0]),
	                        from_reg_signed(0, 18, xform=lambda obj, a: 2 * a * obj._dac_gains()[0])),
	'offset_ch1':        (REG_BASE_WAV_0 + 2,
	                        to_reg_signed(0,16, xform=lambda obj, a: a / obj._dac_gains()[0]),
	                        from_reg_signed(0,16, xform=lambda obj, a: a * obj._dac_gains()[0])),
	't0_ch1':           ((REG_BASE_WAV_0 + 13, REG_BASE_WAV_0 + 12),
	                        to_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR),
	                        from_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR)),
	't1_ch1':           ((REG_BASE_WAV_0 + 15, REG_BASE_WAV_0 + 14),
	                        to_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR),
	                        from_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR)),
	't2_ch1':           ((REG_BASE_WAV_0 + 17, REG_BASE_WAV_0 + 16),
	                        to_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR),
	                        from_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR)),
	'riserate_ch1':     ((REG_BASE_WAV_0 + 19, REG_BASE_WAV_0 + 18),
	                        to_reg_signed(0, 64, xform = lambda obj, o: (o**-1) * _WG_RISESCALE),
	                        from_reg_signed(0, 64, xform = lambda obj, o: (o / _WG_RISESCALE)**-1)),
	'fallrate_ch1':     ((REG_BASE_WAV_0 + 21, REG_BASE_WAV_0 + 20),
	                        to_reg_signed(0, 64, xform = lambda obj, o: (o**-1) * _WG_RISESCALE),
	                        from_reg_signed(0, 64, xform = lambda obj, o: (o / _WG_RISESCALE)**-1)),
	'enable_reset_ch1':  (REG_BASE_WAV_0 + 22, to_reg_unsigned(0,1), from_reg_unsigned(0,1)),
	'phase_dly_ch1':     (REG_BASE_WAV_0 + 23, to_reg_unsigned(0, 32), from_reg_unsigned(0, 32)),

	# channel 2 control:

	# modulation controls
	'adc2_statuslight':     (REG_BASE_MOD_1, to_reg_unsigned(0,1),  from_reg_unsigned(0,1)),
	'amod_enable_ch2':      (REG_BASE_MOD_1, to_reg_unsigned(1,1),  from_reg_unsigned(1,1)),
	'fmod_enable_ch2':      (REG_BASE_MOD_1, to_reg_unsigned(2,1),  from_reg_unsigned(2,1)),
	'pmod_enable_ch2':      (REG_BASE_MOD_1, to_reg_unsigned(3,1),  from_reg_unsigned(3,1)),
	'sweep_enable_ch2':     (REG_BASE_MOD_1, to_reg_unsigned(4,1),  from_reg_unsigned(4,1)),
	'reverse_sweep_ch2':    (REG_BASE_MOD_1, to_reg_unsigned(5,1),  from_reg_unsigned(5,1)),
	'mod_source_ch2':       (REG_BASE_MOD_1, to_reg_unsigned(6,3),  from_reg_unsigned(6,3)),
	'atten_compensate_ch2': (REG_BASE_MOD_1, to_reg_unsigned(9,1),  from_reg_unsigned(9,1)),
	'trig_source_ch2':      (REG_BASE_MOD_1, to_reg_unsigned(10,3), from_reg_unsigned(10,3)),
	'range_shift_ch2':      (REG_BASE_MOD_1, to_reg_unsigned(13,6), from_reg_unsigned(13,6)),
	'sine_trigdly_ch2':     (REG_BASE_MOD_1, to_reg_unsigned(19,1), from_reg_unsigned(19,1)),
	'phasedly_en_ch2':      (REG_BASE_MOD_1, to_reg_unsigned(20,1), from_reg_unsigned(20,1)),
	'trig_sweep_mode_ch2':  (REG_BASE_MOD_1, to_reg_unsigned(29,1), from_reg_unsigned(29,1)),
	'gate_mode_ch2':        (REG_BASE_MOD_1, to_reg_unsigned(30,1), from_reg_unsigned(30,1)),
	'mod_depth_ch2':       ((REG_BASE_MOD_1 + 1), to_reg_unsigned(0,32), from_reg_unsigned(0,32)),
	'gate_thresh_ch2':     ((REG_GATETHRESH_H_CH2, REG_GATETHRESH_L_CH2),
	                           to_reg_signed(16,48), from_reg_signed(16,48)),

	#waveform controls
	'enable_ch2':        (REG_BASE_WAV_1, to_reg_unsigned(0,1), from_reg_unsigned(0,1)),
	'waveform_type_ch2': (REG_BASE_WAV_1, to_reg_unsigned(1,1), from_reg_unsigned(1,1)),
	'amplitude_ch2':    ((REG_BASE_WAV_1 + 1),
	                        to_reg_signed(0, 18, xform=lambda obj, a: 2 * a / obj._dac_gains()[1]),
	                        from_reg_signed(0, 18, xform=lambda obj, a: 2 * a * obj._dac_gains()[1])),
	'offset_ch2':       ((REG_BASE_WAV_1 + 2),
	                        to_reg_signed(0,16, xform=lambda obj, a: a / obj._dac_gains()[1]),
	                        from_reg_signed(0,16, xform=lambda obj, a: a * obj._dac_gains()[1])),
	't0_ch2':           (((REG_BASE_WAV_1 + 13), (REG_BASE_WAV_1 + 12)),
	                        to_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR),
	                        from_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR)),
	't1_ch2':           ((REG_BASE_WAV_1 + 15, REG_BASE_WAV_1 + 14),
	                        to_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR),
	                        from_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR)),
	't2_ch2':           ((REG_BASE_WAV_1 + 17, REG_BASE_WAV_1 + 16),
	                        to_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR),
	                        from_reg_unsigned(0, 48, xform = lambda obj, o: o * _WG_PERIODSCALE_SQR)),
	'riserate_ch2':     ((REG_BASE_WAV_1 + 19, REG_BASE_WAV_1 + 18),
	                        to_reg_signed(0, 64, xform = lambda obj, o: (o**-1) * _WG_RISESCALE),
	                        from_reg_signed(0, 64, xform = lambda obj, o: (o / _WG_RISESCALE)**-1)),
	'fallrate_ch2':     ((REG_BASE_WAV_1 + 21, REG_BASE_WAV_1 + 20),
	                        to_reg_signed(0, 64, xform = lambda obj, o: (o**-1) * _WG_RISESCALE),
	                        from_reg_signed(0, 64, xform = lambda obj, o: (o / _WG_RISESCALE)**-1)),
	'enable_reset_ch2': (REG_BASE_WAV_1 + 22,	to_reg_unsigned(0,1), from_reg_unsigned(0,1)),
	'phase_dly_ch2':    (REG_BASE_WAV_1 + 23,	to_reg_unsigned(0, 32), from_reg_unsigned(0, 32))
}

_wavegen_mod_reg_handlers = {}
