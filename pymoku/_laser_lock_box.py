
import math
import logging

from pymoku._instrument import *
from pymoku._oscilloscope import _CoreOscilloscope, VoltsData
from . import _instrument
from . import _frame_instrument
from . import _utils
from ._pid import PID
from ._sweep_generator import SweepGenerator
from ._iir_block import IIRBlock
from ._embedded_pll import EmbeddedPLL

log = logging.getLogger(__name__)

REGBASE_LLB_IIR				= 28

REGBASE_LLB_AUX				= 40
REG_LLB_AUX_SCALE			= 49
REG_LLB_AUX_CTRL			= 50
REG_LLB_AUX_PHASE_OFFSET	= 51

REG_LLB_MON_SEL				= 75

REGBASE_LLB_LO				= 76
REG_LLB_LO_PHASE_OFFSET		= 85
REG_LLB_LO_CTRL				= 86

REGBASE_LLB_SCAN			= 87
REG_LLB_SCAN_SCALE			= 96
REG_LLB_SCAN_CTRL			= 97

REG_LLB_GAINS_INPUT			= 98
REG_LLB_ENABLES_LIGHTS		= 98
REG_LLB_GAINS_SCALING		= 99

REG_LLB_OFFSETS_FASTINPUT	= 100
REG_LLB_OFFSETS_FASTOUTPUT	= 101
REG_LLB_OFFSETS_SLOWOUTPUT	= 102

REG_LLB_CLIP_FAST			= 103
REG_LLB_CLIP_SLOW			= 104

REGBASE_LLB_PLL				= 105

REGBASE_LLB_PID1			= 109
REGBASE_LLB_PID2			= 118

_LLB_PHASESCALE				= 2**28 / 360.0
_LLB_SCANPHASESCALE			= 2**64 / 360
_LLB_FREQSCALE				= 2**64 / 1e9
_LLB_SWEEP_WTYPE_SAWTOOTH	= 2
_LLB_SWEEP_MAX_STOP			= 2**64 - 1
_LLB_HIGH_RATE				= 0
_LLB_LOW_RATE				= 1

_LLB_COEFFICIENT_WIDTH		= 24

_LLB_TRIG_SRC_CH1			= 0
_LLB_TRIG_SRC_CH2			= 1
_LLB_TRIG_SRC_EXT			= 2

_LLB_SCAN_SAWTOOTH			= 2
_LLB_SCAN_TRIANGLE			= 3

_LLB_SCANSOURCE_DAC1		= 0
_LLB_SCANSOURCE_DAC2		= 1
_LLB_SCANSOURCE_NONE		= 2

_LLB_AUXSOURCE_DAC1		= 0
_LLB_AUXSOURCE_DAC2		= 1
_LLB_AUXSOURCE_NONE		= 2

_LLB_MON_ERROR 				= 1
_LLB_MON_PID_FAST			= 2
_LLB_MON_PID_SLOW			= 3
_LLB_MON_OFFSET_FAST		= 4
_LLB_MON_IN1				= 5
_LLB_MON_IN2				= 6
_LLB_MON_OUT1				= 7
_LLB_MON_OUT2				= 8
_LLB_MON_SCAN				= 9
_LLB_MON_LO 				= 10
_LLB_MON_AUX				= 11

_LLB_SOURCE_A		= 0
_LLB_SOURCE_B		= 1
_LLB_SOURCE_IN1		= 2
_LLB_SOURCE_SCAN	= 3
_LLB_SOURCE_IN2		= 3
_LLB_SOURCE_EXT		= 4

_LLB_OSC_SOURCES = {
	'a' : _LLB_SOURCE_A,
	'b' : _LLB_SOURCE_B,
	'scan': _LLB_SOURCE_SCAN,
	'in1' : _LLB_SOURCE_IN1,
	'in2' : _LLB_SOURCE_IN2,
	'ext' : _LLB_SOURCE_EXT
}

class LaserLockBox(_CoreOscilloscope):
	def __init__(self):
		super(LaserLockBox, self).__init__()
		self._register_accessors(_llb_reg_hdl)

		self.id = 16
		self.type = "laserlockbox"

		self._set_source(1, _LLB_SOURCE_A)
		self._set_source(2, _LLB_SOURCE_B)

		self.monitor_a = 'in1'
		self.monitor_b = 'in2'

		self.fast_fs = 31.25e6
		self.slow_fs = 488.28e3

		self.fast_pid = PID(self, reg_base = REGBASE_LLB_PID1, fs=self.fast_fs)
		self.slow_pid = PID(self, reg_base = REGBASE_LLB_PID2, fs=self.slow_fs)

		self.demod_sweep = SweepGenerator(self, reg_base = REGBASE_LLB_LO)
		self.scan_sweep = SweepGenerator(self, reg_base = REGBASE_LLB_SCAN)
		self.aux_sine_sweep = SweepGenerator(self, reg_base = REGBASE_LLB_AUX)
		self.iir_filter = IIRBlock(self, reg_base=REGBASE_LLB_IIR, num_stages = 2, gain_frac_width = 9, coeff_frac_width = 30, use_mmap = False)
		self.embedded_pll = EmbeddedPLL(self, reg_base=REGBASE_LLB_PLL)
		self.input1_light = True

	@needs_commit
	def set_defaults(self):
		super(LaserLockBox, self).set_defaults()
		self.set_input_gain(0)

		default_filt_coeff = [[1, 1, 0, 0, 0, 0],[1, 1, 0, 0, 0, 0]]
		self.set_custom_filter(default_filt_coeff)
		self.set_local_oscillator()

		self._set_scale()

		self.set_output_enables(1, True)
		self.set_output_enables(2, True)
		self.set_pid_enables(1, True)
		self.set_pid_enables(2, True)
		self.set_channel_pid_enables(1, True)
		self.set_channel_pid_enables(2, True)
		self.fast_pid.bypass = False
		self.slow_pid.bypass = False

		self.set_output_range(1, 1.0, -1.0)
		self.set_output_range(2, 1.0, -1.0)

		self.set_monitor('A', 'error')
		self.set_monitor('B', 'scan')
		self.set_trigger('scan', 'rising', level = 0, hysteresis = 0.1, trig_on_scan_rising = True)
		self.set_timebase(-1e-3, 1e-3)

	def _update_dependent_regs(self, scales):
		super(LaserLockBox, self)._update_dependent_regs(scales)
		self._set_scale()
		
	@needs_commit
	def _set_scale(self):
		# incorporate adc2 scaling if local oscillator source is set to 'external'.
		self.lo_scale_factor = 1.0 if self.MuxLOSignal == 0 else self._adc_gains()[1] * 2**12  / (10.0 if self.get_frontend(2)[1] else 1.0)

		self._fast_scale = self._adc_gains()[0] / self._dac_gains()[0] / 2**3 * self.lo_scale_factor / (10.0 if self.get_frontend(1)[1] else 1.0)
		self._slow_scale = self._adc_gains()[0] / self._dac_gains()[1] / 2**3 * self.lo_scale_factor / (10.0 if self.get_frontend(1)[1] else 1.0)

	@needs_commit
	def set_input_gain(self, gain=0):
		"""
		Set the main input gain (Input Channel 1).

		:type gain: int; {-20, 0, 24, 48} dB
		:param gain: Input gain

		"""
		_utils.check_parameter_valid('set', gain, allowed=[-20,0,24,48], desc="main input gain", units="dB")
		front_end_setting = self.get_frontend(1)

		if gain == 0:
			self.input_gain_select = 0
			self.set_frontend(1, fiftyr = front_end_setting[0], atten=False, ac = front_end_setting[2])
		elif gain == 24:
			self.input_gain_select = 1
			self.set_frontend(1, fiftyr = front_end_setting[0], atten=False, ac = front_end_setting[2])
		elif gain == 48:
			self.input_gain_select = 2
			self.set_frontend(1, fiftyr = front_end_setting[0], atten=False, ac = front_end_setting[2])
		elif gain == -20:
			self.input_gain_select = 0
			self.set_frontend(1, fiftyr = front_end_setting[0], atten=True, ac = front_end_setting[2])
		else:
			raise Exception("Invalid input gain value.")

	@needs_commit
	def set_custom_filter(self, filt_coeffs):

		"""
		Configure the filter coefficients in the IIR filter.

		:type filt_coeffs: array;
		:param filt_coeffs: array containg Direct-Form 1 SOS filter coefficients in the following format:

		+-----+------+------+------+------+-------+
		| s1  | b0.1 | b1.1 | b2.1 | a1.1 |  a2.1 |
		+-----+------+------+------+------+-------+
		| s2  | b0.2 | b1.2 | b2.2 | a1.2 |  a2.2 |
		+-----+------+------+------+------+-------+

		Each 'a' coefficient must be a float in the range [-2.0, +2.0). 's' coefficients are multiplied into each 'b' coefficient before being sent to the device. 
		These products (sN x b0.N, sN x b1.N, sN x b2.N) must also fall in the range [-2.0, +2.0). Internally, the 'a' and 'b' coefficients are represented as 
		signed 32-bit fixed-point numbers, with 30 fractional bits. 

		Filter coefficients can be computed using signal processing toolboxes in e.g. MATLAB or SciPy.


		"""
		# check array format
		_utils.check_parameter_valid('set', len(filt_coeffs), [2], desc='number of a/b filter array rows')
		_utils.check_parameter_valid('set', len(filt_coeffs[0]), [6], desc='number of coefficients in first filter array row')
		_utils.check_parameter_valid('set', len(filt_coeffs[1]), [6], desc='number of coefficients in second filter array row')

		# multiply s coefs into b coefs and set s coefs = 1.0
		for row in range(0, 2):
			for bcoef in range(1, 4):
				filt_coeffs[row][bcoef] *= filt_coeffs[row][0]
				_utils.check_parameter_valid('range', filt_coeffs[row][bcoef], [-2.0, 2.0], desc='product of b{}.{} and s{}'.format(row + 1, bcoef, row + 1), units='linear scalar')
		filt_coeffs[0][0] = 1.0
		filt_coeffs[1][0] = 1.0

		# check value of a coefs
		for row in range(0, 2):
			for coef in range(0, 6):
				_utils.check_parameter_valid('range', filt_coeffs[row][coef], [-2.0, 2.0], desc='coefficient value', units='linear scalar')

		# add G of 1.0 to array 
		filt_coeffs = [[1.0], filt_coeffs[0], filt_coeffs[1]]

		self.iir_filter.write_coeffs(filt_coeffs)

	@needs_commit
	def set_output_range(self, ch, maximum, minimum):
		"""
		Set upper and lower bounds for the signal on each DAC channel. The auxilliary waveform is not restricted to these
		bounds when added to either DAC channel.  

		:type ch : int; [1, 2]
		:param ch : 1 = Output 1, 2 = Output 2 

		:type maximum: float, [-1.0, 1.0] Volts;
		:param maximum: maximum value the output signal can be before clipping occurs.

		:type minimum: float, [-1.0, 1.0] Volts;
		:param maximum: maximum value the output signal can be before clipping occurs.
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'output channel')
		_utils.check_parameter_valid('range', maximum, [-1.0, 1.0], desc='maximum', units='Volts')
		_utils.check_parameter_valid('range', minimum, [-1.0, 1.0], desc='minimum', units='Volts')
		if minimum > maximum:
			raise ValueOutOfRangeException("Maximum range value must be greater than minimum.")

		if ch == 1:
			self.cliprange_upper_ch1 = maximum / self._dac_gains()[0] / 2.0**15
			self.cliprange_lower_ch1 = minimum / self._dac_gains()[0] / 2.0**15
		else:
			self.cliprange_upper_ch2 = maximum / self._dac_gains()[1] / 2.0**15
			self.cliprange_lower_ch2 = minimum / self._dac_gains()[1] / 2.0**15

	@needs_commit
	def set_offsets(self, position, offset):
		"""
		Set offsets throughout the laser locker.

		:type position : list; ['pid_input', 'out1', 'out2']
		:param position : The desired point to add an offset

		:type offset : float, [-2.0, 2.0] Volts.
		:param offset : voltage offset. 
		"""
		_utils.check_parameter_valid('set', position, ['pid_input', 'out1', 'out2'],'position')
		_utils.check_parameter_valid('range', offset, [-2.0, 2.0], desc='offset', units='Volts')

		if position == 'pid_input':
			self.fast_offset =offset / (self._adc_gains()[0] * 2**12) / self.lo_scale_factor
		elif position == 'out1':
			self.output_offset_ch1 = offset / (self._adc_gains()[0] * 2**12) / self.lo_scale_factor
		else:
			self.output_offset_ch2 = offset / (self._adc_gains()[0] * 2**12) / self.lo_scale_factor

	@needs_commit
	def set_pid_by_gain(self, pid_block, g=1, kp=1, ki=0, kd=0, si=None, sd=None, enable = True):
		"""
		Configure the selected PID controller using gain coefficients.

		:type pid_block : int; [1,2]
		:param pid_block : PID controller - 1 = Fast, 2 = Slow 

		:type g: float; [0,2^16 - 1]
		:param g: Gain

		:type kp: float; [-1e3,1e3]
		:param kp: Proportional gain factor

		:type ki: float; 
			[0, 31.25e6] with a resolution of 31.25e6 / 2^24-1 when pid_block = 1
			[0, 488.28e3] with a resolution of 488.28 / 2^24-1 when pid_block = 2.
		:param ki: Integrator gain factor. 

		:type kd: float; [0, 31.25e6] when pid_block = 1, [0, 488.28e3] when pid_block = 2
		:param kd: Differentiator gain factor

		:type si: float; float; [-1e3,1e3]
		:param si: Integrator gain saturation

		:type sd: float; [-1e3,1e3]
		:param sd: Differentiator gain saturation

		:type enable: bool;
		:param enable: enables pid outputs

		:raises InvalidConfigurationException: if the configuration of PID gains is not possible.
		"""

		_utils.check_parameter_valid('set', pid_block, [1,2],'filter channel')
		_utils.check_parameter_valid('range', g, [0, 2**16 - 1], desc='Gain', units='linear scalar')
		_utils.check_parameter_valid('range', kp, [-1e3, 1e3], desc='proportional gain', units='linear scalar')

		if pid_block == 1:
			_utils.check_parameter_valid('range', ki, [0, 31.25e6], desc='integrator gain', units='linear scalar')
			_utils.check_parameter_valid('range', kd, [0, 31.25e6], desc='differentiator gain', units='linear scalar')
		else:
			_utils.check_parameter_valid('range', ki, [0, 488.28e3], desc='integrator gain', units='linear scalar')
			_utils.check_parameter_valid('range', kd, [0, 488.28e3], desc='differentiator gain', units='linear scalar')

		if si != None:
			_utils.check_parameter_valid('range', si, [-1e3, 1e3], desc='integrator gain saturation', units='linear scalar')
		if sd != None:
			_utils.check_parameter_valid('range', sd, [-1e3, 1e3], desc='differentiator gain saturation', units='linear scalar')

		_utils.check_parameter_valid('set', enable, [True, False],'enable')

		if pid_block == 1 :
			self.fast_pid.set_reg_by_gain(g, kp, ki, kd, si, sd)
			self.fast_pid.gain = self.fast_pid.gain * 2**15
			self.fast_pid_en = enable
		else:
			self.slow_pid.set_reg_by_gain(g, kp, ki, kd, si, sd)
			self.slow_pid.gain = self.slow_pid.gain * 2**15
			self.slow_pid_en = enable

	@needs_commit
	def set_pid_by_freq(self, pid_block, kp=1, i_xover=None, d_xover=None, si=None, sd=None, enable = True):
		"""

		Configure the selected PID controller using crossover frequencies.

		:type pid_block : int; [1,2]
		:param pid_block : PID controller - 1 = Fast, 2 = Slow 

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

		:type enable: bool;
		:param enable: enables pid outputs

		:raises InvalidConfigurationException: if the configuration of PID gains is not possible.
		"""
		_utils.check_parameter_valid('set', pid_block, [1,2],'filter channel')
		_utils.check_parameter_valid('range', kp, [-1e3, 1e3], desc='proportional gain', units='linear scalar')
		if i_xover != None:
			_utils.check_parameter_valid('range', i_xover, [1e-3, 1e6], desc='integrator cross over frequency', units='hertz')
		if d_xover != None:
			_utils.check_parameter_valid('range', d_xover, [1, 10e6], desc='differentiator cross over frequency', units='hertz')
		if si != None:
			_utils.check_parameter_valid('range', si, [-1e3, 1e3], desc='integrator gain saturation', units='linear scalar')
		if sd != None:
			_utils.check_parameter_valid('range', sd, [-1e3, 1e3], desc='differentiator gain saturation', units='linear scalar')

		_utils.check_parameter_valid('set', enable, [True, False],'enable')

		if pid_block == 1:
			self.fast_pid.set_reg_by_frequency(kp, i_xover, d_xover, si, sd)
			self.fast_pid.gain = self.fast_pid.gain * 2**15
			self.fast_pid_en = enable
		else:
			self.slow_pid.set_reg_by_frequency(kp, i_xover, d_xover, si, sd)
			self.slow_pid.gain = self.slow_pid.gain * 2**15
			self.slow_pid_en = enable

	@needs_commit
	def set_pid_enables(self, pid_block, en=True):
		"""
		Enable or disable the selected PID controller.

		:type pid_block : int; [1, 2]
		:param pid_block : PID controller - 1 = Fast, 2 = Slow 

		:type en : bool;
		:param en : enable or disable PID controller described in pid_block.
		"""
		_utils.check_parameter_valid('set', pid_block, [1, 2], 'PID controller')
		_utils.check_parameter_valid('set', en, [True, False], 'enable')

		pid_array = [self.fast_pid, self.slow_pid]
		pid_array[pid_block-1].enable = en

	@needs_commit
	def set_output_enables(self, ch, en=True):
		"""
		Enable or disable the selected output channel.

		:type ch : int; [1, 2]
		:param ch : 1 = Output 1, 2 = Output 2 

		:type en : bool;
		:param en : enable or disable channel.
		"""
		_utils.check_parameter_valid('set', ch, [1, 2], 'output channel')
		_utils.check_parameter_valid('set', en, [True, False], 'enable')

		if ch == 1:
			self.out1_en = en
		else:
			self.out2_en = en

	@needs_commit
	def set_channel_pid_enables(self, pid_block, en=True):
		"""
		Enable or disable connection of the selected PID controller to it's corresponding output channel. Fast = Output 1, Slow = Output 2. 

		:type pid_block : int; [1, 2]
		:param pid_block : PID controller - 1 = Fast, 2 = Slow 

		:type en : bool;
		:param en : enable or disable channel.
		"""
		_utils.check_parameter_valid('set', pid_block, [1, 2], 'PID controller')
		_utils.check_parameter_valid('set', en, [True, False], 'enable')
		if pid_block == 1:
			self.fast_channel_en = en
		else:
			self.slow_channel_en = en

	@needs_commit
	def set_local_oscillator(self, frequency=0.0, phase=0.0, source = 'internal', pll_auto_acq = True):
		"""
		Configure the local oscillator. The local oscillator can be generated internally with configurable frequency and phase offset,
		externally via ADC 2 or internally with a PLL phase locked to ADC 2 plus an additional phase offset.

		:type frequency : float; [0, 200e6] Hz
		:param frequency : Internal demodulation frequency

		:type phase : float; [0, 360] degrees
		:param phase : float; Internal demodulation phase

		:type source : list; ['internal', 'external', 'external_pll']
		:param source : Local Oscillator Source

		:type pll_auto_acq : bool
		:param pll_auto_acq : Enable PLL Auto Acquire

		"""
		_utils.check_parameter_valid('range', frequency, [0, 200e6], desc='local oscillator frequency', units='hertz')
		_utils.check_parameter_valid('range', phase, [0, 360], desc='local oscillator phase offset', units='degrees')
		_utils.check_parameter_valid('set', source, ['internal', 'external', 'external_pll'], 'local oscillator source')
		_utils.check_parameter_valid('set', pll_auto_acq, [True, False], 'enable pll auto acquire')

		self.demod_sweep.step = frequency * _LLB_FREQSCALE

		self.embedded_pll.bandwidth = 0
		self.embedded_pll.pllreset = 0
		self.embedded_pll.autoacquire = 1 if pll_auto_acq == True else False
		self.embedded_pll.reacquire = 0
		self.lo_phase_offset = (phase/360.0) * (2**28-1)

		if source == 'internal':
			self.MuxLOPhase = 0
			self.MuxLOSignal = 0
			self.input2_light = 0
		elif source == 'external':
			self.MuxLOPhase = 0
			self.MuxLOSignal = 1
			self.input2_light = 1
		elif source == 'external_pll':
			self.embedded_pll.reacquire = 1
			self.MuxLOPhase = 1
			self.MuxLOSignal = 0
			self.input2_light = 1

		# update scales
		self._set_scale()

	@needs_commit
	def set_aux_sine(self, amplitude = 2.0, frequency = 0.0, phase = 0.0, sync_to_lo = False, output = 'out2'):
		"""
		Configure the aux sine signal.

		:type amplitude : float; [0, 2.0] Vpp
		:param amplitude : Auxiliary sine wave amplitude

		:type frequency : float; [0, 200e6] Hz
		:param frequency : Auxiliary sine wave frequency

		:type phase : float; [0, 360] degrees
		:param phase : float; Auxiliary sine wave phase offset

		:type sync_to_lo : bool
		:param sync_to_lo : True = enable phase synchronisation to local oscillator, False = use auxiliary frequency and phase values. 

		:type output : list; ['out1', 'out2', 'none']
		:param output : select which channel to output the auxiliary signal on. 

		"""
		_utils.check_parameter_valid('range', amplitude, [0, 2.0], desc='aux amplitude', units='volts peak-to-peak')
		_utils.check_parameter_valid('range', frequency, [0, 200e6], desc='aux frequency', units='hertz')
		_utils.check_parameter_valid('range', phase, [0, 360], desc='aux phase offset', units='degrees')
		_utils.check_parameter_valid('set', sync_to_lo, [True, False], 'sync phase to local oscillator')
		_utils.check_parameter_valid('set', output, ['out1', 'out2', 'none'], 'aux output channel')

		_str_to_scansource = {
			'out1' 	: _LLB_AUXSOURCE_DAC1,
			'out2'	: _LLB_AUXSOURCE_DAC2,
			'none'	: _LLB_AUXSOURCE_NONE
		}
		output = _str_to_scansource[output]

		self.aux_sine_sweep.step = frequency * _LLB_FREQSCALE
		self.aux_sine_sweep.stop = 2**64 -1
		self.aux_sine_sweep.duration = 0
		self.aux_sine_sweep.waveform = 2
		self.aux_sine_sweep.start = phase * _LLB_PHASESCALE
		self.aux_sine_sweep.wait_for_trig = False
		self.aux_sine_sweep.hold_last = False

		self.aux_phase_offset = phase * _LLB_PHASESCALE

		if sync_to_lo == True:
			self.MuxAuxPhase = 1
		else:
			self.MuxAuxPhase = 0

		if output == _LLB_AUXSOURCE_DAC1:
			self.fast_aux_enable = True
			self.slow_aux_enable = False
			self._aux_scale = (amplitude / 2.0) / self._dac_gains()[0] / 2.0**15
		elif output == _LLB_AUXSOURCE_DAC2:
			self.fast_aux_enable = False
			self.slow_aux_enable = True
			self._aux_scale = (amplitude / 2.0) / self._dac_gains()[1] / 2.0**15
		else:
			self.fast_aux_enable = False
			self.slow_aux_enable = False
			self._aux_scale = (amplitude / 2.0) / self._dac_gains()[1] / 2.0**15

	@needs_commit
	def set_scan(self, amplitude = 2.0, frequency = 0.0, phase = 0.0, waveform = 'triangle', output = 'out1'):
		"""
		Configure the scanning generator.

		:type amplitude : float; [0, 2.0] Vpp
		:param amplitude : Scan amplitude

		:type frequency : float; [0, 1e6] Hz
		:param frequency : Scan frequency

		:type phase : float; [0, 360] degrees
		:param phase : float; Scan phase offset

		:type waveform : List; ['sawtooth', 'triangle']
		:param sync_to_lo : Scan waveform type. 

		:type output : list; ['out1', 'out2', 'none']
		:param output : select which channel to output the scan signal on. 

		"""
		_utils.check_parameter_valid('range', amplitude, [0, 2.0], desc='scan amplitude', units='volts peak-to-peak')
		_utils.check_parameter_valid('range', frequency, [0, 1e6], desc='scan frequency', units='hertz')
		_utils.check_parameter_valid('range', phase, [0, 360], desc='scan phase offset', units='degrees')
		_utils.check_parameter_valid('set', waveform, ['sawtooth', 'triangle'], 'scan waveform type')
		_utils.check_parameter_valid('set', output, ['out1', 'out2', 'none'], 'scan output channel')

		_str_to_waveform = {
			'sawtooth' 	: _LLB_SCAN_SAWTOOTH,
			'triangle'	: _LLB_SCAN_TRIANGLE
		}
		waveform = _str_to_waveform[waveform]

		_str_to_scansource = {
			'out1' 	: _LLB_SCANSOURCE_DAC1,
			'out2'	: _LLB_SCANSOURCE_DAC2,
			'none'	: _LLB_SCANSOURCE_NONE
		}
		output = _str_to_scansource[output]

		self.scan_sweep.step = frequency * _LLB_FREQSCALE if waveform == _LLB_SCAN_SAWTOOTH else frequency * _LLB_FREQSCALE * 2
		self.scan_sweep.stop = 2**64 -1
		self.scan_sweep.duration = 0
		self.scan_sweep.waveform = waveform
		self.scan_sweep.start = phase * _LLB_SCANPHASESCALE
		self.scan_sweep.wait_for_trig = False
		self.scan_sweep.hold_last = False

		if output == _LLB_SCANSOURCE_DAC1:
			self.fast_scan_enable = True
			self.slow_scan_enable = False
			self.scan_amplitude = (amplitude / 2.0) / self._dac_gains()[0] / 2.0**15
		elif output == _LLB_SCANSOURCE_DAC2:
			self.fast_scan_enable = False
			self.slow_scan_enable = True
			self.scan_amplitude = (amplitude / 2.0) / self._dac_gains()[1] / 2.0**15
		else:
			self.fast_scan_enable = False
			self.slow_scan_enable = False
			self.scan_amplitude = (amplitude / 2.0) / self._dac_gains()[0] / 2.0**15 # default to out 1 scale

	def _signal_source_volts_per_bit(self, source, scales, trigger=False):
		"""
			Converts volts to bits depending on the signal source.
		"""
		# Decimation gain is applied only when using precision mode data
		if (not trigger and self.is_precision_mode()) or (trigger and self.trig_precision):
			deci_gain = self._deci_gain()
		else:
			deci_gain = 1.0

		if (source == _LLB_SOURCE_A):
			level = self._monitor_source_volts_per_bit(self.monitor_a, scales)/deci_gain
		elif (source == _LLB_SOURCE_B):
			level = self._monitor_source_volts_per_bit(self.monitor_b, scales)/deci_gain
		elif (source == _LLB_SOURCE_SCAN):
			level = self._monitor_source_volts_per_bit('scan', scales)/deci_gain
		elif (source == _LLB_SOURCE_IN1):
			level = self._monitor_source_volts_per_bit('in1', scales)/deci_gain
		elif (source == _LLB_SOURCE_IN2):
			level = self._monitor_source_volts_per_bit('in2', scales)/deci_gain
		elif (source == _LLB_TRIG_SRC_EXT):
			level = 1.0
		else:
			level = 1.0

		return level

	@needs_commit
	def _monitor_source_volts_per_bit(self, source, scales):

		lo_scale_factor = 1.0 if self.MuxLOSignal == 0 else self._adc_gains()[1] * 2**12  / (10.0 if self.get_frontend(2)[1] else 1.0)

		monitor_source_gains = {
			'error'			: scales['gain_adc1'] * 2.0 / (10.0 if scales['atten_ch1'] else 1.0) * lo_scale_factor,
			'pid_fast'		: scales['gain_adc1'] * 2.0 / (10.0 if scales['atten_ch1'] else 1.0) * lo_scale_factor,
			'pid_slow'		: scales['gain_adc1'] * 2.0 / (10.0 if scales['atten_ch1'] else 1.0) * lo_scale_factor,
			'offset_fast'	: scales['gain_adc1'] * 2.0 / (10.0 if scales['atten_ch1'] else 1.0) * lo_scale_factor,
			'in1' 			: scales['gain_adc1'] / (10.0 if scales['atten_ch1'] else 1.0),
			'in2' 			: scales['gain_adc2'] / (10.0 if scales['atten_ch2'] else 1.0),
			'out1'			: scales['gain_dac1'] * 2**4,
			'out2'			: scales['gain_dac2'] * 2**4,
			'scan'			: 2**4 * (scales['gain_dac2'] if self.slow_scan_enable== True else scales['gain_dac1']),
			'lo'			: scales['gain_adc2'] / (10.0 if scales['atten_ch2'] else 1.0) if self.MuxLOSignal == True else 2**-12,
			'aux'			: 2**4 * (scales['gain_dac1'] if self.fast_aux_enable == True else scales['gain_dac2'])
		}
		return monitor_source_gains[source]

	@needs_commit
	def set_trigger(self, source, edge, level, minwidth=None, maxwidth=None, hysteresis=10e-2, hf_reject=False, mode='auto', trig_on_scan_rising = False):
		""" 

		Set the trigger source for the monitor channel signals. This can be either of the input or
		monitor signals, the external input or the scan output. 

		:type source: string, {'in1','in2','scan','A','B','ext'}
		:param source: Trigger Source. May be either an input or monitor channel (as set by 
				:py:meth:`~pymoku.instruments.LockInAmp.set_monitor`), external or the scan output. External refers 
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

		:type trig_on_scan_rising: bool
		:param trig_on_scan_rising: trigger only during rising portion of scan signal.
		"""
		_utils.check_parameter_valid('set', source, ['in1', 'in2', 'scan', 'A', 'B', 'ext'], 'trigger source')
		_utils.check_parameter_valid('set', edge, ['rising','falling','both'], 'trigger edge')
		_utils.check_parameter_valid('range', level, [-10.0, 10.0], desc='trigger level', units='volts')

		if minwidth != None:
			_utils.check_parameter_valid('range', minwidth, [0, 2**32 / 62.5e6], desc='PWM triggering minwidth', units='seconds')
		if maxwidth != None:
			_utils.check_parameter_valid('range', minwidth, [0, 2**32 / 62.5e6], desc='PWM triggering maxwidth', units='seconds')

		_utils.check_parameter_valid('range', hysteresis, [100.0e-6, 1.0], desc='hysteresis', units='volts')
		_utils.check_parameter_valid('set', hf_reject, [True, False], 'hf reject')
		_utils.check_parameter_valid('set', mode, ['auto', 'normal'], 'trigger mode')
		_utils.check_parameter_valid('set', trig_on_scan_rising, [True, False], 'trigger only on scan rising edge')

		if source == 'scan':
			self.trig_aux = 1
		else:
			self.trig_aux = 0

		if trig_on_scan_rising:
			self.cond_trig = 1
		else:
			self.cond_trig = 0

		# Define the trigger sources appropriate to the LaserLockBox instrument
		source = _utils.str_to_val(_LLB_OSC_SOURCES, source, 'trigger source')
		# This function is the portion of set_trigger shared among instruments with embedded scopes. 
		self._set_trigger(source, edge, level, minwidth, maxwidth, hysteresis, hf_reject, mode)

	@needs_commit
	def set_monitor(self, monitor_ch, source):
		"""
		Select the point inside the laser lock box to monitor.

		There are two monitoring channels available, 'A' and 'B'; you can mux any of the internal
		monitoring points to either of these channels.

		The source is one of:
			- **error_signal**: error signal (after low-pass filter)
			- **pid_fast**: output of the fast pid
			- **pid_slow**: output of the slow pid
			- **offset_fast**: offset on the input to the fast pid
			- **in1**: input channel 1
			- **in2**: input channel 2
			- **out1**: output channel 1
			- **out2**: output channel 2
			- **scan**: scan signal
			- **lo**: local oscillator signal
			- **aux**: auxiliary sinewave signal

		:type monitor_ch: string; {'A','B'}
		:param monitor_ch: Monitor channel
		:type source: string; {'error', 'pid_fast', 'pid_slow', 'offset_fast', 'offset_slow', 'in1', 'in2', 'out1', 'out2', 'scan', 'lo', 'aux', 'slow_scan'}
		:param source: Signal to monitor
		"""
		_utils.check_parameter_valid('string', monitor_ch, desc="monitor channel")
		_utils.check_parameter_valid('string', source, desc="monitor signal")

		monitor_ch = monitor_ch.lower()
		source = source.lower()

		_utils.check_parameter_valid('set', monitor_ch, allowed=['a','b'], desc="monitor channel")
		_utils.check_parameter_valid('set', source, allowed=['error', 'pid_fast', 'pid_slow', 'offset_fast', 'offset_slow', 'in1', 'in2', 'out1', 'out2', 'scan', 'lo', 'aux', 'slow_scan'], desc="monitor source")

		monitor_sources = {
			'error'			: _LLB_MON_ERROR,
			'pid_fast'		: _LLB_MON_PID_FAST,
			'pid_slow'		: _LLB_MON_PID_SLOW,
			'offset_fast'	: _LLB_MON_OFFSET_FAST,
			'in1'			: _LLB_MON_IN1,
			'in2'			: _LLB_MON_IN2,
			'out1'			: _LLB_MON_OUT1,
			'out2'			: _LLB_MON_OUT2,
			'scan'			: _LLB_MON_SCAN,
			'lo'			: _LLB_MON_LO,
			'aux'			: _LLB_MON_AUX
		}

		if monitor_ch == 'a':
			self.monitor_a = source
			self.monitor_select0 = monitor_sources[source]
		elif monitor_ch == 'b':
			self.monitor_b = source
			self.monitor_select1 = monitor_sources[source]
		else:
			raise ValueOutOfRangeException("Invalid channel %d", monitor_ch)


_llb_reg_hdl = {
	'_fast_scale' :		(REG_LLB_GAINS_SCALING, to_reg_signed(0, 16, xform = lambda obj,  x : x * 2**14),
										from_reg_signed(0, 16, xform = lambda obj, x : x / 2**14)),

	'_slow_scale' : 	(REG_LLB_GAINS_SCALING, to_reg_signed(16, 16, xform = lambda obj, x : x * 2**14),
										from_reg_signed(16, 16, xform = lambda obj, x : x / 2**14)),

	'_aux_scale' : 	(REG_LLB_AUX_SCALE, to_reg_signed(0, 16, xform = lambda obj, x : x * 2**14),
										from_reg_signed(0, 16, xform = lambda obj, x : x / 2**14)),

	'scan_amplitude' :	(REG_LLB_SCAN_SCALE, to_reg_signed(0, 16, xform = lambda obj,  x : x * 2**14),
										from_reg_signed(0, 16, xform = lambda obj, x : x / 2**14)),

	'fast_scan_enable': (REG_LLB_SCAN_CTRL, to_reg_unsigned(0, 1),
											from_reg_unsigned(0, 1)),

	'slow_scan_enable': (REG_LLB_SCAN_CTRL, to_reg_unsigned(1, 1),
											from_reg_unsigned(1, 1)),

	'lo_phase_offset': (REG_LLB_LO_PHASE_OFFSET, to_reg_unsigned(0, 28),
													from_reg_unsigned(0, 28)),

	'aux_phase_offset': (REG_LLB_AUX_PHASE_OFFSET, to_reg_unsigned(0, 28),
													from_reg_unsigned(0, 28)),

	'fast_offset':	(REG_LLB_OFFSETS_FASTINPUT, to_reg_signed(0, 18, xform = lambda obj, x : x * 2**15),
											from_reg_signed(0, 18, xform = lambda obj, x : x / 2**15)),

	'output_offset_ch1': (REG_LLB_OFFSETS_FASTOUTPUT, to_reg_signed(0, 18, xform = lambda obj, x : x * (2**15)),
														from_reg_signed(0, 18, xform = lambda obj, x : x / (2**15))),

	'output_offset_ch2': (REG_LLB_OFFSETS_SLOWOUTPUT, to_reg_signed(0, 18, xform = lambda obj, x : x * (2**15)),
														from_reg_signed(0, 18, xform = lambda obj, x : x / (2**15))),

	'monitor_select0' :	(REG_LLB_MON_SEL, 	to_reg_unsigned(0, 4),
											from_reg_unsigned(0,4)),

	'monitor_select1' : (REG_LLB_MON_SEL,	to_reg_unsigned(4, 4),
											from_reg_unsigned(4, 4)),

	'input_gain_select': (REG_LLB_GAINS_INPUT,	to_reg_unsigned(0, 2),
										from_reg_unsigned(0, 2)),

	'MuxLOPhase':	(REG_LLB_LO_CTRL,	to_reg_unsigned(0, 1),
										from_reg_unsigned(0, 1)),

	'MuxLOSignal':	(REG_LLB_LO_CTRL,	to_reg_unsigned(1, 1),
										from_reg_unsigned(1, 1)),

	'MuxAuxPhase':	(REG_LLB_AUX_CTRL,	to_reg_unsigned(0, 1),
										from_reg_unsigned(0, 1)),

	'trig_aux':		(REG_LLB_MON_SEL,	to_reg_unsigned(8, 1),
										from_reg_unsigned(8, 1)),

	'cond_trig': (REG_LLB_MON_SEL, 	to_reg_unsigned(9, 1),
									from_reg_unsigned(9, 1)),

	'cliprange_lower_ch1':		(REG_LLB_CLIP_FAST, to_reg_signed(0, 16, xform = lambda obj, x : x * 2**15 - 1),
									from_reg_signed(0, 16, xform = lambda obj, x : x / (2**14 - 1))),

	'cliprange_upper_ch1':		(REG_LLB_CLIP_FAST, to_reg_signed(16, 16, xform = lambda obj, x : x * 2**15 - 1),
									from_reg_signed(16, 16, xform = lambda obj, x : x / (2**14 - 1))),

	'cliprange_lower_ch2':		(REG_LLB_CLIP_SLOW, to_reg_signed(0, 16, xform = lambda obj, x : x * 2**15 - 1),
									from_reg_signed(0, 16, xform = lambda obj, x : x / (2**14 - 1))),

	'cliprange_upper_ch2':		(REG_LLB_CLIP_SLOW, to_reg_signed(16, 16, xform = lambda obj, x : x * 2**15 - 1),
									from_reg_signed(16, 16, xform = lambda obj, x : x / (2**14 - 1))),

	'fast_aux_enable':			(REG_LLB_AUX_CTRL, to_reg_bool(1), from_reg_bool(1)),

	'slow_aux_enable':			(REG_LLB_AUX_CTRL, to_reg_bool(2), from_reg_bool(2)),

	'fast_channel_en':				(REG_LLB_ENABLES_LIGHTS, to_reg_bool(2), from_reg_bool(2)),

	'slow_channel_en':				(REG_LLB_ENABLES_LIGHTS, to_reg_bool(3), from_reg_bool(3)),

	'out1_en' :					(REG_LLB_ENABLES_LIGHTS, to_reg_bool(4), from_reg_bool(4)),

	'out2_en':					(REG_LLB_ENABLES_LIGHTS, to_reg_bool(5), from_reg_bool(5)),

	'input1_light':				(REG_LLB_ENABLES_LIGHTS, to_reg_bool(6), from_reg_bool(6)),

	'input2_light':				(REG_LLB_ENABLES_LIGHTS, to_reg_bool(7), from_reg_bool(7))


}