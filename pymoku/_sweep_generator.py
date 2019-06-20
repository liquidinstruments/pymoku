from ._instrument import *
from . import _utils

class SweepGenerator(object):
	_REG_CONFIG = 0
	_REG_START_LSB = 1
	_REG_START_MSB = 2
	_REG_STOP_LSB = 3
	_REG_STOP_MSB = 4
	_REG_STEP_LSB = 5
	_REG_STEP_MSB = 6
	_REG_DURATION_LSB = 7
	_REG_DURATION_MSB = 8

	WAVE_TYPE_SINGLE = 0
	WAVE_TYPE_UPDOWN = 1
	WAVE_TYPE_SAWTOOTH = 2
	WAVE_TYPE_TRIANGLE = 3

	def __init__(self, instr, reg_base):
		self._instr = instr
		self.reg_base = reg_base

	@property
	def waveform(self):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		return self._instr._accessor_get(r, from_reg_unsigned(0, 2))

	@waveform.setter
	def waveform(self, value):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		self._instr._accessor_set(r, to_reg_unsigned(0, 2,
			allow_set=[SweepGenerator.WAVE_TYPE_SINGLE,
			           SweepGenerator.WAVE_TYPE_UPDOWN,
			           SweepGenerator.WAVE_TYPE_SAWTOOTH,
			           SweepGenerator.WAVE_TYPE_TRIANGLE]), value)

	@property
	def direction(self):
		r1 = self.reg_base + SweepGenerator._REG_CONFIG
		return self._instr._accessor_get(r, from_reg_unsigned(5, 1))

	@direction.setter
	def direction(self, value):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		self._instr._accessor_set(r, to_reg_unsigned(5, 1,
			allow_set=[0,1]), value)

	@property
	def logsweep(self):
		r1 = self.reg_base + SweepGenerator._REG_CONFIG
		return self._instr._accessor_get(r, from_reg_unsigned(6, 1))

	@logsweep.setter
	def logsweep(self, value):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		self._instr._accessor_set(r, to_reg_unsigned(6, 1,
			allow_set=[0,1]), value)

	@property
	def start(self):
		r1 = self.reg_base + SweepGenerator._REG_START_LSB
		r2 = self.reg_base + SweepGenerator._REG_START_MSB
		return self._instr._accessor_get((r2, r1), from_reg_unsigned(0, 64))

	@start.setter
	def start(self, value):
		r1 = self.reg_base + SweepGenerator._REG_START_LSB
		r2 = self.reg_base + SweepGenerator._REG_START_MSB
		self._instr._accessor_set((r2, r1), to_reg_unsigned(0, 64), value)

	@property
	def stop(self):
		r1 = self.reg_base + SweepGenerator._REG_STOP_LSB
		r2 = self.reg_base + SweepGenerator._REG_STOP_MSB
		return self._instr._accessor_get((r2, r1), from_reg_unsigned(0, 64))

	@stop.setter
	def stop(self, value):
		r1 = self.reg_base + SweepGenerator._REG_STOP_LSB
		r2 = self.reg_base + SweepGenerator._REG_STOP_MSB
		self._instr._accessor_set((r2, r1), to_reg_unsigned(0, 64), value)

	@property
	def step(self):
		r1 = self.reg_base + SweepGenerator._REG_STEP_LSB
		r2 = self.reg_base + SweepGenerator._REG_STEP_MSB
		return self._instr._accessor_get((r2, r1), from_reg_unsigned(0, 64))

	@step.setter
	def step(self, value):
		r1 = self.reg_base + SweepGenerator._REG_STEP_LSB
		r2 = self.reg_base + SweepGenerator._REG_STEP_MSB
		self._instr._accessor_set((r2, r1), to_reg_unsigned(0, 64), value)

	@property
	def duration(self):
		r1 = self.reg_base + SweepGenerator._REG_DURATION_LSB
		r2 = self.reg_base + SweepGenerator._REG_DURATION_MSB
		return self._instr._accessor_get((r2, r1), from_reg_unsigned(0, 64))

	@duration.setter
	def duration(self, value):
		r1 = self.reg_base + SweepGenerator._REG_DURATION_LSB
		r2 = self.reg_base + SweepGenerator._REG_DURATION_MSB
		self._instr._accessor_set((r2, r1), to_reg_unsigned(0, 64), value)

	@property
	def wait_for_trig(self):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		return self._instr._accessor_get(r, from_reg_bool(2))

	@wait_for_trig.setter
	def wait_for_trig(self, value):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		self._instr._accessor_set(r, to_reg_bool(2), value)

	@property
	def hold_last(self):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		return self._instr._accessor_get(r, from_reg_bool(3))

	@hold_last.setter
	def hold_last(self, value):
		r = self.reg_base + SweepGenerator._REG_CONFIG
		self._instr._accessor_set(r, to_reg_bool(3), value)
