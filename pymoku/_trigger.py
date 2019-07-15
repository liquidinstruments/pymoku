from ._instrument import *
from . import _utils

class Trigger(object):
    _REG_CONFIG = 0
    _REG_LEVEL = 1
    _REG_HYSTERESIS = 2
    _REG_DURATION = 3
    _REG_HOLDOFF = 4
    _REG_NTRIGGER = 5

    TYPE_EDGE = 0
    TYPE_PULSE = 1

    EDGE_RISING = 0
    EDGE_FALLING = 1
    EDGE_BOTH = 2

    PULSE_MIN = 0
    PULSE_MAX = 1

    def __init__(self, instr, reg_base):
        self._instr = instr
        self.reg_base = reg_base

    @property
    def trigtype(self):
        r = self.reg_base + Trigger._REG_CONFIG
        return self._instr._accessor_get(r, from_reg_unsigned(0, 4))

    @trigtype.setter
    def trigtype(self, value):
        r = self.reg_base + Trigger._REG_CONFIG
        self._instr._accessor_set(r, to_reg_unsigned(0, 4, allow_set=[Trigger.TYPE_EDGE, Trigger.TYPE_PULSE]), value)

    @property
    def edge(self):
        r = self.reg_base + Trigger._REG_CONFIG
        return self._instr._accessor_get(r, from_reg_unsigned(4, 2))

    @edge.setter
    def edge(self, value):
        r = self.reg_base + Trigger._REG_CONFIG
        self._instr._accessor_set(r, to_reg_unsigned(4, 2, allow_set=[Trigger.EDGE_RISING, Trigger.EDGE_FALLING, Trigger.EDGE_BOTH]), value)

    @property
    def pulsetype(self):
        r = self.reg_base + Trigger._REG_CONFIG
        return self._instr._accessor_get(r, from_reg_unsigned(7, 2))

    @pulsetype.setter
    def pulsetype(self, value):
        r = self.reg_base + Trigger._REG_CONFIG
        self._instr._accessor_set(r, to_reg_unsigned(7, 2, allow_set=[Trigger.PULSE_MIN, Trigger.PULSE_MAX]), value)

    @property
    def hysteresis(self):
        r = self.reg_base + Trigger._REG_HYSTERESIS
        return self._instr._accessor_get(r, from_reg_unsigned(0, 16))

    @hysteresis.setter
    def hysteresis(self, value):
        r = self.reg_base + Trigger._REG_HYSTERESIS
        self._instr._accessor_set(r, to_reg_unsigned(0, 16), value)

    @property
    def holdoff(self):
        r = self.reg_base + Trigger._REG_HOLDOFF
        return self._instr._accessor_get(r, from_reg_unsigned(0, 32), value)

    @holdoff.setter
    def holdoff(self, value):
        r = self.reg_base + Trigger._REG_HOLDOFF
        self._instr._accessor_set(r, to_reg_unsigned(0, 32), value)

    @property
    def ntrigger(self):
        r = self.reg_base + Trigger._REG_NTRIGGER
        return self._instr._accessor_get(r, from_reg_unsigned(0, 16))

    @ntrigger.setter
    def ntrigger(self, value):
        r = self.reg_base + Trigger._REG_NTRIGGER
        self._instr._accessor_set(r, to_reg_unsigned(0, 16), value)

    @property
    def ntrigger_mode(self):
        r = self.reg_base + Trigger._REG_NTRIGGER
        return self._instr._accessor_get(r, from_reg_bool(31))

    @ntrigger_mode.setter
    def ntrigger_mode(self, value):
        r = self.reg_base + Trigger._REG_NTRIGGER
        self._instr._accessor_set(r, to_reg_bool(31), value)

    @property
    def level(self):
        r = self.reg_base + Trigger._REG_LEVEL
        return self._instr._accessor_get(r, from_reg_signed(0,32))

    @level.setter
    def level(self, value):
        r = self.reg_base + Trigger._REG_LEVEL
        self._instr._accessor_set(r, to_reg_signed(0, 32), value)

    @property
    def duration(self):
        r = self.reg_base + Trigger._REG_DURATION
        return self._instr._accessor_get(r, from_reg_unsigned(0, 32))

    @duration.setter
    def duration(self, value):
        r = self.reg_base + Trigger._REG_DURATION
        self._instr._accessor_set(r, to_reg_unsigned(0, 32), value)

