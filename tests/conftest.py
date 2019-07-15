import pytest
import pymoku
from functools import partial

try:
	from unittest.mock import patch
	from unittest.mock import MagicMock
except ImportError:
	from mock import patch
	from mock import MagicMock

defaults = {
	'system': {
		'bootmode': 'normal'
	},
	'device': {
		'hw_version': 2.0,
	},
	'calibration': {
		'AO-1M-H-D-1': 0.0,
		'AO-1M-H-A-1': 0.0,
		'AO-1M-L-D-1': 0.0,
		'AO-1M-L-A-1': 0.0,
		'AO-50-H-D-1': 0.0,
		'AO-50-H-A-1': 0.0,
		'AO-50-L-D-1': 0.0,
		'AO-50-L-A-1': 0.0,
		'AO-1M-H-D-2': 0.0,
		'AO-1M-H-A-2': 0.0,
		'AO-1M-L-D-2': 0.0,
		'AO-1M-L-A-2': 0.0,
		'AO-50-H-D-2': 0.0,
		'AO-50-H-A-2': 0.0,
		'AO-50-L-D-2': 0.0,
		'AO-50-L-A-2': 0.0,

		'AOT-1M-H-D-1': 0.0,
		'AOT-1M-H-A-1': 0.0,
		'AOT-1M-L-D-1': 0.0,
		'AOT-1M-L-A-1': 0.0,
		'AOT-50-H-D-1': 0.0,
		'AOT-50-H-A-1': 0.0,
		'AOT-50-L-D-1': 0.0,
		'AOT-50-L-A-1': 0.0,
		'AOT-1M-H-D-2': 0.0,
		'AOT-1M-H-A-2': 0.0,
		'AOT-1M-L-D-2': 0.0,
		'AOT-1M-L-A-2': 0.0,
		'AOT-50-H-D-2': 0.0,
		'AOT-50-H-A-2': 0.0,
		'AOT-50-L-D-2': 0.0,
		'AOT-50-L-A-2': 0.0,

		'AG-1M-H-D-1': 3750.0,
		'AG-1M-H-A-1': 3750.0,
		'AG-1M-L-D-1': 375.0,
		'AG-1M-L-A-1': 375.0,
		'AG-50-H-D-1': 3750.0,
		'AG-50-H-A-1': 3750.0,
		'AG-50-L-D-1': 375.0,
		'AG-50-L-A-1': 375.0,
		'AG-1M-H-D-2': 3750.0,
		'AG-1M-H-A-2': 3750.0,
		'AG-1M-L-D-2': 375.0,
		'AG-1M-L-A-2': 375.0,
		'AG-50-H-D-2': 3750.0,
		'AG-50-H-A-2': 3750.0,
		'AG-50-L-D-2': 375.0,
		'AG-50-L-A-2': 375.0,

		'AGT-1M-H-D-1': 0.0,
		'AGT-1M-H-A-1': 0.0,
		'AGT-1M-L-D-1': 0.0,
		'AGT-1M-L-A-1': 0.0,
		'AGT-50-H-D-1': 0.0,
		'AGT-50-H-A-1': 0.0,
		'AGT-50-L-D-1': 0.0,
		'AGT-50-L-A-1': 0.0,
		'AGT-1M-H-D-2': 0.0,
		'AGT-1M-H-A-2': 0.0,
		'AGT-1M-L-D-2': 0.0,
		'AGT-1M-L-A-2': 0.0,
		'AGT-50-H-D-2': 0.0,
		'AGT-50-H-A-2': 0.0,
		'AGT-50-L-D-2': 0.0,
		'AGT-50-L-A-2': 0.0,

		'DO-1': 0.0,
		'DO-2': 0.0,

		'DG-1': 30000.0,
		'DG-2': 30000.0,

		'DOT-1': 0.0,
		'DOT-2': 0.0,

		'DGT-1': 0.0,
		'DGT-2': 0.0,
	}
}

# Side_effects for unmocked functions

def _get_property_section(self, section):
	#TODO needs to be recursive
	d = {}
	for k, v in defaults[section].items():
		d['.'.join((section, k))] = v
	return d

def _get_properties(self, properties):
	results = []
	for prop in properties:
		d = defaults
		for p in prop.split('.'):
			d = d[p]
		results.append((prop, d))
	return results

# Gather methods to wrap before we're in a mock context
unmocks = {
	'get_serial'            : pymoku.Moku.get_serial,
	'get_name'              : pymoku.Moku.get_name,
	'get_firmware_build'    : pymoku.Moku.get_firmware_build,
	'get_version'           : pymoku.Moku.get_version,
	'get_hw_version'        : pymoku.Moku.get_hw_version,
	'get_bootmode'          : pymoku.Moku.get_bootmode,
	'deploy_instrument'     : pymoku.Moku.deploy_instrument,
	'_get_property_single'  : pymoku.Moku._get_property_single,
	'_get_properties'       : _get_properties,
	'_get_property_section' : _get_property_section,
}

@pytest.fixture
@patch('pymoku.Moku', spec=pymoku.Moku)
def moku(*kwargs):
	'''
	We mock the entire Moku class, and the selectively unmock classmethods we need
	side_effects for.
	'''
	m = pymoku.Moku()

	# TODO wrap init properly
	m._instrument = None
	m.load_instruments = False

	for k, v in unmocks.items():
		try:
			# for Python 2.7
			m.configure_mock(**{k + '.side_effect': partial(v.__func__, m)})
		except AttributeError:
			m.configure_mock(**{k + '.side_effect': partial(v, m)})

	return m
