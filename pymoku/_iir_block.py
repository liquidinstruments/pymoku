from ._instrument import to_reg_signed
from . import _utils
from copy import deepcopy


class IIRBlock(object):

    def __init__(self, instr, reg_base, num_stages=1, gain_frac_width=9,
                 coeff_frac_width=16, use_mmap=True):
        self._instr = instr
        self.reg_base = reg_base
        self.num_stages = num_stages
        self._coeff_frac_width = coeff_frac_width
        self._gain_frac_width = gain_frac_width
        self.use_mmap = use_mmap

    def _convert_coeffs(self, filt_coeffs):

        intermediate_filter = deepcopy(filt_coeffs)

        for stage in range(1, self.num_stages + 1):
            intermediate_filter[stage][1] *= intermediate_filter[stage][0]
            intermediate_filter[stage][2] *= intermediate_filter[stage][0]
            intermediate_filter[stage][3] *= intermediate_filter[stage][0]
            intermediate_filter[stage][0] = 1.0

        intermediate_filter[self.num_stages][0] = intermediate_filter[0][0]
        intermediate_filter = intermediate_filter[1:5]

        coeff_list = [[0 for coeff_elements in range(6)] for stage in
                      range(self.num_stages)]

        for stage in range(self.num_stages):
            for coeff in range(6):
                if coeff == 0:
                    coeff_list[stage][coeff] = int(round(
                        2 ** self._gain_frac_width * (
                            intermediate_filter[stage][coeff])))
                else:
                    coeff_list[stage][coeff] = \
                        int(round(2 ** self._coeff_frac_width * (
                            intermediate_filter[stage][coeff])))
        return coeff_list

    def _coeff_dimenension_checks(self, filt_coeffs):
        _utils.check_parameter_valid('set', len(filt_coeffs[0]),
                                     [1], 'number of coefficients '
                                          'in coefficient gain')

        for stage in range(1, self.num_stages + 1):
            _utils.check_parameter_valid('set', len(filt_coeffs[stage]),
                                         [6],
                                         ("number of coefficients in stage %s"
                                          % (stage)))
            for coeff_element in range(6):
                _utils.check_parameter_valid('range',
                                             filt_coeffs[stage][coeff_element],
                                             [-4.0, 4.0 - 2**(-45)],
                                             ("coefficient array entry at "
                                              "stage = %s, coefficient = %s"
                                              % (0, 0)))

    def write_coeffs(self, filt_coeffs):

        self._coeff_dimenension_checks(filt_coeffs)
        reg_coeffs = self._convert_coeffs(filt_coeffs)

        if self.use_mmap:
            # self._write_to_mmap(reg_coeffs)
            self._write_to_reg(reg_coeffs)
        else:
            self._write_to_reg(reg_coeffs)

    def _write_to_reg(self, coeffs_converted):

        for stage in range(self.num_stages):
            for coeff in range(6):
                r = self.reg_base + 6 * stage + coeff
                self._instr._accessor_set(r,
                                          to_reg_signed(
                                              0,
                                              self._coeff_frac_width + 2),
                                          coeffs_converted[stage][coeff])
