
import math
import logging

from pymoku._instrument import to_reg_unsigned
from pymoku._instrument import from_reg_unsigned
from pymoku._instrument import to_reg_signed
from pymoku._instrument import from_reg_signed
from pymoku._instrument import to_reg_bool
from pymoku._instrument import from_reg_bool
from pymoku._instrument import needs_commit
from pymoku._instrument import MokuInstrument
from pymoku import _instrument
from pymoku import _stream_instrument
from pymoku import _utils

_sgn = _instrument._sgn
_usgn = _instrument._usgn
_upsgn = _instrument._upsgn

log = logging.getLogger(__name__)

REG_PM_INITF1_H = 65
REG_PM_INITF1_L = 64
REG_PM_INITF2_L = 68
REG_PM_INITF2_H = 69
REG_PM_OUTDEC = 67
REG_PM_OUTSHIFT = 67
REG_PM_BW1 = 124
REG_PM_BW2 = 125
REG_PM_AUTOA1 = 126
REG_PM_AUTOA2 = 127

REG_PM_LOCKED_OUTS = 95
REG_PM_SG_EN = 96
REG_PM_SG_FREQ1_L = 97
REG_PM_SG_FREQ1_H = 98
REG_PM_SG_FREQ2_L = 99
REG_PM_SG_FREQ2_H = 100
REG_PM_SG_AMP = 105
REG_PM_SG_PHASE1_L = 101
REG_PM_SG_PHASE1_H = 102
REG_PM_SG_PHASE2_L = 103
REG_PM_SG_PHASE2_H = 104

# Phasemeter specific instrument constants
_PM_ADC_SMPS = _instrument.ADC_SMP_RATE
_PM_DAC_SMPS = _instrument.DAC_SMP_RATE
_PM_BUFLEN = _instrument.CHN_BUFLEN
_PM_FREQSCALE = 2.0**48 / _PM_DAC_SMPS
_PM_FREQ_MIN = 1e3
_PM_FREQ_MAX = 200e6
_PM_UPDATE_RATE = 1e6

_PM_CYCLE_SCALE = 2.0 * 2.0**16 / 2.0**48 * _PM_ADC_SMPS / _PM_UPDATE_RATE
_PM_HERTZ_SCALE = 2.0 * _PM_ADC_SMPS / 2**48
_PM_VOLTS_SCALE = 2.0 / (_PM_ADC_SMPS * _PM_ADC_SMPS
                         / _PM_UPDATE_RATE
                         / _PM_UPDATE_RATE)

# Phasemeter waveform generator constants
_PM_SG_AMPSCALE = 2**16 / 4.0
_PM_SG_FREQSCALE = _PM_FREQSCALE
_PM_SG_PHASESCALE = 360.0 / (2**48)  # Wraps

# Pre-defined log rates which ensure samplerate will set to ~120Hz or ~30Hz
_PM_LOGRATE_ULTRA_FAST = 3  # 125 kHz
_PM_LOGRATE_VERY_FAST = 6  # 15.625 kHz
_PM_LOGRATE_FAST = 9  # 1.95 kHz
_PM_LOGRATE_MEDIUM = 11  # 490 Hz
_PM_LOGRATE_SLOW = 13  # 120 Hz
_PM_LOGRATE_VERY_SLOW = 15  # 30 Hz


