from pymoku.instruments import Oscilloscope

try:
	from unittest.mock import patch, ANY
except ImportError:
	from mock import patch, ANY

def test_set_timebase(moku):
	with patch('pymoku._frame_instrument.FrameBasedInstrument._set_running') as fbi:
		i = Oscilloscope()
		moku.deploy_instrument(i)
		i.set_defaults()
		moku.reset_mock()

		i.set_timebase(-1.0, 1.0)
		moku._write_regs.assert_called_with(ANY)
