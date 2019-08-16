import math
import logging

from ._instrument import *
from . import _frame_instrument
from . import _utils

from ._specan_data import SpectrumData

log = logging.getLogger(__name__)

REG_SA_DEMOD		= 64
REG_SA_DECCTL		= 65
REG_SA_RBW			= 66
REG_SA_REFLVL		= 67

REG_SA_SOS0_GAIN	= 68
REG_SA_SOS0_A1		= 69
REG_SA_SOS0_A2		= 70
REG_SA_SOS0_B1		= 71

REG_SA_SOS1_GAIN	= 72
REG_SA_SOS1_A1		= 73
REG_SA_SOS1_A2		= 74
REG_SA_SOS1_B1		= 75

REG_SA_SOS2_GAIN	= 76
REG_SA_SOS2_A1		= 77
REG_SA_SOS2_A2		= 78
REG_SA_SOS2_B1		= 79

REG_SA_TR1_AMP 		= 96
REG_SA_TR1_START_H 	= 97
REG_SA_TR1_START_L 	= 98
REG_SA_TR1_STOP_H 	= 99
REG_SA_TR1_STOP_L	= 100
REG_SA_TR1_INCR_H	= 101
REG_SA_TR1_INCR_L 	= 102

REG_SA_TR2_AMP 		= 103
REG_SA_TR2_START_H 	= 104
REG_SA_TR2_START_L 	= 105
REG_SA_TR2_STOP_H 	= 106
REG_SA_TR2_STOP_L	= 107
REG_SA_TR2_INCR_H	= 108
REG_SA_TR2_INCR_L 	= 109

REG_SA_DEMOD_OFFSET  	= 121
REG_SA_DEMOD_SIN_FREQ	= 122
REG_SA_DEMOD_SHIFT_EN	= 123

_SA_WIN_BH			= 0
_SA_WIN_FLATTOP		= 1
_SA_WIN_HANNING		= 2
_SA_WIN_NONE		= 3

_SA_ADC_SMPS		= ADC_SMP_RATE
_SA_DAC_SMPS		= DAC_SMP_RATE
_SA_BUFLEN			= 2**14
_SA_SCREEN_WIDTH	= 1024
_SA_SCREEN_STEPS	= _SA_SCREEN_WIDTH - 1
_SA_FFT_LENGTH		= 8192/2
_SA_FREQ_SCALE		= 2**32 / _SA_ADC_SMPS
_SA_INT_VOLTS_SCALE = (1.437*pow(2.0,-8.0))
_SA_SG_FREQ_SCALE	= 2**48 / (_SA_ADC_SMPS * 2.0)

'''
	FILTER GAINS AND CORRECTION FACTORS
'''
_SA_WINDOW_WIDTH = {
	_SA_WIN_NONE : 0.89,
	_SA_WIN_BH : 1.90,
	_SA_WIN_HANNING : 1.44,
	_SA_WIN_FLATTOP : 3.77
}

_SA_WINDOW_POWER = {
	_SA_WIN_NONE : 131072.0,
	_SA_WIN_BH : 47015.48706054688,
	_SA_WIN_HANNING : 65527.00146484375,
	_SA_WIN_FLATTOP : 28268.48803710938
}

_SA_IIR_COEFFS = [
	[ 0,         0,         0,         0,         0,         0,         0,         0,         0,         0,         0,         0 ],
	[ 4532,    -97818,     49762,    121739,      3692,    -80900,     29842,    125987,      3304,    -73518,     21158,    130379 ],
	[ 3200,   -111604,     54330,     38124,      2346,    -96970,     38680,     71450,      1764,    -89934,     31184,    121125 ],
	[ 2802,   -117798,     56960,    -21172,      1858,   -105542,     44268,     19380,      1118,    -99312,     37840,    107358 ],
	[ 2672,   -121020,     58550,    -55842,      1658,   -110540,     47846,    -18635,       808,   -105026,     42230,     91389 ],
	[ 2592,   -123058,     59664,    -76871,      1540,   -113966,     50446,    -45291,       626,   -109070,     45494,     74459 ],
	[ 2504,   -124494,     60512,    -90354,      1448,   -116540,     52484,    -64100,       504,   -112182,     48094,     57462 ],
	[ 2516,   -125412,     61090,    -99442,      1428,   -118262,     53888,    -77633,       436,   -114292,     49900,     41025 ],
	[ 2432,   -126218,     61618,   -105830,      1362,   -119840,     55208,    -87595,       374,   -116264,     51618,     25542 ],
	[ 2414,   -126782,     62004,   -110479,      1340,   -120978,     56178,    -95093,       336,   -117698,     52888,     11229 ],
	[ 2466,   -127172,     62280,   -113963,      1360,   -121782,     56872,   -100854,       316,   -118714,     53800,     -1828 ],
	[ 2412,   -127580,     62574,   -116638,      1324,   -122644,     57626,   -105363,       288,   -119820,     54800,    -13631 ],
	[ 2336,   -127934,     62836,   -118734,      1276,   -123410,     58306,   -108951,       264,   -120812,     55706,    -24237 ],
	[ 2438,   -128112,     62972,   -120408,      1330,   -123798,     58652,   -111849,       262,   -121308,     56162,    -33731 ],
	[ 2382,   -128364,     63166,   -121763,      1296,   -124360,     59156,   -114220,       246,   -122040,     56838,    -42213 ],
	[ 2384,   -128548,     63310,   -122877,      1294,   -124776,     59534,   -116183,       238,   -122584,     57342,    -49785]
  ]

