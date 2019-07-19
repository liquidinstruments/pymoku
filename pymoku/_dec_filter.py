
from ._instrument import to_reg_unsigned
import math


class DecFilter(object):
    REG_DECIMATION = 0
    REG_INTERP_WDFRATES = 1
    REG_INTERP_CICRATES = 2
    REG_INTERP_CTRL = 3

    def __init__(self, instr, regbase):
        self._instr = instr
        self.regbase = regbase

    def set_samplerate(self, factor):
        d_wdfmuxsel = 0
        d_outmuxsel = 0
        d_cic1_dec = 0
        d_cic1_bitshift = 0
        d_cic2_dec = 0
        d_cic2_bitshift = 0
        i_muxsel = 0
        i_ratechange_cic2 = 0
        i_interprate_cic2 = 0
        i_bitshift_cic2 = 0
        i_ratechange_cic1 = 0
        i_bitshift_cic1 = 0
        i_interprate_cic1 = 0
        i_highrate_wdf1 = 0
        i_highrate_wdf2 = 0
        if factor == 1:
            d_outmuxsel = 0
            i_muxsel = 0
        elif factor == 2:
            d_wdfmuxsel = 0
            d_outmuxsel = 1
            i_muxsel = 1
            i_highrate_wdf1 = 0
        elif factor == 4:
            d_wdfmuxsel = 0
            d_outmuxsel = 2
            i_muxsel = 2
            i_highrate_wdf1 = factor/2 - 1
            i_highrate_wdf2 = 0
        elif 8 <= factor <= 64:
            d_wdfmuxsel = 1
            d_outmuxsel = 2
            d_cic1_dec = factor/4
            d_cic1_bitshift = 12 - math.log(d_cic1_dec**3, 2)
            i_muxsel = 3
            i_ratechange_cic1 = factor/4
            i_interprate_cic1 = 0
            i_bitshift_cic1 = math.log(i_ratechange_cic1**2, 2)
            i_highrate_wdf1 = factor/2 - 1
            i_highrate_wdf2 = factor/4 - 1
        else:  # 128 <= factor <= 1024
            d_wdfmuxsel = 2
            d_outmuxsel = 2
            d_cic1_dec = 16
            d_cic1_bitshift = 0
            d_cic2_dec = factor/64
            d_cic2_bitshift = math.log(d_cic2_dec**3, 2)
            i_muxsel = 4
            i_ratechange_cic2 = factor/64
            i_interprate_cic2 = 0
            i_bitshift_cic2 = math.log(i_ratechange_cic2**2, 2)
            i_ratechange_cic1 = 16
            i_bitshift_cic1 = 8
            i_interprate_cic1 = i_ratechange_cic2 - 1
            i_highrate_wdf1 = factor/2 - 1
            i_highrate_wdf2 = factor/4 - 1

        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(0, 2), d_wdfmuxsel
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(2, 2), d_outmuxsel
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(4, 4), d_cic1_bitshift
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(8, 4), d_cic2_bitshift
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(12, 5), d_cic1_dec
            )
        self._instr._accessor_set(
            self.regbase + self.REG_DECIMATION,
            to_reg_unsigned(17, 5), d_cic2_dec
            )

        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(0, 3), i_muxsel
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_WDFRATES,
            to_reg_unsigned(0, 16), i_highrate_wdf1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_WDFRATES,
            to_reg_unsigned(16, 16), i_highrate_wdf2
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(3, 5), i_ratechange_cic1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(8, 5), i_ratechange_cic2
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CICRATES,
            to_reg_unsigned(0, 16), i_interprate_cic1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CICRATES,
            to_reg_unsigned(16, 16), i_interprate_cic2
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(13, 4), i_bitshift_cic1
            )
        self._instr._accessor_set(
            self.regbase + self.REG_INTERP_CTRL,
            to_reg_unsigned(17, 4), i_bitshift_cic2
            )
