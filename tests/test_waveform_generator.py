import pytest

from pymoku.instruments import WaveformGenerator

try:
    from unittest.mock import ANY
except ImportError:
    from mock import ANY


@pytest.fixture
def dut(moku):
    i = WaveformGenerator()
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


def test_gen_squarewave(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_squarewave(1, 1.0, 100e3)
    moku._write_regs.assert_called_with(ANY)


def test_gen_rampwave(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_rampwave(1, 1.0, 100e3)
    moku._write_regs.assert_called_with(ANY)


def test_gen_off(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_off()
    moku._write_regs.assert_called_with(ANY)


def test_set_trigger(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_trigger(1, 'sweep', sweep_start_freq=10.0, sweep_end_freq=100.0)
    moku._write_regs.assert_called_with(ANY)


def test_gen_modulate_off(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_modulate_off()
    moku._write_regs.assert_called_with(ANY)


def test_gen_trigger_off(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_trigger_off()
    moku._write_regs.assert_called_with(ANY)


def test_set_modulate_trig_off(dut, moku):
    '''
    TODO Default test
    '''
    dut.set_modulate_trig_off()
    moku._write_regs.assert_called_with(ANY)


def test_gen_modulate(dut, moku):
    '''
    TODO Default test
    '''
    dut.gen_modulate(1, 'amplitude', 'adc1', 0.5)
    moku._write_regs.assert_called_with(ANY)


@pytest.mark.parametrize('attr, value', [
    ('adc1_statuslight', 0),
    ('amod_enable_ch1', 0),
    ('fmod_enable_ch1', 0),
    ('pmod_enable_ch1', 0),
    ('sweep_enable_ch1', 0),
    ('reverse_sweep_ch1', 0),
    ('mod_source_ch1', 0),
    ('atten_compensate_ch1', 0),
    ('trig_source_ch1', 0),
    ('range_shift_ch1', 0),
    ('sine_trigdly_ch1', 0),
    ('phasedly_en_ch1', 0),
    ('trig_sweep_mode_ch1', 0),
    ('gate_mode_ch1', 0),
    ('mod_depth_ch1', 0),
    ('gate_thresh_ch1', 0),
    ('enable_ch1', 0),
    ('waveform_type_ch1', 0),
    ('amplitude_ch1', 1.0),
    ('offset_ch1', 0.0),
    ('t0_ch1', 1.0),
    ('t1_ch1', 1.0),
    ('t2_ch1', 1.0),
    ('riserate_ch1', 1.0),
    ('fallrate_ch1', 1.0),
    ('enable_reset_ch1', 0),
    ('phase_dly_ch1', 0),
    ('adc2_statuslight', 0),
    ('amod_enable_ch2', 0),
    ('fmod_enable_ch2', 0),
    ('pmod_enable_ch2', 0),
    ('sweep_enable_ch2', 0),
    ('reverse_sweep_ch2', 0),
    ('mod_source_ch2', 0),
    ('atten_compensate_ch2', 0),
    ('trig_source_ch2', 0),
    ('range_shift_ch2', 0),
    ('sine_trigdly_ch2', 0),
    ('phasedly_en_ch2', 0),
    ('trig_sweep_mode_ch2', 0),
    ('gate_mode_ch2', 0),
    ('mod_depth_ch2', 0),
    ('gate_thresh_ch2', 0),
    ('enable_ch2', 0),
    ('waveform_type_ch2', 0),
    ('amplitude_ch2', 1.0),
    ('offset_ch2', 0.0),
    ('t0_ch2', 1.0),
    ('t1_ch2', 1.0),
    ('t2_ch2', 1.0),
    ('riserate_ch2', 1.0),
    ('fallrate_ch2', 1.0),
    ('enable_reset_ch2', 1),
    ('phase_dly_ch2', 1),
])
def test_attributes(dut, moku, attr, value):
    '''
    TODO Default test
    '''
    setattr(dut, attr, value)
    dut.commit()
    moku._write_regs.assert_called_with(ANY)