_SA_ADC_FREQ_RESP_0 = [ 1.0000,
	1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
	1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
	1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
	1.0000, 1.0000, 1.0001, 1.0006, 1.0015, 1.0028, 1.0041, 1.0053, 1.0061, 1.0064, 1.0056, 1.0052, 1.0048, 1.0039, 1.0034, 1.0024,
	1.0012, 0.9999, 0.9983, 0.9971, 0.9953, 0.9936, 0.9922, 0.9910, 0.9894, 0.9877, 0.9866, 0.9860, 0.9863, 0.9862, 0.9868, 0.9867,
	0.9873, 0.9881, 0.9891, 0.9901, 0.9908, 0.9913, 0.9922, 0.9935, 0.9940, 0.9941, 0.9936, 0.9927, 0.9923, 0.9911, 0.9897, 0.9876,
	0.9853, 0.9826, 0.9801, 0.9776, 0.9753, 0.9731, 0.9707, 0.9685, 0.9663, 0.9641, 0.9627, 0.9618, 0.9615, 0.9611, 0.9605, 0.9602,
	0.9601, 0.9604, 0.9607, 0.9609, 0.9613, 0.9613, 0.9616, 0.9615, 0.9606, 0.9602, 0.9593, 0.9586, 0.9570, 0.9554, 0.9536, 0.9518,
	0.9496, 0.9473, 0.9451, 0.9429, 0.9408, 0.9388, 0.9368, 0.9355, 0.9343, 0.9342, 0.9336, 0.9335, 0.9330, 0.9333, 0.9328, 0.9328,
	0.9328, 0.9325, 0.9317, 0.9304, 0.9296, 0.9283, 0.9266, 0.9245, 0.9211, 0.9180, 0.9142, 0.9100, 0.9058, 0.9009, 0.8964, 0.8917,
	0.8875, 0.8829, 0.8788, 0.8748, 0.8713, 0.8687, 0.8661, 0.8644, 0.8626, 0.8618, 0.8617, 0.8625, 0.8631, 0.8650, 0.8663, 0.8678,
	0.8685, 0.8691, 0.8703, 0.8708, 0.8712, 0.8706, 0.8691, 0.8661, 0.8621, 0.8569, 0.8510, 0.8442, 0.8366, 0.8285, 0.8198, 0.8107,
	0.8015, 0.7916, 0.7824, 0.7732, 0.7659, 0.7581, 0.7519, 0.7460, 0.7415, 0.7375, 0.7338, 0.7312, 0.7298, 0.7295, 0.7297, 0.7306,
	0.7322, 0.7341, 0.7362, 0.7381, 0.7403, 0.7417, 0.7425, 0.7420, 0.7406, 0.7378, 0.7338, 0.7283, 0.7219, 0.7138, 0.7049, 0.6945,
	0.6839, 0.6721, 0.6601, 0.6480, 0.6364, 0.6250, 0.6142, 0.6039, 0.5945, 0.5863, 0.5784, 0.5716, 0.5656, 0.5610, 0.5572, 0.5543,
	0.5519, 0.5503, 0.5498, 0.5500, 0.5505, 0.5509, 0.5517, 0.5521, 0.5518, 0.5510, 0.5497, 0.5476, 0.5453, 0.5427, 0.5404, 0.5383 ]

