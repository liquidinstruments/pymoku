from setuptools import setup
import os.path, tarfile

with open('pymoku/version.txt') as f:
	version = f.read().strip()

setup(
	name='pymoku',
	version=version,
	author='Ben Coughlan',
	author_email='ben@liquidinstruments.com',
	packages=['pymoku', 'pymoku.tools'],
	package_dir={'pymoku': 'pymoku'},
	package_data={
		'pymoku' : ['version.txt', '*.capnp', os.path.join('data', '*')]
	},
	license='MIT',
	long_description="Python scripting interface to the Liquid Instruments Moku:Lab",

	url="https://github.com/liquidinstruments/pymoku",
	download_url="https://github.com/liquidinstruments/pymoku/archive/%s.tar.gz" % version,

	keywords=['moku', 'liquid instruments', 'test', 'measurement', 'lab', 'equipment'],

	entry_points={
		'console_scripts' : [
			'moku=pymoku.tools.moku:main',
			'moku_convert=pymoku.tools.moku_convert:main',
		]
	},

	install_requires=[
		'future',
		'pyzmq>=15.3.0',
		'requests>=2.18.0',
	],

	zip_safe=False, # Due to bitstream download
)
