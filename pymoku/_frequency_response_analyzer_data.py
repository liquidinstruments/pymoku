import math
import struct

from . import _frame_instrument


class _FRAChannelData():

	def __init__(self, input_signal, gain_correction, front_end_scale, output_amp):

		# Extract the length of the signal (this varies with number of sweep points)
		sig_len = len(gain_correction)

		# De-interleave IQ values
		self.i_sig, self.q_sig = zip(*zip(*[iter(input_signal)]*2))
		self.i_sig = self.i_sig[:sig_len]
		self.q_sig = self.q_sig[:sig_len]

		# Calculates magnitude of a sample given I,Q and gain correction factors
		def calculate_magnitude(I,Q,G,frontend_scale):
			if I is None or Q is None:
				return None
			else:
				return 2.0 * math.sqrt((I or 0)**2 + (Q or 0)**2) * front_end_scale / (G or 1)

		self.magnitude = [calculate_magnitude(I,Q,G,front_end_scale) for I, Q, G in zip(self.i_sig, self.q_sig, gain_correction)]

		# Sometimes there's a transient condition at startup where we don't have a valid output_amp. Return Nones in that
		# case in preference to exploding.
		self.magnitude_dB = [ None if not x else 20.0 * math.log10(x / output_amp) if output_amp else None for x in self.magnitude ]

		self.phase = [ None if (I is None or Q is None) else (math.atan2(Q or 0, I or 0))/(2.0*math.pi) for I, Q in zip(self.i_sig, self.q_sig)]

	def __json__(self):
		return { 'magnitude' : self.magnitude, 'magnitude_dB' : self.magnitude_dB, 'phase' : self.phase }


class FRAData(_frame_instrument.InstrumentData):
	"""
	Object representing a frame of dual-channel (amplitude and phase) vs frequency response data.

	This is the native output format of the :any:`FrequencyResponseAnalyzer` instrument.

	This object should not be instantiated directly, but will be returned by a call to
	:any:`get_data <pymoku.instruments.FrequencyResponseAnalyzer.get_data>` on the associated :any:`FrequencyResponseAnalyzer`
	instrument.

	- ``ch1.magnitude`` = ``[CH1_MAG_DATA]``
	- ``ch1.magnitude_dB`` = ``[CH1_MAG_DATA_DB]``
	- ``ch1.phase`` = ``[CH1_PHASE_DATA]``
	- ``ch2.magnitude`` = ``[CH2_MAG_DATA]``
	- ``ch2.magnitude_dB`` = ``[CH2_MAG_DATA_DB]``
	- ``ch2.phase`` = ``[CH2_PHASE_DATA]``
	- ``frequency`` = ``[FREQ]``
	- ``waveformid`` = ``n``

	"""
	def __init__(self, instrument, scales):
		super(FRAData, self).__init__(instrument)

		#: The frequency range associated with both channels
		self.frequency = []

		#: Obtain all data scaling factors relevant to current NetAn configuration
		self.scales = scales

	def __json__(self):
		# Annoying this doesn't recursively-descend, I thought it did. Manually serialise the children for now
		return { 'ch1' : self.ch1.__json__(), 'ch2' : self.ch2.__json__(), 'frequency' : self.frequency, 'waveform_id' : self.waveformid }

	def process_complete(self):
		super(FRAData, self).process_complete()

		if self._stateid not in self.scales:
			#log.debug("Can't render FRAData frame, haven't saved calibration data for state %d", self._stateid)
			self.complete = False
			return

		# Get scaling/correction factors based on current instrument configuration
		scales = self.scales[self._stateid]

		try:
			self.frequency = scales['frequency_axis']

			smpls = int(len(self._raw1) / 4)
			dat = struct.unpack('<' + 'i' * smpls, self._raw1)
			dat = [ x if x != -0x80000000 else None for x in dat ]

			self.ch1_bits = [ float(x) if x is not None else None for x in dat ]
			self.ch1 = _FRAChannelData(self.ch1_bits, scales['gain_correction'], scales['g1'], scales['sweep_amplitude_ch1'])

			smpls = int(len(self._raw2) / 4)
			dat = struct.unpack('<' + 'i' * smpls, self._raw2)
			dat = [ x if x != -0x80000000 else None for x in dat ]

			self.ch2_bits = [ float(x) if x is not None else None for x in dat ]
			self.ch2 = _FRAChannelData(self.ch2_bits, scales['gain_correction'], scales['g2'], scales['sweep_amplitude_ch2'])

		except (IndexError, TypeError, struct.error):
			# If the data is bollocksed, force a reinitialisation on next packet
			self.frameid = None
			self.complete = False

		# A valid frame is there's at least one valid sample in each channel
		return self.ch1 and self.ch2
