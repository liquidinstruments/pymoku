import threading, collections, time, struct, socket, logging
from functools import wraps

from pymoku import *
from pymoku import _get_autocommit, _set_autocommit


REG_CTL 	= 0
REG_STAT	= 1
REG_ID1		= 2
REG_ID2		= 3
REG_PAUSE	= 4
REG_OUTLEN	= 5
REG_FILT	= 6
REG_FRATE	= 7
REG_SCALE	= 8
REG_OFFSET	= 9
REG_OFFSETA	= 10
REG_STRCTL0	= 11
REG_STRCTL1	= 12
REG_AINCTL	= 13
# 14 was Decimation before that moved in to instrument space
REG_PRETRIG	= 15
REG_CAL_ADC0, REG_CAL_ADC1, REG_CAL_DAC0, REG_CAL_DAC1 = list(range(16, 20))
REG_TEMP_DAC = 14
REG_MMAP_ACCESS = 62
REG_STATE	= 63

# Common instrument parameters
ADC_SMP_RATE = 500e6
DAC_SMP_RATE = 1e9
CHN_BUFLEN = 2**14

### None of these constants will be exported to pymoku.instruments. If an instrument wants to
### give users access to these (e.g. relay settings) then the Instrument should define their
### own symbols equal to these guys

# REG_CTL Constants
COMMIT		= 0x80000000
INSTR_RST	= 0x00000001

# REG_OUTLEN Constants
ROLL		= 1
SWEEP		= 2
FULL_FRAME	= 0

# REG_FILT Constants
RDR_CUBIC	= 0
RDR_MINMAX	= 1
RDR_DECI	= 2
RDR_DDS		= 3

# REG_AINCTL Constants
RELAY_DC	= 1
RELAY_LOWZ	= 2
RELAY_LOWG	= 4

log = logging.getLogger(__name__)


def _usgn(i, width):
	""" Return i as an unsigned of given width, raising exceptions for out of bounds """
	if 0 <= i < 2**width:
		return int(i)

	raise ValueOutOfRangeException("%d doesn't fit in %d unsigned bits" % (i, width))

def _sgn(i, width):
	""" Return the unsigned that, when interpretted with given width, represents
	    the signed value i """
	if i < -2**(width - 1) or 2**(width - 1) - 1 < i:
		raise ValueOutOfRangeException("%d doesn't fit in %d signed bits" % (i, width))

	if i >= 0:
		return int(i)

	return int(2**width + i)

def _upsgn(i, width):
	""" Return the signed integer that comes about by interpretting *i* as a signed
	field of *width* bytes"""

	if i < 0 or i > 2**width:
		raise ValueOutOfRangeException()

	if i < 2**(width - 1):
		return i

	return i - 2**width


def to_reg_signed(_offset, _len, allow_set=None, allow_range=None, xform=lambda obj, x: x):
	""" Returns a callable that will pack a new signed data value in to a register.
	Designed as shorthand for common use in instrument register accessor lists. Supports
	single and compound registers (i.e. data values that span more than one register).

	:param _offset: Offset of data field in the register (set)
	:param _len: Length of data field in the register (set)
	:param allow_set: Set containing all valid values of the data field.
	:param allow_range: a two-tuple specifying the bounds of the data value.
	:param xform: a callable that translates the user value written to the attribute to the register value
	"""
	# TODO: This signed and the below unsigned share all but one line of code, should consolidate
	def __ss(obj, val, old):
		val = xform(obj, val)
		mask = ((1 << _len) - 1) << _offset

		if allow_set and allow_range:
			raise MokuException("Can't check against both ranges and sets")

		if allow_set and val not in allow_set:
			return None
		elif allow_range and (val < allow_range[0] or val > allow_range[1]):
			return None

		v = _sgn(val, _len) << _offset

		try:
			return (old & ~mask) | v
		except TypeError:
			r = []
			for o in reversed(old):
				r.insert(0, (o & ~mask) | v & 0xFFFFFFFF)

				v = v >> 32
				mask = mask >> 32

			return tuple(r)


	return __ss


