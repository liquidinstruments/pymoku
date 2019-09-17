#!/usr/bin/env python

from argparse import ArgumentParser
from pymoku.dataparser import LIDataFileReader
import logging
import sys
import datetime
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger()

parser = ArgumentParser()
parser.add_argument("-f", "--format", help="Output file format",
                    choices=['csv', 'hdf5'], default='csv')
parser.add_argument("input_file")


def to_csv(reader, filename):
    return reader.to_csv(filename)


def to_hdf5(reader, filename):
    try:
        import h5py
    except Exception:
        log.error("HDF5 output requires the h5py package to be installed")
        log.error(2)

    writer = h5py.File(sys.argv[2], 'w')
    ncols = reader.nch

    set_name = 'moku:datalog'

    # Start with storage for 100 items, it'll be expanded as we add data.
    # We don't know the length of the data set to begin with.
    writer.create_dataset(set_name, (100, ncols), maxshape=(None, ncols))
    writer[set_name].attrs['timestep'] = reader.deltat
    writer[set_name].attrs['start_secs'] = reader.starttime
    writer[set_name].attrs['start_time'] = datetime.fromtimestamp(
        reader.starttime).strftime('%c')
    writer[set_name].attrs['start_offset'] = reader.startoffset
    writer[set_name].attrs['instrument'] = reader.instr
    writer[set_name].attrs['instrument_version'] = reader.instrv

    i = 0
    for record in reader:
        curlen = len(writer[set_name])
        if curlen <= i:
            # Exponential allocation strategy, works fairly well for
            # different sized files.
            # We truncate to the correct length at the end anyway.
            writer[set_name].resize((2*curlen, ncols))

        writer[set_name][i, :] = record[:ncols]
        i += 1

    # Truncate the file to the correct length
    writer[set_name].resize((i, ncols))
    writer.close()

    return 0


type_map = {
    'csv': (to_csv, '.csv'),
    'hdf5': (to_hdf5, '.hd5'),
}


def main():
    args = parser.parse_args()

    if not args.input_file.endswith('.li'):
        log.error("Input file must be an LI file")
        exit(1)

    reader = LIDataFileReader(args.input_file)

    func, extension = type_map[args.format]
    fname = args.input_file[:-3] + extension  # trim off .li, add new extension

    return func(reader, fname)


if __name__ == '__main__':
    main()
