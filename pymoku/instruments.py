import sys

from . import _instrument
from . import _oscilloscope
from . import _waveform_generator
from . import _phasemeter
from . import _specan
from . import _lockinamp
from . import _datalogger
from . import _frequency_response_analyzer
from . import _bode_analyzer
from . import _arbwavegen
from . import _stream_instrument
from . import _frame_instrument
from . import _input_instrument
from . import _pid_controller
from . import _iirfilterbox
from . import _firfilter
from . import _laser_lock_box
''' Preferred import point. Aggregates the separate instruments and helper classes
    to flatten the import heirarchy (e.g. pymoku.instruments.Oscilloscope rather
    than pymoku.instruments._oscilloscope.Oscilloscope)
'''

InstrumentData = _frame_instrument.InstrumentData
VoltsData = _oscilloscope.VoltsData
SpectrumData = _specan.SpectrumData
FRAData = _frequency_response_analyzer.FRAData

MokuInstrument = _instrument.MokuInstrument

Oscilloscope = _oscilloscope.Oscilloscope
WaveformGenerator = _waveform_generator.WaveformGenerator
Phasemeter = _phasemeter.Phasemeter
SpectrumAnalyzer = _specan.SpectrumAnalyzer
LockInAmp = _lockinamp.LockInAmp
Datalogger = _datalogger.Datalogger
BodeAnalyzer = _bode_analyzer.BodeAnalyzer
FrequencyResponseAnalyzer = _frequency_response_analyzer.FrequencyResponseAnalyzer
PIDController = _pid_controller.PIDController
ArbitraryWaveGen = _arbwavegen.ArbitraryWaveGen
IIRFilterBox = _iirfilterbox.IIRFilterBox
FIRFilter = _firfilter.FIRFilter
LaserLockBox = _laser_lock_box.LaserLockBox

id_table = {
	1: Oscilloscope,
	2: SpectrumAnalyzer,
	3: Phasemeter,
	4: WaveformGenerator,
	5: PIDController,
	6: IIRFilterBox,
	7: Datalogger,
	8: LockInAmp,
	9: FrequencyResponseAnalyzer,
	10: FIRFilter,
	11: None,
	12: None,
	13: None,
	14: None,
	15: ArbitraryWaveGen,
	16: LaserLockBox
}