_SA_ADC_FREQ_RESP_20 = [ 1.0000,
	1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
	1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
	1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
	1.0000, 1.0000, 0.9999, 0.9993, 0.9996, 1.0003, 1.0008, 1.0010, 1.0004, 1.0007, 1.0006, 1.0003, 0.9999, 0.9993, 0.9984, 0.9978,
	0.9975, 0.9972, 0.9968, 0.9956, 0.9944, 0.9940, 0.9928, 0.9921, 0.9916, 0.9921, 0.9927, 0.9928, 0.9926, 0.9923, 0.9923, 0.9923,
	0.9922, 0.9923, 0.9931, 0.9947, 0.9954, 0.9968, 0.9978, 0.9982, 0.9985, 0.9983, 0.9985, 0.9991, 0.9993, 1.0000, 0.9999, 0.9996,
	0.9989, 0.9986, 0.9982, 0.9981, 0.9976, 0.9973, 0.9970, 0.9962, 0.9957, 0.9950, 0.9944, 0.9940, 0.9940, 0.9939, 0.9940, 0.9937,
	0.9943, 0.9942, 0.9953, 0.9959, 0.9967, 0.9973, 0.9971, 0.9977, 0.9981, 0.9986, 0.9984, 0.9982, 0.9972, 0.9970, 0.9963, 0.9954,
	0.9944, 0.9933, 0.9926, 0.9917, 0.9900, 0.9888, 0.9876, 0.9876, 0.9873, 0.9861, 0.9850, 0.9840, 0.9839, 0.9839, 0.9840, 0.9843,
	0.9842, 0.9836, 0.9821, 0.9818, 0.9819, 0.9820, 0.9810, 0.9794, 0.9776, 0.9760, 0.9741, 0.9720, 0.9698, 0.9674, 0.9654, 0.9621,
	0.9586, 0.9555, 0.9516, 0.9486, 0.9455, 0.9429, 0.9403, 0.9381, 0.9365, 0.9357, 0.9344, 0.9319, 0.9303, 0.9304, 0.9301, 0.9298,
	0.9280, 0.9271, 0.9272, 0.9264, 0.9259, 0.9254, 0.9247, 0.9247, 0.9229, 0.9204, 0.9179, 0.9160, 0.9138, 0.9109, 0.9056, 0.9019,
	0.8952, 0.8893, 0.8830, 0.8773, 0.8732, 0.8694, 0.8627, 0.8562, 0.8468, 0.8389, 0.8318, 0.8258, 0.8225, 0.8173, 0.8135, 0.8088,
	0.8051, 0.8018, 0.7992, 0.7970, 0.7952, 0.7929, 0.7914, 0.7902, 0.7888, 0.7865, 0.7839, 0.7815, 0.7778, 0.7739, 0.7696, 0.7652,
	0.7595, 0.7526, 0.7453, 0.7387, 0.7310, 0.7228, 0.7139, 0.7054, 0.6965, 0.6872, 0.6786, 0.6702, 0.6619, 0.6538, 0.6452, 0.6385,
	0.6320, 0.6270, 0.6211, 0.6158, 0.6107, 0.6061, 0.6016, 0.5972, 0.5929, 0.5895, 0.5863, 0.5832, 0.5814, 0.5794, 0.5780, 0.5765 ]


