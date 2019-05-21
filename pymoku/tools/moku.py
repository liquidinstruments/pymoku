#!/usr/bin/env python

from argparse import ArgumentParser
import os, os.path, shutil, tempfile, tarfile
import requests, hashlib, sys, threading

from pymoku import *
from pymoku.tools.compat import *

MOKUDATAURL = 'http://updates.liquidinstruments.com/static/' + MOKUDATAFILE

import logging
logging.basicConfig(format='%(message)s', level=logging.INFO)

parser = ArgumentParser()
subparsers = parser.add_subparsers(title="action", dest='action', description="Action to take")
subparsers.required = True

# Global arguments
parser.add_argument('--serial', default=None, help="Serial Number of the Moku to connect to")
parser.add_argument('--name', default=None, help="Name of the Moku to connect to")
parser.add_argument('--ip', default=None, help="IP Address of the Moku to connect to")
parser.add_argument('--force', action='store_true', help="Bypass compatibility checks with the target Moku. Don't touch unless you know what you're doing.")

# View and load new instrument bitstreams
def update(args):
	if args.action == 'fetch':
		url = args.url

		try:
			r = requests.get(url.replace('tar.gz', 'md5'))
			r.raise_for_status() # Checks for any HTTP errors
			remote_hash = r.text.split(' ')[0]

			with open(DATAPATH + '/' + MOKUDATAFILE, 'rb') as f:
				assert hashlib.md5(f.read()).hexdigest() == remote_hash and not args.force

		except requests.HTTPError as e:
			logging.error("ERROR: Unable to retrieve updates from server.\n%s" % e.message)
			return
		except:
			# Any non-HTTP exception causes new archive to download
			logging.info("Fetching data pack from: %s" % url)
			with requests.get(url, stream=True) as r:
				r.raise_for_status() # Check for any HTTP errors
				length = int(r.headers['content-length'])
				recvd = 0

				with open(DATAPATH + '/' + MOKUDATAFILE, 'wb') as f:
					for chunk in r.iter_content(chunk_size=400000):
						f.write(chunk)
						recvd = recvd + len(chunk)
						sys.stdout.write("\r[%-30s] %3d%%" % ('#' * int(30.0 * recvd / length), (100.0 * recvd / length)))
						sys.stdout.flush()
					sys.stdout.write('\r[%-30s] Done!\n' % ('#' * 30))

			with open(DATAPATH + '/' + MOKUDATAFILE, 'rb') as f:
				assert hashlib.md5(f.read()).hexdigest() == remote_hash
		else:
			logging.info("%s Already up to date" % MOKUDATAFILE)
	elif args.action == 'install':
		firmware_reboot = False
		patch_reboot = False
		moku = connect(args, force=True)

		v = moku.get_hw_version()
		f = DATAPATH + '/' + MOKUDATAFILE

		def _load_firmware():
			tardata = tarfile.open(DATAPATH + '/' + MOKUDATAFILE)
			fw_tarinfo = tardata.getmember('moku%2d.fw' % (v * 10))
			fw_file = tardata.extractfile(fw_tarinfo)
			moku._send_file_bytes('f', 'moku.fw', fw_file.read())
			fw_file.close()
			tardata.close()
			return True

		def _load_patches():
			moku._delete_packs()
			tardata = tarfile.open(DATAPATH + '/' + MOKUDATAFILE)
			tar_packs = [ f for f in tardata.getnames() if f.endswith(('hgp','hgp.aes')) ]
			for p in tar_packs:
				pack_name = p.split('/')[-1]
				pack_tarinfo = tardata.getmember(p)
				pack_file = tardata.extractfile(pack_tarinfo)
				logging.info("Installing pack - %s" % pack_name)
				moku._send_file_bytes('p', pack_name, pack_file.read())
				pack_file.close()
			tardata.close()
			return True

		old_fw = moku.get_firmware_build()
		new_fw = version.compat_fw[0]
		logging.info('Updating Moku %06d from %d to %d...' % (int(moku.get_serial()), old_fw, new_fw))

		if args.force:
			if old_fw > new_fw:
				logging.warning('Downgrading firmware.')
			firmware_reboot |= _load_firmware()
		else:
			if old_fw == new_fw:
				logging.info('Firmware already up to date.')
			elif old_fw > new_fw:
				logging.error('Refusing to downgrade firmware.')
			else:
				firmware_reboot |= _load_firmware()

		if firmware_reboot:
			serial_num = int(moku.get_serial())
			moku._trigger_fwload()
			log.info("Successfully started firmware update.\n"
			         "Your Moku:Lab will shut down automatically when complete. "
			         "This process can take up to 30 minutes.\n"
			         "Please run `moku --serial=%d update install` "
			         "a second time to ensure all updates are installed correctly." % (serial_num))
			return

		# Applying patches
		logging.info('Checking for updates.')

		if not patch_is_compatible(moku):
			logging.info('Applying updates...')
			patch_reboot |= _load_patches()
		else:
			logging.info('Moku:Lab already up to date.')

		if patch_reboot:
			moku._restart_board()
			log.info("Successfully applied updates. Your Moku:Lab will now shut down to complete the update process.")

parser_update = subparsers.add_parser('update', help="Check and update instruments on the Moku.")
parser_update.add_argument('--url', help='Override location of data pack', default=MOKUDATAURL)
parser_update.add_argument('--force', action='store_true')
parser_update.add_argument('action', help='Action to perform', choices=['fetch', 'install'])
parser_update.set_defaults(func=update)

