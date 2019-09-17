import pytest

from pymoku.instruments import Datalogger
from pymoku import _datalogger

try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY


@pytest.fixture
def dut(moku):
    with patch('pymoku._stream_instrument.StreamBasedInstrument._set_running'):
        i = Datalogger()
        moku.deploy_instrument(i)
        moku.reset_mock()
        return i


def test_set_samplerate(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_samplerate(1e3)
    dut.get_samplerate()
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


def test_set_source(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_source(1, 'in1')
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('source_ch1', _datalogger._DL_SOURCE_ADC1),
    ('source_ch2', _datalogger._DL_SOURCE_ADC2),
    ('loopback_mode_ch1', _datalogger._DL_LB_CLIP),
    ('loopback_mode_ch2', _datalogger._DL_LB_ROUND),
    ('ain_mode', _datalogger._DL_AIN_DECI),
    ('decimation_rate', 0)
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
