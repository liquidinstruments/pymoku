import math
import logging

from ._instrument import *
from . import _frame_instrument
from . import _utils

from ._frequency_response_analyzer_data import FRAData

log = logging.getLogger(__name__)

REG_FRA_SWEEP_FREQ_MIN_L   = 64
REG_FRA_SWEEP_FREQ_MIN_H   = 65
REG_FRA_SWEEP_FREQ_DELTA_L = 66
REG_FRA_SWEEP_FREQ_DELTA_H = 67
REG_FRA_LOG_EN             = 68
REG_FRA_HOLD_OFF_L         = 69
REG_FRA_SWEEP_LENGTH       = 71
REG_FRA_AVERAGE_TIME       = 72
REG_FRA_ENABLES            = 73
REG_FRA_SWEEP_AMP_MULT     = 74
REG_FRA_SETTLE_CYCLES      = 76
REG_FRA_AVERAGE_CYCLES     = 77
REG_FRA_SWEEP_OFF_MULT     = 78
REG_FRA_PHASE_OFF_CH1_LSB  = 79
REG_FRA_PHASE_OFF_CH1_MSB  = 80
REG_FRA_HARMONIC_MULT_CH1  = 81
REG_FRA_PHASE_OFF_CH2_LSB  = 82
REG_FRA_PHASE_OFF_CH2_MSB  = 83
REG_FRA_HARMONIC_MULT_CH2  = 84

_FRA_FPGA_CLOCK   = 125e6
_FRA_DAC_SMPS     = 1e9
_FRA_DAC_VRANGE   = 1
_FRA_DAC_BITDEPTH = 2**16
_FRA_DAC_BITS2V   = _FRA_DAC_BITDEPTH/_FRA_DAC_VRANGE
_FRA_SCREEN_WIDTH = 1024
_FRA_FREQ_SCALE   = 2**48 / _FRA_DAC_SMPS
_FRA_FXP_SCALE    = 2.0**30

