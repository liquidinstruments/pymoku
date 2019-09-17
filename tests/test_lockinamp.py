import pytest

from pymoku.instruments import LockInAmp
from pymoku import _lockinamp

try:
    from unittest.mock import ANY
except ImportError:
    from mock import ANY


@pytest.fixture
def dut(moku):
    i = LockInAmp()
    moku.deploy_instrument(i)
    moku.reset_mock()
    return i


def test_set_defaults(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_defaults()
    moku._write_regs.assert_called_with(ANY)


def test_set_input_gain(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_input_gain()
    moku._write_regs.assert_called_with(ANY)


def test_set_outputs(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_outputs('x', 'sine')
    moku._write_regs.assert_called_with(ANY)


def test_set_pid_by_frequency(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_pid_by_frequency('main')
    moku._write_regs.assert_called_with(ANY)


def test_set_pid_by_gain(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_pid_by_gain('main', 1.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_gain(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_gain('main', 10.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_demodulation(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_demodulation('external')
    moku._write_regs.assert_called_with(ANY)


def test_set_filter(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_filter(100e3, 2)
    moku._write_regs.assert_called_with(ANY)


def test_set_lo_output(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_lo_output(1.0, 100e3, 0.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_monitor(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_monitor('A', 'in1')
    moku._write_regs.assert_called_with(ANY)


def test_set_trigger(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_trigger('in1', 'rising', 0.0)
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('lpf_en', True),
    ('ch1_pid1_en', True),
    ('ch1_pid1_ien', True),
    ('ch1_pid1_pen', True),
    ('ch1_out_en', True),
    ('ch2_out_en', True),
    ('lpf_den', True),
    ('pid1_ch1_den', True),
    ('ch1_pid1_bypass', True),
    ('ch1_signal_en', True),
    ('ch1_pid1_int_dc_pole', True),
    ('ch2_signal_en', True),
    ('ext_demod', True),
    ('lo_PLL', True),
    ('filt_bypass1', True),
    ('filt_bypass2', True),
    ('pid_ch_select', True),
    ('aux_select', 0),
    ('input_gain_select', 1),
    ('ch1_pid1_in_offset', 0.0),
    ('ch1_pid1_out_offset', 0.0),
    ('main_offset', 0.0),
    ('lpf_pidgain', 1.0),
    ('ch1_pid1_pidgain', 1.0),
    ('lpf_int_i_gain', 1.0),
    ('ch1_pid1_int_i_gain', 1.0),
    ('lpf_int_ifb_gain', 1.0),
    ('ch1_pid1_int_ifb_gain', 1.0),
    ('lpf_int_p_gain', 1.0),
    ('ch1_pid1_int_p_gain', 1.0),
    ('gainstage_gain', 1.0),
    ('ch1_pid1_diff_p_gain', 1.0),
    ('ch1_pid1_diff_i_gain', 1.0),
    ('ch1_pid1_diff_ifb_gain', 1.0),
    ('frequency_demod', 100e3),
    ('phase_demod', 45.0),
    ('lo_frequency', 100e3),
    ('lo_phase', 0.0),
    ('monitor_select0', _lockinamp._LIA_MON_IN1),
    ('monitor_select1', _lockinamp._LIA_MON_IN1),
    ('sineout_amp', 1.0),
    ('aux_offset', 0.0),
    ('input_gain', 1.0),
    ('bandwidth', 4),
    ('lo_PLL_reset', False),
    ('lo_reacquire', False),
    ('pid_sig_select', 1),
    ('gain_sig_select', 1),
    ('output_decimation', 1),
    ('output_shift', 1),
    ('autoacquire', True),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
