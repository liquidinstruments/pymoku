
Advanced Features
=========================

Auto-commit
------------

.. warning:: 

		Be aware that the :py:meth:`commit` function and auto-commit feature are **NOT** thread-safe. Auto-commit may cease to work if you are changing instrument settings in multiple threads. In the case that auto-commit is OFF, it can happen that instrument settings are applied pre-emptively due to non-deterministic ordering of commit calls between threads. 

		It is advised that instrument settings only be modified in a single thread to avoid unexpected behaviour.

By default, any modifications to instrument settings (i.e. as a result of calling *gen_* and *set_* instrument methods) are automatically sent to the device to take effect. This is called the `auto-commit` feature of pymoku. 


.. code-block:: python

		from pymoku import Moku
		from pymoku.instruments import *

		m = Moku.get_by_name('Moku')
		i = Oscilloscope()
		m.deploy_instrument(i)

		i.set_timebase(-1,1)
		# Timebase settings are 'committed' to the Moku automatically
		i.set_samplerate(10)
		# Samplerate settings are 'committed' to the Moku automatically

In some cases it may be desirable to wait until many settings have been configured, and then atomically apply them to your Moku:Lab device. This can be achieved by turning OFF the `autocommit` property of pymoku. Instrument setting changes will subsequently only take effect on the device when you explicitly `commit` them.


.. code-block:: python

		import pymoku
		from pymoku import Moku
		from pymoku.instruments import *

		# Turn off the auto-commit feature
		pymoku.autocommit = False

		m = Moku.get_by_name('Moku')
		i = Oscilloscope()
		m.deploy_instrument(i)

		i.set_timebase(-1,1)
		# Settings have not yet been sent to the Moku
		i.set_samplerate(10)
		# Settings have not yet been sent to the Moku
		i.commit()
		# Timebase and samplerate settings have now been sent to the Moku


InstrumentData
---------------

.. autoclass:: pymoku.instruments.InstrumentData

MokuInstrument
----------------

.. autoclass:: pymoku.instruments.MokuInstrument