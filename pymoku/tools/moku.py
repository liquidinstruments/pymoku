#!/usr/bin/env python

from argparse import ArgumentParser
import os, os.path

from pymoku import *

parser = ArgumentParser()
subparsers = parser.add_subparsers()

# Global arguments
parser.add_argument('--serial', default=None, help="Serial Number of the Moku to connect to")
parser.add_argument('--name', default=None, help="Name of the Moku to connect to")
parser.add_argument('--ip', default=None, help="IP Address of the Moku to connect to")


# View and download updates from a remote server
def update(moku, args):
	if args.action == 'list':
		print('list updates')
	elif args.action == 'load':
		print('load updates')
	else:
		exit(1)

parser_updates = subparsers.add_parser('update')
parser_updates.add_argument('action', help='list load')
parser_updates.set_defaults(func=update)


# View and load new instrument bitstreams
def instrument(moku, args):
	if args.action == 'list':
		instrs = moku.list_bitstream(include_version=True)

		if len(instrs):
			print("The following instruments are available on your Moku:")
			for i in instrs:
				print('\t{}'.format(i))
		else:
			print("No instruments found on your Moku.")
	elif args.action == 'load':
		if not args.file or not args.file.endswith('bit'):
			print('Package load requires a BIT file to be specified')
			return

		fname = os.path.basename(args.file)
		chk = moku.load_bitstream(args.file)
		print("Successfully loaded new instrument {} version {:X}".format(fname, chk))
	else:
		exit(1)

parser_instruments = subparsers.add_parser('instrument')
parser_instruments.add_argument('action', help='list load')
parser_instruments.add_argument('file', nargs='?', default=None)
parser_instruments.set_defaults(func=instrument)


# View and load new packages
def package(moku, args):
	if args.action == 'list':
		packs = moku.list_package(include_version=True)

		if len(packs):
			print("The following packages are available on your Moku:")
			for i in packs:
				print('\t{}'.format(i))
		else:
			print("No packages found on your Moku.")
	elif args.action == 'load':
		if not args.file or not args.file.endswith('hgp'):
			print('Package load requires an HGP file to be specified')
			return

		fname = os.path.basename(args.file)
		chk = moku.load_persistent(args.file)

		if os.path.exists(args.file + '.sha256'):
			moku.load_persistent(args.file + '.sha256')
		else:
			print("WARNING: No signing information found, this package might not run correctly on your Moku.")

		print("Successfully loaded new instrument {} version {:X}".format(fname, chk))
	else:
		exit(1)

parser_package = subparsers.add_parser('package')
parser_package.add_argument('action', help='list load')
parser_package.add_argument('file', nargs='?', default=None)
parser_package.set_defaults(func=package)


# View firmware version and load new versions.
def firmware(moku, args):
	if args.action == 'list':
		print("Moku Firmware Version {}".format(moku.get_version()))
	elif args.action == 'load':
		if not args.file or not args.file.endswith('fw'):
			print('Package load requires an FW file to be specified')
			return

		moku.load_firmware(args.file)
		print("Successfully started firmware update. Your Moku will shut down automatically when complete.")
	else:
		exit(1)

parser_firmware = subparsers.add_parser('firmware')
parser_firmware.add_argument('action', help='version load')
parser_firmware.add_argument('file', nargs='?', default=None)
parser_firmware.set_defaults(func=firmware)


def main():
	args = parser.parse_args()

	if len([ x for x in (args.serial, args.name, args.ip) if x]) != 1:
		print("Please specify exactly one of serial, name or IP address of target Moku")
		exit(1)

	if args.serial:
		moku = Moku.get_by_serial(args.serial)
	elif args.name:
		moku = Moku.get_by_name(args.name)
	else:
		moku = Moku(args.ip)

	try:
		args.func(moku, args)
	finally:
		moku.close()

# Compatible with direct run and distutils binary packaging
if __name__ == '__main__':
	main()