def to_reg_unsigned(_offset, _len, allow_set=None, allow_range=None, xform=lambda obj, x: x):
	""" Returns a callable that will pack a new unsigned data value or bitfield in to a register.
	Designed as shorthand for common use in instrument register accessor lists. Supports
	single and compound registers (i.e. data values that span more than one register).

	:param _offset: Offset of data field in the register (set)
	:param _len: Length of data field in the register (set)
	:param allow_set: Set containing all valid values of the data field.
	:param allow_range: a two-tuple specifying the bounds of the data value.
	:param xform: a callable that translates the user value written to the attribute to the register value
	"""

	def __us(obj, val, old):
		val = xform(obj, val)
		mask = ((1 << _len) - 1) << _offset

		if allow_set and allow_range:
			raise MokuException("Can't check against both ranges and sets")

		if allow_set and val not in allow_set:
			return None
		elif allow_range and (val < allow_range[0] or val > allow_range[1]):
			return None

		v = _usgn(val, _len) << _offset

		try:
			return (old & ~mask) | v
		except TypeError:
			r = []
			for o in reversed(old):
				r.insert(0, (o & ~mask) | v & 0xFFFFFFFF)

				v = v >> 32
				mask = mask >> 32

			return tuple(r)

	return __us


def to_reg_bool(_offset):
	""" Returns a callable that will pack a new boolean data value in to a single bit of a register.
	Designed as shorthand for common use in instrument register accessor lists. Equivalent to
	:any:`to_reg_unsigned(_offset, 1, allow_set=[0, 1], xform=int)`

	:param _offset: Offset of bit in the register (set)
	"""
	return to_reg_unsigned(_offset, 1, allow_set=[0,1], xform=lambda obj, x: int(x))


def from_reg_signed(_offset, _len, xform=lambda obj, x: x):
	""" Returns a callable that will unpack a signed data value from a register bitfield.
	Designed as shorthand for common use in instrument register accessor lists. Supports
	single and compound registers (i.e. data values that span more than one register).

	:param _offset: Offset of data field in the register (set)
	:param _len: Length of data field in the register (set)
	:param xform: a callable that translates the register value to the user attribute's natural units
	"""
	# TODO: As above, this and the unsigned version share all but one line of code, should consolidate.
	mask = ((1 << _len) - 1) << _offset

	def __sg(obj, reg):
		try:
			return xform(obj, _upsgn((reg & mask) >> _offset, _len))
		except TypeError:
			v = 0
			for r in reg:
				v <<= 32
				v |= r

			return xform(obj, _upsgn((v & mask) >> _offset, _len))

	return __sg


def from_reg_unsigned(_offset, _len, xform=lambda obj, x: x):
	""" Returns a callable that will unpack an unsigned data value from a register bitfield.
	Designed as shorthand for common use in instrument register accessor lists. Supports
	single and compound registers (i.e. data values that span more than one register).

	:param _offset: Offset of data field in the register (set)
	:param _len: Length of data field in the register (set)
	:param xform: a callable that translates the register value to the user attribute's natural units
	"""
	mask = ((1 << _len) - 1) << _offset

	def __ug(obj, reg):
		try:
			return xform(obj, (reg & mask) >> _offset)
		except TypeError:
			v = 0
			for r in reg:
				v <<= 32
				v |= r

			return xform(obj, (v & mask) >> _offset)

	return __ug


def from_reg_bool(_offset):
	""" Returns a callable that will unpack a boolean value from a register bit.
	Designed as shorthand for common use in instrument register accessor lists.
	Equivalent to :any:`from_reg_unsigned(_offset, 1, xform=bool)`.

	:param _offset: Offset of data field in the register (set)
	"""
	return from_reg_unsigned(_offset, 1, xform=lambda obj, x: bool(x))

_awaiting_commit = False

def needs_commit(func):
	""" Wrapper function which checks whether settings should be committed automatically.
	"""
	@wraps(func)
	def wrapper(self, *args, **kwargs):
		if not _get_autocommit():
			# Not auto-committing
			return func(self, *args, **kwargs)
		else:
			# Auto-committing
			global _awaiting_commit

			was_awaiting = _awaiting_commit # Remember if a commit was already being waited on
			if not _awaiting_commit:
				_awaiting_commit = True # Lock the commit

			try:
				# Attempt to call the wrapped function
				res = func(self, *args, **kwargs)
			finally:
				# Do this even if the function raises an Exception

				# Commit if we weren't already waiting for one before
				if not was_awaiting:
					self.commit()
					# Reset the intention to commit
					_awaiting_commit = False
			return res
	return wrapper





