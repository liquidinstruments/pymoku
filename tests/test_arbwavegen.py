import pytest

from pymoku.instruments import ArbitraryWaveGen
from pymoku import _arbwavegen

try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY


@pytest.fixture
def dut(moku):
    with patch('pymoku._frame_instrument.FrameBasedInstrument._set_running'):
        i = ArbitraryWaveGen()
        moku.deploy_instrument(i)
        moku.reset_mock()
        return i


def test_set_defaults(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_defaults()
    moku._write_regs.assert_called_with(ANY)


def test_write_lut(dut, moku):
    '''
    TODO Default test
    '''
    dut.write_lut(1, [x / 100.0 for x in range(100)])
    moku._write_regs.assert_called_with(ANY)


def test_gen_waveform(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_waveform(1, 10e2, 1.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_waveform_trigger(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_waveform_trigger(1, 'in1', 'rising', 0.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_waveform_trigger_output(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_waveform_trigger_output(1)
    moku._write_regs.assert_called_with(ANY)


def test_sync_phase(dut, moku):
    '''
    TODO Default test
    '''
    dut.sync_phase()
    moku._write_regs.assert_called_with(ANY)


def test_reset_phase(dut, moku):
    '''
    TODO Default test
    '''
    dut.reset_phase(1)
    moku._write_regs.assert_called_with(ANY)


def test_gen_off(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_off()
    moku._write_regs.assert_called_with(ANY)


def test_enable_output(dut, moku):
    '''
    TODO Default test
    '''
    dut.enable_output()
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('enable1', True),
    ('phase_rst1', True),
    ('mode1', _arbwavegen._ARB_MODE_125),
    ('interpolation1', True),
    ('trig_source1', _arbwavegen._ARB_TRIG_SRC_CH1,),
    ('lut_length1', 1000),
    ('dead_value1', 0.0),
    ('amplitude1', 1.0),
    ('offset1', 0.0),
    ('enable2', True),
    ('phase_rst2', True),
    ('mode2', _arbwavegen._ARB_MODE_125),
    ('interpolation2', True),
    ('trig_source2', _arbwavegen._ARB_TRIG_SRC_CH1),
    ('lut_length2', 1000),
    ('dead_value2', 0.0),
    ('amplitude2', 1.0),
    ('offset2', 0.0),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
