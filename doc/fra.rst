
Frequency Response Analyzer Instrument
======================================

This instrument measures the transfer function of a system by generating a swept output sinewave and measuring the system response on the input. 

Example Usage
-------------

The following example code and a wide range of other pymoku demo scripts can be found at the `pymoku Github repository <https://github.com/liquidinstruments/pymoku>`_.

.. literalinclude:: ../examples/freq_response_analyzer_basic.py
	:language: python
	:caption: frequency_response_analyzer_basic.py

The FRAData Class
-----------------------

.. autoclass:: pymoku.instruments.FRAData

	.. Don't use :members: as it doesn't handle instance attributes well. Directives in the source code list required attributes directly.


The FrequencyResponseAnalyzer Class
------------------------------------

.. autoclass:: pymoku.instruments.FrequencyResponseAnalyzer
	:members:
	:inherited-members:
