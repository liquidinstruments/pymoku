from . import _frequency_response_analyzer
from ._instrument import deprecated


class BodeAnalyzer(_frequency_response_analyzer.FrequencyResponseAnalyzer):
	@deprecated(category='class', message='BodeAnalyzer is deprecated; use FrequencyResponseAnalyzer')
	def __init__(self):
		super(BodeAnalyzer, self).__init__()