class Phasemeter_WaveformGenerator(MokuInstrument):
    def __init__(self):
        super(Phasemeter_WaveformGenerator, self).__init__()
        self._register_accessors(_pm_siggen_reg_hdl)

    @needs_commit
    def set_defaults(self):
        # Turn off generated output waves
        self.gen_off()

    @needs_commit
    def gen_sinewave(self, ch, amplitude, frequency, phase=0.0,
                     phase_locked=False):
        """ Generate a sinewave signal on the specified output channel

        :type ch: int; {1,2}
        :param ch: Channel number
        :type amplitude: float; V
        :param amplitude: Signal peak-to-peak amplitude
        :type frequency: float; Hz
        :param frequency: Frequency
        :type phase: float; degrees
        :param phase: Phase
        :type phase_locked: boolean
        :param phase_locked: Locks the phase of the generated sinewave to the
                measured phase of the input signal

        :raises ValueError: if the channel number is invalid
        :raises ValueOutOfRangeException: if wave parameters are out of range

        """
        _utils.check_parameter_valid(
            'set', ch, [1, 2], 'output channel')
        _utils.check_parameter_valid(
            'range', amplitude, [0.0, 2.0], 'sinewave amplitude', 'Volts')
        _utils.check_parameter_valid(
            'range', frequency, [0, 250e6], 'sinewave frequency', 'Hz')
        _utils.check_parameter_valid(
            'range', phase, [0, 360], 'sinewave phase', 'degrees')
        _utils.check_parameter_valid('set',
                                     phase_locked,
                                     [True, False],
                                     'phase locked output',
                                     'boolean')

        if ch == 1:
            self.pm_out1_frequency = frequency
            self.pm_out1_amplitude = amplitude
            self.pm_out1_phase = phase
            self.pm_out1_locked_out = phase_locked
        elif ch == 2:
            self.pm_out2_frequency = frequency
            self.pm_out2_amplitude = amplitude
            self.pm_out2_phase = phase
            self.pm_out2_locked_out = phase_locked

    @needs_commit
    def gen_off(self, ch=None):
        """ Turn Waveform Generator output(s) off.

        The channel will be turned on when configuring the waveform type but
        can be turned off using this function. If *ch* is None (the default),
        both channels will be turned off, otherwise just the one specified by
        the argument.

        :type ch: int; {1,2} or *None*
        :param ch: Channel to turn off or *None* for all channels

        :raises ValueOutOfRangeException: if the channel number is invalid
        """
        _utils.check_parameter_valid(
            'set', ch, [1, 2], 'output channel', allow_none=True)

        if (ch is None) or ch == 1:
            self.pm_out1_amplitude = 0
        if (ch is None) or ch == 2:
            self.pm_out2_amplitude = 0


_pm_siggen_reg_hdl = {
    'pm_out1_frequency':
        ((REG_PM_SG_FREQ1_H, REG_PM_SG_FREQ1_L),
            to_reg_unsigned(0, 48,
                            xform=lambda obj, f: f * _PM_SG_FREQSCALE),
            from_reg_unsigned(0, 48,
                              xform=lambda obj, f: f / _PM_FREQSCALE)),
    'pm_out2_frequency':
        ((REG_PM_SG_FREQ2_H, REG_PM_SG_FREQ2_L),
            to_reg_unsigned(0, 48,
                            xform=lambda obj, f: f * _PM_SG_FREQSCALE),
            from_reg_unsigned(0, 48,
                              xform=lambda obj, f: f / _PM_FREQSCALE)),
    'pm_out1_amplitude':
        (REG_PM_SG_AMP,
            to_reg_unsigned(0, 16,
                            xform=lambda obj, a: a / obj._dac_gains()[0]),
            from_reg_unsigned(0, 16,
                              xform=lambda obj, a: a * obj._dac_gains()[0])),
    'pm_out2_amplitude':
        (REG_PM_SG_AMP,
            to_reg_unsigned(16, 16,
                            xform=lambda obj, a: a / obj._dac_gains()[1]),
            from_reg_unsigned(16, 16,
                              xform=lambda obj, a: a * obj._dac_gains()[1])),
    'pm_out1_phase':
        ((REG_PM_SG_PHASE1_H, REG_PM_SG_PHASE1_L),
            to_reg_unsigned(0, 48,
                            xform=lambda obj, p: (p / _PM_SG_PHASESCALE)),
            from_reg_unsigned(0, 48,
                              xform=lambda obj, p: p * _PM_SG_PHASESCALE)),
    'pm_out2_phase':
        ((REG_PM_SG_PHASE2_H, REG_PM_SG_PHASE2_L),
            to_reg_unsigned(0, 48,
                            xform=lambda obj, p: (p / _PM_SG_PHASESCALE)),
            from_reg_unsigned(0, 48,
                              xform=lambda obj, p: p * _PM_SG_PHASESCALE)),
    'pm_out1_locked_out':
        (REG_PM_LOCKED_OUTS,
            to_reg_bool(0),
            from_reg_bool(0)),
    'pm_out2_locked_out':
        (REG_PM_LOCKED_OUTS,
            to_reg_bool(1),
            from_reg_bool(1))
}


