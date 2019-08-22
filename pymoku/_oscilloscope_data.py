import struct

from pymoku import _frame_instrument

_OSC_SCREEN_WIDTH = 1024


class VoltsData(_frame_instrument.InstrumentData):
    """
    Object representing a frame of dual-channel data in units of Volts, and
    time in units of seconds. This is the native output format of the
    :any:`Oscilloscope` instrument. The *waveformid* property enables
    identification of uniqueness of a frame of data, as it is possible to
    retrieve the same data more than once (i.e. if the instrument has been
    paused).

    This object should not be instantiated directly, but will be returned by a
    call to :any:`get_data <pymoku.instruments.Oscilloscope.get_data>` or
    :any:`get_realtime_data
    <pymoku.instruments.Oscilloscope.get_realtime_data>` on the associated
    :any:`Oscilloscope` instrument.

    .. autoinstanceattribute:: pymoku._frame_instrument.VoltsData.ch1
        :annotation: = [CH1_DATA]

    .. autoinstanceattribute:: pymoku._frame_instrument.VoltsData.ch2
        :annotation: = [CH2_DATA]

    .. autoinstanceattribute:: pymoku._frame_instrument.VoltsData.time
        :annotation: = [TIME]

    .. autoinstanceattribute:: pymoku._frame_instrument.VoltsData.waveformid
        :annotation: = n
    """
    def __init__(self, instrument, scales):
        super(VoltsData, self).__init__(instrument)

        # : Channel 1 data array in units of Volts. Present whether or not the
        # channel is enabled, but the
        # : contents are undefined in the latter case.
        self.ch1 = []

        #: Channel 2 data array in units of Volts.
        self.ch2 = []

        #: Timebase
        self.time = []

        self._scales = scales

    def __json__(self):
        return {'ch1': self.ch1,
                'ch2': self.ch2,
                'time': self.time,
                'waveform_id': self.waveformid}

    def process_complete(self):
        super(VoltsData, self).process_complete()

        if self._stateid not in self._scales:
            return

        scales = self._scales[self._stateid]
        scale_ch1 = scales['scale_ch1']
        scale_ch2 = scales['scale_ch2']
        t1 = scales['time_min']
        ts = scales['time_step']

        try:
            smpls = int(len(self._raw1) / 4)
            dat = struct.unpack('<' + 'i' * smpls, self._raw1)
            dat = [x if x != -0x80000000 else None for x in dat]

            self._ch1_bits = [float(x) if x is not None
                              else None for x in dat[:_OSC_SCREEN_WIDTH]]
            self.ch1 = [x * scale_ch1 if x is not None
                        else None for x in self._ch1_bits]

            smpls = int(len(self._raw2) / 4)
            dat = struct.unpack('<' + 'i' * smpls, self._raw2)
            dat = [x if x != -0x80000000 else None for x in dat]

            self._ch2_bits = [float(x) if x is not None
                              else None for x in dat[:_OSC_SCREEN_WIDTH]]
            self.ch2 = [x * scale_ch2 if x is not None
                        else None for x in self._ch2_bits]
        except (IndexError, TypeError, struct.error):
            # If the data is bollocksed, force a reinitialisation on next
            # packet
            self._frameid = None
            self._complete = False

        self.time = [t1 + (x * ts) for x in range(_OSC_SCREEN_WIDTH)]

        return True

    def process_buffer(self):
        # Compute the x-axis of the buffer
        if self._stateid not in self._scales:
            return
        scales = self._scales[self._stateid]
        self.time = [scales['buff_time_min'] + (scales['buff_time_step'] * x)
                     for x in range(len(self.ch1))]
        return True

    def _get_timescale(self, tspan):
        # Returns a scaling factor and units for time 'T'
        if(tspan < 1e-6):
            scale_str = 'ns'
            scale_const = 1e9
        elif (tspan < 1e-3):
            scale_str = 'us'
            scale_const = 1e6
        elif (tspan < 1):
            scale_str = 'ms'
            scale_const = 1e3
        else:
            scale_str = 's'
            scale_const = 1.0

        return [scale_str, scale_const]

    def _get_xaxis_fmt(self, x, pos):
        # This function returns a format string for the x-axis ticks and
        # x-coordinates along the time scale. Use this to set an x-axis format
        # during plotting of Oscilloscope frames

        if self._stateid not in self._scales:
            return

        scales = self._scales[self._stateid]
        ts = scales['time_step']
        tscale_str, tscale_const = self._get_timescale(ts*_OSC_SCREEN_WIDTH)

        return {'xaxis': '%.1f %s' % (x*tscale_const, tscale_str),
                'xcoord': '%.3f %s' % (x*tscale_const, tscale_str)}

    def get_xaxis_fmt(self, x, pos):
        """ Function suitable to use as argument to a matplotlib FuncFormatter
            for X (time) axis """
        return self._get_xaxis_fmt(x, pos)['xaxis']

    def get_xcoord_fmt(self, x):
        """ Function suitable to use as argument to a matplotlib FuncFormatter
            for X (time) coordinate """
        return self._get_xaxis_fmt(x, None)['xcoord']

    def _get_yaxis_fmt(self, y, pos):
        return {'yaxis': '%.1f %s' % (y, 'V'), 'ycoord': '%.3f %s' % (y, 'V')}

    def get_yaxis_fmt(self, y, pos):
        """ Function suitable to use as argument to a matplotlib FuncFormatter
            for Y (voltage) axis """
        return self._get_yaxis_fmt(y, pos)['yaxis']

    def get_ycoord_fmt(self, y):
        """ Function suitable to use as argument to a matplotlib FuncFormatter
            for Y (voltage) coordinate """
        return self._get_yaxis_fmt(y, None)['ycoord']