class SpectrumAnalyzer(_frame_instrument.FrameBasedInstrument):
	""" Spectrum Analyzer instrument object.

	To run a new Spectrum Analyzer instrument, this should be instantiated and deployed via a connected
	:any:`Moku` object using :any:`deploy_instrument`. Alternatively, a pre-configured instrument object
	can be obtained by discovering an already running Spectrum Analyzer instrument on a Moku:Lab device via
	:any:`discover_instrument`.

	.. automethod:: pymoku.instruments.SpectrumAnalyzer.__init__

	.. attribute:: framerate
		:annotation: = 10

		Frame Rate, range 10 - 30.

	.. attribute:: type
		:annotation: = "spectrumanalyzer"

		Name of this instrument.

	"""
	def __init__(self):
		"""Create a new Spectrum Analyzer instrument, ready to be attached to a Moku."""
		super(SpectrumAnalyzer, self).__init__()
		self._register_accessors(_sa_reg_handlers)

		self.scales = {}
		self._set_frame_class(SpectrumData, instrument=self, scales=self.scales)

		self.id = 2
		self.type = "spectrumanalyzer"
		self.calibration = None

		self.tr1_incr = 0
		self.tr2_incr = 0
		self.sweep1 = False
		self.sweep2 = False

		self.f1 = 0
		self.f2 = 250e6

		self.rbw = None
		self.dbmscale = True


	def _calculate_decimations(self):
		# Computes the decimations given the input span
		# Doesn't guarantee a total decimation of the ideal value, even if such an integer sequence exists
		f1 = self.f1
		f2 = self.f2

		fspan = f2 - f1
		ideal = math.floor(_SA_ADC_SMPS / 8.0 /  fspan)
		if ideal < 2:
			d1 = 1
			d2 = d3 = d4 = 1
		else:

			'''
			# TODO: Use the table of optimal decimations to find d1-d4
			deci_idx = bisect_right(_DECIMATIONS_TABLE, (ideal,99,99,99,99))
			deci, d1, d2, d3, d4 = _DECIMATIONS_TABLE[deci_idx - 1]
			'''
			d1 = 4
			dec = ideal / d1

			d2 = min(max(math.ceil(dec / 16 / 16), 1), 64)
			dec /= d2

			d3 = min(max(math.ceil(dec / 16), 1), 16)
			dec /= d3

			d4 = min(max(math.floor(dec), 1), 16)

		return d1, d2, d3, d4, ideal

	def _set_decimations(self, d1, d2, d3, d4, ideal):

		# d1 can only be x4 decimation
		self.bs_cic2 = math.ceil(2 * math.log(d2, 2))
		self.bs_cic3 = math.ceil(3 * math.log(d3, 2))

		self.dec_enable = d1 == 4
		self.dec_cic2 = d2
		self.dec_cic3 = d3
		self.dec_iir  = d4

		total_decimation = d1 * d2 * d3 * d4
		self._total_decimation = total_decimation if total_decimation else 1

		log.debug("Decimations: %d %d %d %d = %d (ideal %f)", d1, d2, d3, d4, total_decimation, ideal)

	def _calculate_rbw(self):
		"""
			Calculates the RBW value based on current mode
		"""
		fspan = self.f2 - self.f1
		rbw = self.rbw

		if rbw == None:
			if self.sweep1 or self.sweep2:
				rbw = fspan / 50.0
			else:
				rbw = 5.0 * fspan / _SA_SCREEN_STEPS

		window_factor = _SA_WINDOW_WIDTH[self.window]
		fbin_resolution = _SA_ADC_SMPS / 2.0 /_SA_FFT_LENGTH / self._total_decimation

		return min(max(rbw, (17.0 / 16.0) * fbin_resolution * window_factor), 2**10.0 * fbin_resolution * window_factor)

	def _set_rbw_ratio(self, rbw):
		window_factor = _SA_WINDOW_WIDTH[self.window]
		fbin_resolution = _SA_ADC_SMPS / 2.0 / _SA_FFT_LENGTH / self._total_decimation

		self.rbw = rbw
		self.rbw_ratio = rbw / window_factor / fbin_resolution
		log.info("Resolution bandwidth set to %.2f Hz", self.rbw)

	def _set_demodulation_compensation(self):
		"""
			This function is called to re-calculate the offsets, dithering gains and under saturation
			sinewave gains used to remove spectral artefacts from the instrument.
		"""
		self._compensation_singen()
		self._compensation_dithering()
		self._compensation_offset()

	def _compensation_singen(self):
		# Increase sinewave amplitude as span is reduced. Don't consider spans less than 1 kHz
		span = max(self.f2 - self.f1, 1.0e3)
		self.demod_sinegen_bitshift = max(min(17 - math.floor(2.4 * math.log10(span)), 7), 0)
		self.demod_sinegen_enable = (span < 2.0e6) and (self.demod_sinegen_bitshift != 0)

		# Phase dither to broaden sinewave peak to ~512 FFT points
		self.demod_phase_bitshift = round(14.0 - 0.58 * math.log(1.0e6 / span, 2))

		# Sinewave frequency. Place at 1.9 screens from DC. Need to correct for phase dither offset
		fbin_resolution = _SA_ADC_SMPS / 2.0 / _SA_FFT_LENGTH / self._total_decimation
		desired_frequency = fbin_resolution * _SA_FFT_LENGTH * 0.475
		phase_step = min(round(desired_frequency / _SA_DAC_SMPS * 2**32), 2**32)
		self.demod_sinegen_freq = phase_step - round(31.0/32.0 * 2**(self.demod_phase_bitshift + 4))

	def _compensation_dithering(self):
		self.demod_dither_bitshift = max(min(int(self.demod_sinegen_bitshift) - 1, 2), 0)
		self.demod_dither_enable = True

	def _compensation_offset(self):
		# normal 0.5 lsb rounding offset
		iq_offset = 0x4000

		# offset from additive dither
		iq_offset += 0x400 * (1 << self.demod_dither_bitshift)

		# filter offsets
		d1, d2, d3, d4, ideal = self._calculate_decimations()
		if d2 == 1 and d3 == 4:
			iq_offset -= 80
		elif d2 == 3:
			iq_offset -= 896
		elif d2 > 3 and d2 < 16:
			iq_offset -= round(2**(-0.52 * d2 + 10.8))
		elif d2 > 16:
			iq_offset += 64

		self.demod_iq_offset = iq_offset

	def _update_dependent_regs(self):
		"""
			This function is called at commit time to ensure a consistent Moku register state.
			It sets all registers that are dependent on other register values (sensitive to ordering).
		"""
		# Set the demodulation frequency to mix down the signal to DC
		self.demod = self.f2

		# Set the CIC decimations
		d1, d2, d3, d4, ideal = self._calculate_decimations()
		self._set_decimations(d1, d2, d3, d4, ideal)

		# Set the filter gains based on the set CIC decimations
		filter_set = _SA_IIR_COEFFS[self.dec_iir-1]
		self.gain_sos0, self.a1_sos0, self.a2_sos0, self.b1_sos0 = filter_set[0:4]
		self.gain_sos1, self.a1_sos1, self.a2_sos1, self.b1_sos1 = filter_set[4:8]
		self.gain_sos2, self.a1_sos2, self.a2_sos2, self.b1_sos2 = filter_set[8:12]

		# Set rendering decimations
		fspan = self.f2 - self.f1
		buffer_span = _SA_ADC_SMPS / 2.0 / self._total_decimation
		self.render_dds = min(max(math.ceil(fspan / buffer_span * _SA_FFT_LENGTH/ _SA_SCREEN_STEPS), 1.0), 4.0)
		self.render_dds_alt = self.render_dds

		# Calculate and set the Resolution Bandwidth (RBW)
		rbw = self._calculate_rbw()
		self._set_rbw_ratio(rbw)

		self.ref_level = 6

		# Output waveform generator sweep depends on the instrument parameters for optimal
		# increment vs screen update rate
		self._set_sweep_increments()

		# Calculate demodulation offsets, gains and dithering
		self._set_demodulation_compensation()

		log.debug("DM: %f FS: %f, BS: %f, RD: %f, W:%d, RBW: %f, RBR: %f", self.demod, fspan, buffer_span, self.render_dds, self.window, rbw, self.rbw_ratio)


	@needs_commit
	def set_span(self,f1,f2):
		""" Sets the frequency span to be analysed.

		Rounding and quantization in the instrument limits the range of spans for which a full set of 1024
		data points can be calculated. This means that the resultant number of data points in
		:any:`SpectrumData` frames will vary with the set span. Note however that the associated frequencies are
		given with the frame containing the data.

		:type f1: float
		:param f1: Left-most frequency (Hz)
		:type f2: float
		:param f2: Right-most frequency (Hz)

		:raises InvalidConfigurationException: if the span is not positive-definite.
		"""
		_utils.check_parameter_valid('range', f1, [0,250e6], 'left frequency', 'Hz')
		_utils.check_parameter_valid('range', f2, [0,250e6], 'right frequency', 'Hz')
		if f2 <= f1:
			raise InvalidConfigurationException("Span must be non-negative with f2 > f1")

		# Set the actual input frequencies
		self.f1 = f1
		self.f2 = f2

	@needs_commit
	def set_rbw(self, rbw=None):
		""" Set desired Resolution Bandwidth

		Actual resolution bandwidth will be rounded to the nearest allowable unit
		when settings are applied to the device.

		:type rbw: float
		:param rbw: Desired resolution bandwidth (Hz), or ``None`` for auto-mode

		:raises ValueError: if the RBW is not positive-definite or *None*
		"""
		if rbw and rbw < 0:
			raise ValueError("Invalid RBW (should be >= 0 or None) %d", rbw)

		self.rbw = rbw

	def get_rbw(self):
		""":return: The current resolution bandwidth (Hz) """
		return self.rbw

	@needs_commit
	def set_window(self, window):
		""" Set Window function

		:type window: string, {'blackman-harris','flattop','hanning','none'}
		:param window: Window Function
		"""
		_str_to_window_function = {
			'blackman-harris': _SA_WIN_BH,
			'flattop' : _SA_WIN_FLATTOP,
			'hanning' : _SA_WIN_HANNING,
			'none'	: _SA_WIN_NONE
		}
		window = _utils.str_to_val(_str_to_window_function, window, 'window function')
		self.window = window

	@needs_commit
	def set_dbmscale(self,dbm=True):
		""" Configures the scale of the Spectrum Analyzer amplitude data.
		This can be either power in dBm, or RMS Voltage.

		:type dbm: bool
		:param dbm: Enable dBm scale
		"""
		_utils.check_parameter_valid('bool', dbm, desc='enable dBm scale')
		self.dbmscale = dbm

	@needs_commit
	def set_defaults(self):
		""" Reset the Spectrum Analyzer to sane defaults. """
		super(SpectrumAnalyzer, self).set_defaults()
		#TODO this should reset ALL registers
		self.frame_length = _SA_SCREEN_WIDTH

		self.offset = 0
		self.offset_alt = 0

		self.ref_level = 0

		self.render_mode = RDR_DDS
		self.x_mode = FULL_FRAME

		self.set_frontend(1,fiftyr=False, atten=True, ac=False)
		self.set_frontend(2,fiftyr=False, atten=True, ac=False)
		self.en_in_ch1 = True
		self.en_in_ch2 = True

		# Signal generator defaults
		self.sweep1 = False
		self.sweep2 = False
		self.tr1_start = 100e6
		self.tr1_stop = 0
		self.tr2_start = 100e6
		self.tr2_stop = 0
		self.tr1_incr = 0
		self.tr2_incr = 0

		self.set_span(0,250e6)
		self.window = _SA_WIN_BH

	def _calculate_freq_step(self):
		bufspan = _SA_ADC_SMPS / 2.0 / self._total_decimation
		buf_freq_step = bufspan / _SA_FFT_LENGTH

		return (buf_freq_step * self.render_dds)

	def _calculate_start_freq(self):
		freq_step = self._calculate_freq_step()

		bufspan = _SA_ADC_SMPS / 2.0 / self._total_decimation
		buf_start_freq = self.demod
		buf_freq_step = bufspan / _SA_FFT_LENGTH

		dev_stop_freq = buf_start_freq + (self.offset + 4) * buf_freq_step

		return (dev_stop_freq - _SA_SCREEN_WIDTH * freq_step)

	def _calculate_adc_freq_resp(self, f, atten):
		frac_idx = f / (_SA_ADC_SMPS / 2.0)

		idx = (len(_SA_ADC_FREQ_RESP_0) - 1) * min(max(frac_idx, 0.0), 1.0)
		r = _SA_ADC_FREQ_RESP_20 if atten else _SA_ADC_FREQ_RESP_0

		# Return linear interpolation of table values
		correction = r[int(math.floor(idx))] + (idx - math.floor(idx)) * (r[int(math.ceil(idx))] - r[int(math.floor(idx))])
		return correction

	def _calculate_cic_freq_resp(self, f, dec, order):
		"""
		Calculate the CIC filter droop correction.
		In this case 'f' is the frequency (Hz) relative to the demodulation frequency.
		"""
		freq = f/_SA_ADC_SMPS

		correction = 1.0 if (freq == 0.0) else math.pow(math.fabs(math.sin(math.pi*freq*dec)/(math.sin(math.pi*freq)*dec)), order)

		return correction

	def _calculate_scales(self):
		"""
		Returns per-channel correction and scaling parameters required for interpretation of incoming bit frames
		Parameters are based on current instrument state
		"""
		# Returns the bits-to-volts numbers for each channel in the current state
		g1, g2 = self._adc_gains()

		filt_gain1 = 2 ** (-5.0) if self.dec_enable else 1.0
		filt_gain2 = 2.0 ** (self.bs_cic2 - 2.0 * math.log(self.dec_cic2, 2))
		filt_gain3 = 2.0 ** (self.bs_cic3 - 3.0 * math.log(self.dec_cic3, 2))
		filt_gain4 = 1.0

		filt_gain = filt_gain1 * filt_gain2 * filt_gain3 * filt_gain4
		window_gain = 1.0 / _SA_WINDOW_POWER[self.window]

		g1 *= _SA_INT_VOLTS_SCALE * filt_gain * window_gain * self.rbw_ratio * (2**10)
		g2 *= _SA_INT_VOLTS_SCALE * filt_gain * window_gain * self.rbw_ratio * (2**10)

		# Find approximate frequency bin values
		dev_start_freq = self._calculate_start_freq()
		dev_freq_step = self._calculate_freq_step()
		freqs = [ (dev_start_freq + dev_freq_step*i) for i in range(_SA_SCREEN_WIDTH)]

		# Compute the frequency dependent correction arrays
		# The CIC correction is only for CIC1 which is decimation=4 only, and 10th order
		if self._total_decimation >= 4:
			cic_corrs = [ self._calculate_cic_freq_resp(i*dev_freq_step, 4, 10) for i in range(len(freqs))]
		else:
			cic_corrs = [1.0] * len(freqs)

		fcorrs = [ (1 / self._calculate_adc_freq_resp(f, True) / cic_corr) for f, cic_corr in zip(freqs, cic_corrs)]

		return {'g1': g1, 'g2': g2, 'fs': freqs, 'fcorrs': fcorrs, 'fspan': [self.f1, self.f2], 'dbmscale': self.dbmscale}

	@needs_commit
	def gen_off(self, ch=None):
		"""
		Turn waveform generator output off.

		If *ch* is specified, turn off only a single channel, otherwise turn off both.

		:type ch: int; {1,2}
		:param ch: Channel number to turn off (None, or leave blank, for both)firmware_is_compatible
		"""
		_utils.check_parameter_valid('set', ch, [1,2,None],'output channel')
		if ch is None or ch == 1:
			self.tr1_amp = 0
		if ch is None or ch == 2:
			self.tr2_amp = 0

	@needs_commit
	def gen_sinewave(self, ch, amp, freq, sweep=False):
		"""
		Configure the output sinewaves on DAC channels

		:type ch: int; {1,2}
		:param ch: Output DAC channel to configure

		:type amp: float, 0.0 - 2.0 volts
		:param amp: Peak-to-peak output voltage

		:type freq: float, 0 - 250e6 Hertz
		:param freq: Frequency of output sinewave (ignored if sweep=True)

		:type sweep: bool
		:param sweep: Sweep current frequency span (ignores freq parameter if True). Defaults to False.

		:raises ValueError: if the channel number is invalid
		:raises ValueOutOfRangeException: if wave parameters are out of range

		"""
		_utils.check_parameter_valid('set', ch, [1,2],'output channel')
		_utils.check_parameter_valid('range', amp, [0.0, 2.0],'sinewave amplitude','Volts')
		_utils.check_parameter_valid('range', freq, [0,250e6],'sinewave frequency', 'Hz')
		_utils.check_parameter_valid('bool', sweep, desc='sweep enable')

		if ch == 1:
			self.sweep1 = sweep
			self.tr1_amp = amp
			if sweep:
				self.tr1_start = self.f1
				self.tr1_stop  = self.f2
			else:
				self.tr1_start = freq
				self.tr1_stop = 0
				self.tr1_incr = 0
		elif ch == 2:
			self.sweep2 = sweep
			self.tr2_amp = amp
			if sweep:
				self.tr2_start = self.f1
				self.tr2_stop  = self.f2
			else:
				self.tr2_start = freq
				self.tr2_stop = 0
				self.tr2_incr = 0

	def _set_sweep_increments(self):
		"""
		Calculates the optimal frequency increment for the generated output sinewaves sweep
		based on FFT computation time and framerate.
		"""
		fspan = self.f2 - self.f1
		framerate = self.framerate
		decimation = self._total_decimation

		increment = 0
		if self.sweep1 or self.sweep2:
			samplerate = _SA_ADC_SMPS / decimation
			windowed_points = 2*_SA_FFT_LENGTH/self.rbw_ratio
			fft_time = windowed_points / samplerate + (2*_SA_FFT_LENGTH - windowed_points)/125e6 + (1.0/1788.8)
			screen_update_time = max(round(fft_time*framerate)/framerate, 1.0/framerate)

			increment =  fspan / 100.5 * (fft_time / screen_update_time)

		if self.sweep1:
			self.tr1_incr = increment
		if self.sweep2:
			self.tr2_incr = increment

		log.debug("SW1: %s, AMP1: %f, INCR1: %f, FREQ1: %f/%f, SW2: %s, AMP2: %f, INCR2: %f, FREQ2: %f/%f", self.sweep1, self.tr1_amp, self.tr1_incr, self.tr1_start, self.tr1_stop, self.sweep2, self.tr2_amp, self.tr2_incr, self.tr2_start, self.tr2_stop)

	def commit(self):
		# Update registers that depend on others being calculated
		self._update_dependent_regs()

		# Push the controls through to the device
		super(SpectrumAnalyzer, self).commit()

		# Update the scaling factors for processing of incoming frames
		# stateid allows us to track which scales correspond to which register state
		self.scales[self._stateid] = self._calculate_scales()

		# TODO: Trim scales dictionary, getting rid of old ids

	# Bring in the docstring from the superclass for our docco.
	commit.__doc__ = MokuInstrument.commit.__doc__

	def _on_reg_sync(self):
		super(SpectrumAnalyzer, self)._on_reg_sync()

		if self.dec_enable:
			d1 = 4
			total_decimation = d1 * self.dec_cic2 * self.dec_cic3 * self.dec_iir
		else:
			total_decimation = 1
		self._total_decimation = total_decimation

		fspan = _SA_ADC_SMPS / 2.0 / self._total_decimation

		fbin_resolution = fspan / _SA_FFT_LENGTH
		window_factor = _SA_WINDOW_WIDTH[self.window]

		self.rbw = self.rbw_ratio * window_factor * fbin_resolution

		self.f2 = self.demod
		self.f1 = self.demod - fspan
		self.scales[self._stateid] = self._calculate_scales()

	def get_data(self, timeout=None, wait=True):
		"""
		Get the latest sweep results.

		On SpectrumAnalyzer this is an alias for :any:`get_realtime_data <pymoku.instruments.SpectrumAnalyzer.get_realtime_data>` as the
		output data is never downsampled from the sweep results.
		"""
		_utils.check_parameter_valid('float', timeout, desc='data timeout', allow_none=True)
		_utils.check_parameter_valid('bool', wait, desc='data wait')
		return self.get_realtime_data(timeout=timeout,wait=wait)

