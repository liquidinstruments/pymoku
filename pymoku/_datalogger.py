from ._instrument import ADC_SMP_RATE
from ._instrument import CHN_BUFLEN
from ._instrument import ROLL
from ._instrument import needs_commit
from ._instrument import log
from ._instrument import to_reg_unsigned, from_reg_unsigned
from . import _stream_instrument
from . import _waveform_generator
from . import _utils

REG_DL_OUTSEL = 64
REG_DL_ACTL = 66
REG_DL_DECIMATION = 65

# REG_DL_OUTSEL constants
_DL_SOURCE_ADC1 = 0
_DL_SOURCE_ADC2 = 1
_DL_SOURCE_DAC1 = 2
_DL_SOURCE_DAC2 = 3
_DL_SOURCE_EXT = 4

_DL_LB_ROUND = 0
_DL_LB_CLIP = 1

_DL_AIN_DDS = 0
_DL_AIN_DECI = 1

_DL_ADC_SMPS = ADC_SMP_RATE
_DL_BUFLEN = CHN_BUFLEN
_DL_SCREEN_WIDTH = 1024
_DL_ROLL = ROLL

_DL_SAMPLERATE_MIN = 10             # Smp/s
_DL_SAMPLERATE_MAX = _DL_ADC_SMPS   # 500MSmp/s


