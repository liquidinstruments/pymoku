
import math
import logging
import re

from ._instrument import *
from . import _frame_instrument
from . import _waveform_generator
from . import _utils
from ._trigger import Trigger

from ._oscilloscope_data import VoltsData, _OSC_SCREEN_WIDTH

log = logging.getLogger(__name__)

REG_OSC_OUTSEL      = 64
REG_OSC_TRIGCTL     = 67
REG_OSC_ACTL        = 66
REG_OSC_DECIMATION  = 65
REG_OSC_AUTOTIMER   = 74

### Every constant that starts with OSC_ will become an attribute of pymoku.instruments ###
_OSC_SOURCE_CH1     = 0
_OSC_SOURCE_CH2     = 1
_OSC_SOURCE_DA1     = 2
_OSC_SOURCE_DA2     = 3
_OSC_SOURCE_EXT     = 4

# Input mux selects for Oscilloscope
_OSC_SOURCES = {
    'in1' : _OSC_SOURCE_CH1,
    'in2' : _OSC_SOURCE_CH2,
    'out1' : _OSC_SOURCE_DA1,
    'out2' : _OSC_SOURCE_DA2,
    'ext' : _OSC_SOURCE_EXT
}

_OSC_ROLL           = ROLL
_OSC_SWEEP          = SWEEP
_OSC_FULL_FRAME     = FULL_FRAME

_OSC_LB_ROUND       = 0
_OSC_LB_CLIP        = 1

_OSC_AIN_DDS        = 0
_OSC_AIN_DECI       = 1

_OSC_ADC_SMPS       = ADC_SMP_RATE
_OSC_BUFLEN         = CHN_BUFLEN

# Max/min values for instrument settings
_OSC_TRIGLVL_MAX = 10.0 # V
_OSC_TRIGLVL_MIN = -10.0 # V

_OSC_SAMPLERATE_MIN = 10 # smp/s
_OSC_SAMPLERATE_MAX = 500e6 # smp/s

_OSC_PRETRIGGER_MAX = (2**12)-1
_OSC_POSTTRIGGER_MAX = -2**28

_CLK_FREQ = 125e6
_TIMER_ACCUM = 2.0**32

