import pytest

from pymoku.instruments import PIDController


try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY


@pytest.fixture
def dut(moku):
    with patch('pymoku._frame_instrument.FrameBasedInstrument._set_running'):
        i = PIDController()
        moku.deploy_instrument(i)
        moku.reset_mock()
        return i


def test_set_defaults(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_defaults()
    moku._write_regs.assert_called_with(ANY)


def test_set_by_frequency(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_by_frequency(1)
    moku._write_regs.assert_called_with(ANY)


def test_set_by_gain(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_by_gain(1, 1)
    moku._write_regs.assert_called_with(ANY)


def test_set_control_matrix(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_control_matrix(1, 1, 1)
    moku._write_regs.assert_called_with(ANY)


def test_set_trigger(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_trigger('a', 'rising', 0, mode='auto')
    moku._write_regs.assert_called_with(ANY)


def test_set_monitor(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_monitor('a', 'in1')
    moku._write_regs.assert_called_with(ANY)


def test_enable_output(dut, moku):
    '''
    TODO Default test
    '''
    dut.enable_output()
    moku._write_regs.assert_called_with(ANY)


def test_enable_input(dut, moku):
    '''
    TODO Default test
    '''
    dut.enable_input()
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('ch1_pid1_bypass', True),
    ('ch1_pid2_bypass', True),
    ('ch1_pid1_int_dc_pole', True),
    ('ch1_pid2_int_dc_pole', True),
    ('ch2_pid1_bypass', True),
    ('ch2_pid2_bypass', True),
    ('ch2_pid1_int_dc_pole', True),
    ('ch2_pid2_int_dc_pole', True),
    ('ch1_pid1_en', True),
    ('ch1_pid2_en', True),
    ('ch2_pid1_en', True),
    ('ch2_pid2_en', True),
    ('ch1_pid1_ien', True),
    ('ch1_pid2_ien', True),
    ('ch2_pid1_ien', True),
    ('ch2_pid2_ien', True),
    ('ch1_pid1_pen', True),
    ('ch1_pid2_pen', True),
    ('ch2_pid1_pen', True),
    ('ch2_pid2_pen', True),
    ('ch1_pid1_den', True),
    ('ch1_pid2_den', True),
    ('ch2_pid1_den', True),
    ('ch2_pid2_den', True),
    ('ch1_output_en', True),
    ('ch2_output_en', True),
    ('ch1_input_en', True),
    ('ch2_input_en', True),
    ('ch1_input_light', True),
    ('ch2_input_light', True),
    ('ch1_ch1_gain', 1),
    ('ch1_ch2_gain', 1),
    ('ch2_ch1_gain', 1),
    ('ch2_ch2_gain', 1),
    ('ch1_pid1_in_offset', 0),
    ('ch1_pid2_in_offset', 0),
    ('ch1_pid1_out_offset', 0),
    ('ch1_pid2_out_offset', 0),
    ('ch1_pid1_pidgain', 0),
    ('ch1_pid2_pidgain', 0),
    ('ch1_pid1_int_i_gain', 0),
    ('ch1_pid2_int_i_gain', 0),
    ('ch1_pid1_int_ifb_gain', 0),
    ('ch1_pid2_int_ifb_gain', 0),
    ('ch1_pid1_int_p_gain', 0),
    ('ch1_pid2_int_p_gain', 0),
    ('ch1_pid1_diff_p_gain', 0),
    ('ch1_pid1_diff_i_gain', 0),
    ('ch1_pid1_diff_ifb_gain', 0),
    ('ch2_pid1_in_offset', 0),
    ('ch2_pid2_in_offset', 0),
    ('ch2_pid1_out_offset', 0),
    ('ch2_pid2_out_offset', 0),
    ('ch2_pid1_pidgain', 0),
    ('ch2_pid2_pidgain', 0),
    ('ch2_pid1_int_i_gain', 0),
    ('ch2_pid2_int_i_gain', 0),
    ('ch2_pid1_int_ifb_gain', 0),
    ('ch2_pid2_int_ifb_gain', 0),
    ('ch2_pid1_int_p_gain', 0),
    ('ch2_pid2_int_p_gain', 0),
    ('ch2_pid1_diff_p_gain', 0),
    ('ch2_pid1_diff_i_gain', 0),
    ('ch2_pid1_diff_ifb_gain', 0),
    ('mon1_source', 0),
    ('mon2_source', 0),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