class FrequencyResponseAnalyzer(_frame_instrument.FrameBasedInstrument):
	""" Frequency Response Analyzer instrument object.

	This should be instantiated and attached to a :any:`Moku` instance.
	"""
	def __init__(self):
		super(FrequencyResponseAnalyzer, self).__init__()
		self._register_accessors(_fra_reg_handlers)

		self.scales = {}
		self._set_frame_class(FRAData, instrument=self, scales=self.scales)

		self.id = 9
		self.type = "frequency_response_analyzer"

		self.sweep_amp_volts_ch1 = 0
		self.sweep_amp_volts_ch2 = 0

	def _calculate_sweep_delta(self, start_frequency, end_frequency, sweep_length, log_scale):
		if log_scale:
			sweep_freq_delta = round(((float(end_frequency)/float(start_frequency))**(1.0/(sweep_length - 1)) - 1) * _FRA_FXP_SCALE)
		else:
			sweep_freq_delta = round((float(end_frequency - start_frequency)/(sweep_length-1)) * _FRA_FREQ_SCALE)

		return sweep_freq_delta

	def _calculate_freq_axis(self):
		# Generates the frequency vector for plotting.
		f_start = self.sweep_freq_min
		fs = []

		if self.log_en:
			# Delta register becomes a multiplier in the logarithmic case
			# Fixed-point precision is used in the FPGA multiplier (30 fractional bits)
			fs = [ f_start*(1 + (self.sweep_freq_delta/ _FRA_FXP_SCALE))**n for n in range(self.sweep_length)]
		else:
			fs = [ (f_start + n*(self.sweep_freq_delta/_FRA_FREQ_SCALE)) for n in range(self.sweep_length) ]

		return fs

	def _calculate_gain_correction(self, fs):
		sweep_freq = fs

		cycles_time = [0.0] * self.sweep_length

		if all(sweep_freq):
			cycles_time = [ self.averaging_cycles / sweep_freq[n] for n in range(self.sweep_length)]

		points_per_freq = [math.ceil(a * max(self.averaging_time, b) - 1e-12) for (a, b) in zip(sweep_freq, cycles_time)]

		average_gain = [0.0] * self.sweep_length
		gain_scale = [0.0] * self.sweep_length

		# Calculate gain scaling due to accumulator bit ranging
		for f in range(self.sweep_length):
			sweep_period = 1 / sweep_freq[f]

			# Predict how many FPGA clock cycles each frequency averages for:
			average_period_cycles = self.averaging_cycles * sweep_period * _FRA_FPGA_CLOCK
			if self.averaging_time % sweep_period == 0:
				average_period_time = self.averaging_time * _FRA_FPGA_CLOCK
			else :
				average_period_time = math.ceil(self.averaging_time / sweep_period) * sweep_period * _FRA_FPGA_CLOCK

			if average_period_time >= average_period_cycles:
				average_period = average_period_time
			else :
				average_period = average_period_cycles

			# Scale according to the predicted accumulator counter size:
			if average_period <= 2**15:
				average_gain[f] = 2**4
			elif average_period <= 2**20:
				average_gain[f] = 2**-1
			elif average_period <= 2**25:
				average_gain[f] = 2**-6
			elif average_period <= 2**30:
				average_gain[f] = 2**-11
			elif average_period <= 2**35:
				average_gain[f] = 2**-16
			else :
				average_gain[f] = 2**-20

		for f in range(self.sweep_length):
			if sweep_freq[f] > 0.0 :
				gain_scale[f] =  math.ceil(average_gain[f] * points_per_freq[f] * _FRA_FPGA_CLOCK / sweep_freq[f])
			else :
				gain_scale[f] = average_gain[f]

		return gain_scale

	@needs_commit
	def set_input_range(self, ch, input_range):
		"""Set the input range for a channel.

		:type ch: int; {1,2}
		:param ch: channel

		:type input_range: {1, 10}
		:param input_range: the peak to peak voltage (Vpp) range of the inputs.
		"""

		_utils.check_parameter_valid('set', ch, [1, 2], 'input channel', allow_none=True)
		_utils.check_parameter_valid('set', input_range, [1, 10], 'input range', allow_none=False)

		front_end_setting = self.get_frontend(ch)
		self.set_frontend(ch, fiftyr=front_end_setting[0], atten=(input_range == 10), ac=front_end_setting[2])

	def _calculate_scales(self):
		g1, g2 = self._adc_gains()
		fs = self._calculate_freq_axis()
		gs = self._calculate_gain_correction(fs)

		return {'g1': g1, 'g2': g2,
				'gain_correction' : gs,
				'frequency_axis' : fs,
				'sweep_freq_min': self.sweep_freq_min,
				'sweep_freq_delta': self.sweep_freq_delta,
				'sweep_length': self.sweep_length,
				'log_en': self.log_en,
				'averaging_time': self.averaging_time,
				'sweep_amplitude_ch1' : self.sweep_amp_volts_ch1,
				'sweep_amplitude_ch2' : self.sweep_amp_volts_ch2
				}

	@needs_commit
	def set_sweep(self, f_start=100, f_end=120e6, sweep_points=512, sweep_log=False, averaging_time=1e-3, settling_time=1e-3, averaging_cycles=1, settling_cycles=1):
		""" Set the output sweep parameters

		:type f_start: int; 1 <= f_start <= 120e6 Hz
		:param f_start: Sweep start frequency

		:type f_end: int; 1 <= f_end <= 120e6 Hz
		:param f_end: Sweep end frequency

		:type sweep_points: int; 32 <= sweep_points <= 512
		:param sweep_points: Number of points in the sweep (rounded to nearest power of 2).

		:type sweep_log: bool
		:param sweep_log: Enable logarithmic frequency sweep scale.

		:type averaging_time: float; sec
		:param averaging_time: Minimum averaging time per sweep point.

		:type settling_time: float; sec
		:param settling_time: Minimum setting time per sweep point.

		:type averaging_cycles: int; cycles
		:param averaging_cycles: Minimum averaging cycles per sweep point.

		:type settling_cycles: int; cycles
		:param settling_cycles: Minimum settling cycles per sweep point.
		"""
		_utils.check_parameter_valid('range', f_start, [1,120e6],'sweep start frequency', 'Hz')
		_utils.check_parameter_valid('range', f_end, [1,120e6],'sweep end frequency', 'Hz')
		_utils.check_parameter_valid('range', sweep_points, [32,512],'sweep points')
		_utils.check_parameter_valid('bool', sweep_log, desc='sweep log scale enable')
		_utils.check_parameter_valid('range', averaging_time, [1e-6,10], 'sweep averaging time', 'sec')
		_utils.check_parameter_valid('range', settling_time, [1e-6,10], 'sweep settling time', 'sec')
		_utils.check_parameter_valid('range', averaging_cycles, [1,2**20], 'sweep averaging cycles', 'cycles')
		_utils.check_parameter_valid('range', settling_cycles, [1,2**20], 'sweep settling cycles', 'cycles')

		# Frequency span check
		if (f_end - f_start) == 0:
			raise ValueOutOfRangeException("Sweep frequency span must be non-zero: f_start/f_end/span - %.2f/%.2f/%.2f." % (f_start, f_end, f_end-f_start))

		self.sweep_freq_min = f_start
		self.sweep_length = sweep_points
		self.log_en = sweep_log

		self.averaging_time = averaging_time
		self.averaging_cycles = averaging_cycles
		self.settling_time = settling_time

		self.sweep_freq_delta = self._calculate_sweep_delta(f_start, f_end, sweep_points, sweep_log)
		self.settling_cycles = settling_cycles

	@needs_commit
	def start_sweep(self, single=False):
		"""	Start sweeping

		:type single: bool
		:param single: Enable single sweep (otherwise loop)
		"""
		_utils.check_parameter_valid('bool', single, desc='enable single sweep')

		self.adc1_en = True
		self.adc2_en = True
		self.dac1_en = True
		self.dac2_en = True

		self.sweep_reset = False
		self.single_sweep = single
		self.loop_sweep = not single

	@needs_commit
	def stop_sweep(self):
		""" Stop sweeping.

		This will stop new data frames from being received, so ensure you implement a timeout
		on :any:`get_data<pymoku.instruments.FrequencyResponseAnalyzer.get_data>` calls.
		"""
		self.single_sweep = self.loop_sweep = False

		self.adc2_en = False
		self.dac1_en = False
		self.dac2_en = False
		self.adc1_en = False

	@needs_commit
	def _restart_sweep(self):
		self.sweep_reset = True

	@needs_commit
	def set_output(self, ch, amplitude, offset=0):
		""" Set the output sweep amplitude.

		.. note::
			Ensure that the output amplitude is set so as to not saturate the inputs.
			Inputs are limited to 1.0Vpp with attenuation turned off.

		:type ch: int; {1, 2}
		:param ch: Output channel

		:type amplitude: float; [0.0, 2.0] Vpp
		:param amplitude: Sweep amplitude

		:type offset: float; [-1.0, 1.0] Volts
		:param offset: Sweep offset
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'output channel')
		_utils.check_parameter_valid('range', amplitude, [0.001, 2.0], 'sweep amplitude', 'Vpp')
		_utils.check_parameter_valid('range', offset, [-1.0, 1.0], 'sweep offset', 'volts')

		# ensure combination of amplitude and offset doesn't cause output clipping
		if ((amplitude/2.0) + abs(offset)) > 1.0:
			raise ValueOutOfRangeException("Output sweep waveform must not exceed +/- 1.0 volts. Reduce output amplitude and/or offset.")

		# Set up the output scaling register but also save the voltage value away for use
		# in the state dictionary to scale incoming data
		if ch == 1:
			self.sweep_amplitude_ch1 = amplitude
			self.sweep_amp_volts_ch1 = amplitude
			self.sweep_offset_ch1 = offset
			self.channel1_en = amplitude > 0

		elif ch == 2:
			self.sweep_amplitude_ch2 = amplitude
			self.sweep_amp_volts_ch2 = amplitude
			self.sweep_offset_ch2 = offset
			self.channel2_en = amplitude > 0

	@needs_commit
	def enable_amplitude(self, ch, en = True):
		""" Enable/disable amplitude on the selected channel.

		:type ch: int; {1, 2}
		:param ch: Output channel

		:type en: bool
		:param en: Enable amplitude)
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'output channel')
		_utils.check_parameter_valid('set', en, [True, False], 'enable amplitude')

		if ch == 1:
			self.dac1_en = en
		else:
			self.dac2_en = en

	@needs_commit
	def enable_offset(self, ch, en = True):
		""" Enable/disable output offset on the selected channel.

		:type ch: int; {1, 2}
		:param ch: Output channel

		:type en: bool
		:param en: Enable offset
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'output channel')
		_utils.check_parameter_valid('set', en, [True, False], 'enable offset')

		if ch == 1:
			self.channel1_en = en
		else:
			self.channel2_en = en

	@needs_commit
	def gen_off(self, ch=None):
		""" Turn off the output sweep.

		If *ch* is specified, turn off only a single channel, otherwise turn off both.

		:type ch: int; {1,2}
		:param ch: Channel number to turn off (None, or leave blank, for both)
		"""
		_utils.check_parameter_valid('set', ch, [1,2,None],'output sweep channel')
		if ch is None or ch == 1:
			self.channel1_en = False
		if ch is None or ch == 2:
			self.channel2_en = False

	@needs_commit
	def set_xmode(self, xmode):
		"""
		Set rendering mode for the horizontal axis.

		:type xmode: string, {'sweep','fullframe'}
		:param xmode:
			Respectively; Sweep Mode (bode function sweeping across the screen)
			or Full Frame (like sweep, but waits for the frame to be completed).
		"""
		_str_to_xmode = {
			'sweep' : SWEEP,
			'fullframe' : FULL_FRAME
		}
		xmode = _utils.str_to_val(_str_to_xmode, xmode, 'X-mode')
		self.x_mode = xmode

	@needs_commit
	def set_defaults(self):
		""" Reset the Frequency Response Analyzer to sane defaults """
		super(FrequencyResponseAnalyzer, self).set_defaults()
		self.frame_length = _FRA_SCREEN_WIDTH

		self.x_mode = FULL_FRAME
		self.render_mode = RDR_DDS
		self.framerate = 10

		self.en_in_ch1 = True
		self.en_in_ch2 = True

		self.set_frontend(1, fiftyr=True, atten=False, ac=False)
		self.set_frontend(2, fiftyr=True, atten=False, ac=False)

		self.set_sweep()
		self.set_ch_phase(1)
		self.set_ch_phase(2)

		self.set_harmonic_multiplier(1)
		self.set_harmonic_multiplier(2)
		# 100mVpp swept outputs
		self.set_output(1, 0.1, 0.0)
		self.set_output(2, 0.1, 0.0)

		self.set_input_range(1, 10)
		self.set_input_range(2, 10)

		self.start_sweep()

	@needs_commit
	def set_ch_phase(self, ch, phase = 0.0):
		""" set the phase of the measurement with respect to the output signal.

		:type ch: int; {1, 2}
		:param ch: selects the channel to apply settings.

		:type phase: float [0.0, 360.0] deg
		:param phase: phase difference between channel 1 and channel 2.
		"""
		_utils.check_parameter_valid('set', ch, [1,2],'channel')
		_utils.check_parameter_valid('range', phase, [0.0, 360.0], 'phase', 'degrees')
		if ch == 1:
			self.ch1_meas_phase = (phase / 360.0 ) * 2**64
		else:
			self.ch2_meas_phase = (phase / 360.0 ) * 2**64


	@needs_commit
	def set_harmonic_multiplier(self, ch, multiplier = 1):
		""" set the harmonic multiplier to demodulate at integer harmonic of output.

		:type ch: int; {1, 2}
		:param ch: selects the channel to apply settings.

		:type multiplier: int; [0, 15]
		:param multiplier: multiplier applied to fundemental.
		"""
		_utils.check_parameter_valid('set', ch, [1,2],'channel')
		_utils.check_parameter_valid('set', multiplier,
			[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],'harmonics select')
		if ch == 1:
			self.ch1_harmonic_mult = multiplier
		elif ch == 2:
			self.ch2_harmonic_mult = multiplier


	def get_data(self, timeout=None, wait=True):
		""" Get current sweep data.
		In the FrequencyResponseAnalyzer this is an alias for ``get_realtime_data`` as the data
		is never downsampled.
		"""
		return super(FrequencyResponseAnalyzer, self).get_realtime_data(timeout, wait)

	def commit(self):
		# Restart the sweep as instrument settings are being changed
		self._restart_sweep()
		super(FrequencyResponseAnalyzer, self).commit()

		# Update the scaling factors for processing of incoming frames
		# stateid allows us to track which scales correspond to which register state
		self.scales[self._stateid] = self._calculate_scales()
	commit.__doc__ = MokuInstrument.commit.__doc__


_fra_reg_handlers = {
	'loop_sweep':          (REG_FRA_ENABLES, to_reg_bool(0), from_reg_bool(0)),
	'single_sweep':        (REG_FRA_ENABLES, to_reg_bool(1), from_reg_bool(1)),
	'sweep_reset':         (REG_FRA_ENABLES, to_reg_bool(2), from_reg_bool(2)),
	'channel1_en':         (REG_FRA_ENABLES, to_reg_bool(3), from_reg_bool(3)),
	'channel2_en':         (REG_FRA_ENABLES, to_reg_bool(4), from_reg_bool(4)),
	'adc1_en':             (REG_FRA_ENABLES, to_reg_bool(5), from_reg_bool(5)),
	'adc2_en':             (REG_FRA_ENABLES, to_reg_bool(6), from_reg_bool(6)),
	'dac1_en':             (REG_FRA_ENABLES, to_reg_bool(7), from_reg_bool(7)),
	'dac2_en':             (REG_FRA_ENABLES, to_reg_bool(8), from_reg_bool(8)),
	'sweep_freq_min':     ((REG_FRA_SWEEP_FREQ_MIN_H, REG_FRA_SWEEP_FREQ_MIN_L),
	                        to_reg_unsigned(0, 48, xform=lambda obj, f: f * _FRA_FREQ_SCALE),
	                        from_reg_unsigned(0, 48, xform=lambda obj, f: f / _FRA_FREQ_SCALE)),
	'sweep_freq_delta':   ((REG_FRA_SWEEP_FREQ_DELTA_H, REG_FRA_SWEEP_FREQ_DELTA_L),
	                        to_reg_signed(0, 48),
	                        from_reg_signed(0, 48)),
	'log_en':              (REG_FRA_LOG_EN, to_reg_bool(0), from_reg_bool(0)),
	'sweep_length':        (REG_FRA_SWEEP_LENGTH, to_reg_unsigned(0, 10), from_reg_unsigned(0, 10)),
	'settling_time':       (REG_FRA_HOLD_OFF_L,
	                        to_reg_unsigned(0, 32, xform=lambda obj, t: t * _FRA_FPGA_CLOCK),
	                        from_reg_unsigned(0, 32, xform=lambda obj, t: t / _FRA_FPGA_CLOCK)),
	'averaging_time':      (REG_FRA_AVERAGE_TIME,
	                        to_reg_unsigned(0, 32, xform=lambda obj, t: t * _FRA_FPGA_CLOCK),
	                        from_reg_unsigned(0, 32, xform=lambda obj, t: t / _FRA_FPGA_CLOCK)),
	'sweep_amplitude_ch1': (REG_FRA_SWEEP_AMP_MULT,
	                        to_reg_unsigned(0, 16, xform=lambda obj, a: a / obj._dac_gains()[0]),
	                        from_reg_unsigned(0, 16, xform=lambda obj, a: a * obj._dac_gains()[0])),
	'sweep_amplitude_ch2': (REG_FRA_SWEEP_AMP_MULT,
	                        to_reg_unsigned(16, 16, xform=lambda obj, a: a / obj._dac_gains()[1]),
	                        from_reg_unsigned(16, 16, xform=lambda obj, a: a * obj._dac_gains()[1])),
	'sweep_offset_ch1':    (REG_FRA_SWEEP_OFF_MULT,
	                        to_reg_signed(0, 16, xform=lambda obj, a: a / obj._dac_gains()[0]),
	                        from_reg_signed(0, 16, xform=lambda obj, a: a * obj._dac_gains()[0])),
	'sweep_offset_ch2':    (REG_FRA_SWEEP_OFF_MULT,
	                        to_reg_signed(16, 16, xform=lambda obj, a: a / obj._dac_gains()[1]),
	                        from_reg_signed(16, 16, xform=lambda obj, a: a * obj._dac_gains()[1])),
	'settling_cycles':     (REG_FRA_SETTLE_CYCLES, to_reg_unsigned(0, 32), from_reg_unsigned(0, 32)),
	'averaging_cycles':    (REG_FRA_AVERAGE_CYCLES, to_reg_unsigned(0, 32), from_reg_unsigned(0, 32)),
	'ch1_harmonic_mult':   (REG_FRA_HARMONIC_MULT_CH1, to_reg_unsigned(0,4), from_reg_unsigned(0, 4)),
	'ch2_harmonic_mult':   (REG_FRA_HARMONIC_MULT_CH2, to_reg_unsigned(0,4), from_reg_unsigned(0, 4)),
	'ch1_meas_phase':     ((REG_FRA_PHASE_OFF_CH1_MSB, REG_FRA_PHASE_OFF_CH1_LSB),
	                        to_reg_unsigned(0, 64),
	                        from_reg_unsigned(0, 64)),
	'ch2_meas_phase':     ((REG_FRA_PHASE_OFF_CH2_MSB, REG_FRA_PHASE_OFF_CH2_LSB),
	                        to_reg_unsigned(0, 64),
	                        from_reg_unsigned(0,64))
}