def listmokus(args):
	mokus = pymoku.BonjourFinder().find_all(timeout=2.0)
	mokus.sort()
	print("{: <20} {: >6} {: >6} {: >15}".format('Name', 'Serial', 'FW', 'IP'))
	print("-" * (20 + 6 + 6 + 15 + 3))

	def _querytask(m):
		x = None
		try:
			x = Moku(m, force=True)
			print("{: <20} {: 06d} {: 6d} {: >15}".format(
				x.get_name()[:20],
				int(x.get_serial()),
				x.get_firmware_build(),
				m))
		except:
			print("Couldn't query IP %s" % m)
		finally:
			try:
				x.close()
			except:
				pass

	tasks = []
	for m in mokus:
		tasks.append(threading.Thread(target=_querytask, args=[m]))

	for t in tasks:
		t.start()
	for t in tasks:
		t.join()

parser_list = subparsers.add_parser('list', help="List Moku:Labs on the network.")
parser_list.set_defaults(func=listmokus)

def query_property(args):
	moku = None
	try:
		moku = connect(args, force=True)
		if args.value:
			moku._set_property_single(args.property, args.value)
		print("%s = %s" % (args.property, moku._get_property_single(args.property)))
	finally:
		if moku:
			moku.close()

parser_set = subparsers.add_parser('property', help="Set Moku:Lab property.")
parser_set.add_argument('property', help='Property to query')
parser_set.add_argument('value', help='Value to write to property', nargs='?')
parser_set.set_defaults(func=query_property)

# View and load new instrument bitstreams
def instrument(args):
	moku = None
	try:
		moku = connect(args, force=True)
		if args.action == 'load':
			if not len(args.files):
				print("No instrument files specified for loading")
				return

			for file in args.files:
				fname = os.path.basename(file)
				chk = moku._load_bitstream(file)
				print("Successfully loaded new instrument {} version {}".format(fname, chk))
		else:
			exit(1)
	finally:
		if moku:
			moku.close()

parser_instruments = subparsers.add_parser('instrument', help="Check and update instruments on the Moku.")
parser_instruments.add_argument('action', help='Action to take', choices=['load'])
parser_instruments.add_argument('files', nargs='*', default=None, help="Path to local instrument file(s), if any")
parser_instruments.set_defaults(func=instrument)

# View and load new packages
def package(args):
	moku = None
	try:
		moku = connect(args)
		if args.action == 'load':
			if not args.file or not args.file.endswith(('hgp', 'hgp.aes')):
				print('Package load requires an HGP file to be specified')
				return

			fname = os.path.basename(args.file)
			moku._send_file('p', args.file)

			print("Successfully loaded new package {}".format(fname))
		else:
			exit(1)
	finally:
		if moku:
			moku.close()

parser_package = subparsers.add_parser('package', help="Check and load special feature packages on the Moku.")
parser_package.add_argument('action', help='Action to perform', choices=['load'])
parser_package.add_argument('file', nargs='?', default=None, help="Path to local package file, if any")
parser_package.set_defaults(func=package)


# View firmware version and load new versions.
def firmware(args):
	moku = None

	try:
		moku = connect(args, force=True)
		if args.action == 'version':
			print("Moku Firmware Version {}".format(moku.get_firmware_build()))
		elif args.action == 'load':
			v = moku.get_hw_version()
			if not args.file:
				f = DATAPATH + '/moku%2d.fw' % (v * 10)	#TODO
			else:
				f = args.file

			if not f.endswith('fw'):
				print('Package load requires an FW file to be specified')
				return

			print("Loading firmware from: %s" % f)
			moku._load_firmware(f)
			print("Successfully started firmware update. Your Moku will shut down automatically when complete.")
		elif args.action == 'check_compat':
			compat = firmware_is_compatible(moku)

			if compat == None:
				print("Unable to determine compatibility, perhaps you're running a development or pre-release build?")
			else:
				print("Compatible." if compat else "Moku:Lab firmware {} incompatible with Pymoku v{}. "
					"Please update using\n moku --ip={} update fetch\n moku --ip={} update install"
					.format(moku.get_firmware_build(), PYMOKU_VERSION, moku.get_ip(), moku.get_ip()))
		elif args.action == 'restart':
			moku._restart_board()
			print("Moku rebooted.")
		else:
			exit(1)
	finally:
		try:
			if moku:
				moku.close()
		except zmq.error.Again:
			pass # Firmware update can stop us being able to close

parser_firmware = subparsers.add_parser('firmware', help="Check and load new firmware for your Moku.")
parser_firmware.add_argument('action', help='Action to perform', choices=['version', 'load', 'check_compat', 'restart'])
parser_firmware.add_argument('file', nargs='?', default=None, help="Path to local firmware file, if any")
parser_firmware.set_defaults(func=firmware)

def main():
	logging.info("PyMoku %s" % PYMOKU_VERSION)
	args = parser.parse_args()
	args.func(args)

def connect(args, force=False):
	if len([ x for x in (args.serial, args.name, args.ip) if x]) != 1:
		print("Please specify exactly one of serial, name or IP address of target Moku")
		exit(1)

	force = force or args.force
	if args.serial:
		moku = Moku.get_by_serial(args.serial, force=force)
		print(moku.get_name())
	elif args.name:
		moku = Moku.get_by_name(args.name, force=force)
	else:
		moku = Moku(args.ip, force=force)

	return moku


# Compatible with direct run and distutils binary packaging
if __name__ == '__main__':
	main()