_sa_reg_handlers = {
	'demod':			(REG_SA_DEMOD,		to_reg_unsigned(0, 32, xform=lambda obj, f: f * _SA_FREQ_SCALE),
											from_reg_unsigned(0, 32, xform=lambda obj, f: f / _SA_FREQ_SCALE)),

	'dec_enable':		(REG_SA_DECCTL,		to_reg_bool(0),				from_reg_bool(0)),
	'dec_cic2':			(REG_SA_DECCTL,		to_reg_unsigned(1, 6, 	xform=lambda obj, x: x - 1),
											from_reg_unsigned(1, 6, xform=lambda obj, x: x + 1)),
	'bs_cic2':			(REG_SA_DECCTL,		to_reg_unsigned(7, 4),		from_reg_unsigned(7, 4)),
	'dec_cic3':			(REG_SA_DECCTL,		to_reg_unsigned(11, 4, 	xform=lambda obj, x: x - 1),
											from_reg_unsigned(11, 4,xform=lambda obj, x: x + 1)),
	'bs_cic3':			(REG_SA_DECCTL,		to_reg_unsigned(15, 4),		from_reg_unsigned(15, 4)),
	'dec_iir':			(REG_SA_DECCTL,		to_reg_unsigned(19, 4, 	xform=lambda obj, x: x - 1),
											from_reg_unsigned(19, 4,xform=lambda obj, x: x + 1)),
	'rbw_ratio':		(REG_SA_RBW,		to_reg_unsigned(0, 24, 	xform=lambda obj, x: round(x * 2.0**10.0)),
											from_reg_unsigned(0, 24,xform=lambda obj, x: x / (2.0**10.0))),

	'window':			(REG_SA_RBW,		to_reg_unsigned(24, 2, allow_set=[_SA_WIN_NONE, _SA_WIN_BH, _SA_WIN_HANNING, _SA_WIN_FLATTOP]),
											from_reg_unsigned(24, 2)),

	'ref_level':		(REG_SA_REFLVL,		to_reg_unsigned(0, 4),		from_reg_unsigned(0, 4)),
	'gain_sos0':		(REG_SA_SOS0_GAIN,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'a1_sos0':			(REG_SA_SOS0_A1,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'a2_sos0':			(REG_SA_SOS0_A2,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'b1_sos0':			(REG_SA_SOS0_B1,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'gain_sos1':		(REG_SA_SOS1_GAIN,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'a1_sos1':			(REG_SA_SOS1_A1,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'a2_sos1':			(REG_SA_SOS1_A2,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'b1_sos1':			(REG_SA_SOS1_B1,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'gain_sos2':		(REG_SA_SOS2_GAIN,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'a1_sos2':			(REG_SA_SOS2_A1,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'a2_sos2':			(REG_SA_SOS2_A2,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),
	'b1_sos2':			(REG_SA_SOS2_B1,	to_reg_signed(0, 18),		from_reg_signed(0, 18)),

	'tr1_amp'	:	(REG_SA_TR1_AMP,	to_reg_unsigned(0, 16, xform=lambda obj, p:p / obj._dac_gains()[0]),
										from_reg_unsigned(0, 16, xform=lambda obj, p:p * obj._dac_gains()[0])),
	'tr1_start'	:	((REG_SA_TR1_START_H, REG_SA_TR1_START_L),
										to_reg_unsigned(0, 48, xform=lambda obj, p:p * _SA_SG_FREQ_SCALE),
										from_reg_unsigned(0, 48, xform=lambda obj, p:p / _SA_SG_FREQ_SCALE)),
	'tr1_stop'	:	((REG_SA_TR1_STOP_H, REG_SA_TR1_STOP_L),
										to_reg_unsigned(0, 48, xform=lambda obj, p:p * _SA_SG_FREQ_SCALE),
										from_reg_unsigned(0, 48, xform=lambda obj, p:p / _SA_SG_FREQ_SCALE)),
	'tr1_incr'	:	((REG_SA_TR1_INCR_H, REG_SA_TR1_INCR_L),
										to_reg_unsigned(0, 48, xform=lambda obj, p:p * _SA_SG_FREQ_SCALE),
										from_reg_unsigned(0, 48, xform=lambda obj, p:p / _SA_SG_FREQ_SCALE)),

	'tr2_amp'	:	(REG_SA_TR2_AMP,	to_reg_unsigned(0, 16, xform=lambda obj, p:p / obj._dac_gains()[1]),
										from_reg_unsigned(0, 16, xform=lambda obj, p:p * obj._dac_gains()[1])),
	'tr2_start'	:	((REG_SA_TR2_START_H, REG_SA_TR2_START_L),
										to_reg_unsigned(0, 48, xform=lambda obj, p:p * _SA_SG_FREQ_SCALE),
										from_reg_unsigned(0, 48, xform=lambda obj, p:p / _SA_SG_FREQ_SCALE)),
	'tr2_stop'	:	((REG_SA_TR2_STOP_H, REG_SA_TR2_STOP_L),
										to_reg_unsigned(0, 48, xform=lambda obj, p:p * _SA_SG_FREQ_SCALE),
										from_reg_unsigned(0, 48, xform=lambda obj, p:p / _SA_SG_FREQ_SCALE)),
	'tr2_incr'	:	((REG_SA_TR2_INCR_H, REG_SA_TR2_INCR_L),
										to_reg_unsigned(0, 48, xform=lambda obj, p:p * _SA_SG_FREQ_SCALE),
										from_reg_unsigned(0, 48, xform=lambda obj, p:p / _SA_SG_FREQ_SCALE)),

	'demod_iq_offset':			(REG_SA_DEMOD_OFFSET,		to_reg_unsigned(0, 28),	from_reg_unsigned(0, 28)),
	'demod_sinegen_freq':		(REG_SA_DEMOD_SIN_FREQ,		to_reg_unsigned(0, 32),	from_reg_unsigned(0, 32)),
	'demod_dither_enable':		(REG_SA_DEMOD_SHIFT_EN,				to_reg_bool(0),			from_reg_bool(0)),
	'demod_sinegen_enable':		(REG_SA_DEMOD_SHIFT_EN,				to_reg_bool(1),			from_reg_bool(1)),
	'demod_dither_bitshift':	(REG_SA_DEMOD_SHIFT_EN,		to_reg_unsigned(2, 3),	from_reg_unsigned(2, 3)),
	'demod_sinegen_bitshift':	(REG_SA_DEMOD_SHIFT_EN,		to_reg_unsigned(5, 3),	from_reg_unsigned(5, 3)),
	'demod_phase_bitshift':		(REG_SA_DEMOD_SHIFT_EN,		to_reg_unsigned(8, 5),	from_reg_unsigned(8, 5))
}