class _CoreOscilloscope(_frame_instrument.FrameBasedInstrument):

    def __init__(self):
        super(_CoreOscilloscope, self).__init__()
        self._register_accessors(_osc_reg_handlers)

        self._trigger = Trigger(self, reg_base=68)

        self.id = 1
        self.type = "oscilloscope"
        self.calibration = None

        # Defines the samplerate as seen at the input of the instrument
        # This value should be overwritten by all child instruments inheriting the Oscilloscope
        self._input_samplerate  = _OSC_ADC_SMPS
        self._chn_buffer_len    = _OSC_BUFLEN

        # NOTE: Register mapped properties will be overwritten in sync registers call
        # on deploy_instrument(). No point setting them here.
        self.scales = {}
        self._set_frame_class(VoltsData, instrument=self, scales=self.scales)

        # All instruments need a binstr, procstr and format string.
        self.logname = "MokuOscilloscopeData"
        self.binstr = "<s32"
        self.procstr = ['','']
        self.fmtstr = ''
        self.hdrstr = ''
        self.timestep = 1

        # Initialise any local user config variables
        self._trig_hysteresis = 0
        self._trig_level = 0
        self._trig_duration = 0

    def _calculate_decimation(self, t1, t2):

        # Calculate time the buffer should contain
        # Want one frame to be approximately 1/3 of a buffer (RD ~ 5)
        # or the full buffer if it would take longer than 100ms

        # TODO: Put some limits on what the span/decimation can be
        if (t2 < 0):
            buffer_span = -float(t1)
        else:
            buffer_span = float(t2 - t1)

        deci = math.ceil(self._input_samplerate * buffer_span / self._chn_buffer_len)

        return deci

    def _calculate_render_downsample(self, t1, t2, decimation):
        # Calculate how much to render downsample
        tspan = float(t2) - float(t1)
        buffer_smp_rate = self._input_samplerate/float(decimation)
        buffer_time_span = self._chn_buffer_len/buffer_smp_rate

        def _cubic_int_to_scale(integer):
            # Integer to cubic scaling ratio (see Wiki)
            return float(integer/(2.0**7)) + 1

        # Enforce a maximum ADC sampling rate
        screen_smp_rate = min(_OSC_SCREEN_WIDTH/tspan, self._input_samplerate)

        # Clamp the render downsampling ratio between 1.0 and ~16.0
        render_downsample = min(max(buffer_smp_rate/screen_smp_rate, 1.0), _cubic_int_to_scale(0x077E))
        return render_downsample

    def _calculate_buffer_offset(self, t1, decimation):
        # Calculate the number of pretrigger samples and offset it by an additional (CubicRatio) samples
        buffer_smp_rate = self._input_samplerate/decimation
        buffer_offset_secs = -1.0 * t1
        buffer_offset = math.ceil(min(max(math.ceil(buffer_offset_secs * buffer_smp_rate / 4.0), _OSC_POSTTRIGGER_MAX), _OSC_PRETRIGGER_MAX))

        # Apply a correction in pretrigger because of the way cubic interpolation occurs when rendering
        return buffer_offset

    def _calculate_render_offset(self, t1, decimation):
        # TODO: Render offset should be unique to buffer offset
        #       For now they are the same thing.
        buffer_offset = self._calculate_buffer_offset(t1, decimation)

        return buffer_offset * 4.0

    def _calculate_frame_start_time(self, decimation, render_decimation, frame_offset):
        return (render_decimation - frame_offset) * decimation/self._input_samplerate

    def _calculate_frame_timestep(self, decimation, render_decimation):
        return decimation*render_decimation/self._input_samplerate

    def _calculate_buffer_timestep(self, decimation):
        return float(decimation)/float(self._input_samplerate)

    def _calculate_buffer_start_time(self, decimation, buffer_offset):
        return self._calculate_buffer_timestep(decimation) * (-1.0 * buffer_offset) * 4.0

    def _deci_gain(self):
        if self.decimation_rate == 0:
            return 1

        if self.decimation_rate < 2**20:
            return self.decimation_rate
        else:
            return self.decimation_rate / 2**10


    @needs_commit
    def set_timebase(self, t1, t2):
        """ Set the left- and right-hand span for the time axis.
        Units are seconds relative to the trigger point.

        :type t1: float
        :param t1:
            Time, in seconds, from the trigger point to the left of screen. This may be negative (trigger on-screen)
            or positive (trigger off the left of screen).

        :type t2: float
        :param t2: As *t1* but to the right of screen.

        :raises InvalidConfigurationException: if the timebase is backwards or zero.
        """
        if(t2 <= t1):
            raise InvalidConfigurationException("Timebase must be non-zero, with t1 < t2. Attempted to set t1=%f and t2=%f" % (t1, t2))

        decimation = self._calculate_decimation(t1,t2)
        render_decimation = self._calculate_render_downsample(t1, t2, decimation)
        buffer_offset = self._calculate_buffer_offset(t1, decimation)
        frame_offset = self._calculate_render_offset(t1, decimation)

        self.decimation_rate = decimation
        self.render_deci = render_decimation
        self.pretrigger = buffer_offset
        self.offset = frame_offset

    @needs_commit
    def set_samplerate(self, samplerate, trigger_offset=0):
        """ Manually set the sample rate of the instrument.

        The sample rate is automatically calculated and set in :any:`set_timebase`.

        This interface allows you to specify the rate at which data is sampled, and set
        a trigger offset in number of samples. This interface is useful for datalogging and capturing
        of data frames.

        :type samplerate: float; *0 < samplerate <= MAX_SAMPLERATE smp/s*
        :param samplerate: Target samples per second. Will get rounded to the nearest allowable unit.

        :type trigger_offset: int; *-2^16 < trigger_offset < 2^31*
        :param trigger_offset: Number of samples before (-) or after (+) the trigger point to start capturing.

        :raises ValueOutOfRangeException: if either parameter is out of range.
        """
        _utils.check_parameter_valid('range', samplerate, [_OSC_SAMPLERATE_MIN,_OSC_SAMPLERATE_MAX], 'samplerate', 'smp/s')
        _utils.check_parameter_valid('range', trigger_offset, [-2**16 + 1, 2**31 - 1], 'trigger offset', 'samples')

        decimation = self._input_samplerate / float(samplerate)

        self.decimation_rate = decimation
        self.timestep = 1.0/(self._input_samplerate/self.decimation_rate)
        # Ensure the buffer offset is large enough to incorporate the desired pretrigger/posttrigger data
        self.pretrigger = - math.ceil(trigger_offset/4.0) if trigger_offset > 0 else - math.floor(trigger_offset/4.0)
        # We don't want any rendering as each sample is already at the desired samplerate
        self.render_deci = 1
        # The render offset needs to be corrected for cubic downsampling (even with unity decimation)
        self.offset = - round(trigger_offset) + self.render_deci

    def get_samplerate(self):
        """ :return: The current instrument sample rate (Hz) """
        if(self.decimation_rate == 0):
            log.info("Decimation rate appears to be unset.")
            return self._input_samplerate
        return self._input_samplerate / float(self.decimation_rate)

    @needs_commit
    def set_xmode(self, xmode):
        """
        Set rendering mode for the horizontal axis.

        :type xmode: string, {'roll','sweep','fullframe'}
        :param xmode:
            Respectively; Roll Mode (scrolling), Sweep Mode (normal oscilloscope trace sweeping across the screen)
            or Full Frame (like sweep, but waits for the frame to be completed).
        """
        _str_to_xmode = {
            'roll' : _OSC_ROLL,
            'sweep' : _OSC_SWEEP,
            'fullframe' : _OSC_FULL_FRAME
        }
        xmode = _utils.str_to_val(_str_to_xmode, xmode, 'X-mode')
        self.x_mode = xmode

    @needs_commit
    def set_precision_mode(self, state):
        """ Change aquisition mode between downsampling and decimation.
        Precision mode, a.k.a Decimation, samples at full rate and applies a low-pass filter to the data. This improves
        precision. Normal mode works by direct downsampling, throwing away points it doesn't need.

        :param state: Select Precision Mode
        :type state: bool
        """
        _utils.check_parameter_valid('bool', state, desc='precision mode enable')
        self.ain_mode = _OSC_AIN_DECI if state else _OSC_AIN_DDS

    def is_precision_mode(self):
        return self.ain_mode is _OSC_AIN_DECI

    def _set_trigger(self, source, edge, level, minwidth, maxwidth, hysteresis, hf_reject, mode):
        if (self._moku.get_hw_version() == 1.0) and source == _OSC_SOURCE_EXT:
            raise InvalidConfigurationException('External trigger source is not available on your hardware.')

        # Convert the input parameter strings to bit-value mappings
        _utils.check_parameter_valid('range', level, [_OSC_TRIGLVL_MIN, _OSC_TRIGLVL_MAX], 'trigger level', 'Volts')
        _utils.check_parameter_valid('bool', hf_reject, 'High-frequency reject enable')
        _utils.check_parameter_valid('set', mode, ['auto', 'normal'], desc='mode')
        _utils.check_parameter_valid('range', hysteresis, [100e-6, 1.0], 'hysteresis', 'Volts')
        if not (maxwidth is None or minwidth is None):
            raise InvalidConfigurationException("Can't set both 'minwidth' and 'maxwidth' for Pulse Width trigger mode. Choose one.")
        if (maxwidth or minwidth) and (edge is 'both'):
            raise InvalidConfigurationException("Can't set trigger edge type 'both' in Pulse Width trigger mode. Choose one of {'rising','falling'}.")

        _str_to_edge = {
            'rising' : Trigger.EDGE_RISING,
            'falling' : Trigger.EDGE_FALLING,
            'both'  : Trigger.EDGE_BOTH
        }
        edge = _utils.str_to_val(_str_to_edge, edge, 'edge type')

        self.hf_reject = hf_reject

        if mode == 'auto':
            #TODO these should scale with the timebase
            self.auto_timer = 20.0
            self.auto_holdoff = 5
        elif mode == 'normal':
            self.auto_timer = 0.0
            self.auto_holdoff = 0

        self.trig_ch = source
        # Locally store user settings and calculate regs at commit-time
        self._trig_level = level
        self._trig_duration = minwidth or maxwidth or 0.0
        self._trig_hysteresis = hysteresis

        self._trigger.edge = edge
        self._trigger.mode = mode
        if maxwidth:
            self._trigger.trigtype = Trigger.TYPE_PULSE
            self._trigger.pulsetype = Trigger.PULSE_MAX
        elif minwidth:
            self._trigger.trigtype = Trigger.TYPE_PULSE
            self._trigger.pulsetype = Trigger.PULSE_MIN
        else:
            self._trigger.trigtype = Trigger.TYPE_EDGE

    def _set_source(self, ch, source):
        """ Sets the source of the channel data to either the analog input or internally looped-back digital output.
        """
        # TODO: Add loopback mode parameter
        _utils.check_parameter_valid('set', ch, [1,2], 'channel')

        if ch == 1:
            self.source_ch1 = source
        elif ch == 2:
            self.source_ch2 = source
        else:
            raise ValueOutOfRangeException("Incorrect channel number %d", ch)

    @needs_commit
    def set_defaults(self):
        """ Reset the Oscilloscope to sane defaults. """
        super(_CoreOscilloscope, self).set_defaults()
        self.set_precision_mode(True)
        self.trig_precision = True # Set to always trigger off precision data
        self.set_timebase(-1, 1)
        self._set_pause(False)

        self.frame_length = _OSC_SCREEN_WIDTH
        self._set_buffer_length(4)
        self.set_xmode('fullframe')

        self.set_frontend(1, fiftyr=True, atten=False, ac=False)
        self.set_frontend(2, fiftyr=True, atten=False, ac=False)
        self.en_in_ch1 = True
        self.en_in_ch2 = True

    def _calculate_scales(self):
        g1, g2 = self._adc_gains()
        d1, d2 = self._dac_gains()
        a1 = self.get_frontend(1)[1]
        a2 = self.get_frontend(2)[1]

        if(self.decimation_rate == 0 or self.render_deci == 0):
            log.warning("ADCs appear to be turned off or decimation unset")
            t1 = 0
            ts = 1
            bt1 = 0
            bts = 1
        else:
            t1 = self._calculate_frame_start_time(self.decimation_rate, self.render_deci, self.offset)
            ts = self._calculate_frame_timestep(self.decimation_rate, self.render_deci)
            bt1 = self._calculate_buffer_start_time(self.decimation_rate, self.pretrigger)
            bts = self._calculate_buffer_timestep(self.decimation_rate)

        scales = {
                'gain_adc1': g1,
                'gain_adc2': g2,
                'gain_dac1': d1,
                'gain_dac2': d2,
                'atten_ch1': a1,
                'atten_ch2': a2,
                'time_min': t1,
                'time_step': ts,
                'buff_time_min': bt1,
                'buff_time_step': bts
                }

        # Replace scaling factors depending on the monitor signal source
        scales['scale_ch1'] = self._signal_source_volts_per_bit(self.source_ch1, scales)
        scales['scale_ch2'] = self._signal_source_volts_per_bit(self.source_ch2, scales)

        return scales

    def _update_dependent_regs(self, scales):
        # Update trigger level and duration settings based on current trigger source and timebase
        self._trigger.duration = self._trig_duration * self._input_samplerate / (self.decimation_rate if self.is_precision_mode() else 1.0)
        self._trigger.level = int(round(self._trig_level/self._signal_source_volts_per_bit(self.trig_ch, scales, trigger=True)))

        # Notify the user if hysteresis has been clamped
        max_hysteresis = 2**16 - 1
        hysteresis = int(round(self._trig_hysteresis/self._signal_source_volts_per_bit(self.trig_ch, scales, trigger=True)))
        if hysteresis > max_hysteresis:
            hysteresis = max_hysteresis
            log.info("Hysteresis set to maximum value.")
        self._trigger.hysteresis = hysteresis

    def _update_datalogger_params(self):
        scales = self._calculate_scales()

        samplerate = self.get_samplerate()
        self.timestep = 1.0/samplerate

        # Use the new scales to decide on the processing string
        self.procstr[0] = "*{:.15f}".format(scales['scale_ch1'])
        self.procstr[1] = "*{:.15f}".format(scales['scale_ch2'])

        self.fmtstr = self._get_fmtstr(self.ch1,self.ch2)
        self.hdrstr = self._get_hdrstr(self.ch1,self.ch2)

    def _get_hdrstr(self, ch1, ch2):
        chs = [ch1, ch2]

        hdr = "% Moku:Oscilloscope\r\n"
        for i,c in enumerate(chs):
            if c:
                r = self.get_frontend(i+1)
                hdr += "% Ch {i} - {} coupling, {} Ohm impedance, {} V range\r\n".format("AC" if r[2] else "DC", "50" if r[0] else "1M", "10" if r[1] else "1", i=i+1 )
        hdr += "% Acquisition rate: {:.10e} Hz, {} mode\r\n".format(self.get_samplerate(), "Precision" if self.is_precision_mode() else "Normal")
        hdr += "% {} 10 MHz clock\r\n".format("External" if self._moku._get_actual_extclock() else "Internal")
        hdr += "% Acquired {}\r\n".format(_utils.formatted_timestamp())
        hdr += "% Time"
        for i,c in enumerate(chs):
            if c:
                hdr += ", Ch {i} voltage (V)".format(i=i+1)
        hdr += "\r\n"
        return hdr

    def _get_fmtstr(self, ch1, ch2):
        chs = [ch1, ch2]
        fmtstr = "{t:.10e}"
        for i,c in enumerate(chs):
            if c:
                fmtstr += ",{{ch{i}:.10e}}".format(i=i+1)
        fmtstr += "\r\n"
        return fmtstr

    def _on_reg_sync(self):
        # Do the instrument-level post-sync stuff
        super(_CoreOscilloscope, self)._on_reg_sync()

        # This function is used to update any local variables when a Moku has
        # had its registers synchronised with the current instrument
        if self.decimation_rate == 0:
            self.timestep = 1.0/(self._input_samplerate)
        else:
            self.timestep = float(self.decimation_rate) / self._input_samplerate

        scales = self._calculate_scales()
        self.scales[self._stateid] = scales

        # Read back trigger settings into local variables
        self._trig_duration = self._trigger.duration * (self.decimation_rate if self.is_precision_mode() else 1.0) / self._input_samplerate
        self._trig_level = self._trigger.level * self._signal_source_volts_per_bit(self.trig_ch, scales, trigger=True)
        self._trig_hysteresis = self._trigger.hysteresis * self._signal_source_volts_per_bit(self.trig_ch, scales, trigger=True)

        self._update_datalogger_params()

    def commit(self):
        scales = self._calculate_scales()
        # Update any calibration scaling dependent register values
        self._update_dependent_regs(scales)
        self._update_datalogger_params()

        # Commit the register values to the device
        super(_CoreOscilloscope, self).commit()
        # Associate new state ID with the scaling factors of the state
        self.scales[self._stateid] = scales
        # TODO: Trim scales dictionary, getting rid of old ids

    # Bring in the docstring from the superclass for our docco.
    commit.__doc__ = MokuInstrument.commit.__doc__


