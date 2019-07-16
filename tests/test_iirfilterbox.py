import pytest

from pymoku.instruments import IIRFilterBox
from pymoku import _iirfilterbox

try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY

filt_coeff = [[1.0],
              [1.0, 0.64, -1.02, 0.646, -1.637, 0.898],
              [1.0, 0.51, -0.75, 0.518, -1.403, 0.679],
              [1.0, 0.31, -0.31, 0.314, -1.082, 0.410],
              [1.0, 0.13, 0.122, 0.130, -0.795, 0.178]]


@pytest.fixture
def dut(moku):
    with patch(
               'pymoku._frame_instrument.'
               'FrameBasedInstrument._set_running'):
        i = IIRFilterBox()
        moku.deploy_instrument(i)
        moku.reset_mock()
        return i


def test_set_defaults(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_defaults()
    moku._write_regs.assert_called_with(ANY)


def test_set_control_matrix(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_control_matrix(1, 1, 1)
    moku._write_regs.assert_called_with(ANY)


def test_set_filter(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_filter(1, 'high', filt_coeff)
    moku._write_regs.assert_called_with(ANY)


def test_disable_output(dut, moku):
    '''
    TODO Default test
    '''
    dut.disable_output(1)
    moku._write_regs.assert_called_with(ANY)


def test_set_gains_offsets(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_gains_offsets(1, 1.0, 1.0, 0, 0)
    moku._write_regs.assert_called_with(ANY)


def test_set_monitor(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_monitor('a', 'adc1')
    moku._write_regs.assert_called_with(ANY)


def test_set_trigger(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_trigger('in1', 'rising', 1.0, None, None, 10e-3, False, 'auto')
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('mon1_source', 1),
    ('mon2_source', 1),
    ('input_en1', True),
    ('input_en2', True),
    ('output_en1', True),
    ('output_en2', True),
    ('matrixscale_ch1_ch1', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
    ('matrixscale_ch1_ch2', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
    ('matrixscale_ch2_ch1', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
    ('matrixscale_ch2_ch2', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
    ('ch1_sampling_freq', 1),
    ('ch2_sampling_freq', 1),
    ('filter_reset', 1),
    ('input_scale1', 2**5),
    ('input_scale2', 2**5),
    ('output_scale1', 2**5),
    ('output_scale2', 2**5),
    ('input_offset1', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
    ('input_offset2', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
    ('output_offset1', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
    ('output_offset2', 1/_iirfilterbox._ADC_DEFAULT_CALIBRATION),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
