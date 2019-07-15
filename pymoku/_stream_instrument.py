
import select, socket, struct, sys
import os, os.path
import logging, time, threading, math
import zmq

from . import *
from . import dataparser, _input_instrument, _instrument
from . import _utils

log = logging.getLogger(__name__)

class StreamBasedInstrument(_input_instrument.InputInstrument, _instrument.MokuInstrument):

	def __init__(self):
		super(StreamBasedInstrument, self).__init__()

		self._strparser = None

		# Flag to indicate if there is no more stream data to get for last session
		self._no_data = True

		self._dlserial = 0
		self._dlskt = None
		self._dlftype = None
		self.logfile = None

		self.timestep = 0

	def start_stream_data(self, duration=10, ch1=True, ch2=True):
		"""	Start streaming instrument data over the network.

		Samples being streamed can be retrieved by calls to `get_stream_data`.

		All outstanding settings must have been committed before starting the stream. This
		will always be true if *pymoku.autocommit=True*, the default.

		:type duration: float
		:param duration: Log duration in seconds
		:type use_sd: bool
		:type ch1: bool
		:param ch1: Enable streaming on Channel 1
		:type ch2: bool
		:param ch2: Enable streaming on Channel 2

		:raises ValueError: if invalid channel enable parameter
		:raises ValueOutOfRangeException: if duration is invalid
		"""
		_utils.check_parameter_valid('bool', ch1, desc='stream channel 1')
		_utils.check_parameter_valid('bool', ch2, desc='stream channel 2')
		_utils.check_parameter_valid('float', duration, desc='stream duration', units='sec')

		if self.check_uncommitted_state():
			raise UncommittedSettings("Can't start a streaming session due to uncommitted device settings.")
		self._stream_start(start=0, duration=duration, ch1=ch1, ch2=ch2, use_sd=False, filetype='net')
		self._no_data = False

	def stop_stream_data(self):
		""" Stops instrument data being streamed over the network.

		Should be called exactly once for every `start_stream_data` call, even if the streaming session
		stopped itself due to timeout. Calling this function not only causes the stream to stop, but
		also resets error and transfer state, ready to start a new streaming session.
		"""
		self._no_data = True
		self._stream_stop()

	def get_stream_data(self, n=0, timeout=None):
		""" Get any new instrument samples that have arrived on the network.

		This returns a tuple containing two arrays (one per channel) of up to 'n' samples of instrument data.
		If a channel is disabled, the corresponding array is empty. If there were less than 'n' samples
		remaining for the session, then the arrays will contain this remaining amount of samples.

		:type n: int
		:param n: Number of samples to get off the network. Set this to '0' to get
			all currently available samples, or '-1' to wait on all samples of the currently
			running streaming session to be received.
		:type timeout: float
		:param timeout: Timeout in seconds

		:rtype: tuple
		:returns: ([CH1_DATA], [CH2_DATA])

		:raises NoDataException: if the logging session has stopped
		:raises FrameTimeout: if the timeout expired
		:raises InvalidOperationException: if there is no streaming session running
		:raises ValueOutOfRangeException: invalid input parameters
		:raises DataIntegrityException: If the network layer detects dropped data
		"""
		if timeout and timeout <= 0:
			raise ValueOutOfRangeException("Timeout must be positive or 'None'")
		if n < -1:
			raise ValueOutOfRangeException("Invalid number of samples. Expected (n >= -1).")

		# If no network session exists, can't get samples
		if not self._stream_net_is_running():
			raise InvalidOperationException("No network streaming session is running.")
		if self._no_data:
			log.debug("No more samples to get.")
			return ([],[])
		if type(n) is not int:
			raise TypeError("Sample number 'n' must be an integer")

		# Check how many samples are already processed and waiting to be read out
		processed_samples = self._stream_get_processed_samples()
		if n > 0:
			# Actual number of samples processed already
			num_processed_samples = [len(x) for x in processed_samples]
		else:
			# We don't need to track the number of processed samples if n = [0,1]
			num_processed_samples = [-1,-1]

		# Only "get" samples off the network if we haven't already processed enough to return 'n'
		# for all enabled channels.
		while ((n == -1) or
			(self.ch1 and ((num_processed_samples[0] <= n) or (num_processed_samples[0] <= 0))) or
			(self.ch2 and ((num_processed_samples[1] <= n) or (num_processed_samples[1] <= 0)))):
			try:
				self._stream_receive_samples(timeout)
			except NoDataException:
				log.debug("No more data available for current stream.")
				self._no_data = True

			# Update our list of current processed samples
			processed_samples = self._stream_get_processed_samples()
			if n != -1:
				# Update the number of processed samples if we aren't asking for 'all' of them
				num_processed_samples = [len(x) for x in processed_samples]

			# Check if the streaming session has completed
			if self._no_data:
				break

		active_channels = [self.ch1, self.ch2]
		to_return = min([len(p) for c, p in zip(active_channels, processed_samples) if c])

		if n > 0:
			to_return = min(n, to_return)

		dout_ch1 = processed_samples[0][0:to_return] if self.ch1 else []
		dout_ch2 = processed_samples[1][0:to_return] if self.ch2 else []

		self._stream_clear_processed_samples(to_return)

		return (dout_ch1, dout_ch2)

	def start_data_log(self, duration=10, ch1=True, ch2=True, use_sd=True, filetype='csv'):
		"""	Start logging instrument data to a file.

		Progress of the data log may be checked calling `progress_data_log`.

		All outstanding settings must have been committed before starting the data log. This
		will always be true if *pymoku.autocommit=True*, the default.

		.. note:: The Moku's internal filesystem is volatile and will be wiped when the Moku is turned off.
			If you want your data logs to persist either save to SD card or move them to a permanent
			storage location prior to powering your Moku off.

		:type duration: float
		:param duration: Log duration in seconds
		:type ch1: bool
		:param ch1: Enable streaming on Channel 1
		:type ch2: bool
		:param ch2: Enable streaming on Channel 2
		:type use_sd: bool
		:param use_sd: Whether to log to the SD card, else the internal Moku filesystem.
		:type filetype: string
		:param filetype: Log file type, one of {'csv','bin','mat','npy'} for CSV, Binary, MATLAB or NPY (Numpy Data) respectively.

		:raises ValueError: if invalid channel enable parameter
		:raises ValueOutOfRangeException: if duration is invalid
		"""
		_utils.check_parameter_valid('bool', ch1, desc='log channel 1')
		_utils.check_parameter_valid('bool', ch2, desc='log channel 2')
		_utils.check_parameter_valid('bool', use_sd, desc='log to SD card')
		_utils.check_parameter_valid('float', duration, desc='log duration', units='sec')
		_utils.check_parameter_valid('set', filetype, ['csv', 'mat', 'bin', 'npy'], 'log filetype')

		if self.check_uncommitted_state():
			raise UncommittedSettings("Can't start a logging session due to uncommitted device settings.")
		self._stream_start(start=0, duration=duration, ch1=ch1, ch2=ch2, use_sd=use_sd, filetype=filetype)

	def stop_data_log(self):
		""" Stops the current instrument data logging session.

		This must be called exactly once for every `start_data_log` call, even if the log terminated itself
		due to timeout. Calling this function doesn't just stop the session (if it isn't already stopped),
		but also resets error and transfer state, ready to start a new logging session.
		"""
		self._stream_stop()

	def progress_data_log(self):
		""" Estimates progress of a logging session started by a `start_data_log` call.

		:rtype: float
		:returns: [0.0-100.0] representing 0 - 100% completion of the current logging session.Note that 100% is only returned when the session has completed, the progress may pause at 99% for a time as internal buffers are flushed.
		:raises: StreamException: if an error occurred with the current logging session.
		"""
		stat, bt, time_since_start, time_to_end, fname = self._stream_status()
		# Check for error state
		self._stream_error(status=stat)

		if self._stream_completed(status=stat):
			return 100
		else:
			duration = float(abs(-time_since_start + time_to_end))
			if duration > 0:
				# Only return 100% if complete
				return min(int(abs(time_since_start/duration)*100),99)
			else:
				return 99

	def data_log_filename(self):
		""" Returns the current base filename of the logging session.

		The base filename doesn't include the file extension as multiple files might be
		recorded simultaneously with different extensions.

		:rtype: str
		:returns: The file name of the current, or most recent, log file.
		"""
		if self.logfile:
			return self.logfile.split(':')[1]
		else:
			return None

	def upload_data_log(self):
		""" Load most recently recorded data file from the Moku to the local PC.

		:raises NotDeployedException: if the instrument is not yet operational.
		:raises InvalidOperationException: if no files are present.
		"""
		import re

		if self._moku is None: raise NotDeployedException()

		uploaded = 0
		target = self.data_log_filename()

		if not target:
			raise InvalidOperationException("No data has been logged in current session.")
		# Check internal and external storage
		for mp in ['i', 'e']:
			try:
				for f in self._moku._fs_list(mp):
					if str(f[0]).startswith(target):
						# Don't overwrite existing files of the name name. This would be nicer
						# if we could pass receive_file a local filename to save to, but until
						# that change is made, just move the clashing file out of the way.
						if os.path.exists(f[0]):
							i = 1
							while os.path.exists(f[0] + ("-%d" % i)):
								i += 1

							os.rename(f[0], f[0] + ("-%d" % i))

						# Data length of zero uploads the whole file
						self._moku._receive_file(mp, f[0], 0)
						log.debug('Uploaded file %s',f[0])
						uploaded += 1
			except MPNotMounted:
				log.debug("Attempted to list files on unmounted device '%s'" % mp)

		if not uploaded:
			raise InvalidOperationException("Log files not present")
		else:
			log.debug("Uploaded %d files", uploaded)

	def get_timestep(self):
		""" Returns the expected time between streamed samples.

		This returns the inverse figure to `get_samplerate`. This form is more useful
		for constructing time axes to support, for example, `get_stream_data`.

		:rtype: float
		:returns: Time between data samples in seconds.
		"""
		if self.timestep == 0:
			raise Exception("Samplerate looks to be unset.")
		return self.timestep