class Phasemeter(_stream_instrument.StreamBasedInstrument,
                 Phasemeter_WaveformGenerator):
    # TODO Frame instrument may not be appropriate when we get streaming going.
    """ Phasemeter instrument object.

    To run a new Phasemeter instrument, this should be instantiated and
    deployed via a connected :any:`Moku` object using
    :any:`deploy_instrument`. Alternatively, a pre-configured instrument object
    can be obtained by discovering an already running Phasemeter
    instrument on a Moku:Lab device via
    :any:`discover_instrument`.

    .. automethod:: pymoku.instruments.Phasemeter.__init__

    .. attribute:: type
        :annotation: = "phasemeter"

        Name of this instrument.

    """
    def __init__(self):
        """Create a new Phasemeter instrument, ready to be attached to a
        Moku."""
        super(Phasemeter, self).__init__()
        self._register_accessors(_pm_reg_handlers)

        self.id = 3
        self.type = "phasemeter"
        self.logname = "MokuPhasemeterData"

        self.binstr = "<p32,0xAAAAAAAA:u48:u48:s15:p1,0:s48:s32:s32"
        self.procstr = ["*{:.16e} : *{:.16e} : : *{:.16e} : *C*{:.16e} "
                        ": *C*{:.16e}".format(_PM_HERTZ_SCALE,
                                              _PM_HERTZ_SCALE,
                                              _PM_CYCLE_SCALE,
                                              _PM_VOLTS_SCALE,
                                              _PM_VOLTS_SCALE),
                        "*{:.16e} : *{:.16e} : : *{:.16e} : *C*{:.16e} "
                        ": *C*{:.16e}".format(_PM_HERTZ_SCALE,
                                              _PM_HERTZ_SCALE,
                                              _PM_CYCLE_SCALE,
                                              _PM_VOLTS_SCALE,
                                              _PM_VOLTS_SCALE)]

    def _update_datalogger_params(self):
        # Call this function when any instrument configuration parameters are
        # set
        self.fmtstr = self._get_fmtstr(self.ch1, self.ch2)
        self.hdrstr = self._get_hdrstr(self.ch1, self.ch2)

    @needs_commit
    def set_samplerate(self, samplerate):
        """ Set the sample rate of the Phasemeter.

        Options are {'veryslow','slow','medium','fast','veryfast','ultrafast'}
        corresponding to 30.5176 smp/s, 122.0703 smp/s, 1.9531 ksmp/s,
        15.625 ksmp/s, 125 ksps/s.

        :type samplerate: string, {'veryslow','slow','medium','fast',
        'veryfast','ultrafast'}
        :param samplerate: Desired sample rate

        :raises ValueError: If samplerate parameter is invalid.
        """
        _str_to_samplerate_index = {
            'ultrafast': _PM_LOGRATE_ULTRA_FAST,
            'veryfast': _PM_LOGRATE_VERY_FAST,
            'fast': _PM_LOGRATE_FAST,
            'medium': _PM_LOGRATE_MEDIUM,
            'slow': _PM_LOGRATE_SLOW,
            'veryslow': _PM_LOGRATE_VERY_SLOW
        }
        N = _utils.str_to_val(_str_to_samplerate_index,
                              samplerate, 'samplerate')

        self.output_decimation = 2**N
        self.output_shift = N
        self.timestep = 1.0 / (_PM_UPDATE_RATE / self.output_decimation)
        log.info("Samplerate set to %.2f smp/s",
                 _PM_UPDATE_RATE / float(self.output_decimation))

    def get_samplerate(self):
        """ Get the samplerate of the Phasemeter

        :rtype: float; smp/s
        :return: Samplerate
        """
        return _PM_UPDATE_RATE / self.output_decimation

    @needs_commit
    def set_initfreq(self, ch, f):
        """ Manually set the initial frequency of the designated channel

        :type ch: int; *{1,2}*
        :param ch: Channel number to set the initial frequency of.

        :type f: int; *2e6 < f < 200e6*
        :param f: Initial locking frequency of the designated channel

        :raises ValueError: If the channel number is invalid.
        :raises ValueOutOfRangeException: If the frequency parameter is out of
            range.
        """
        _utils.check_parameter_valid('range',
                                     f,
                                     [_PM_FREQ_MIN, _PM_FREQ_MAX],
                                     'initial frequency')
        _utils.check_parameter_valid('set', ch, [1, 2], 'channel')

        if ch == 1:
            self.init_freq_ch1 = int(f)
        elif ch == 2:
            self.init_freq_ch2 = int(f)

    def get_initfreq(self, ch):
        """
        Reads the seed frequency register of the phase tracking loop
        Valid if auto acquire has not been used.

        :type ch: int; *{1,2}*
        :param ch: Channel number to read the initial frequency of.
        :rtype: float; Hz
        :return: Seed frequency

        :raises ValueError: If the channel number is invalid.
        """
        _utils.check_parameter_valid('set', ch, [1, 2], 'channel')

        if ch == 1:
            return self.init_freq_ch1
        elif ch == 2:
            return self.init_freq_ch2

    @needs_commit
    def set_bandwidth(self, ch, bw):
        """ Set the bandwidth of the phasemeter.

        The phasemeter can measure deviations in phase and frequency up to the
        set bandwidth.

        :type ch: int; *{1,2}*
        :param ch: Analog channel number to set bandwidth of.

        :type bw: float; Hz
        :param n: Desired bandwidth (will be rounded up to to the nearest
            multiple 10kHz / 2^N with N = [0,10])

        :raises ValueError: If the channel number is invalid.
        :raises ValueOutOfRangeException: if the bandwidth is not
            positive-definite or the channel number is invalid
        """
        _utils.check_parameter_valid('set', ch, [1, 2], 'channel')
        _utils.check_parameter_valid(
            'range', bw, [10, 10e3], 'bandwidth', 'Hz')

        n = max(min(math.ceil(math.log(10e3/bw, 2)), 10), 0)

        if ch == 1:
            self.bandwidth_ch1 = n
        elif ch == 2:
            self.bandwidth_ch2 = n

        log.info("Bandwidth (Ch %d) set to %.2f Hz", ch, 10e3/(2**n))

    def get_bandwidth(self, ch):
        """ Get the bandwidth of the phasemeter.

        :type ch: int; *{1,2}*
        :param ch: Analog channel number to get bandwidth of.

        :rtype: float; Hz
        :return: Bandwidth

        :raises ValueError: If the channel number is invalid.
        """
        _utils.check_parameter_valid('set', ch, [1, 2], 'channel')
        return 10e3 / (2**(self.bandwidth_ch1
                           if ch == 1 else self.bandwidth_ch2))

    def _strobe_acquire(self, ch, auto):
        """ Helper function which strobes the reacquire or auto-acquire for
        single or both channels

        :type ch: int; *{1,2}*
        :param ch: Analog channel number to get bandwidth of.

        :type: auto; bool
        :param auto: True will turn the auto aquire on. False will require
        using the using the init frequency.
        """
        if not ch or (ch == 1):
            self.autoacquire_ch1 = auto
        if not ch or (ch == 2):
            self.autoacquire_ch2 = auto

    @needs_commit
    def reacquire(self, ch=None):
        """
        Restarts the frequency tracking loop and phase counter for the
        specified channel, or both if no channel is specified. The starting
        frequency of the channel's tracking loop is set to the seed frequency
        as set by calling :any:`set_initfreq`.

        To automatically acquire a seed frequency, see :any:`auto_acquire`.

        :type ch: int; *{1,2}*
        :param ch: Channel number, or ``None`` for both

        :raises ValueError: If the channel number is invalid.
        """
        _utils.check_parameter_valid('set', ch, [1, 2, None], 'channel')
        self._strobe_acquire(ch=ch, auto=False)

    @needs_commit
    def auto_acquire(self, ch=None):
        """
        Restarts the frequency tracking loop and phase counter for the
        specified channel, or both if no channel is specified. The initial
        frequency of the channel's tracking loop is automatically acquired,
        ignoring the manually set seed frequency by :any:`set_initfreq`.

        To acquire using the manually set seed frequency, see :any:`reacquire`.

        :type ch: int; *{1,2}*
        :param ch: Channel number, or ``None`` for both

        :raises ValueError: If the channel number is invalid.
        """
        _utils.check_parameter_valid('set', ch, [1, 2, None], 'channel')
        self._strobe_acquire(ch=ch, auto=True)

    def _get_hdrstr(self, ch1, ch2):
        chs = [ch1, ch2]

        hdr = "% Moku:Phasemeter \r\n"
        for i, c in enumerate(chs):
            if c:
                r = self.get_frontend(i+1)
                hdr += "% Ch {i} - {} coupling, {} Ohm impedance, "
                "{} V range\r\n".format("AC" if r[2] else "DC",
                                        "50" if r[0] else "1M", "10"
                                        if r[1] else "1", i=i+1)

        hdr += "%"
        for i, c in enumerate(chs):
            if c:
                hdr += "{} Ch {i} bandwidth = {:.10e} (Hz)".format(
                    "," if ((ch1 and ch2) and i == 1)
                    else "", self.get_bandwidth(i+1), i=i+1)
        hdr += "\r\n"

        hdr += "% Acquisition rate: {:.10e} " \
            "Hz\r\n".format(self.get_samplerate())
        hdr += "% {} 10 MHz clock\r\n".format("External" if
                                              self._moku._get_actual_extclock()
                                              else "Internal")
        hdr += "% Acquired {}\r\n".format(_utils.formatted_timestamp())
        hdr += "% Time,"
        for i, c in enumerate(chs):
            if c:
                hdr += "{} Set frequency {i} (Hz), Frequency {i} (Hz)," \
                    " Phase {i} (cyc), I {i} (V), Q {i} " \
                    "(V)".format("," if ((ch1 and ch2) and i == 1)
                                 else "", i=i+1)

        hdr += "\r\n"

        return hdr

    def _get_fmtstr(self, ch1, ch2):
        fmtstr = "{t:.10e}"
        if ch1:
            fmtstr += ", {ch1[0]:.16e}, {ch1[1]:.16e}, {ch1[3]:.16e}," \
                " {ch1[4]:.10e}, {ch1[5]:.10e}"
        if ch2:
            fmtstr += ", {ch2[0]:.16e}, {ch2[1]:.16e}, {ch2[3]:.16e}," \
                " {ch2[4]:.10e}, {ch2[5]:.10e}"
        fmtstr += "\r\n"
        return fmtstr

    @needs_commit
    def set_defaults(self):
        super(Phasemeter, self).set_defaults()

        # Because we have to deal with a "frame" type instrument
        self.x_mode = _instrument.ROLL

        # Set basic configurations
        self.set_samplerate('medium')
        self.set_initfreq(1, 30e6)
        self.set_initfreq(2, 30e6)

        # Set output decimation gain compensation
        self.output_shift = math.log(self.output_decimation, 2)

        # Configure the analog front-end relays for impedance, voltage range
        # and input coupling.
        self.set_frontend(1, fiftyr=True, atten=True, ac=True)
        self.set_frontend(2, fiftyr=True, atten=True, ac=True)

        self.en_in_ch1 = True
        self.en_in_ch2 = True

    def _on_sync_regs(self):
        self.timestep = 1.0/(_PM_UPDATE_RATE/self.output_decimation)