class Datalogger(_stream_instrument.StreamBasedInstrument,
                 _waveform_generator.BasicWaveformGenerator):
    """ Datalogger instrument object.

    To run a new Datalogger instrument, this should be instantiated and
    deployed via a connected
    :any:`Moku` object using :any:`deploy_instrument`. Alternatively,
    a pre-configured instrument object
    can be obtained by discovering an already running Datalogger instrument
    on a Moku:Lab device via
    :any:`discover_instrument`.

    .. automethod:: pymoku.instruments.Datalogger.__init__

    .. attribute:: type
        :annotation: = "datalogger"

        Name of this instrument.

    """

    def __init__(self):
        """Create a new Datalogger instrument, ready to deploy to a Moku.
        """
        super(Datalogger, self).__init__()
        self._register_accessors(_dl_reg_handlers)

        self.id = 7
        self.type = "datalogger"
        self.calibration = None

        # TODO: Allow user to disable logging of either channel
        self.logname = "MokuDataloggerData"
        self.binstr = "<s32"
        self.procstr = ['', '']
        self.hdrstr = ''
        self.fmtstr = ''
        self.timestep = 1

    @needs_commit
    def set_defaults(self):
        # Force X-Mode to be "roll" for streaming
        super(Datalogger, self).set_defaults()
        self.x_mode = _DL_ROLL
        self.set_samplerate(1e3)
        self.framerate = 0

        # Disable the waveform generator by default
        # TODO: Disable without using a gen_ function
        self.gen_off()

        self.set_source(1, 'in1')
        self.set_source(2, 'in2')
        self.set_precision_mode(False)
        self._set_pause(False)

        self.set_frontend(1, fiftyr=True, atten=False, ac=False)
        self.set_frontend(2, fiftyr=True, atten=False, ac=False)
        self.en_in_ch1 = True
        self.en_in_ch2 = True

    @needs_commit
    def set_samplerate(self, samplerate):
        """ Manually set the sample rate of the instrument.

        This interface allows you to specify the rate at which data is sampled.

        .. note::
            The samplerate must be set to within the allowed range for your
            datalogging session type.
            See the Datalogger instrument tutorial for more details.

        :type samplerate: float; *0 < samplerate < 500Msmp/s*
        :param samplerate: Target samples per second. Will get rounded to the
        nearest unit.

        :raises ValueOutOfRangeException: if samplerate is out of range.
        """
        _utils.check_parameter_valid('range', samplerate,
                                     [_DL_SAMPLERATE_MIN, _DL_SAMPLERATE_MAX],
                                     'samplerate', 'Hz'
                                     )

        decimation = _DL_ADC_SMPS / float(samplerate)
        self.decimation_rate = decimation
        self.timestep = 1.0 / (_DL_ADC_SMPS / decimation)

    def get_samplerate(self):
        """ :return: The current instrument sample rate """
        if(self.decimation_rate == 0):
            log.warning("Decimation rate appears to be unset.")
            return _DL_ADC_SMPS
        return _DL_ADC_SMPS / float(self.decimation_rate)

    @needs_commit
    def set_precision_mode(self, state):
        """ Change aquisition mode between downsampling and decimation.
        Precision mode, a.k.a Decimation, samples at full rate and applies a
        low-pass filter to the data. This improves
        precision. Normal mode works by direct downsampling, throwing away
        points it doesn't need.

        :param state: Select Precision Mode
        :type state: bool

        :raises ValueError: if input parameter is invalid
        """
        _utils.check_parameter_valid('bool', state, desc='precision mode')
        self.ain_mode = _DL_AIN_DECI if state else _DL_AIN_DDS

    def is_precision_mode(self):
        return self.ain_mode is _DL_AIN_DECI

    @needs_commit
    def set_source(self, ch, source, lmode='round'):
        """ Sets the source of the channel data to either the analog input or
        internally looped-back digital output.

        This feature allows the user to capture the Waveform Generator outputs.

        :type ch:  int; {1,2}
        :param ch: Channel Number

        :type source: string, {'in1', 'in2', 'out1','out2', 'ext'}
        :param source: Where the specified channel should source data from
        (either the input or internally looped back output)

        :type lmode: string, {'clip','round'}
        :param lmode: DAC Loopback mode (ignored 'in' sources)

        :raises ValueOutOfRangeException: if the channel number is incorrect
        :raises ValueError: if any of the string parameters are incorrect
        """
        _str_to_lmode = {
            'round': _DL_LB_ROUND,
            'clip': _DL_LB_CLIP
        }
        _str_to_channel_data_source = {
            'in1': _DL_SOURCE_ADC1,
            'in2': _DL_SOURCE_ADC2,
            'out1': _DL_SOURCE_DAC1,
            'out2': _DL_SOURCE_DAC2,
            'ext': _DL_SOURCE_EXT
        }
        _utils.check_parameter_valid('set', ch, [1, 2], 'channel')
        source = _utils.str_to_val(_str_to_channel_data_source, source,
                                   'channel data source')
        lmode = _utils.str_to_val(_str_to_lmode, lmode, 'DAC loopback mode')
        if ch == 1:
            self.source_ch1 = source
            if source in [_DL_SOURCE_DAC1, _DL_SOURCE_DAC2]:
                self.loopback_mode_ch1 = lmode
        elif ch == 2:
            self.source_ch2 = source
            if source in [_DL_SOURCE_DAC1, _DL_SOURCE_DAC2]:
                self.loopback_mode_ch2 = lmode

    def _update_datalogger_params(self):
        scales = self._calculate_scales()

        samplerate = self.get_samplerate()
        self.timestep = 1.0 / samplerate

        # Use the new scales to decide on the processing string
        self.procstr[0] = "*{:.15f}".format(scales['scale_ch1'])
        self.procstr[1] = "*{:.15f}".format(scales['scale_ch2'])
        self.fmtstr = self._get_fmtstr(self.ch1, self.ch2)
        self.hdrstr = self._get_hdrstr(self.ch1, self.ch2)

    def _on_reg_sync(self):
        super(Datalogger, self)._on_reg_sync()
        if self.decimation_rate == 0:
            self.timestep = 1.0 / (_DL_ADC_SMPS)
        else:
            samplerate = _DL_ADC_SMPS / float(self.decimation_rate)
            self.timestep = 1.0 / samplerate

    def _get_hdrstr(self, ch1, ch2):
        chs = [ch1, ch2]

        hdr = "% Moku:Datalogger\r\n"
        for i, c in enumerate(chs):
            if c:
                r = self.get_frontend(i + 1)
                hdr += ("% Ch {i} - {} coupling, {} Ohm impedance, "
                        "{} V range\r\n").format("AC" if r[2] else "DC",
                                                 "50" if r[0] else "1M",
                                                 "10" if r[1] else "1",
                                                 i=i + 1)
        hdr += ("% Acquisition rate: {:.10e} Hz, "
                "{} mode\r\n").format(self.get_samplerate(),
                                      "Precision" if self.is_precision_mode()
                                      else "Normal"
                                      )
        hdr += "% {} 10 MHz clock\r\n".format(
            "External"
            if self._moku._get_actual_extclock()
            else "Internal"
        )
        hdr += "% Acquired {}\r\n".format(_utils.formatted_timestamp())
        hdr += "% Time"
        for i, c in enumerate(chs):
            if c:
                hdr += ", Ch {i} voltage (V)".format(i=i + 1)
        hdr += "\r\n"
        return hdr

    def _get_fmtstr(self, ch1, ch2):
        chs = [ch1, ch2]
        fmtstr = "{t:.10e}"
        for i, c in enumerate(chs):
            if c:
                fmtstr += ",{{ch{i}:.10e}}".format(i=i + 1)
        fmtstr += "\r\n"
        return fmtstr

    def _deci_gain(self):
        if self.decimation_rate == 0:
            return 1

        if self.decimation_rate < 2**20:
            return self.decimation_rate
        else:
            return self.decimation_rate / 2**10

    def _calculate_scales(self):
        g1, g2 = self._adc_gains()
        d1, d2 = self._dac_gains()

        gains = [g1, g2, d1, d2, 2.0**-11]

        l1 = self.loopback_mode_ch1
        l2 = self.loopback_mode_ch2

        s1 = self.source_ch1
        s2 = self.source_ch2

        scale_ch1 = gains[s1]
        scale_ch2 = gains[s2]

        if self.ain_mode == _DL_AIN_DECI:
            scale_ch1 /= self._deci_gain()
            scale_ch2 /= self._deci_gain()

        def _compute_total_scaling_factor(adc, dac, src, lmode):
            # Change scaling factor depending on the source type
            if src in [_DL_SOURCE_ADC1, _DL_SOURCE_ADC2]:
                scale = 1.0
            elif src in [_DL_SOURCE_DAC1, _DL_SOURCE_DAC2]:
                if(lmode == _DL_LB_CLIP):
                    scale = 1.0
                else:  # Rounding mode
                    scale = 16.0
            else:
                log.error("Invalid source type on channel.")
                return
            return scale

        # These are the combined scaling factors for both channel 1
        # and channel 2 raw data
        scale_ch1 *= _compute_total_scaling_factor(g1, d1, s1, l1)
        scale_ch2 *= _compute_total_scaling_factor(g2, d2, s2, l2)

        return {'scale_ch1': scale_ch1,
                'scale_ch2': scale_ch2,
                'gain_adc1': g1,
                'gain_adc2': g2,
                'gain_dac1': d1,
                'gain_dac2': d2,
                'source_ch1': s1,
                'source_ch2': s2,
                'gain_loopback1': l1,
                'gain_loopback2': l2
                }


