
# Pull in Python 3 string object on Python 2.
from builtins import str

import select, socket, struct, sys
import os, os.path
import logging, time, threading, math
import zmq

from collections import deque
from queue import Queue, Empty

from . import *
from . import _instrument, _get_autocommit, _input_instrument

from ._instrument import needs_commit

from ._frame_instrument_data import InstrumentData

log = logging.getLogger(__name__)

class FrameQueue(Queue):
    def put(self, item, block=True, timeout=None):
        # Behaves the same way as default except that instead of raising Full, it
        # just pushes the item on to the deque anyway, throwing away old frames.
        self.not_full.acquire()
        try:
            if self.maxsize > 0 and block:
                if timeout is None:
                    while self._qsize() == self.maxsize:
                        self.not_full.wait()
                elif timeout < 0:
                    raise ValueError("'timeout' must be a non-negative number")
                else:
                    endtime = _time() + timeout
                    while self._qsize() == self.maxsize:
                        remaining = endtime - _time()
                        if remaining <= 0.0:
                            break
                        self.not_full.wait(remaining)
            self._put(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()
        finally:
            self.not_full.release()

    def get(self, block=True, timeout=None):
        item = None
        while True:
            try:
                item = Queue.get(self, block=block, timeout=timeout or 1)
            except Empty:
                if timeout is None:
                    continue
                else:
                    raise
            else:
                return item

    # The default _init for a Queue doesn't actually bound the deque, relying on the
    # put function to bound.
    def _init(self, maxsize):
        self.queue = deque(maxlen=maxsize)

# Revisit: Should this be a Mixin? Are there more instrument classifications of this type, recording ability, for example?
class FrameBasedInstrument(_input_instrument.InputInstrument, _instrument.MokuInstrument):
    def __init__(self):
        super(FrameBasedInstrument, self).__init__()
        self._buflen = 1
        self._queue = FrameQueue(maxsize=self._buflen)
        self._hb_forced = False

        self.skt, self.mon_skt = None, None

        # Tracks whether the waveformid of frames received so far has wrapped
        self._data_syncd = False

    def _set_frame_class(self, frame_class, **frame_kwargs):
        self._frame_class = frame_class
        self._frame_kwargs = frame_kwargs

    def _flush(self):
        """ Clear the Frame Buffer.
        This is normally not required as one can simply wait for the correctly-generated frames to propagate through
        using the appropriate arguments to :any:`get_data`.
        """
        with self._queue.mutex:
            self._queue.queue.clear()

    def _set_buffer_length(self, buflen):
        """ Set the internal frame buffer length."""
        self._buflen = buflen
        self._queue = FrameQueue(maxsize=buflen)

    def _get_buffer_length(self):
        """ Return the current length of the internal frame buffer
        """
        return self._buflen

    def set_defaults(self):
        """ Set instrument default parameters"""
        super(FrameBasedInstrument, self).set_defaults()

        # TODO: All instruments currently run at 10Hz due to kernel timing
        self.framerate = 10


    def get_data(self, timeout=None, wait=True):
        """ Get full-resolution data from the instrument.

        This will pause the instrument and download the entire contents of the instrument's
        internal memory. This may include slightly more data than the instrument is set up
        to record due to rounding of some parameters in the instrument.

        All settings must be committed before you call this function. If *pymoku.autocommit=True*
        (the default) then this will always be true, otherwise you will need to have called
        :any:`commit` first.

        The download process may take a second or so to complete. If you require high rate
        data, e.g. for rendering a plot, see `get_realtime_data`.

        If the *wait* parameter is true (the default), this function will wait for any new
        settings to be applied before returning. That is, if you have set a new timebase (for example),
        calling this with *wait=True* will guarantee that the data returned has this new timebase.

        Note that if instrument configuration is changed, a trigger event must occur before data
        captured with that configuration set can become available. This can take an arbitrary amount
        of time. For this reason the *timeout* should be set appropriately.

        :type timeout: float
        :param timeout: Maximum time to wait for new data, or *None* for indefinite.

        :type wait: bool
        :param wait: If *true* (default), waits for a new waveform to be captured with the most
            recently-applied settings, otherwise just return the most recently captured valid data.

        :return: :any:`InstrumentData` subclass, specific to the instrument.
        """
        if self._moku is None: raise NotDeployedException()

        if self.check_uncommitted_state():
            raise UncommittedSettings("Detected uncommitted instrument settings.")

        # Stop existing logging sessions
        self._stream_stop()

        # Block waiting on state to propagate (if wait=True) or a trigger to occur (wait=False)
        # This also gives us acquisition parameters for the buffer we will subsequently stream
        frame = self.get_realtime_data(timeout=timeout, wait=wait)

        # Wait on a synchronised frame or timeout, whichever comes first.
        # XXX: Timeout is not well-handled, in that each sub-operation has its own timeout
        # rather than the timeout applying to the whole function. This works in most circumstances
        # but can mean that the function's maximum return time is several times longer than the
        # user wanted.
        start = time.time()
        while not(frame.synchronised):
            if timeout is not None and (time.time() > start + timeout):
                raise FrameTimeout("Timed out waiting on instrument data.")
            frame = self.get_realtime_data(timeout=timeout, wait=wait)

        # Check if it is already paused
        was_paused = self._get_pause()

        # Force a pause so we can start streaming the buffer out
        if not was_paused:
            self._set_pause(True)
            if not _get_autocommit():
                self.commit()

        # Get buffer data using a network stream
        self._stream_start(start=0, duration=0, use_sd=False, ch1=True, ch2=True, filetype='net')

        while True:
            try:
                self._stream_receive_samples(timeout)
            except NoDataException:
                break

        # Clean up data streaming threads
        self._stream_stop()

        # Set pause state to what it was before
        if not was_paused:
            self._set_pause(False)
            if not _get_autocommit():
                self.commit()

        channel_data = self._stream_get_processed_samples()
        self._stream_clear_processed_samples()

        # Take the channel buffer data and put it into an 'InstrumentData' object
        if(getattr(self, '_frame_class', None)):
            buff = self._frame_class(**self._frame_kwargs)
            buff.ch1 = channel_data[0]
            buff.ch2 = channel_data[1]
            buff.waveformid = frame.waveformid
            buff._stateid = frame._stateid
            buff._trigstate = frame._trigstate
            # Finalise the buffer processing stage
            buff.process_buffer()
            return buff
        else:
            raise Exception("Unable to process instrument data.")

    @needs_commit
    def set_framerate(self, fr):
        """ Set framerate """
        self.framerate = fr


    def get_realtime_data(self, timeout=None, wait=True):
        """ Get downsampled data from the instrument with low latency.

        Returns a new :any:`InstrumentData` subclass (instrument-specific), containing
        a version of the data that may have been downsampled from the original in order to
        be transferred quickly.

        This function always returns a new object at `framerate` (10Hz by default), whether
        or not there is new data in that object. This can be verified by checking the return
        object's *waveformid* parameter, which increments each time a new waveform is captured
        internally.

        The downsampled, low-latency nature of this data makes it particularly suitable for
        plotting in real time. If you require high-accuracy, high-resolution data for analysis,
        see `get_data`.

        If the *wait* parameter is true (the default), this function will wait for any new
        settings to be applied before returning. That is, if you have set a new timebase (for example),
        calling this with *wait=True* will guarantee that the data returned has this new timebase.

        Note that if instrument configuration is changed, a trigger event must occur before data
        captured with that configuration set can become available. This can take an arbitrary amount
        of time. For this reason the *timeout* should be set appropriately.

        :type timeout: float
        :param timeout: Maximum time to wait for new data, or *None* for indefinite.

        :type wait: bool
        :param wait: If *true* (default), waits for a new waveform to be captured with the most
            recently-applied settings, otherwise just return the most recently captured valid data.

        :return: :any:`InstrumentData` subclass, specific to the instrument.
        """
        try:
            # Dodgy hack, infinite timeout gets translated in to just an exceedingly long one
            endtime = time.time() + (timeout or sys.maxsize)
            while self._running:
                frame = self._queue.get(block=True, timeout=timeout)
                # Return only frames with a triggered and rendered state being equal (so we can
                # interpret the data correctly using the entire state)
                # If wait is set, only frames that have the triggered state equal to the
                # currently committed state will be returned.
                if (not wait and frame._trigstate == frame._stateid) or (frame._trigstate == self._stateid):
                    return frame
                elif time.time() > endtime:
                    raise FrameTimeout()
                else:
                    log.debug("Incorrect state received: %d/%d", frame._trigstate, self._stateid)
        except Empty:
            raise FrameTimeout()

    def _set_running(self, state):
        prev_state = self._running
        super(FrameBasedInstrument, self)._set_running(state)
        if state and not prev_state:
            self._fr_worker = threading.Thread(target=self._frame_worker)
            self._fr_worker.start()
        elif not state and prev_state:
            self._fr_worker.join()

    def _make_frame_socket(self):

        if self.skt:
            self.skt.close()

        ctx = zmq.Context.instance()
        self.skt = ctx.socket(zmq.SUB)
        self.skt.connect("tcp://%s:27185" % self._moku._ip)
        self.skt.setsockopt_string(zmq.SUBSCRIBE, u'')
        self.skt.setsockopt(zmq.RCVHWM, 2)
        self.skt.setsockopt(zmq.LINGER, 0)

    def _frame_worker(self):
        connected = False
        if(getattr(self, '_frame_class', None)):
            self._make_frame_socket()

            fr = self._frame_class(**self._frame_kwargs)

            try:
                while self._running:
                    if self.skt in zmq.select([self.skt], [], [], 1.0)[0]:
                        connected = True
                        d = self.skt.recv()
                        fr.add_packet(d)

                        if fr._complete:
                            self._queue.put_nowait(fr)
                            fr = self._frame_class(**self._frame_kwargs)
                    else:
                        if connected:
                            connected = False
                            log.info("Frame socket reconnecting")
                            self._make_frame_socket()
            except Exception as e:
                log.exception("Closed Frame worker")
            finally:
                self.skt.close()