_pm_reg_handlers = {
    'init_freq_ch1':
        ((REG_PM_INITF1_H, REG_PM_INITF1_L),
            to_reg_unsigned(0, 48, xform=lambda obj, f: f * _PM_FREQSCALE),
            from_reg_unsigned(0, 48, xform=lambda obj, f: f / _PM_FREQSCALE)),
    'init_freq_ch2':
        ((REG_PM_INITF2_H, REG_PM_INITF2_L),
            to_reg_unsigned(0, 48, xform=lambda obj, f: f * _PM_FREQSCALE),
            from_reg_unsigned(0, 48, xform=lambda obj, f: f / _PM_FREQSCALE)),
    'output_decimation':
        (REG_PM_OUTDEC,
            to_reg_unsigned(0, 17),
            from_reg_unsigned(0, 17)),
    'output_shift':
        (REG_PM_OUTSHIFT,
            to_reg_unsigned(17, 5),
            from_reg_unsigned(17, 5)),
    'bandwidth_ch1':
        (REG_PM_BW1,
            to_reg_signed(0, 5, xform=lambda obj, b: b),
            from_reg_signed(0, 5, xform=lambda obj, b: b)),
    'bandwidth_ch2':
        (REG_PM_BW2,
            to_reg_signed(0, 5, xform=lambda obj, b: b),
            from_reg_signed(0, 5, xform=lambda obj, b: b)),
    'autoacquire_ch1':
        (REG_PM_AUTOA1,
            to_reg_bool(0),
            from_reg_bool(0)),
    'autoacquire_ch2':
        (REG_PM_AUTOA2,
            to_reg_bool(0),
            from_reg_bool(0))
}
