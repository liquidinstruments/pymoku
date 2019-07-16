import pytest

from pymoku.instruments import SpectrumAnalyzer
from pymoku import _specan

try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY


@pytest.fixture
def dut(moku):
    with patch('pymoku._frame_instrument.FrameBasedInstrument._set_running'):
        i = SpectrumAnalyzer()
        moku.deploy_instrument(i)
        moku.reset_mock()
        return i


def test_set_span(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_span(0, 100e6)
    moku._write_regs.assert_called_with(ANY)


def test_set_rbw(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_rbw(100e3)
    dut.get_rbw()
    moku._write_regs.assert_called_with(ANY)


def test_set_window(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_window('flattop')
    moku._write_regs.assert_called_with(ANY)


def test_set_dbmscale(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_dbmscale(True)
    moku._write_regs.assert_called_with(ANY)


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
    dut.gen_sinewave(1, 1.0, 100e6, True)
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('demod', 10),
    ('dec_enable', True),
    ('dec_cic2', 4),
    ('bs_cic2', 4),
    ('dec_cic3', 1),
    ('bs_cic3', 1),
    ('dec_iir', 4),
    ('rbw_ratio', 50),
    ('window', _specan._SA_WIN_NONE),
    ('ref_level', 6),
    ('gain_sos0', 2802),
    ('a1_sos0', -117798),
    ('a2_sos0', 56960),
    ('b1_sos0', -21172),
    ('gain_sos1', 1858),
    ('a1_sos1', -105542),
    ('a2_sos1', 44268),
    ('b1_sos1', 19380),
    ('gain_sos2', 1118),
    ('a1_sos2', -99312),
    ('a2_sos2', 37840),
    ('b1_sos2', 107358),
    ('tr1_amp', 0),
    ('tr1_start', 100e6),
    ('tr1_stop', 0),
    ('tr1_incr', 0),
    ('tr2_amp', 0),
    ('tr2_start', 100e6),
    ('tr2_stop', 0),
    ('tr2_incr', 0)
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
