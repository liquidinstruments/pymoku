import pytest

from pymoku.instruments import FrequencyResponseAnalyzer

try:
	from unittest.mock import patch, ANY
except ImportError:
	from mock import patch, ANY


@pytest.fixture
def dut(moku):
	with patch('pymoku._frame_instrument.FrameBasedInstrument._set_running') as fbi:
		i = FrequencyResponseAnalyzer()
		moku.deploy_instrument(i)
		moku.reset_mock()
		return i


def test_set_input_range(dut, moku):
	'''
	TODO Default test
	'''
	dut.set_input_range(1, 10)
	moku._write_regs.assert_called_with(ANY)


def test_set_sweep(dut, moku):
	'''
	TODO Default test
	'''
	dut.set_sweep()
	moku._write_regs.assert_called_with(ANY)


def test_set_harmonic_multiplier(dut, moku):
	'''
	TODO Default test
	'''
	dut.set_harmonic_multiplier(1)
	moku._write_regs.assert_called_with(ANY)


def test_set_ch_phase(dut, moku):
	'''
	TODO Default test
	'''
	dut.set_ch_phase(1, 0.0)
	moku._write_regs.assert_called_with(ANY)


def test_set_defaults(dut, moku):
	'''
	TODO Default test
	'''
	dut.set_defaults()
	moku._write_regs.assert_called_with(ANY)


def test_set_xmode(dut, moku):
	'''
	TODO Default test
	'''
	dut.set_xmode('sweep')
	moku._write_regs.assert_called_with(ANY)


def test_gen_off(dut, moku):
	'''
	TODO Default test
	'''
	dut.gen_off(1)
	moku._write_regs.assert_called_with(ANY)


def test_enable_offset(dut, moku):
	'''
	TODO Default test
	'''
	dut.enable_offset(1, True)
	moku._write_regs.assert_called_with(ANY)


def test_enable_amplitude(dut, moku):
	'''
	TODO Default test
	'''
	dut.enable_amplitude(1, True)
	moku._write_regs.assert_called_with(ANY)


def test_set_output(dut, moku):
	'''
	TODO Default test
	'''
	dut.set_output(1, 0.5)
	moku._write_regs.assert_called_with(ANY)


def test_stop_sweep(dut, moku):
	'''
	TODO Default test
	'''
	dut.stop_sweep()
	moku._write_regs.assert_called_with(ANY)


def test_start_sweep(dut, moku):
	'''
	TODO Default test
	'''
	dut.start_sweep(True)
	moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
	('loop_sweep', True),
	('single_sweep', False),
	('sweep_reset', True),
	('channel1_en', True),
	('channel2_en', True),
	('adc1_en', False),
	('adc2_en', False),
	('dac1_en', False),
	('dac2_en', False),
	('sweep_freq_min', 10),
	('sweep_freq_delta', 34408047),
	('log_en', False),
	('sweep_length', 512),
	('settling_time', 1e-6),
	('averaging_time', 1e-6),
	('sweep_amplitude_ch1', 0.5),
	('sweep_amplitude_ch2', 0.5),
	('sweep_offset_ch1', 0),
	('sweep_offset_ch2', 0),
	('settling_cycles', 1),
	('averaging_cycles', 1),
	('ch1_harmonic_mult', 1),
	('ch2_harmonic_mult', 1),
	('ch1_meas_phase', 0),
	('ch2_meas_phase', 0),
])
def test_attributes(dut, moku, attr, value):
	'''
	TODO Default test
	'''
	setattr(dut, attr, value)
	dut.commit()
	moku._write_regs.assert_called_with(ANY)
