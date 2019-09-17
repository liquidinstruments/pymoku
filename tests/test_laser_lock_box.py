import pytest

from pymoku.instruments import LaserLockBox

try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY

filt_coeff = [[1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
              [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]]


@pytest.fixture
def dut(moku):
    with patch(
            'pymoku._frame_instrument.'
            'FrameBasedInstrument._set_running'):
        i = LaserLockBox()
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
    dut.set_input_gain(0)
    moku._write_regs.assert_called_with(ANY)


def test_set_custom_filter(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_custom_filter(filt_coeff)
    moku._write_regs.assert_called_with(ANY)


def test_set_output_range(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_output_range(1, 0.1, 0.1)
    moku._write_regs.assert_called_with(ANY)


def test_set_offsets(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_offsets('out1', 1.0)
    moku._write_regs.assert_called_with(ANY)


def test_set_pid_by_gain(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_pid_by_gain(1, 1, 1, 0, 0, None, None, True)
    moku._write_regs.assert_called_with(ANY)


def test_set_pid_by_freq(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_pid_by_freq(1, 1, None, None, None, None, True)
    moku._write_regs.assert_called_with(ANY)


def test_set_pid_enables(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_pid_enables(1, True)
    moku._write_regs.assert_called_with(ANY)


def test_set_output_enables(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_output_enables(1, True)
    moku._write_regs.assert_called_with(ANY)


def test_set_channel_pid_enables(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_channel_pid_enables(1, True)
    moku._write_regs.assert_called_with(ANY)


def test_set_local_oscillator(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_local_oscillator(0, 0, 'internal', True)
    moku._write_regs.assert_called_with(ANY)


def test_set_aux_sine(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_aux_sine(2, 0, 0, False, 'out2')
    moku._write_regs.assert_called_with(ANY)


def test_set_scan(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_scan(2, 0, 0, 'triangle', 'out1')
    moku._write_regs.assert_called_with(ANY)


def test_set_trigger(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_trigger('in1', 'rising', 1.0,
                    None, None, 10e-2, False, 'auto', False)
    moku._write_regs.assert_called_with(ANY)


def test_set_monitor(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_monitor('a', 'pid_fast')
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('_fast_scale', 1.0 / 2 ** 14),
    ('_slow_scale', 1.0 / 2 ** 14),
    ('_aux_scale', 1 / 2 ** 14),
    ('scan_amplitude', 1 / 2 ** 14),
    ('fast_scan_enable', 1),
    ('slow_scan_enable', 1),
    ('lo_phase_offset', 1),
    ('aux_phase_offset', 1),
    ('fast_offset', 1 / 2 ** 15),
    ('output_offset_ch1', 1 / 2 ** 15),
    ('output_offset_ch2', 1 / 2 ** 15),
    ('monitor_select0', 1),
    ('monitor_select1', 1),
    ('input_gain_select', 1),
    ('MuxLOPhase', 1),
    ('MuxLOSignal', 1),
    ('MuxAuxPhase', 1),
    ('trig_aux', 1),
    ('cond_trig', 1),
    ('cliprange_lower_ch1', 1 / 2 ** 15),
    ('cliprange_upper_ch1', 1 / 2 ** 15),
    ('cliprange_lower_ch2', 1 / 2 ** 15),
    ('cliprange_upper_ch2', 1 / 2 ** 15),
    ('fast_aux_enable', 1),
    ('slow_aux_enable', 1),
    ('fast_channel_en', 1),
    ('slow_channel_en', 1),
    ('out1_en', 1),
    ('out2_en', 1),
    ('input1_light', 1),
    ('input2_light', 1),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
