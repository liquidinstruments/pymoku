from ._instrument import from_reg_signed, from_reg_bool
from ._instrument import to_reg_signed, to_reg_bool


class EmbeddedPLL(object):

    _REG_BANDWIDTH = 0
    _REG_AUTOACQ = 1
    _REG_REACQ = 2
    _REG_RESET = 3

    def __init__(self, instr, reg_base):
        self._instr = instr
        self.reg_base = reg_base

    @property
    def bandwidth(self):
        r = self.reg_base + EmbeddedPLL._REG_BANDWIDTH
        return self._instr._accessor_get(r, from_reg_signed(0, 5))

    @bandwidth.setter
    def bandwidth(self, value):
        r = self.reg_base + EmbeddedPLL._REG_BANDWIDTH
        self._instr._accessor_set(r, to_reg_signed(0, 5), value)  # allow_set?

    @property
    def autoacquire(self):
        r = self.reg_base + EmbeddedPLL._REG_AUTOACQ
        return self._instr._accessor_get(r, from_reg_bool(0))

    @autoacquire.setter
    def autoacquire(self, value):
        r = self.reg_base + EmbeddedPLL._REG_AUTOACQ
        self._instr._accessor_set(r, to_reg_bool(0), value)  # allow_set?

    @property
    def reacquire(self):
        r = self.reg_base + EmbeddedPLL._REG_REACQ
        return self._instr._accessor_get(r, from_reg_bool(0))

    @reacquire.setter
    def reacquire(self, value):
        r = self.reg_base + EmbeddedPLL._REG_REACQ
        self._instr._accessor_set(r, to_reg_bool(0), value)  # allow_set?

    @property
    def pllreset(self):
        r = self.reg_base + EmbeddedPLL._REG_RESET
        return self._instr._accessor_get(r, from_reg_bool(31))

    @pllreset.setter
    def pllreset(self, value):
        r = self.reg_base + EmbeddedPLL._REG_RESET
        self._instr._accessor_set(r, to_reg_bool(31), value)  # allow_set?