class Oscilloscope(_CoreOscilloscope, _waveform_generator.BasicWaveformGenerator):
    """ Oscilloscope instrument object.

    To run a new Oscilloscope instrument, this should be instantiated and deployed via a connected
    :any:`Moku` object using :any:`deploy_instrument`. Alternatively, a pre-configured instrument object
    can be obtained by discovering an already running Oscilloscope instrument on a Moku:Lab device via
    :any:`discover_instrument`.

    .. automethod:: pymoku.instruments.Oscilloscope.__init__

    .. attribute:: framerate
        :annotation: = 10

        Frame Rate, range 10 - 30.

    .. attribute:: type
        :annotation: = "oscilloscope"

        Name of this instrument.

    """
    # The Oscilloscope core is split out without the siggen so it can be used as embedded in other instruments,
    # e.g. lockin, pid etc.

    @needs_commit
    def set_defaults(self):
        super(Oscilloscope, self).set_defaults()
        self.set_source(1,'in1')
        self.set_source(2,'in2')
        self.set_trigger('in1','rising', 0)

    @needs_commit
    def set_trigger(self, source, edge, level, minwidth=None, maxwidth=None, hysteresis=10e-3, hf_reject=False, mode='auto'):
        """ Sets trigger source and parameters.

        :type source: string, {'in1','in2','out1','out2','ext'}
        :param source: Trigger Source. May be either an input or output channel, or external. The output options allow
                triggering off an internally-generated waveform. External refers to the back-panel connector of the same
                name, allowing triggering from an externally-generated digital [LV]TTL or CMOS signal.

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

        .. note::
            Traditional Oscilloscopes have a "Single Trigger" mode that captures an event then
            pauses the instrument. In pymoku, there is no need to pause the instrument as you
            can simply choose to continue using the last captured frame.  That is, set trigger
            ``mode='normal'`` then retrieve a single frame using :any:`get_data <pymoku.instruments.Oscilloscope.get_data>`
            or :any:`get_realtime_data <pymoku.instruments.Oscilloscope.get_realtime_data>`
            with ``wait=True``.

        """
        source = _utils.str_to_val(_OSC_SOURCES, source, 'trigger source')
        self._set_trigger(source, edge, level, minwidth, maxwidth, hysteresis, hf_reject, mode)

    @needs_commit
    def set_source(self, ch, source, lmode='round'):
        """ Sets the source of the channel data to either the analog input or internally looped-back digital output.

        This feature allows the user to preview the Waveform Generator outputs.

        :type ch: int; {1,2}
        :param ch: Channel Number

        :type source: string, {'in1','in2','out1','out2','ext'}
        :param source: Where the specified channel should source data from (either the input or internally looped back output)

        :type lmode: string, {'clip','round'}
        :param lmode: DAC Loopback mode (ignored 'in' sources)
        """
        # TODO: Add loopback mode functionality
        source = _utils.str_to_val(_OSC_SOURCES, source, 'channel data source')
        self._set_source(ch, source)

    def _signal_source_volts_per_bit(self, source, scales, trigger=False):
        """
            Converts volts to bits depending on the signal source
        """
        if (not trigger and self.is_precision_mode()) or (trigger and self.trig_precision):
            deci_gain = self._deci_gain()
        else:
            deci_gain = 1.0

        if (source == _OSC_SOURCE_CH1):
            level = scales['gain_adc1']/deci_gain
        elif (source == _OSC_SOURCE_CH2):
            level = scales['gain_adc2']/deci_gain
        elif (source == _OSC_SOURCE_DA1):
            level = (scales['gain_dac1'])*16/deci_gain
        elif (source == _OSC_SOURCE_DA2):
            level = (scales['gain_dac2'])*16/deci_gain
        else:
            level = 1.0

        return level

