
Laser Lock Box Instrument
============================

Moku:Lab’s Laser Lock Box allows you to stabilize a laser's frequency to a reference cavity or transition
using high-performance modulation locking techniques. The Laser Lock Box includes a ‘Tap-to-Lock’ feature
enabling you to quickly lock to any zero-crossing on the demodulated error signal.

The Laser Lock Box can have monitor points set up, providing a "virtual Oscillscope" view of input,
output and internal signals. Once configured, these can be displayed and logged using
the same API as the :any:`Oscilloscope` object.

Example Usage
-------------

The following example code and a wide range of other pymoku demo scripts can be found at the `pymoku Github repository <https://github.com/liquidinstruments/pymoku>`_.

.. literalinclude:: ../examples/laser_lock_box_basic.py
	:language: python
	:caption: laser_lock_box_basic.py


The LaserLockBox Class
----------------------

.. autoclass:: pymoku.instruments.LaserLockBox
	:members:
	:inherited-members:
