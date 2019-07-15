
PID Controller Instrument
============================

The PID Controller allows for dual channel (independent or MIMO) control of voltage-input,
voltage-output signals. The PID includes a double-integrator and fully-configurable integrator
saturation (anti-windup) and differentiator saturation.

Example Usage
-------------

The following example code and a wide range of other pymoku demo scripts can be found at the `pymoku Github repository <https://github.com/liquidinstruments/pymoku>`_.

.. literalinclude:: ../examples/pidcontroller_basic.py
	:language: python
	:caption: pidcontroller_basic.py

The PIDController Class
------------------------

.. autoclass:: pymoku.instruments.PIDController
	:members:
	:inherited-members:

