from ._instrument import *
from . import _utils
import math

class PID(object):
	_REG_EN 			= 0
	_REG_GAIN 			= 1
	_REG_I_GAIN			= 2
	_REG_I_FB			= 3
	_REG_P_GAIN			= 4
	_REG_D_GAIN			= 5
	_REG_D_FB			= 6
	_REG_IN_OFFSET		= 7
	_REG_OUT_OFFSET		= 8

	def __init__(self, instr, reg_base, fs):
		self._instr = instr
		self.reg_base = reg_base
		self.fs = fs
		self.ang_freq = fs / ( 2 * math.pi)
		self.enable = True
		self.bypass = False
		self.int_en = True
		self.dc_pole = False
		self.p_en = True
		self.d_i_en = True
		self.input_en = True

	@property
	def enable(self):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_get(r, from_reg_bool(0))

	@enable.setter
	def enable(self, value):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_set(r, to_reg_bool(0), value)

	@property
	def bypass(self):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_get(r, from_reg_bool(1))

	@bypass.setter
	def bypass(self, value):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_set(r, to_reg_bool(1), value)

	@property
	def int_en(self):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_get(r, from_reg_bool(2))

	@int_en.setter
	def int_en(self, value):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_set(r, to_reg_bool(2), value)

	@property
	def dc_pole(self):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_get(r, from_reg_bool(3))

	@dc_pole.setter
	def dc_pole(self, value):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_set(r, to_reg_bool(3), value)

	@property
	def p_en(self):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_get(r, from_reg_bool(4))

	@p_en.setter
	def p_en(self, value):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_set(r, to_reg_bool(4), value)

	@property
	def d_i_en(self):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_get(r, from_reg_bool(5))

	@d_i_en.setter
	def d_i_en(self, value):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_set(r, to_reg_bool(5), value)

	@property
	def input_en(self):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_get(r, from_reg_bool(6))

	@input_en.setter
	def input_en(self, value):
		r = self.reg_base + PID._REG_EN
		return self._instr._accessor_set(r, to_reg_bool(6), value)

	@property
	def gain(self):
		r = self.reg_base + PID._REG_GAIN
		return self._instr._accessor_get(r, from_reg_unsigned(0, 32))

	@gain.setter
	def gain(self, value):
		r = self.reg_base + PID._REG_GAIN
		self._instr._accessor_set(r, to_reg_unsigned(0, 32), value)

	@property
	def i_gain(self):
		r =  self.reg_base + PID._REG_I_GAIN
		return self._instr._accessor_get(r, from_reg_unsigned(0, 25, xform=lambda obj, x: x / (2.0**24-1)))

	@i_gain.setter
	def i_gain(self, value):
		r = self.reg_base + PID._REG_I_GAIN
		self._instr._accessor_set(r, to_reg_unsigned(0, 25, xform=lambda obj, x: x * (2.0**24-1)), value)

	@property
	def i_fb(self):
		r = self.reg_base + PID._REG_I_FB
		return self._instr._accessor_get(r, from_reg_signed(0, 25, xform=lambda obj, x: x / (2.0**24 -1)))

	@i_fb.setter
	def i_fb(self, value):
		r = self.reg_base + PID._REG_I_FB
		self._instr._accessor_set(r, to_reg_signed(0, 25, xform=lambda obj, x: x * (2.0**24 - 1)), value)

	@property
	def p_gain(self):
		r = self.reg_base + PID._REG_P_GAIN
		return self._instr._accessor_get(r, from_reg_unsigned(0, 25, xform=lambda obj, x: x / (2.0**11)))

	@p_gain.setter
	def p_gain(self, value):
		r = self.reg_base + PID._REG_P_GAIN
		self._instr._accessor_set(r, to_reg_unsigned(0, 25, xform=lambda obj, x: x * (2.0**11)), value)

	@property
	def d_gain(self):
		r = self.reg_base + PID._REG_D_GAIN
		return self._instr._accessor_get(r, from_reg_unsigned(0, 25))

	@d_gain.setter
	def d_gain(self, value):
		r = self.reg_base + PID._REG_D_GAIN
		return self._instr._accessor_set(r, to_reg_unsigned(0, 25), value)

	@property
	def d_fb(self):
		r = self.reg_base + PID._REG_D_FB
		return self._instr._accessor_get(r, from_reg_unsigned(0, 25, xform=lambda obj, x: x / (2.0**24 -1)))

	@d_fb.setter
	def d_fb(self, value):
		r = self.reg_base + PID._REG_D_FB
		return self._instr._accessor_set(r, to_reg_unsigned(0, 25, xform=lambda obj, x: x * (2.0**24-1)), value)

	@property
	def input_offset(self):
		r = self.reg_base + PID._REG_IN_OFFSET
		return self._instr._accessor_get(r, from_reg_signed(16, 16))

	@input_offset.setter
	def input_offset(self, value):
		r = self.reg_base + PID._REG_IN_OFFSET
		return self._instr._accessor_set(r, to_reg_unsigned(16, 16), value)

	@property
	def output_offset(self):
		r = self.reg_base + PID._REG_OUT_OFFSET
		return self._instr._accessor_get(r, from_reg_signed(16, 16))

	@output_offset.setter
	def output_offset(self, value):
		r = self.reg_base + PID._REG_OUT_OFFSET
		return self._instr._accessor_set(r, to_reg_unsigned(16, 16), value)

	def set_reg_by_gain(self, g, kp, ki, kd, si, sd):
		# calculates the device registers ased on the gain values given.
		# Note that additional scaling due to external gain such as
		# ADC, DAC, decimation gains, etc. are not accounted for here))

		self.gain = g
		self.p_gain = kp
		self.i_gain = ki / self.ang_freq
		if kd == 0:
			self.d_gain = 0
		else:
			self.d_gain = 4 * sd if sd else self.ang_freq / float(kd)

		if si is None:
			i_c = 0
		elif ki == 0.0:
			i_c = 0
		else:
			i_c = ki / si
			if i_c < self.ang_freq / (2**24 - 1):
				si_max = (g * ki / (2 * self.ang_freq / (2**24 - 1)))
				print(si_max)
				raise InvalidConfigurationException("Integrator corner below"
													" minimum. Decrease "
													"integrator saturation "
													"below %.3f dB."
													% (20 *
													   math.log(si_max, 10)))
		self.i_fb = 1.0 - (i_c / self.ang_freq)

		if sd :
			if kd > 0 :
				fc_coeff = sd / ( self.ang_freq / float(kd))
			else:
				fc_coeff = 1
		else:
			fc_coeff = (math.sqrt(2*math.pi) / 10.0) # default differentiator roll off to a 10th of the nyquist

		if fc_coeff > (math.sqrt(2*math.pi) / 10.0):
			raise InvalidConfigurationException("Differentiator saturation corner above maximum. Reduce differentiator saturation below %.3f." % (fc_coeff * kd * self.ang_freq))

		self.d_fb = 1.0 - fc_coeff

	def set_reg_by_frequency(self, kp, i_xover, d_xover, si, sd, overall_scaling=1):
		# converts frequency cross over information

		# Particularly high or low I or D crossover frequencies (<1Hz, >1MHz) require that some of their gain is
		# pushed to the overall gain on the end due to dynamic range limitations

		cross_over_gain = kp if kp else 1.0

		i_gmin = d_gmin = 1.0
		i_gmax = d_gmax = 1.0
		if i_xover:
			i_unity = i_xover * cross_over_gain
			i_gmin = min(i_unity, 1.0)
			i_gmax = max(i_unity / 1e6, 1.0)

		if d_xover:
			d_unity = d_xover * (2*math.pi) * self.ang_freq / d_xover
			d_gmin = sd if sd is not None and sd < 1 else max(10.0e6 / d_unity, 1.0)
			d_gmax = max(1 / d_unity, 1.0)

		g_min = min(i_gmin, d_gmin)
		g_max = max(i_gmax, d_gmax)

		if g_min < 1.0 and g_max == 1.0:
			best_gain = g_min
		elif g_max > 1.0 and g_min == 1.0:
			best_gain = g_max
		elif g_min < 1.0 and g_max > 1.0:
			best_gain = math.sqrt(g_min * g_max)
		else:
			best_gain = 1.0

		cross_over_gain /= best_gain

		si = None if i_xover is None else si
		sd = None if d_xover is None else sd

		if i_xover :
			ki = cross_over_gain * i_xover
		else:
			ki = 0.0

		kd = d_xover/cross_over_gain if d_xover else 0.0
		si = si / best_gain if si else None

		# if ii_xover :
		# 	si = math.sqrt(si)

		sd = sd / best_gain if sd else None
		self.set_reg_by_gain(best_gain * overall_scaling, kp, ki, kd, si, sd)