_osc_reg_handlers = {
    'source_ch1':       (REG_OSC_OUTSEL,    to_reg_unsigned(0, 8, allow_set=[_OSC_SOURCE_CH1, _OSC_SOURCE_CH2, _OSC_SOURCE_DA1, _OSC_SOURCE_DA2, _OSC_SOURCE_EXT]),
                                            from_reg_unsigned(0, 8)),

    'source_ch2':       (REG_OSC_OUTSEL,    to_reg_unsigned(8, 8, allow_set=[_OSC_SOURCE_CH1, _OSC_SOURCE_CH2, _OSC_SOURCE_DA1, _OSC_SOURCE_DA2, _OSC_SOURCE_EXT]),
                                            from_reg_unsigned(8, 8)),

    'trig_ch':          (REG_OSC_TRIGCTL,   to_reg_unsigned(4, 6, allow_set=[_OSC_SOURCE_CH1, _OSC_SOURCE_CH2, _OSC_SOURCE_DA1, _OSC_SOURCE_DA2, _OSC_SOURCE_EXT]),
                                            from_reg_unsigned(4, 6)),

    'hf_reject':        (REG_OSC_TRIGCTL,   to_reg_bool(12),            from_reg_bool(12)),

    'loopback_mode_ch1':    (REG_OSC_ACTL,  to_reg_unsigned(0, 1, allow_set=[_OSC_LB_CLIP, _OSC_LB_ROUND]),
                                            from_reg_unsigned(0, 1)),
    'loopback_mode_ch2':    (REG_OSC_ACTL,  to_reg_unsigned(1, 1, allow_set=[_OSC_LB_CLIP, _OSC_LB_ROUND]),
                                            from_reg_unsigned(1, 1)),
    'ain_mode':         (REG_OSC_ACTL,      to_reg_unsigned(16,2, allow_set=[_OSC_AIN_DDS, _OSC_AIN_DECI]),
                                            from_reg_unsigned(16,2)),
    'trig_precision':   (REG_OSC_ACTL,      to_reg_bool(18),        from_reg_bool(18)),

    'decimation_rate':  (REG_OSC_DECIMATION,to_reg_unsigned(0, 32), from_reg_unsigned(0, 32)),
    'auto_timer':       (REG_OSC_AUTOTIMER, to_reg_unsigned(0, 16, xform=lambda obj, a:int(round(a * (_TIMER_ACCUM / _CLK_FREQ)))),
                                            from_reg_unsigned(0, 16, xform=lambda obj, a:(_CLK_FREQ * a) / _TIMER_ACCUM)),
    'auto_holdoff':     (REG_OSC_AUTOTIMER, to_reg_unsigned(16, 8), from_reg_unsigned(16, 8))
}
