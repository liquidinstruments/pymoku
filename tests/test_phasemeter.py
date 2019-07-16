import pytest

from pymoku.instruments import Phasemeter

try:
    from unittest.mock import ANY
except ImportError:
    from mock import ANY


@pytest.fixture
def dut(moku):
    i = Phasemeter()
    moku.deploy_instrument(i)
    moku.reset_mock()
    return i


def test_set_defaults(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_defaults()
    moku._write_regs.assert_called_with(ANY)


def test_gen_sinewave(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_sinewave(1, 1.0, 100e3)
    moku._write_regs.assert_called_with(ANY)


def test_gen_off(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_off()
    moku._write_regs.assert_called_with(ANY)


def test_set_samplerate(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_samplerate('fast')
    dut.get_samplerate()
    moku._write_regs.assert_called_with(ANY)


def test_set_initfreq(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_initfreq(1, 100e3)
    dut.get_initfreq(1)
    moku._write_regs.assert_called_with(ANY)


def test_set_bandwidth(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_bandwidth(1, 5e3)
    dut.get_bandwidth(1)
    moku._write_regs.assert_called_with(ANY)


def test_reacquire(dut, moku):
    '''
    TODO Default test
    '''
    dut.reacquire(1)
    moku._write_regs.assert_called_with(ANY)


def test_auto_acquire(dut, moku):
    '''
    TODO Default test
    '''
    dut.reacquire(1)
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('pm_out1_frequency', 100e3),
    ('pm_out2_frequency', 100e3),
    ('pm_out1_amplitude', 1.0),
    ('pm_out2_amplitude', 1.0),
    ('pm_out1_phase', 0.0),
    ('pm_out2_phase', 0.0),
    ('pm_out1_locked_out', 1),
    ('pm_out2_locked_out', 1),
    ('init_freq_ch1', 100e3),
    ('init_freq_ch2', 100e3),
    ('output_decimation', 6),
    ('output_shift', 2),
    ('bandwidth_ch1', 1),
    ('bandwidth_ch2', 1),
    ('autoacquire_ch1', 1),
    ('autoacquire_ch2', 0),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
