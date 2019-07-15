import struct

import logging
log = logging.getLogger('frdat')

class InstrumentData(object):
    """
    Superclass representing a full frame of some kind of data. This class is never used directly,
    but rather it is subclassed depending on the type of data contained and the instrument from
    which it originated. For example, the :any:`Oscilloscope` instrument will generate :any:`VoltsData`
    objects, where :any:`VoltsData` is a subclass of :any:`InstrumentData`.
    """
    def __init__(self, instrument):
        #: A reference to the parent instrument that generates this data object
        self._instrument = instrument

        self._complete = False
        self._chs_valid = [False, False]

        #: Channel 1 raw data array. Present whether or not the channel is enabled, but the contents
        #: are undefined in the latter case.
        self._raw1 = []

        #: Channel 2 raw data array.
        self._raw2 = []

        self._stateid = None
        self._trigstate = None

        #: Frame number. Increments monotonically but wraps at 16-bits.
        self._frameid = 0

        #: Incremented once per trigger event. Wraps at 32-bits.
        self.waveformid = 0

        #: True if at least one trigger event has occured, synchronising the data across all channels.
        self.synchronised = False

        self._flags = None

    def add_packet(self, packet):
        hdr_len = 8
        meta_len = 8 * 4

        stateid, trigstate, chan, instrid, waveformid = struct.unpack('<BBBBI', packet[:hdr_len])
        self._metadata = packet[hdr_len: hdr_len + meta_len]

        if self.waveformid != waveformid or self._stateid != stateid or self._trigstate != trigstate:
            self.waveformid = waveformid
            self._stateid = stateid
            self._trigstate = trigstate
            self._chs_valid = [False, False]

        if chan == 0:
            self._chs_valid[0] = True
            self._raw1 = packet[hdr_len + meta_len:]
        else:
            self._chs_valid[1] = True
            self._raw2 = packet[hdr_len + meta_len:]

        self._complete = all(self._chs_valid)

        if self._complete:
            if not self.process_complete():
                self._complete = False
                self._chs_valid = [False, False]

    def process_complete(self):
        # Update the waveform ID latch of the parent instrument as soon as waveform ID increments
        self._instrument._data_syncd |= self.waveformid > 0

        # We can't be sure the channels have synchronised in the channel buffers until the first
        # triggered waveform is received.
        if not self._instrument._data_syncd:
            self._raw1 = struct.pack('<i',-0x80000000)*int(len(self._raw1)/4)
            self._raw2 = struct.pack('<i',-0x80000000)*int(len(self._raw2)/4)
        else:
            self.synchronised = True

        return True

    def process_buffer(self):
        # Designed to be overridden by subclasses needing to add x-axis to buffer data etc.
        return True
