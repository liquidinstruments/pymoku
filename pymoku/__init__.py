import socket, select, struct, logging
import os, os.path
import zmq, zmq.auth
import pymoku.version

import pkg_resources
import threading
import tarfile

from functools import wraps
import warnings

from pymoku.tools import compat as cp

__version__ = pkg_resources.get_distribution("pymoku").version

DATAPATH = os.path.expanduser(os.environ.get('PYMOKU_INSTR_PATH', None) or pkg_resources.resource_filename('pymoku', 'data'))
PYMOKU_VERSION = __version__
MOKUDATAFILE = 'mokudata-%s-%s.tar.gz' % (pymoku.version.compat_fw[0], pymoku.version.compat_patch[0])

log = logging.getLogger(__name__)

try:
	from pymoku.finders import BonjourFinder
except Exception as e:
	print("Can't import the Bonjour libraries, I won't be able to automatically detect Mokus ({:s}).  Please install DNSSD libraries (e.g. libavahi-dnssd-compat on Linux)".format(str(e)))

from pymoku import dataparser

class MokuException(Exception):	"""Base class for other Exceptions""";	pass
class MokuNotFound(MokuException): """Can't find Moku. Raised from discovery factory functions."""; pass
class NetworkError(MokuException): """Network connection to Moku failed"""; pass
class DeployException(MokuException): """Couldn't start instrument. Moku may not be licenced to use that instrument"""; pass
class InvalidOperationException(MokuException): """Can't perform that operation at this time"""; pass
class InvalidParameterException(MokuException): """Invalid parameter type or value for this operation"""; pass
class ValueOutOfRangeException(MokuException): """Invalid value for this operation"""; pass
class NotDeployedException(MokuException): """Tried to perform an action on an Instrument before it was deployed to a Moku"""; pass
class FrameTimeout(MokuException): """No new :any:`InstrumentData` arrived within the given timeout"""; pass
class NoDataException(MokuException): """A request has been made for data but none will be generated """; pass
class InvalidConfigurationException(MokuException): """A request for an invalid instrument configuration has been made."""; pass
class StreamException(MokuException):
	def __init__(self, message, err=None):
		"""Data logging was interrupted or failed"""
		super(StreamException, self).__init__(message)
		self.err = err
class FileNotFound(MokuException): """Requested file or directory could not be found"""; pass
class InsufficientSpace(MokuException): """There is insufficient memory/disk space for the action being performed"""; pass
class MPNotMounted(MokuException): """The requested mount point has not been mounted"""; pass
class MPReadOnly(MokuException): """The requested mount point is Read Only"""; pass
class UnknownAction(MokuException): """The request was unknown"""; pass
class MokuBusy(MokuException): """The Moku is busy"""; pass
class UncommittedSettings(MokuException): """Instrument settings are awaiting commit."""; pass


# Re-export the exceptions that get raised by instruments, that aren't part of the instruments themselves.
# XXX: Don't love it..
InvalidFormatException = dataparser.InvalidFormatException
InvalidFileException = dataparser.InvalidFileException
DataIntegrityException = dataparser.DataIntegrityException

autocommit = True
def _get_autocommit():
	return autocommit
def _set_autocommit(enable):
	global autocommit
	autocommit = enable

# Allow environment variable override of bitstream path
data_folder = os.path.expanduser(os.environ.get('PYMOKU_INSTR_PATH', None) or pkg_resources.resource_filename('pymoku', 'data'))

# Network status codes
_ERR_OK = 0
_ERR_INVAL = 1
_ERR_NOTFOUND = 2
_ERR_NOSPC = 3
_ERR_NOMP = 4
_ERR_ACTION = 5
_ERR_BUSY = 6
_ERR_RO = 7
_ERR_UNKNOWN = 99

# Chosen to trade off number of network transactions with memory usage.
# 4MB is a little larger than a bitstream so those uploads aren't chunked.
_FS_CHUNK_SIZE = 1024 * 1024 * 4

