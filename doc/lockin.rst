
Lock-in Amplifier Instrument
============================

The Lock-in Amplifier instrument can be used to retrieve small signals of known frequency
from within the noise floor. The Moku:Lab Lock-in supports internal or external demodulation
(reference) frequency, multiple possible output signals and an optional PID controller to
be used in a closed-loop system to drive the recovered signal towards a set point.

The Lock-in can have monitor points set up, providing a "virtual Oscillscope" view of input,
output and internal signals. Once configured, these can be displayed and logged using
the same API as the :any:`Oscilloscope` object.

Example Usage
-------------

The following example code and a wide range of other pymoku demo scripts can be found at the `pymoku Github repository <https://github.com/liquidinstruments/pymoku>`_.

.. literalinclude:: ../examples/lockinamp_basic.py
	:language: python
	:caption: lockinamp_basic.py


The LockInAmp Class
-------------------

.. autoclass:: pymoku.instruments.LockInAmp
	:members:
	:inherited-members:
