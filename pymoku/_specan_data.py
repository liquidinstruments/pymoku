import struct
import math

from pymoku import _instrument
from pymoku import _frame_instrument

from bisect import bisect_right

_SA_SCREEN_WIDTH = 1024
_SA_BUFLEN = _instrument.CHN_BUFLEN


class SpectrumData(_frame_instrument.InstrumentData):
    """
    Object representing a frame of dual-channel frequency spectrum data
    (amplitude vs frequency in Hz). Amplitude is in units of either dBm power
    or RMS Voltage, as indicated by the `dbm` attribute of the frame. The
    amplitude scale may be selected by calling :any:`set_dbmscale` on the
    relevant :any:`SpectrumAnalyzer` instrument.

    This is the native output format of the :any:`SpectrumAnalyzer` instrument.

    This object should not be instantiated directly, but will be returned by
    a call to :any:`get_data <pymoku.instruments.SpectrumAnalyzer.get_data>`
    on the associated :any:`SpectrumAnalyzer` instrument.

    .. autoinstanceattribute:: pymoku._frame_instrument.SpectrumData.ch1
        :annotation: = [CH1_DATA]

    .. autoinstanceattribute:: pymoku._frame_instrument.SpectrumData.ch2
        :annotation: = [CH2_DATA]

    .. autoinstanceattribute:: pymoku._frame_instrument.SpectrumData.frequency
        :annotation: = [FREQ]

    .. autoinstanceattribute:: pymoku._frame_instrument.SpectrumData.dbm
        :annotation: = bool

    .. autoinstanceattribute:: pymoku._frame_instrument.SpectrumData.waveformid
        :annotation: = n
    """
    def __init__(self, instrument, scales):
        super(SpectrumData, self).__init__(instrument)

        #: Channel 1 data array in units of power. Present whether or not the
        # channel is enabled, but the
        #: contents are undefined in the latter case.
        self.ch1 = []

        #: Channel 2 data array in units of power.
        self.ch2 = []

        #: The frequency range associated with both channels
        self.frequency = []

        #: Whether the data is in logarithmic (dBm) scale. The alternative is
        # a linear scale.
        self.dbm = None

        #: Obtain all data scaling factors relevant to current SpectrumAnalyzer
        # configuration
        self._scales = scales

    def __json__(self):
        return {'ch1': self.ch1, 'ch2': self.ch2,
                'frequency': self.frequency, 'dbm': self.dbm,
                'waveform_id': self.waveformid}

    # convert an RMS voltage to a power level (assuming 50Ohm load)
    def _vrms_to_dbm(self, v):
        return 10.0 * math.log(v * v / 50.0, 10) + 30.0

    def process_complete(self):
        super(SpectrumData, self).process_complete()

        if self._stateid not in self._scales:
            return

        # Get scaling/correction factors based on current instrument
        # configuration
        scales = self._scales[self._stateid]
        scale1 = scales['g1']
        scale2 = scales['g2']
        fs = scales['fs']
        f1, f2 = scales['fspan']
        fcorrs = scales['fcorrs']
        dbmscale = scales['dbmscale']

        try:
            self.dbm = dbmscale

            # Find the starting index for the valid frame data
            # SpectrumAnalyzer generally gives more than we ask for due to
            # integer decimations
            start_index = bisect_right(fs, f1)

            # Set the frequency range of valid data in the current frame
            # (same for both channels)
            self.frequency = fs[start_index:-1]

            ##################################
            # Process Ch1 Data
            ##################################
            smpls = int(len(self._raw1) / 4)
            dat = struct.unpack('<' + 'i' * smpls, self._raw1)
            dat = [x if x != -0x80000000 else None for x in dat]

            # SpectrumAnalyzer data is backwards because $(EXPLETIVE), also
            # remove zeros for the sake of common
            # display on a log axis.
            self._ch1_bits = [max(float(x), 1) if x is not None else None
                              for x in reversed(dat[:_SA_SCREEN_WIDTH])]

            # Apply frequency dependent corrections
            self.ch1 = [self._vrms_to_dbm(a * c * scale1) if dbmscale
                        else a * c * scale1 if a is not None else None
                        for a, c in zip(self._ch1_bits, fcorrs)]

            # Trim invalid part of frame
            self.ch1 = self.ch1[start_index:-1]

            ##################################
            # Process Ch2 Data
            ##################################
            smpls = int(len(self._raw2) / 4)
            dat = struct.unpack('<' + 'i' * smpls, self._raw2)
            dat = [x if x != -0x80000000 else None for x in dat]

            self._ch2_bits = [max(float(x), 1) if x is not None else None
                              for x in reversed(dat[:_SA_SCREEN_WIDTH])]

            self.ch2 = [self._vrms_to_dbm(a * c * scale2) if dbmscale
                        else a*c*scale2 if a is not None else None
                        for a, c in zip(self._ch2_bits, fcorrs)]
            self.ch2 = self.ch2[start_index:-1]

        except (IndexError, TypeError, struct.error):
            # If the data is bollocksed, force a reinitialisation on next
            # packet
            self._frameid = None
            self._complete = False

        # A valid frame is there's at least one valid sample in each channel
        return any(self.ch1) and any(self.ch2)

    def process_buffer(self):
        # Compute the x-axis of the buffer
        if self._stateid not in self._scales:
            return
        scales = self._scales[self._stateid]
        self.time = [scales['buff_time_min']
                     + (scales['buff_time_step'] * x)
                     for x in range(_SA_BUFLEN)]
        self.dbm = scales['dbmscale']
        return True

    def _get_freq_scale(self, f):
        # Returns a scaling factor and units for frequency 'X'
        if (f > 1e6):
            scale_str = 'MHz'
            scale_const = 1e-6
        elif (f > 1e3):
            scale_str = 'kHz'
            scale_const = 1e-3
        elif (f > 1):
            scale_str = 'Hz'
            scale_const = 1
        elif (f > 1e-3):
            scale_str = 'mHz'
            scale_const = 1e3
        else:
            scale_str = 'uHz'
            scale_const = 1e6

        return [scale_str, scale_const]

    def _get_xaxis_fmt(self, x, pos):
        # This function returns a format string for the x-axis ticks and
        # x-coordinates along the frequency scale use this to set an x-axis
        # format during plotting of SpectrumAnalyzer frames

        if self._stateid not in self._scales:
            return

        scales = self._scales[self._stateid]
        f1, f2 = scales['fspan']

        fscale_str, fscale_const = self._get_freq_scale(f2)

        return {'xaxis': '%.1f %s' % (x * fscale_const, fscale_str),
                'xcoord': '%.3f %s' % (x * fscale_const, fscale_str)}

    def get_xaxis_fmt(self, x, pos):
        """ Function suitable to use as argument to a matplotlib
            FuncFormatter for X (time) axis """
        return self._get_xaxis_fmt(x, pos)['xaxis']

    def get_xcoord_fmt(self, x):
        """ Function suitable to use as argument to a matplotlib
            FuncFormatter for X (time) coordinate """
        return self._get_xaxis_fmt(x, None)['xcoord']

    def _get_yaxis_fmt(self, y, pos):

        if self._stateid not in self._scales:
            return

        scales = self._scales[self._stateid]
        dbm = scales['dbmscale']

        yfmt = {
            'linear': '%.1f %s' % (y, 'V'),
            'log': '%.1f %s' % (y, 'dBm')
        }
        ycoord = {
            'linear': '%.3f %s' % (y, 'V'),
            'log': '%.3f %s' % (y, 'dBm')
        }

        return {'yaxis': (yfmt['log'] if dbm else yfmt['linear']),
                'ycoord': (ycoord['log'] if dbm else ycoord['linear'])}

    def get_yaxis_fmt(self, y, pos):
        """ Function suitable to use as argument to a matplotlib
            FuncFormatter for Y (voltage) axis """
        return self._get_yaxis_fmt(y, pos)['yaxis']

    def get_ycoord_fmt(self, y):
        """ Function suitable to use as argument to a matplotlib FuncFormatter
            for Y (voltage) coordinate """
        return self._get_yaxis_fmt(y, None)['ycoord']
