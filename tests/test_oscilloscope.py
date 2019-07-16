import pytest

from pymoku.instruments import Oscilloscope
from pymoku import _oscilloscope

try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY


@pytest.fixture
def dut(moku):
    with patch('pymoku._frame_instrument.FrameBasedInstrument._set_running'):
        i = Oscilloscope()
        moku.deploy_instrument(i)
        moku.reset_mock()
        return i


def test_set_timebase(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_timebase(-1.0, 1.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_samplerate(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_samplerate(100e3)
    dut.get_samplerate()
    moku._write_regs.assert_called_with(ANY)


def test_set_xmode(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_xmode('roll')
    moku._write_regs.assert_called_with(ANY)


def test_set_precision_mode(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_precision_mode(True)
    dut.is_precision_mode()
    moku._write_regs.assert_called_with(ANY)


def test_set_defaults(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_defaults()
    moku._write_regs.assert_called_with(ANY)


def test_set_trigger(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_trigger('in1', 'rising', 0.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_source(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_source(1, 'in1', 0.0)
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('source_ch1', _oscilloscope._OSC_SOURCE_CH1),
    ('source_ch2', _oscilloscope._OSC_SOURCE_CH1),
    ('trig_ch', _oscilloscope._OSC_SOURCE_CH1),
    ('hf_reject', True),
    ('loopback_mode_ch1', _oscilloscope._OSC_LB_CLIP),
    ('loopback_mode_ch2', _oscilloscope._OSC_LB_CLIP),
    ('ain_mode', _oscilloscope._OSC_AIN_DDS),
    ('trig_precision', True),
    ('decimation_rate', 1),
    ('auto_timer', 1.0),
    ('auto_holdoff', 0),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