_dl_reg_handlers = {
    'source_ch1':
        (REG_DL_OUTSEL,
            to_reg_unsigned(0, 8, allow_set=[_DL_SOURCE_ADC1,
                                             _DL_SOURCE_ADC2,
                                             _DL_SOURCE_DAC1,
                                             _DL_SOURCE_DAC2,
                                             _DL_SOURCE_EXT]),
            from_reg_unsigned(0, 8)),

    'source_ch2':
        (REG_DL_OUTSEL,
            to_reg_unsigned(8, 8, allow_set=[_DL_SOURCE_ADC1,
                                             _DL_SOURCE_ADC2,
                                             _DL_SOURCE_DAC1,
                                             _DL_SOURCE_DAC2,
                                             _DL_SOURCE_EXT]),
            from_reg_unsigned(8, 8)),

    'loopback_mode_ch1':
        (REG_DL_ACTL,
            to_reg_unsigned(0, 1, allow_set=[_DL_LB_CLIP,
                                             _DL_LB_ROUND]),
            from_reg_unsigned(0, 1)),
    'loopback_mode_ch2':
        (REG_DL_ACTL,
            to_reg_unsigned(1, 1, allow_set=[_DL_LB_CLIP,
                                             _DL_LB_ROUND]),
            from_reg_unsigned(1, 1)),
    'ain_mode':
        (REG_DL_ACTL,
            to_reg_unsigned(16, 2, allow_set=[_DL_AIN_DDS,
                                              _DL_AIN_DECI]),
            from_reg_unsigned(16, 2)),
    'decimation_rate':
        (REG_DL_DECIMATION,
            to_reg_unsigned(0, 32),
            from_reg_unsigned(0, 32))
}