class MokuInstrument(object):
	"""Superclass for all Instruments that may be attached to a :any:`Moku` object.

	Should never be instantiated directly; instead, instantiate the subclass of the instrument
	you wish to run (e.g. :any:`Oscilloscope`, :any:`WaveformGenerator`)
	"""

	def __init__(self):
		""" Must be called as the first line from any child implementations. """
		self._accessor_dict = {}
		self._moku = None
		self._remoteregs = [None]*128
		self._localregs = [None]*128
		self._running = False
		self._stateid = 0

		self.id = 0
		self.type = "Dummy Instrument"

		self._register_accessors(_instr_reg_handlers)

	def _register_accessors(self, accessor_dict):
		self._accessor_dict.update(accessor_dict)

	def _accessor_get(self, reg, get_xform):
		# Return local if present. Support a single register or a tuple of registers
		try:
			c = [ self._localregs[r] if self._localregs[r] is not None else self._remoteregs[r] or 0 for r in reg ]
			if all(i is not None for i in c): return get_xform(self, c)
		except TypeError:
			c = self._localregs[reg] if self._localregs[reg] is not None else self._remoteregs[reg] or 0
			if c is not None: return get_xform(self, c)

	def _accessor_set(self, reg, set_xform, data):
		# Support a single register or a tuple of registers
		try:
			old = [ self._localregs[r] if self._localregs[r] is not None else self._remoteregs[r] or 0 for r in reg ]
		except TypeError:
			old = self._localregs[reg] if self._localregs[reg] is not None else self._remoteregs[reg] or 0

		new = set_xform(self, data, old)
		if new is None:
			raise ValueOutOfRangeException("Reg %d Data %d" % (reg, data))

		try:
			for r, n in zip(reg, new):
				self._localregs[r] = n
		except TypeError:
			self._localregs[reg] = new

	def __getattr__(self, name):
		if name != '_accessor_dict' and name in self._accessor_dict:
			reg, set_xform, get_xform = self._accessor_dict[name]
			return self._accessor_get(reg, get_xform)
		else:
			raise AttributeError("No Attribute %s" % name)

	def __setattr__(self, name, value):
		if name != '_accessor_dict' and name in self._accessor_dict:
			reg, set_xform, get_xform = self._accessor_dict[name]
			return self._accessor_set(reg, set_xform, value)
		else:
			return super(MokuInstrument, self).__setattr__(name, value)

	@needs_commit
	def set_defaults(self):
		""" Can be extended in implementations to set initial state """

		# Base implementation: load DAC calibration values in to the bitstream.
		o1, o1t, o2, o2t = self._dac_offsets()
		self.dac1_offset = o1
		self.dac1_offset_t = o1t
		self.dac2_offset = o2
		self.dac2_offset_t = o2t

		# These may be called again in the instrument's implementation to overwrite this,
		# however they must be called at least once to load the initial calibration values
		self._set_frontend(1, fiftyr=True, atten=False, ac=False)
		self._set_frontend(2, fiftyr=True, atten=False, ac=False)


	def attach_moku(self, moku):
		self._moku = moku
		try:
			self.calibration = dict(self._moku._get_property_section("calibration"))
		except:
			log.warning("Can't read calibration values.")

	def _commit(self, update_state=True):
		if self._moku is None: raise NotDeployedException()
		if update_state:
			self._stateid = (self._stateid + 1) % 256 # Some statid docco says 8-bits, some 16.
			self.state_id = self._stateid
			self.state_id_alt = self._stateid
		regs = [ (i, d) for i, d in enumerate(self._localregs) if d is not None ]
		# TODO: Save this register set against stateid to be retrieved later
		log.debug("Committing reg set %s", str(regs))
		self._moku._write_regs(regs)
		self._remoteregs = [ l if l is not None else r for l, r in zip(self._localregs, self._remoteregs)]
		self._localregs = [None] * 128

	def commit(self):
		"""
		Apply all modified settings.

		.. note::

		    If the `autocommit` feature has been turned off, this function can be used to manually apply any instrument
		    settings to the Moku device. These instrument settings are those configured by calling all *set_* and *gen_* type
		    functions. Manually calling this function allows you to atomically apply many instrument settings at once.
		"""
		# We wrap up the implementation of the actual commit so we dont expose the update_state parameter to normal users
		return self._commit(update_state=True)

	def check_uncommitted_state(self):
		return any(self._localregs)

	def _sync_registers(self):
		"""
		Reload state from the Moku.

		This should never have to be called explicitly, however in advanced operation where the
		Moku state is being updated outside of pymoku, this will give the user access to those
		modified states through their attributes or accessors
		"""
		if self._moku is None: raise NotDeployedException()
		self._remoteregs = [ val for reg, val in self._moku._read_regs(list(range(128)))]
		self._stateid = self.state_id
		self._on_reg_sync()

	def _on_reg_sync(self):
		# This function acts when a Moku's register state is synchronised to the
		# local Moku instance. It is useful to update local variables and perform
		# sanity checks on the device state before it is deemed 'useable'.

		# Denotes the list of registers we expect to be non-zero on instrument deploy
		# Control registers [0:4], DAC Test [26], State ID [63]
		reg_blacklist = [0,1,2,3,26,63]

		# Get all register values that aren't blacklisted
		reg_data = [d for i,d in enumerate(self._remoteregs) if i not in reg_blacklist ]
		log.debug(reg_data)
		# If none of these register values are non-zero, assume the instrument has not been
		# configured and set defaults
		if not any(reg_data):
			log.warning("Moku seems to be unconfigured - setting instrument defaults.")
			self.set_defaults()
			self.commit()

		return

	def _dump_remote_regs(self):
		"""
		Return the current register state of the Moku.

		This should never have to be called explictly, however in advanced operation where the
		Moku state is being updated outside of pymoku, this gives the user access to the register
		values directly.

		Unlike :any:`sync_registers`, no local state is updated to reflect these register values
		and they are not made available through attributes or accessors.
		"""
		return self._moku._read_regs(list(range(128)))

	def _set_running(self, state):
		"""
		Set the local instrument object running state

		This is used to clean up helper threads and sockets. Should never be called explicitly.
		"""
		self._running = state

	def _set_instrument_active(self, active):
		"""
		Assert or release the intrument reset line on the device.

		This should never have to be called explicitly, as the instrument is correctly reset when
		it is attached and detached. In advanced operation, this can be used to force the instrument
		in to its initial state without a redeploy.
		"""
		reg = (INSTR_RST if not active else 0)
		self._localregs[REG_CTL] = reg
		self._commit(update_state=False)

	@needs_commit
	def _set_frontend(self, channel, fiftyr, atten, ac):
		# Set the analog frontend configuration
		relays =  RELAY_LOWZ if fiftyr else 0
		relays |= RELAY_LOWG if atten else 0
		relays |= RELAY_DC if not ac else 0

		off1, off1_t, off2, off2_t = self._adc_offsets()

		if channel == 1:
			self.relays_ch1 = relays
			self.adc1_offset = off1
			self.adc1_offset_t = off1_t
		elif channel == 2:
			self.relays_ch2 = relays
			self.adc2_offset = off2
			self.adc2_offset_t = off2_t

	def _get_frontend(self, channel):
		# Get the analog frontend
		if channel == 1:
			r = self.relays_ch1
		elif channel == 2:
			r = self.relays_ch2

		return [bool(r & RELAY_LOWZ), bool(r & RELAY_LOWG), not bool(r & RELAY_DC)]

	def _dac_gains(self):
		g1s = "calibration.DG-1"
		g2s = "calibration.DG-2"
		gt1s = "calibration.DGT-1"
		gt2s = "calibration.DGT-2"

		try:
			g1  = float(self.calibration[g1s])
			g2  = float(self.calibration[g2s])
			gt1 = float(self.calibration[gt1s])
			gt2 = float(self.calibration[gt2s])
		except (KeyError, TypeError):
			log.warning("Moku appears uncalibrated")
			g1 = g2 = 1
			gt1 = gt2 = 0

		# For now, assume a fixed 48 degrees C board temperature. In future, should read temperature registers
		g1 += gt1 * 48.0
		g2 += gt2 * 48.0

		# The sense of these parameters as used in pymoku is inverted from the storage on the Moku
		g1 = 1 / g1
		g2 = 1 / g2

		return g1, g2

	def _dac_offsets(self):
		o1s = "calibration.DO-1"
		o2s = "calibration.DO-2"
		ot1s = "calibration.DOT-1"
		ot2s = "calibration.DOT-2"

		try:
			o1  = float(self.calibration[o1s])
			o2  = float(self.calibration[o2s])
			ot1 = float(self.calibration[ot1s])
			ot2 = float(self.calibration[ot2s])
		except (KeyError, TypeError):
			log.warning("Moku appears uncalibrated")
			o1 = o2 = 0
			ot1 = ot2 = 0

		return o1, ot1, o2, ot2


	def _adc_gains(self):
		relay_string_1 = '-'.join(( "50" if self.relays_ch1 & RELAY_LOWZ else "1M",
								  "L" if self.relays_ch1 & RELAY_LOWG else "H",
								  "D" if self.relays_ch1 & RELAY_DC else "A"))

		relay_string_2 = '-'.join(( "50" if self.relays_ch2 & RELAY_LOWZ else "1M",
								  "L" if self.relays_ch2 & RELAY_LOWG else "H",
								  "D" if self.relays_ch2 & RELAY_DC else "A"))

		g1s = "calibration.AG-%s-1" % relay_string_1
		g2s = "calibration.AG-%s-2" % relay_string_2

		gt1s = "calibration.AGT-%s-1" % relay_string_1
		gt2s = "calibration.AGT-%s-2" % relay_string_2

		try:
			g1  = float(self.calibration[g1s])
			g2  = float(self.calibration[g2s])
			gt1 = float(self.calibration[gt1s])
			gt2 = float(self.calibration[gt2s])
		except (KeyError, TypeError):
			log.warning("Moku appears uncalibrated")
			g1 = g2 = 1
			gt1 = gt2 = 0

		# For now, assume a fixed 48 degrees C board temperature. In future, should read temperature registers
		g1 += gt1 * 48.0
		g2 += gt2 * 48.0

		# The sense of these parameters as used in pymoku is inverted from the storage on the Moku
		g1 = 1 / g1
		g2 = 1 / g2

		return g1, g2


	def _adc_offsets(self):
		relay_string_1 = '-'.join(( "50" if self.relays_ch1 & RELAY_LOWZ else "1M",
								  "L" if self.relays_ch1 & RELAY_LOWG else "H",
								  "D" if self.relays_ch1 & RELAY_DC else "A"))

		relay_string_2 = '-'.join(( "50" if self.relays_ch2 & RELAY_LOWZ else "1M",
								  "L" if self.relays_ch2 & RELAY_LOWG else "H",
								  "D" if self.relays_ch2 & RELAY_DC else "A"))

		o1s = "calibration.AO-%s-1" % relay_string_1
		o2s = "calibration.AO-%s-2" % relay_string_2
		ot1s = "calibration.AOT-%s-1" % relay_string_1
		ot2s = "calibration.AOT-%s-2" % relay_string_2

		try:
			o1  = float(self.calibration[o1s])
			o2  = float(self.calibration[o2s])
			ot1 = float(self.calibration[ot1s])
			ot2 = float(self.calibration[ot2s])
		except (KeyError, TypeError):
			log.warning("Moku appears uncalibrated")
			o1 = o2 = 0
			ot1 = ot2 = 0

		return o1, ot1, o2, ot2

	@needs_commit
	def _set_pause(self, pause):
		self.pause = pause

	def _get_pause(self):
		return self.pause

	def _load_feature(self, index):
		# For now we don't support switching clock modes during a partial deploy
		self._moku._deploy(use_external=self._moku.external_reference, partial_index=index)

	@needs_commit
	def _set_mmap_access(self, access):
		self.mmap_access = access