class Moku(object):
	"""
	Core class representing a connection to a physical Moku:Lab unit.

	This must always be created first. Once a :any:`Moku` object exists, it can be queried for running instruments
	or new instruments deployed to the device.
	"""
	PORT = 27184

	def __init__(self, ip_addr, load_instruments=None, force=False):
		"""Create a connection to the Moku:Lab unit at the given IP address

		:type ip_addr: string
		:param ip_addr: The address to connect to. This should be in IPv4 dotted notation.

		:type load_instruments: bool or None
		:param load_instruments: Leave default (*None*) unless you know what you're doing.

		:type force: bool
		:param force: Ignore firmware and network compatibility checks and force the instrument
		to deploy. This is dangerous on many levels, leave *False* unless you know what you're doing.

		"""
		self._ip = ip_addr
		self._seq = 0
		self._instrument = None
		self._known_mokus = []

		self._ctx = zmq.Context.instance()
		self._conn_lock = threading.RLock()

		try:
			self._conn = self._ctx.socket(zmq.REQ)
			self._conn.setsockopt(zmq.LINGER, 5000)
			self._conn.curve_publickey, self._conn.curve_secretkey = zmq.curve_keypair()
			self._conn.curve_serverkey, _ = zmq.auth.load_certificate(os.path.join(data_folder, '000'))
			self._conn.connect("tcp://%s:%d" % (self._ip, Moku.PORT))

			# Getting the serial should be fairly quick; it's a simple operation. More importantly we
			# don't wait to block the fall-back operation for too long
			self._conn.setsockopt(zmq.SNDTIMEO, 1000)
			self._conn.setsockopt(zmq.RCVTIMEO, 1000)

			self.serial = self.get_serial()
			self._set_timeout()
		except zmq.error.Again:
			if not force:
				print("Connection failed, either the Moku cannot be reached or the firmware is out of date")
				raise

			# If we're force-connecting, try falling back to non-encrypted.
			self._conn = self._ctx.socket(zmq.REQ)
			self._conn.setsockopt(zmq.LINGER, 5000)
			self._conn.connect("tcp://%s:%d" % (self._ip, Moku.PORT))

			self._set_timeout()

			self.serial = self.get_serial()

		self.name = None
		self.led = None
		self.led_colours = None

		# Check that pymoku is compatible with the Moku:Lab's firmware version
		if not force:
			if cp.firmware_is_compatible(self) == False: # Might be None = unknown, don't print that.
				raise MokuException("Moku:Lab firmware {} incompatible with Pymoku v{}. "
					"Please update using\n moku update fetch\n moku --ip={} update install"
					.format(self.get_firmware_build(), PYMOKU_VERSION, self.get_ip()))

		self.load_instruments = load_instruments if load_instruments is not None else self.get_bootmode() == 'normal'

	@staticmethod
	def list_mokus(timeout=5, all_versions=True):
		""" Discovers all compatible Moku instances on the network.

		For most applications, the user should use the *get_by_* functions. These
		functions are faster to return as they don't have to wait to find and validate
		all Moku devices on the network, they can look for a specific one.

		:type timeout: float
		:param timeout: time for which to search for Moku devices
		:type all_versions: bool
		:param all_versions: list all Moku:Labs on the network, ignoring compatibility

		:rtype: [(ip, serial, name),...]
		:return: List of tuples, one per Moku
		"""
		known_mokus = []
		ips = BonjourFinder().find_all(timeout=timeout)

		for ip in ips:
			try:
				m = Moku(ip, force=all_versions)
				name = m.get_name()
				ser = m.get_serial()
				known_mokus.append((ip, ser, name))
				m.close()
			except Exception as e:
				continue

		return known_mokus

	@staticmethod
	def get_by_ip(ip_addr, timeout=10, force=False, *args, **kwargs):
		"""
		Factory function, returns a :any:`Moku` instance with the given IP address.

		:type serial: str
		:param serial: Target IP address i.e. '192.168.73.1'

		:type timeout: float, seconds
		:param timeout: Operation timeout

		:type force: bool
		:param force: Ignore firmware compatibility checks and force the instrument to deploy.

		:rtype: :any:`Moku`
		:return: Connected :any:`Moku <pymoku.Moku>` object with specified IP address.

		:raises *MokuNotFound*: If no such Moku:Lab is found within the timeout period.
		"""
		def _filter(ip):
			return ip == ip_addr

		mokus = BonjourFinder().find_all(max_results=1, filter_type='ip', filter_callback=_filter, timeout=timeout)

		if len(mokus):
			return Moku(mokus[0], force=force, *args, **kwargs)

		raise MokuNotFound("Couldn't find Moku:Lab with IP address: %s" % ip_addr)

	@staticmethod
	def get_by_serial(serial, timeout=10, force=False, *args, **kwargs):
		"""
		Factory function, returns a :any:`Moku` instance with the given serial number.

		:type serial: str
		:param serial: Target serial number i.e. '000123'

		:type timeout: float, seconds
		:param timeout: Operation timeout

		:type force: bool
		:param force: Ignore firmware compatibility checks and force the instrument to deploy.

		:rtype: :any:`Moku`
		:return: Connected :any:`Moku <pymoku.Moku>` object with specified serial number.

		:raises *MokuNotFound*: if no such Moku:Lab is found within the timeout period.
		"""
		try:
			serial_num = int(serial)
		except ValueError:
			raise InvalidParameterException("Moku:Lab serial number must be an integer e.g. '000231'. See base plate of your device.")

		def _filter(txtrecord):
			try:
				txt_serial = int(txtrecord['device.serial'])
				return txt_serial == serial_num
			except ValueError:
				log.warning("Discovered a Moku:Lab with invalid serial number '%s'." % txtrecord['device.serial'])
				return False
			except KeyError:
				return False

		mokus = BonjourFinder().find_all(max_results=1, filter_type='serial', filter_callback=_filter, timeout=timeout)

		if len(mokus):
			return Moku(mokus[0], force=force, *args, **kwargs)

		raise MokuNotFound("Couldn't find Moku:Lab with serial number: %s" % serial)

	@staticmethod
	def get_by_name(name, timeout=10, force=False, *args, **kwargs):
		"""
		Factory function, returns a :any:`Moku` instance with the given device name.

		:type serial: str
		:param serial: Target device name i.e. 'MyMoku'

		:type timeout: float, seconds
		:param timeout: Operation timeout

		:type force: bool
		:param force: Ignore firmware compatibility checks and force the instrument to deploy.

		:rtype: :any:`Moku`
		:return: Connected :any:`Moku <pymoku.Moku>` object with specified device name.

		:raises *MokuNotFound*: if no such Moku:Lab is found within the timeout period.
		"""
		def _filter(devname):
			return devname==name

		mokus = BonjourFinder().find_all(max_results=1, filter_type='name', filter_callback=_filter, timeout=timeout)

		if len(mokus):
			return Moku(mokus[0], force=force, *args, **kwargs)

		raise MokuNotFound("Couldn't find Moku:Lab with name: %s" % name)

	def _set_timeout(self, short=True, seconds=None):
		if seconds is not None:
			base = seconds * 1000
		else:
			base = 5000
			if not short:
				base *= 2

		self._conn.setsockopt(zmq.SNDTIMEO, base) # A send should always be quick
		self._conn.setsockopt(zmq.RCVTIMEO, 2 * base) # A receive might need to wait on processing


	def _get_seq(self):
		self._seq = (self._seq + 1) % 256
		return self._seq


	def _ownership(self, t, flags):
		name = socket.gethostname()[:255]
		packet_data = struct.pack("<BBB", t, len(name) + 1, flags) + name.encode('ascii')
		with self._conn_lock:
			self._conn.send(packet_data)
			rep = self._conn.recv()

		t, plen, own = struct.unpack("<BBB", rep[:3])
		rep = rep[3:]

		last_seen = None
		if t == 0x41:
			last_seen = struct.unpack("<I", rep[:4])
			rep = rep[4:]

		owner = rep

		return own, owner, last_seen

	def take_ownership(self):
		"""
		Register your ownership of the connected Moku:Lab device.

		Having ownership enables you to send commands to and receive data from the corresponding Moku:Lab.
		"""
		return self._ownership(0x40, 1)[0] == 2 # 2 is "owner is me"

	def relinquish_ownership(self):
		"""
		Drop your claim to the connected Moku:Lab device.

		This will allow other clients to connect immedaitely rather than waiting for a timeout
		"""
		self._ownership(0x40, 0)

	def is_owned(self):
		""" Checks whether the Moku:Lab device is currently owned by another user.

		:rtype: bool
		:return: True if someone, including you, currently owns the Moku:Lab device
		"""
		return self._ownership(0x41, 0)[0] != 0

	def owned_by(self):
		""" Return the name of the device that currently owns the Moku:Lab.

		This will be the iPad name or PC hostname of the device that most recently took
		ownership of the Moku:Lab. This will be the current PC's hostname if
		:any:`is_owner` returns *True*.

		:rtype: str
		:return: String name of current owner
		"""
		return self._ownership(0x41, 0)[1]

	def is_owner(self):
		"""	Checks if you are the current owner of the Moku:Lab device.

		:rtype: bool
		:return: True if you are the owner of the device."""
		return self._ownership(0x41, 0)[0] == 2


	def _read_regs(self, commands):
		packet_data = bytearray([0x47, 0x00, len(commands)])
		packet_data += b''.join([struct.pack('<B', x) for x in commands])

		with self._conn_lock:
			self._conn.send(packet_data)
			ack = self._conn.recv()

		t, err, l = struct.unpack('<BBB', ack[:3])

		if t != 0x47 or l != len(commands) or err:
			raise NetworkError()

		return [struct.unpack('<BI', ack[x:x + 5]) for x in range(3, len(commands) * 5, 5)]


	def _write_regs(self, commands):
		packet_data = bytearray([0x47, 0x00, len(commands)])
		packet_data += b''.join([struct.pack('<BI', x[0] + 0x80, x[1]) for x in commands])

		with self._conn_lock:
			self._conn.send(packet_data)
			ack = self._conn.recv()

		t, err, l = struct.unpack('<BBB', ack[:3])

		if t != 0x47 or err or l:
			raise NetworkError()

	def _slotdata_write_commit(self):
		return struct.pack("<H", 0)

	def _slotdata_read_regs(self, regs):
		return b''.join([struct.pack("<H", r) for r in regs])

	def _slotdata_write_regs(self, regdat):
		return b''.join([struct.pack("<HI", r, d) for r, d in regdat])

	def _slotdata_read_lut(self, off, _len, mirrored=False):
		addr = 257 if not mirrored else 258
		return struct.pack("<HII", addr, off, _len)

	def _slotdata_write_lut(self, off, data):
		addr = 257 # Mirrored and unmirrored are the same for writing
		return struct.pack("<HII", addr, off, len(data)) + data

	def _slotdata_read_maxi(self, addr):
		return struct.pack("<H", addr + 1024) # Addr is 0-based, not 1024

	def _slotdata_write_maxi(self, addr, data):
		return struct.pack("<HH", addr + 1024, len(data)) + data

	def _slot_packet(self, data, read=True):
		packet_data = struct.pack("<BQB", 0x55, len(data), 0 if read else 1)

		with self._conn_lock:
			self._conn.send(packet_data + data)
			ack = self._conn.recv()

		t, _, c = struct.unpack("<BQQ", ack[:17])

		if t != 0x55:
			raise NetworkError()

		return ack[17:]

	def _read_slots(self, data):
		# Takes a data string which is the concatenation of one or more strings
		# built using the _slotdata_read_* helpers
		return self._slot_packet(data)

	def _write_slots(self, data):
		# Takes a data string which is the concatenation of one of more strings
		# built using the _slotdata_write_* helpers
		return self._slot_packet(data, False)



	def _deploy(self, sub_index=0, is_partial=False, use_external=False):
		if self._instrument is None:
			DeployException("No Instrument Selected")

		# Deploy doesn't return until the deploy has completed which can take several
		# seconds on the device. Set an appropriately long timeout for this case.
		self._set_timeout(short=False)
		if sub_index < 0 or sub_index > 2**7:
			raise DeployException("Invalid sub-index %d" % sub_index)

		flags = (sub_index << 2) | (int(is_partial) << 1) | int(use_external)

		with self._conn_lock:
			self._conn.send(bytearray([0x43, self._instrument.id, flags]))
			ack = self._conn.recv()

		self._set_timeout(short=True)

		t, err = struct.unpack('<BB', ack[:2])

		if t != 0x43 or err:
			raise DeployException("Deploy Error %d" % err)

		self._set_property_single('ipad.name', socket.gethostname())

		# Return bitstream version
		return struct.unpack("<H", ack[3:5])[0]


	def _reset_instrument(self):
		with self._conn_lock:
			self._conn.send(bytearray([0x48, self._get_seq()]))
			self._conn.recv()

	def _set_clock_source(self, use_external=False):
		with self._conn_lock:
			self._conn.send(struct.pack("<BBB", 0x54, 0x01, use_external))
			self._conn.recv()

	def _get_clock_source(self):
		with self._conn_lock:
			self._conn.send(bytearray([0x54, 0x02]))
			ack = self._conn.recv()
		status = struct.unpack("<BBB", ack)[2]

		return bool(status & 0x02), bool(status & 0x01)

	def _get_requested_extclock(self):
		return self._get_clock_source()[0]

	def _get_actual_extclock(self):
		return self._get_clock_source()[1]


	def _get_properties(self, properties):
		ret = []

		if len(properties) > 255:
			raise InvalidOperationException("Properties request too long (%d)" % len(properties))
		pkt = bytearray([0x46, self._get_seq(), len(properties)])

		for p in properties:
			pkt += bytearray([1, len(p)]) # Read action
			pkt += p.encode('ascii')
			pkt += bytearray([0]) # No data for reads

		with self._conn_lock:
			self._conn.send(pkt)
			reply = self._conn.recv()

		hdr, seq, stat, nr = struct.unpack("<BBBB", reply[:4])
		reply = reply[4:]

		if hdr != 0x46:
			raise NetworkError("Bad header %d" % hdr)

		p, d = '', ''
		for n in range(nr):
			plen = ord(reply[:1]); reply = reply[1:]
			p = reply[:plen].decode('ascii'); reply = reply[plen:]
			dlen = ord(reply[:1]); reply = reply[1:]
			d = reply[:dlen].decode('ascii'); reply = reply[dlen:]

			if stat == 0:
				ret.append((p, d))
			else:
				break

		# Reply should just contain the \r\n by this time.

		if stat:
			# An error will have exactly one property reply, the property that caused
			# the error with empty data
			raise InvalidOperationException("Property Read Error, status %d on property %s" % (stat, p))

		return ret

	def _get_property_section(self, section):
		ret = []

		pkt = struct.pack("<BBBBB", 0x46, self._get_seq(), 1, 3, len(section))
		pkt += section.encode('ascii')
		pkt += bytearray([0]) # No data for reads

		with self._conn_lock:
			self._conn.send(pkt)
			reply = self._conn.recv()
		hdr, seq, stat, nr = struct.unpack("<BBBB", reply[:4])
		reply = reply[4:]

		if hdr != 0x46:
			raise NetworkError("Bad header %d" % hdr)

		p, d = '',''
		for n in range(nr):
			plen = ord(reply[:1]); reply = reply[1:]
			p = reply[:plen].decode('ascii'); reply = reply[plen:]
			dlen = ord(reply[:1]); reply = reply[1:]
			d = reply[:dlen].decode('ascii'); reply = reply[dlen:]

			if stat == 0:
				ret.append((p, d))
			else:
				break

		if stat:
			# An error will have exactly one property reply, the property that caused
			# the error with empty data
			raise InvalidOperationException("Property Read Error, status %d on property %s" % (stat, p))

		return ret

	def _get_property_single(self, prop):
		r = self._get_properties([prop])
		return r[0][1]

	def _set_properties(self, properties):
		ret = []
		if len(properties) > 255:
			raise InvalidOperationException("Properties request too long (%d)" % len(properties))
		pkt = struct.pack("<BBB", 0x46, self._get_seq(), len(properties))

		for p, d in properties:
			pkt += bytearray([2, len(p)])
			pkt += p.encode('ascii')
			pkt += bytearray([len(d)])
			pkt += d.encode('ascii')

		with self._conn_lock:
			self._conn.send(pkt)
			reply = self._conn.recv()
		hdr, seq, stat, nr = struct.unpack("<BBBB", reply[:4])
		reply = reply[4:]

		if hdr != 0x46:
			raise NetworkError("Bad header %d" % hdr)

		for n in range(nr):
			plen = ord(reply[:1]); reply = reply[1:]
			p = reply[:plen].decode('ascii'); reply = reply[plen:]
			dlen = ord(reply[:1]); reply = reply[1:]
			d = reply[:dlen].decode('ascii'); reply = reply[dlen:]

			if stat == 0:
				# Writes have the new value echoed back
				ret.append((p, d))
			else:
				break

		if stat:
			# An error will have exactly one property reply, the property that caused
			# the error with empty data
			raise InvalidOperationException("Property Read Error, status %d on property %s" % (stat, p))

		return ret

	def _set_property_single(self, prop, val):
		r = self._set_properties([(prop, val)])
		return r[0][1]


	def _stream_prep(self, ch1, ch2, start, end, offset, timestep, tag, binstr, procstr, fmtstr, hdrstr, fname, ftype='csv', use_sd=True):
		mp = 'e' if use_sd else 'i'

		if start < 0 or end < start:
			raise ValueOutOfRangeException("Invalid start/end times: %s/%s" %(str(start), str(end)))

		try:
			ftype = { 'bin': 0, 'csv': 1, 'mat': 2, 'npy': 3, 'net': 31}[ftype]
		except KeyError:
			raise ValueOutOfRangeException("Invalid file type %s" % ftype)

		# TODO: Support multiple file types simultaneously
		flags = ftype << 2
		flags |= int(ch2) << 1
		flags |= int(ch1)

		pkt = struct.pack("<BB", 0, 1) #TODO: Proper sequence number
		pkt += tag.encode('ascii')
		pkt += mp.encode('ascii')
		pkt += struct.pack("<IIdBd", start, end, offset, flags, timestep)
		pkt += struct.pack("<H", len(fname))
		pkt += fname.encode('ascii')
		pkt += struct.pack("<H", len(binstr))
		pkt += binstr.encode('ascii')

		# Build up a single procstring with "|" as a delimiter
		# TODO: Allow empty procstrings
		procstr_pkt = ''
		for i,ch in enumerate([ch1,ch2]):
			if ch:
				if len(procstr_pkt):
					procstr_pkt += '|'
				procstr_pkt += procstr[i]

		pkt += struct.pack("<H", len(procstr_pkt))
		pkt += procstr_pkt.encode('ascii')

		pkt += struct.pack("<H", len(fmtstr))
		pkt += fmtstr.encode('ascii')
		pkt += struct.pack("<H", len(hdrstr))
		pkt += hdrstr.encode('ascii')

		hdr = struct.pack("<BI", 0x53, len(pkt))

		with self._conn_lock:
			self._conn.send(hdr + pkt)
			reply = self._conn.recv()

		hdr, l, seq, ae, stat = struct.unpack("<BIBBB", reply[:8])

		if stat not in [ 1, 2 ]:
			raise StreamException("Stream start exception %d" % stat, stat)

	def _stream_start(self):
		pkt = struct.pack("<BIBB", 0x53, 2, 0, 4)
		with self._conn_lock:
			self._conn.send(pkt)
			reply = self._conn.recv()

		hdr, l, seq, ae, stat = struct.unpack("<BIBBB", reply[:8])

		return stat

	def _stream_stop(self):
		pkt = struct.pack("<BIBB", 0x53, 2, 0, 2)
		with self._conn_lock:
			self._conn.send(pkt)
			reply = self._conn.recv()

		hdr, l, seq, ae, stat, bt = struct.unpack("<BIBBBQ", reply[:16])

		return stat

	def _stream_status(self):
		pkt = struct.pack("<BIBB", 0x53, 2, 0, 3)
		with self._conn_lock:
			self._conn.send(pkt)
			reply = self._conn.recv()

		hdr, l, seq, ae, stat, bt, trems, treme, flags, fname_len = struct.unpack("<BIBBBQiiBH", reply[:27])
		fname = reply[27:27 + fname_len].decode('ascii')
		return stat, bt, trems, treme, fname

	def _fs_send_generic(self, action, data):
		pkt = struct.pack("<BQB", 0x49, len(data) + 1, action)
		pkt += data
		self._conn.send(pkt)

	def _fs_receive_generic(self, action):
		reply = self._conn.recv()
		hdr, l = struct.unpack("<BQ", reply[:9])
		pkt = reply[9:]

		if l != len(pkt):
			raise NetworkError("Unexpected file reply length %d/%d" % (l, len(pkt)))

		act, status = struct.unpack("BB", pkt[:2])

		if status:
			if status == _ERR_INVAL:
				ex = InvalidConfigurationException("Invalid fileserver request parameters.")
			elif status == _ERR_NOTFOUND:
				ex = FileNotFound("Could not find directory or file.")
			elif status == _ERR_NOSPC:
				ex = InsufficientSpace("Insufficient space to perform action.")
			elif status == _ERR_NOMP:
				ex = MPNotMounted("Mount point has not been mounted.")
			elif status == _ERR_ACTION:
				ex = InvalidOperationException("Unknown fileserver action requested.")
			elif status == _ERR_BUSY:
				ex = MokuBusy("Fileserver busy")
			elif status == _ERR_RO:
				ex = MPReadOnly("Requested mount point was Read-Only.")
			elif status == _ERR_UNKNOWN:
				ex = UnknownAction("Unknown fileserver action requested: %d" % act)
			else:
				ex = NetworkError("Received invalid status ID: %d" % stat)

			ex.dat = pkt[2:]
			raise ex

		return pkt[2:]

	def _send_file_bytes(self, mp, remotename, data, offset=0):
		# NOTE: The calling function should also perform a "finalise request" on completion of
		#		byte sending to ensure the file resource becomes available for use.
		data = bytearray(data)
		data_length = len(data)
		fname = mp + ":" + remotename

		self._set_timeout(short=False)
		i = 0

		while i < data_length:
			n_bytes = min(data_length-i, _FS_CHUNK_SIZE)
			pkt_data = data[i:i+n_bytes]

			pkt = bytearray([len(fname)])
			pkt += fname.encode('ascii')
			pkt += struct.pack("<QQ", offset+i, len(pkt_data))
			pkt += pkt_data
			with self._conn_lock:
				self._fs_send_generic(2, pkt)
				self._fs_receive_generic(2)

			# Increment the offset counter
			i += len(pkt_data)

		self._set_timeout(short=True)


	def _send_file(self, mp, localname, remotename=None):
		if remotename is None:
			remotename = os.path.basename(localname)

		self._set_timeout(short=False)
		i = 0

		with open(localname, 'rb') as f:
			while True:
				data = f.read(_FS_CHUNK_SIZE)
				if not len(data):
					break
				self._send_file_bytes(mp, remotename, data, i)
				i += len(data)

		# Once all chunks have been uploaded, finalise the file on the
		# device making it available for use
		self._fs_finalise_fromlocal(mp, localname, remotename)

		return remotename

	def _receive_file(self, mp, fname, length, localname=None):
		qfname = mp + ":" + fname
		self._set_timeout(short=False)

		localname = localname or fname

		i = 0
		with open(localname, "wb") as f:
			if length == 0:
				# A zero length file implies transfer the entire file
				# So we get the the file size
				length = self._fs_size(mp, fname)

			while i < length:
				to_transfer = min(length, _FS_CHUNK_SIZE)
				pkt = bytearray([len(qfname)])
				pkt += qfname.encode('ascii')
				pkt += struct.pack("<QQ", i, to_transfer)

				with self._conn_lock:
					self._fs_send_generic(1, pkt)
					reply = self._fs_receive_generic(1)

				dl = struct.unpack("<Q", reply[:8])[0]

				f.write(reply[8:])

				i += to_transfer

		self._set_timeout(short=True)


	def _fs_chk(self, mp, fname):
		fname = mp + ":" + fname

		pkt = bytearray([len(fname)])
		pkt += fname.encode('ascii')

		with self._conn_lock:
			self._fs_send_generic(3, pkt)
			rep = self._fs_receive_generic(3)
		return struct.unpack("<I", rep)[0]

	def _fs_sha(self, mp, fname):
		fname = mp + ":" + fname

		pkt = bytearray([len(fname)])
		pkt += fname.encode('ascii')

		with self._conn_lock:
			self._fs_send_generic(10, pkt)
			rep = self._fs_receive_generic(10)

		return rep.decode('ascii')

	def _fs_size(self, mp, fname):
		fname = mp + ":" + fname

		pkt = bytearray([len(fname)])
		pkt += fname.encode('ascii')

		with self._conn_lock:
			self._fs_send_generic(4, pkt)
			rep = self._fs_receive_generic(4)

		return struct.unpack("<Q", rep)[0]

	def _fs_list(self, mp, calculate_crc=False, calculate_sha=False):
		flags = 0
		flags |= int(calculate_crc)
		flags |= int(calculate_sha) << 1

		data = mp.encode('ascii')
		data += bytearray([flags])

		with self._conn_lock:
			self._fs_send_generic(5, data)
			reply = self._fs_receive_generic(5)

		n = struct.unpack("<H", reply[:2])[0]
		reply = reply[2:]

		names = []

		for i in range(n):
			if calculate_sha:
				chk = reply[:64].decode('ascii')
				reply = reply[64:]
			elif calculate_crc:
				chk = struct.unpack("<I", reply[:4])
				reply = reply[4:]
			else:
				chk = ''

			bl, fl = struct.unpack("<QB", reply[:9])
			reply = reply[9:]
			names.append((reply[:fl].decode(), chk, bl))
			reply = reply[fl:]

		return names

	def _fs_free(self, mp):
		with self._conn_lock:
			self._fs_send_generic(6, mp.encode('ascii'))
			rep = self._fs_receive_generic(6)

		t, f = struct.unpack("<QQ", rep)

		return t, f

	def _fs_finalise(self, mp, fname, fsize):
		fname = mp + ":" + fname
		pkt = bytearray([len(fname)])
		pkt += fname.encode('ascii')
		pkt += struct.pack('<Q', fsize)

		with self._conn_lock:
			self._fs_send_generic(7, pkt)
			self._fs_receive_generic(7)


	def _fs_finalise_fromlocal(self, mp, localname, remotename=None):
		fsize = os.path.getsize(localname)
		remotename = remotename or os.path.basename(localname)

		return self._fs_finalise(mp, remotename, fsize)

	def _fs_rename(self, smp, sname, dmp, dname, move=False):
		sname = smp + ":" + sname
		dname = dmp + ":" + dname
		pkt = bytearray([len(sname)])
		pkt += sname.encode('ascii')
		pkt += bytearray([len(dname)])
		pkt += dname.encode('ascii')

		flags = 1 if move else 0
		pkt += bytearray([flags])

		with self._conn_lock:
			self._fs_send_generic(8, pkt)
			rep = self._fs_receive_generic(8)

		return rep


	def _fs_rename_status(self):

		with self._conn_lock:
			self._fs_send_generic(9, b'')
			try:
				dat = self._fs_receive_generic(9)
				stat = _ERR_OK
			except MokuBusy as e:
				dat = e.dat
				stat = _ERR_BUSY

		size, pc = struct.unpack("<QB", dat)

		return stat, size, pc

	def _fs_rename_busy(self):
		return self._fs_rename_status()[0] == _ERR_BUSY

	def _fs_rename_progress(self):
		return self._fs_rename_status()[2]

	def _delete_bitstream(self, path):
		self._fs_finalise('b', path, 0)

	def _delete_file(self, mp, path):
		self._fs_finalise(mp, path, 0)

	def _list_packs(self):
		return [f[0] for f in self._fs_list('p') if f[0].endswith(('hgp','hgp.aes'))]

	def _delete_packs(self):
		for p in self._list_packs():
			self._delete_file('p', p)

	def _list_running_packs(self):
		return [(p[0].split('.')[1], p[1]) for p in self._get_property_section('packs')]

	def _load_bitstream(self, path, instr_id=None, sub_id=0):
		"""
		Load a bitstream file to the Moku, ready for deployment.

		:type path: String
		:param path: Local path to bitstream file.

		:raises NetworkError: if the upload fails verification.
		"""
		localname = os.path.basename(path)

		if instr_id is not None:
			remotename = "{:03d}.{:03d}".format(instr_id, sub_id)
		elif localname.count('.') == 2:
			remotename = '.'.join(localname.split('.')[1:])
		else:
			remotename = None

		remotename = self._send_file('b', path, remotename)

		return self._fs_sha('b', remotename)

	def _list_bitstreams(self, include_version=True):
		fs = self._fs_list('b', calculate_sha=include_version)

		if include_version:
			return [(b.split('.')[0], c) for b, c, s in fs]
		else:
			return [b.split('.')[0] for b, c, s in fs]

	def _trigger_fwload(self):
		self._set_timeout(seconds=20)
		with self._conn_lock:
			self._conn.send(bytearray([0x52, 0x01]))
			hdr, reply = struct.unpack("<BB", self._conn.recv())
		self._set_timeout()
		if reply:
			raise InvalidOperationException("Firmware update failure %d" % reply)

	def _restart_board(self):
		with self._conn_lock:
			self._conn.send(bytearray([0x52, 0x02]))
			hdr, reply = struct.unpack("<BB", self._conn.recv())
		if reply:
			raise InvalidOperationException("Reboot failed %d" % reply)

	def _load_firmware(self, path):
		"""
		Updates the firmware on the Moku.

		The Moku will automatically power off when the update is complete.

		:type path: String
		:param path: Path to compatible *moku.fw*
		:raises InvalidOperationException: if the firmware is not compatible.
		"""
		log.debug("Sending firmware file")
		self._send_file('f', path, 'moku.fw')
		log.debug("Updating firmware")
		try:
			self._trigger_fwload()
		except zmq.error.Again:
			# Sometimes the network connection goes down before the ack can be received
			pass

	def get_ip(self):
		""" :return: IP address of the connected Moku:Lab """
		return self._ip

	def get_serial(self):
		""" :return: Serial number of connected Moku:Lab """
		self.serial = self._get_property_single('device.serial')
		return self.serial

	def get_name(self):
		""" :return: Name of connected Moku:Lab """
		self.name = self._get_property_single('system.name')
		return self.name

	def get_firmware_build(self):
		""" :return: Build number of the current Moku:Lab firmware."""
		return int(self._get_property_single('system.micro'))

	def get_version(self):
		""" :return: Version of connected Moku:Lab """
		return version.release

	def get_hw_version(self):
		""" :return: Hardware version of connected Moku:Lab """
		return float(self._get_property_single('device.hw_version'))

	def set_name(self, name):
		""" :param name: Set new name for the Moku:Lab. This can make it easier to discover the device if multiple Moku:Labs are on a network"""
		self.name = self._set_property_single('system.name', name)

	def get_led_colour(self):
		""" :return: The colour of the under-Moku "UFO" ring lights"""
		self.led = self._get_property_single('leds.ufo1')
		return self.led

	def get_bootmode(self):
		""" :return: A string representing the boot mode of the attached Moku:Lab """
		return self._get_property_single('system.bootmode')

	def set_led_colour(self, colour):
		"""
		:type colour: string
		:param colour: New colour for the under-Moku "UFO" ring lights. Possible colours are listed by :any:`get_colour_list`"""
		if self.led_colours is None:
			self.get_colour_list()

		if not colour in self.led_colours:
			raise InvalidOperationException("Invalid LED colour %s" % colour)

		self.led = self._set_properties([('leds.ufo1', colour),
			('leds.ufo2', colour),
			('leds.ufo3', colour),
			('leds.ufo4', colour)])[0][1]

	def get_colour_list(self):
		"""
		:return: Available colours for the under-Moku "UFO" ring lights"""
		cols = self._get_property_section('colourtable')
		self.led_colours = [ x.split('.')[1] for x in list(zip(*cols))[0] ]
		return self.led_colours

	def is_active(self):
		""":return: True if the Moku currently is connected and has an instrument deployed and operating"""
		return self._instrument is not None and self._instrument.is_active()

	def deploy_instrument(self, instrument, set_default=True, use_external=False):
		"""
		Attaches a :any:`MokuInstrument` to the Moku, deploying and activating an instrument.

		Either this function, :any:`deploy_or_connect` or :any:`discover_instrument` must be called before an
		instrument can be manipulated.

		The *instrument* parameter can be a class or object. In the former case, the class is instantiated
		before being deployed, and the resulting object is returned.

		:type instrument: :any:`MokuInstrument` subclass or instantiation thereof
		:param instrument: The instrument instance to attach.
		:type set_default: bool
		:param set_default: Set the instrument to its default config upon connection, overwriting user changes before this point.
		:type use_external: bool
		:param use_external: Attempt to lock to an external reference clock.

		:return: Instrument object that has been deployed
		:rtype: :any:`MokuInstrument` object
		"""
		from pymoku.instruments import MokuInstrument
		self.external_reference = use_external

		if self._instrument:
			self.detach_instrument()

		# Instrument accepts a class or object, instantiate in the former case
		if not isinstance(instrument, MokuInstrument):
			instrument = instrument()

		self.take_ownership()
		self._instrument = instrument
		self._instrument.attach_moku(self)

		if self.load_instruments:
			log.debug("Loading instrument")
			try:
				# HW version 2.0, instrument 1 -> 20.001.000 (no partial/sub-id support)
				bs_name = "{:02d}.{:03d}.000".format(int(self.get_hw_version() * 10), instrument.id)

				tardata = tarfile.open(DATAPATH + '/' + MOKUDATAFILE)
				bs_tarinfo = tardata.getmember(bs_name)
				bs_file = tardata.extractfile(bs_tarinfo)
				self._send_file_bytes('b', '.'.join(bs_name.split('.')[1:]), bs_file.read())
				bs_file.close()
				tardata.close()

				log.debug("Load complete.")
			except:
				log.exception("Unable to automatically load instrument, deploy may fail")
		else:
			log.info("Moku in development mode, no instrument upload.")

		bsv = self._deploy(use_external=use_external)
		log.debug("Bitstream version %d", bsv)
		self._instrument._set_running(True)
		self._instrument._set_instrument_active(True)

		if set_default:
			self._instrument.set_defaults()
			# Ensure this always implicitly commits
			self._instrument.commit()

		return self._instrument

	def deploy_or_connect(self, instrument, set_default=True, use_external=False):
		"""
		Ensures the Moku:Lab is running the given instrument, either by connecting to an already-running instance, or deploying a new one.

		*instrument* is the class of the instrument you wish to deploy, e.g. :any:`Oscilloscope`. This function
		will check what instrument, if any, is already running on the Moku:Lab using :any:`discover_instrument`. If
		that instrument is of the wrong type, a new instance of the given instrument class is created and deployed
		using :any:`deploy_instrument`.

		:param instrument: A Class representing the instrument type required
		:type instrument: :any:`MokuInstrument` subclass

		:type set_default: bool
		:param set_default: Set the instrument to its default config upon connection, overwriting user changes before this point.

		:type use_external: bool
		:param use_external: Attempt to lock to an external reference clock.

		:return: An object of type *instrument* representing the running Instrument.
		"""
		i = self.discover_instrument()
		if i is None or pymoku.instruments.id_table[i.id] != instrument:
			log.debug("New %s required", instrument.__name__)
			i = instrument()
			self.deploy_instrument(i, set_default, use_external)
		else:
			log.debug("%s already deployed, taking ownership", instrument.__name__)
			self.take_ownership()

		return i

	def detach_instrument(self):
		"""
		Detaches the :any:`MokuInstrument` from this Moku.

		This has little effect usually, as a new Instrument can be attached without detaching the old one. This is mostly
		useful when you want to save network bandwidth between measurements without closing the entire Moku device
		"""
		if self._instrument:
			self._instrument._set_running(False)
			self._instrument = None

	def get_instrument(self):
		"""
		:return:
			Currently running instrument object. If the user has not deployed the instrument themselves,
			then :any:`discover_instrument` must be called first."""
		return self._instrument

	def discover_instrument(self):
		"""Query a Moku:Lab device to see what instrument, if any, is currently running.

		:rtype: :any:`MokuInstrument` or `None`
		:returns: The detected instrument ready to be controlled, otherwise None.
		"""
		import pymoku.instruments
		i = int(self._get_property_single('system.instrument').split('.')[0])
		try:
			instr = pymoku.instruments.id_table[i]
		except KeyError:
			return None

		self.detach_instrument()

		running = instr()
		running.attach_moku(self)
		running._sync_registers()
		running._set_running(True)
		self._instrument = running
		return running

	def close(self):
		"""Close connection to the Moku:Lab."""

		if self._instrument is not None:
			self._instrument._set_running(False)

		try:
			self.relinquish_ownership()
		except struct.error:
			# This error occurs on earlier firmware versions (<=1.5) due to ownership packet format changes
			pass
		finally:
			with self._conn_lock:
				self._conn.close()

		# Don't clobber the ZMQ context as it's global to the interpretter, if the user has multiple Moku
		# objects then we don't want to mess with that.


def deprecated(category, message):
	def deprecate_warn(func):
		header = 'Method Deprecation: ' if category == 'method' else 'Class Deprecation: ' if category == 'class' else 'Parameter Deprecation: '
		@wraps(func)
		def wrapper(*args, **kwargs):
			if category != 'param':
				warnings.warn(
					message=header+message,
					category=DeprecationWarning,
					stacklevel=2
				)
			return func(*args, **kwargs)
		wrapper.__doc__ = '\n\t\t.. warning::\n\t\t\t{} {}\n\n\t\t'.format(header, message)
		if func.__doc__ is not None:
			wrapper.__doc__ += func.__doc__.lstrip()
		return wrapper

	return deprecate_warn