import zmq
import math
import time

from . import *
from . import _instrument, dataparser
from . import _utils

_STREAM_STATE_NONE      = 0
_STREAM_STATE_RUNNING   = 1
_STREAM_STATE_WAITING   = 2
_STREAM_STATE_INVAL     = 3
_STREAM_STATE_FSFULL    = 4
_STREAM_STATE_OVERFLOW  = 5
_STREAM_STATE_BUSY      = 6
_STREAM_STATE_STOPPED   = 7

class InputInstrument(_instrument.MokuInstrument):
    """
        Helper class - should not be instantiated directly.
        This class is intended to handle streams: checking status, receiving/parsing raw data,
        translating error messages and setting up new streaming sessions.
    """

    def __init__(self):
        super(InputInstrument, self).__init__()
        # Stream socket connection
        self._dlskt = None
        # Data parser for current session
        self._strparser = None
        # Stream identifier number
        self._dlserial = 0
        # Current stream file type
        self._dlftype = None

        # Enabled channels for streaming session
        self.ch1 = False
        self.ch2 = False
        self.nch = 0

        self.procstr = ''
        self.binstr = ''
        self.hdrstr = ''
        self.fmtstr = ''

    """
        Expose all the get/set input instrument functions from the MokuInstrument class
    """
    def set_frontend(self, channel, fiftyr=True, atten=False, ac=False):
        """ Configures gain, coupling and termination for each channel.

        :type channel: int; {1,2}
        :param channel: Channel to which the settings should be applied

        :type fiftyr: bool
        :param fiftyr: 50Ohm termination; default is 1MOhm.

        :type atten: bool
        :param atten: Turn on 10x attenuation. Changes the dynamic range between 1Vpp and 10Vpp.

        :type ac: bool
        :param ac: AC-couple; default DC.
        """
        _utils.check_parameter_valid('set', channel, [1,2], 'channel')
        _utils.check_parameter_valid('bool', fiftyr, desc='50 Ohm termination')
        _utils.check_parameter_valid('bool', atten, desc='attenuation')
        _utils.check_parameter_valid('bool', ac, desc='AC coupling')
        return super(InputInstrument, self)._set_frontend(channel, fiftyr, atten, ac)

    def get_frontend(self, channel):
        """ Get the analog frontend configuration.

        :type channel: int; {1,2}
        :param channel: Channel for which the relay settings are being retrieved

        :return: Array of bool with the front end configuration of channels
            - [0] 50 Ohm
            - [1] 10xAttenuation
            - [2] AC Coupling
        """
        _utils.check_parameter_valid('set', channel, [1,2], 'channel')
        return super(InputInstrument, self)._get_frontend(channel)

    def _set_pause(self, pause):
        """ Pauses or unpauses the instrument's data output.

        :type pause: bool
        :param pause: Paused
        """
        return super(InputInstrument, self)._set_pause(pause)

    def _get_pause(self):
        """ Get whether the instrument's data output was paused.

        :rtype: bool
        :return: Paused
        """
        return super(InputInstrument, self)._get_pause()

    def _max_stream_rate(self, use_sd, filetype):
        """
        Returns the maximum rate at which the instrument can be streamed for the given
        streaming configuration
        """

        # These are checked on the client side too but we sanity-check here as an invalid
        # rate can hard-hang the Moku. These rates are approximate and experimentally
        # derived, should be updated as we test and optimize things.
        # Logging rates depend on which storage medium, and the filetype as well
        maxrates = None

        # The record length in the dataparser is in bits, convert to words; that's the unit
        # of the rate (more precisely, 32-bit samples is the unit)
        record_length = math.ceil(dataparser.LIDataParser.record_length(self.binstr) / 32.0)

        if self.nch == 2:
            if(use_sd):
                maxrates = { 'bin': 150e3, 'csv': 10e3, 'mat': 10e3, 'net': 20e3, 'npy': 10e3}
            else:
                maxrates = { 'bin': 500e3, 'csv': 10e3, 'mat': 10e3, 'net': 20e3, 'npy': 50e3}
        else:
            if(use_sd):
                maxrates = { 'bin': 250e3, 'csv': 10e3, 'mat': 10e3, 'net': 40e3, 'npy': 20e3}
            else:
                maxrates = { 'bin': 1e6, 'csv': 10e3, 'mat': 10e3, 'net': 40e3, 'npy': 100e3}

        return maxrates[filetype] / record_length

    def _estimate_logsize(self, ch1, ch2, duration, filetype):
        if filetype in ['bin', 'mat', 'npy']:
            # The record length in the dataparser is in bits, convert to bytes
            record_length = math.ceil(dataparser.LIDataParser.record_length(self.binstr) / 8.0)
            sample_size_bytes = record_length * (ch1 + ch2)
            return (duration / self.timestep) * sample_size_bytes
        elif filetype is 'csv':
            if '[' in self.fmtstr: # Assume that if the string includes [, it's expecting data arrays
                ch1, ch2 = [[-1] * 10] * 2 # Assume no instrument provides more than 10 entries per record
            else:
                ch1, ch2 = -1, -1
            f = self.fmtstr.format(ch1=ch1, ch2=ch2, t=-1, T=-1, n=1, d=0.1) # Dummy values chosen for maximum formatted length
            return (duration / self.timestep) *  len(f)

    def _stream_start(self, start, duration, use_sd, ch1, ch2, filetype):
        """ Start an instrument streaming session.

        If the duration is non-zero, the device must be in ROLL mode (via a call to :any:`set_xmode`).
        Also, the sample rate must be appropriate to the instrument and file type (as calculated by
        :any:`_max_stream_rates`)

        :raises InvalidOperationException: if the sample rate is too high for the selected filetype or if the
            device *x_mode* isn't set to *ROLL* when running non-'net' type streams.

        .. warning:: Start parameter not currently implemented, must be set to zero

        :type start: float
        :param start: Start time in seconds from the time of function call
        :type duration: float
        :param duration: Log duration in seconds
        :type use_sd: bool
        :param use_sd: Log to SD card (default is internal volatile storage). Ignored if 'net' file type.
        :type ch1: bool
        :param ch1: Log from Channel 1
        :type ch2: bool
        :param ch2: Log from Channel 2
        :param filetype: Type of log to start. One of the types below.

        *File Types*

        - **csv** -- CSV file
        - **bin** -- LI Binary file
        - **mat** -- MATLAB file
        - **npy** -- NPY (Numpy) data file
        - **net** -- Log to network, retrieve data with :any:`_stream_receive_samples`
        """
        if (not ch1) and (not ch2):
            raise InvalidOperationException("No channels were selected for logging")
        if duration < 0:
            raise InvalidOperationException("Invalid duration %d", duration)

        from datetime import datetime
        if self._moku is None: raise NotDeployedException()

        self._dlserial += 1
        self.tag = u"%04d" % self._dlserial

        self.ch1 = bool(ch1)
        self.ch2 = bool(ch2)
        self.nch = bool(self.ch1) + bool(self.ch2)
        # Update all child instrument local datalogging variables
        self._update_datalogger_params()

        # TODO: Only set a filename for non-net filetype sessions
        # This breaks in the firmware due to a check for valid filename for all session types
        fname = datetime.now().strftime(self.logname + "_%Y%m%d_%H%M%S")

        # Currently the data stream genesis is from the x_mode commit below, meaning that delayed start
        # doesn't work properly. Once this is fixed in the FPGA/daemon, remove this check and the note
        # in the documentation above.
        if start:
            raise InvalidOperationException("Logging start time parameter currently not supported")

        # Logging rates depend on which storage medium, and the filetype as well
        if duration > 0:
            maxrate = self._max_stream_rate(use_sd, filetype)
            if math.floor(1.0 / self.timestep) > maxrate:
                session_type = "Filetype: %s, #Channels: %d, SDCard: %s" % (filetype, self.nch, use_sd)
                #raise InvalidOperationException("Sample rate (%d smp/s) too high for datalogging session type (%s). Maximum rate is %d smp/s. " % (1.0 / self.timestep, session_type, maxrate))

            if self.x_mode != _instrument.ROLL:
                raise InvalidOperationException("Instrument must be in roll mode to perform data logging")

        if not all([ len(s) for s in [self.binstr, self.procstr, self.fmtstr, self.hdrstr]]):
            raise InvalidOperationException("Instrument currently doesn't support data logging")

        # If not a network stream, we must check the mount point is available
        # if filetype is not 'net':
        #   mp = 'e' if use_sd else 'i'
        #   try:
        #       t, f = self._moku._fs_free(mp)
        #       logsize = self._estimate_logsize(ch1, ch2, duration, filetype)
        #       if f < logsize:
        #           raise InsufficientSpace("Insufficient disk space for requested log file (require %d kB, available %d kB)" % (logsize/(2**10), f/(2**10)))
        #       elif logsize > 4 * 1024 * 1024 * 1024:
        #           raise InsufficientSpace("SD Cards cannot hold files larger than 4GB, estimated log size %d MB", logsize / (1024 * 1024))
        #       elif logsize > 250 * 1024 * 1024 and filetype == 'mat':
        #           raise InsufficientSpace("MAT format cannot exceed 250MB, estimated %d MB", logsize / 1024 / 1024)
        #   except MPReadOnly as e:
        #       if use_sd:
        #           raise MPReadOnly("SD Card is read only.")
        #       raise e
        #   except MPNotMounted as e:
        #       if use_sd:
        #           raise MPNotMounted("SD Card is unmounted.")
        #       raise e

        # We have to be in this mode anyway because of the above check, but rewriting this register and committing
        # is necessary in order to reset the channel buffers on the device and flush them of old data.
        if duration > 0:
            self.x_mode = _instrument.ROLL
            self.commit()

        try:
            self._moku._stream_prep(ch1=self.ch1, ch2=self.ch2, start=start, end=start + duration, offset=0, timestep=self.timestep,
            binstr=self.binstr, procstr=self.procstr, fmtstr=self.fmtstr, hdrstr=self.hdrstr,
            fname=fname, ftype=filetype, tag=self.tag, use_sd=use_sd)
        except StreamException as e:
            self._stream_error(status=e.err)

        if filetype == 'net':
            self._streamsub_init(self.tag)

        log.info("Starting new data streaming session.")
        self._moku._stream_start()

        # This may not actually exist as a file (e.g. if a 'net' session was run)
        self.logfile = str(self._stream_status()[4]).strip()

        # Store the requested filetype in the case of a "wait" call
        self._dlftype = filetype

    def _stream_stop(self):
        """ Stop a recording session previously started with :py:func:`datalogger_start`

        This function signals that the user no longer needs to know the status of the previous
        log, discarding that state. It must be called before a second log is started or else
        that start attempt will fail with a "busy" error.

        :rtype: int
        :return: final status code (see :py:func:`_stream_status`
        """
        if self._moku is None: raise NotDeployedException()

        log.info("Stopping data streaming session.")
        stat = self._moku._stream_stop()
        self._streamsub_destroy()

        return stat

    def _stream_status(self):
        """ Return the status of the most recent recording session to be started.
        This is still valid after the stream has stopped, in which case the status will reflect that it's safe
        to start a new session.

        Returns a tuple of state variables:

        - **status** -- Current datalogger state
        - **logged** -- Number of samples recorded so far. If more than one channel is active, this is the sum of all points across all channels.
        - **to start** -- Number of seconds until/since start. Time until start is positive, a negative number indicates that the record has started already.
        - **to end** -- Number of seconds until/since end.
        - **filename** -- Base filename of current log session (without filetype)

        Status is one of:

        - **_STREAM_STATE_NONE** -- No session
        - **_STREAM_STATE_RUNNING** -- Session currently running
        - **_STREAM_STATE_WAITING** -- Session waiting to run (delayed start)
        - **_STREAM_STATE_INVAL** -- An attempt was made to start a session with invalid parameters
        - **_STREAM_STATE_FSFULL** -- A session has terminated early due to the storage filling up
        - **_STREAM_STATE_OVERFLOW** -- A session has terminated early due to the sample rate being too high for the storage speed
        - **_STREAM_STATE_BUSY** -- An attempt was made to start a session when one was already running
        - **_STREAM_STATE_STOPPED** -- A session has successfully completed.

        :rtype: int, int, int, int
        :return: status, logged, to start, to end, filename.
        """
        if self._moku is None: raise NotDeployedException()
        return self._moku._stream_status()

    def _stream_data_remaining(self):
        """ Returns number of seconds from session start and end.

        - **to start** -- Number of seconds until/since start. Time until start is positive, a negative number indicates that the record has started already.
        - **to end** -- Number of seconds until/since end.

        :rtype: int, int
        :return: to start, to end
        """
        d1, d2, start, end, fname = self._stream_status()
        return start, end

    def _stream_data_captured(self):
        """ Returns number of samples captures in this datalogging session.

        :rtype: int
        :returns: sample count
        """
        return self._stream_status()[1]

    def _stream_completed(self, status=None):
        """ Returns whether or not the datalogger is expecting to log any more data.

        If the log is completed then the results files are ready to be uploaded or simply
        read off the SD card. At most one subsequent :any:`get_stream_data` call
        will return without timeout.

        If the datalogger has entered an error state, a StreamException is raised.

        :rtype: bool
        :returns: Whether the current session has finished running.

        :raises StreamException: if the session has entered an error state
        """
        if status == None:
            status = self._stream_status()[0]

        # Check the status for error state
        self._stream_error(status=status)

        # No session in progress
        if status == _STREAM_STATE_NONE:
            raise StreamException("Attempted to check progress of non-existent streaming session.")

        return status not in [_STREAM_STATE_RUNNING, _STREAM_STATE_WAITING]

    def _stream_error(self, status=None):
        """ Checks the current datalogger session for errors. Alternatively, the status
        parameter returned by :any:`_stream_status` call can be translated to the
        associated exception (if any).

        :raises StreamException: if the session is in error.
        :raises InvalidArgument:
        """
        if not status:
            status = self._stream_status()[0]
        msg = None

        if status in [_STREAM_STATE_NONE, _STREAM_STATE_RUNNING, _STREAM_STATE_WAITING, _STREAM_STATE_STOPPED]:
            msg = None
        elif status == _STREAM_STATE_INVAL:
            msg = "Invalid Parameters for Datalogger Operation"
        elif status == _STREAM_STATE_FSFULL:
            msg = "Target Filesystem Full"
        elif status == _STREAM_STATE_OVERFLOW:
            msg ="Session overflowed, sample rate too fast."
        elif status == _STREAM_STATE_BUSY:
            msg = "Tried to start a logging session while one was already running."
        else:
            raise ValueError('Invalid status argument')

        if msg:
            raise StreamException(msg, status)

    def _stream_net_is_running(self):
        return self._dlskt is not None

    def _stream_receive_samples(self,timeout):
        """
            Gets raw samples off the network and parses them.

            :raises NoDataException: Once the stream terminates.
            :raises FrameTimeout: If the network times out waiting for data.
            :raises DataIntegrityException: If the network layer detects dropped data
        """
        if not self._stream_net_is_running():
            raise StreamException("No network stream is currently running.")

        ch, start, coeff, raw = self._stream_get_samples_raw(timeout)

        self._strparser.set_coeff(ch, coeff)
        self._strparser.parse(raw, ch, start_idx=start)

    def _stream_get_processed_samples(self):
        """
            Gets any already parsed samples for the current session.

            :rtype: array
            :returns: Array where each entry is an array corresponding to
            processed channel samples [[Ch1 Samples],[Ch2 Samples]].
        """
        processed_smps = self._strparser.processed
        if self.nch == 1:
            if self.ch1:
                return [processed_smps[0],[]]
            if self.ch2:
                return [[],processed_smps[0]]
        return processed_smps

    def _stream_clear_processed_samples(self, _len=None):
        """
            Clears out already processed samples

            :type _len: int
            :param _len: Number of processed samples to clear.
        """
        if not _len:
            self._strparser.clear_processed()
        else:
            self._strparser.clear_processed(_len)

    def _stream_get_samples_raw(self, timeout):
        """
            Receives raw instrument samples off the network

            :type timeout: int
            :param timeout: Timeout in seconds

            :raises NoDataException: Once the stream terminates.
            :raises FrameTimeout: If the network times out waiting for data.
            :raises DataIntegrityException: If the network layer detects dropped data

        """
        if self._dlskt in zmq.select([self._dlskt], [], [], timeout)[0]:
            hdr, data = self._dlskt.recv_multipart()

            hdr = hdr.decode('ascii')
            tag, ch, start, coeff = hdr.split('|')
            ch = int(ch)
            start = int(start)
            coeff = float(coeff)

            # Special value to indicate the stream has finished
            if ch == -1:
                raise NoDataException("Data log terminated")

            return ch, start, coeff, data
        else:
            raise FrameTimeout("Data log timed out after %d seconds", timeout)

    def _streamsub_init(self, tag):
        """
            Initialises a ZMQ stream subscriber and data parser for current session.
        """
        ctx = zmq.Context.instance()
        self._dlskt = ctx.socket(zmq.SUB)
        self._dlskt.connect("tcp://%s:27186" % self._moku._ip)
        self._dlskt.setsockopt_string(zmq.SUBSCRIBE, tag)

        self._strparser = dataparser.LIDataParser(self.ch1, self.ch2,
            self.binstr, self.procstr, self.fmtstr, self.hdrstr,
            self.timestep, int(time.time()), [0] * self.nch,
            0) # Zero offset from start time to first sample, valid for streams but not so much for single frame transfers

    def _streamsub_destroy(self):
        if self._dlskt is not None:
            self._dlskt.close()
            self._dlskt = None

    def _update_datalogger_params(self):
        # To be overwritten by child instruments to update local datalogger parameters
        # prior to starting any stream session

        return