_instr_reg_handlers = {
	# Name : Register, set-transform (user to register), get-transform (register to user); either None is W/R-only
	'instr_id':			(REG_ID1, 		None, 						from_reg_unsigned(0, 8)),
	'instr_buildno':	(REG_ID1, 		None,						from_reg_unsigned(8, 8)),
	'hwver':			(REG_ID2, 		None,						from_reg_unsigned(24, 0)),
	'hwserial':			(REG_ID2, 		None,						from_reg_unsigned(0, 24)),
	'pause':			(REG_PAUSE,		to_reg_bool(0),				from_reg_bool(0)),
	'frame_length':		(REG_OUTLEN,	to_reg_unsigned(0, 12),		from_reg_unsigned(0, 12)),
	'keep_last':		(REG_OUTLEN,	to_reg_bool(28),			from_reg_bool(28)),

	'x_mode':			(REG_OUTLEN,	to_reg_unsigned(29, 2, allow_set=[ROLL, SWEEP, FULL_FRAME]),
										from_reg_unsigned(29, 2)),

	'render_mode':		(REG_FILT,		to_reg_unsigned(0, 2, allow_set=[RDR_CUBIC, RDR_MINMAX, RDR_DECI, RDR_DDS]),
										from_reg_unsigned(0, 2)),

	'waveform_avg1':	(REG_FILT,		to_reg_unsigned(2, 4, allow_range=(0,13)),		from_reg_unsigned(2, 4)),
	'waveform_avg2':	(REG_FILT,		to_reg_unsigned(6, 4, allow_range=(0,13)),		from_reg_unsigned(6, 4)),

	# Allow range is set to allow ~0-30Hz
	'framerate':		(REG_FRATE,		to_reg_unsigned(0, 8, allow_range=(0,15), xform=lambda obj, f: f * 256.0 / 477.0),
										from_reg_unsigned(0, 8, xform=lambda obj, f: f / 256.0 * 477.0)),

	# Cubic Downsampling accessors
	'render_deci':		(REG_SCALE,		to_reg_unsigned(0, 16, xform=lambda obj, x: 128 * (x - 1), allow_range=(0,0x077E)),
										from_reg_unsigned(0, 16, xform=lambda obj, x: (x / 128.0) + 1)),

	'render_deci_alt':	(REG_SCALE,		to_reg_unsigned(16, 16, xform=lambda obj, x: 128 * (x - 1), allow_range=(0,0x077E)),
										from_reg_unsigned(16, 16, xform=lambda obj, x: (x / 128.0) + 1)),
	# Direct Downsampling accessors
	'render_dds':		(REG_SCALE,		to_reg_unsigned(0, 16, xform=lambda obj, x: x - 1),
										from_reg_unsigned(0, 16, xform=lambda obj, x: x + 1)),

	'render_dds_alt':	(REG_SCALE,		to_reg_unsigned(16, 16, xform=lambda obj, x: x - 1),
										from_reg_unsigned(16, 16, xform=lambda obj, x: x + 1)),

	'offset':			(REG_OFFSET, 	to_reg_signed(0, 32),		from_reg_signed(0, 32)),

	'offset_alt':		(REG_OFFSETA,	to_reg_signed(0, 32),		from_reg_signed(0, 32)),

	'relays_ch1':		(REG_AINCTL, 	to_reg_unsigned(0, 3),		from_reg_unsigned(0, 3)),
	'relays_ch2':		(REG_AINCTL, 	to_reg_unsigned(3, 3),		from_reg_unsigned(3, 3)),
	'en_in_ch1':		(REG_AINCTL,	to_reg_bool(6),				from_reg_bool(6)),
	'en_in_ch2':		(REG_AINCTL,	to_reg_bool(7),				from_reg_bool(7)),
	'pretrigger':		(REG_PRETRIG,	to_reg_signed(0, 32),		from_reg_signed(0, 32)),

	'adc1_offset':		(REG_CAL_ADC0,	to_reg_signed(0, 7),		from_reg_signed(0, 7)),
	'adc1_offset_t':	(REG_CAL_ADC0,	to_reg_signed(16, 16, xform=lambda obj, x: round(max(-2**15, min(2**15-1, x * 2.0**13)))),
										from_reg_signed(16, 16, xform=lambda obj, x: x / 2.0**13)),

	'adc2_offset':		(REG_CAL_ADC1,	to_reg_signed(0, 7),		from_reg_signed(0, 7)),
	'adc2_offset_t':	(REG_CAL_ADC1,	to_reg_signed(16, 16, xform=lambda obj, x: round(max(-2**15, min(2**15-1, x * 2.0**13)))),
										from_reg_signed(16, 16, xform=lambda obj, x: x / 2.0**13)),

	'dac1_offset':		(REG_CAL_DAC0,	to_reg_signed(0, 11),		from_reg_signed(0, 11)),
	'dac1_offset_t':	(REG_CAL_DAC0,	to_reg_signed(16, 16, xform=lambda obj, x: round(max(-2**15, min(2**15-1, x * 2.0**12)))),
										from_reg_signed(16, 16, xform=lambda obj, x: x / 2.0**12)),

	'dac2_offset':		(REG_CAL_DAC1,	to_reg_signed(0, 11),		from_reg_signed(0, 11)),
	'dac2_offset_t':	(REG_CAL_DAC1,	to_reg_signed(16, 16, xform=lambda obj, x: round(max(-2**15, min(2**15-1, x * 2.0**12)))),
										from_reg_signed(16, 16, xform=lambda obj, x:  x / 2.0**12)),

	'state_id':			(REG_STATE,	 	to_reg_unsigned(0, 8),		from_reg_unsigned(0, 8)),
	'state_id_alt':		(REG_STATE,	 	to_reg_unsigned(16, 8),		from_reg_unsigned(16, 8)),
	'mmap_access':		(REG_MMAP_ACCESS,		to_reg_bool(0),			from_reg_bool(0)),
	'temp_dac':			(REG_TEMP_DAC,	None,		from_reg_signed(0, 12, xform=lambda obj, f: f * 0.0625)),
	'temp_adc':			(REG_AINCTL,	None,		from_reg_signed(20, 12, xform=lambda obj, f: f * 0.0625)),
}
