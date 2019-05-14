from . import _frequency_response_analyzer
import warnings

warnings.simplefilter('always', DeprecationWarning)

class BodeAnalyzer(_frequency_response_analyzer.FrequencyResponseAnalyzer):
	def __init__(self):
		warnings.warn("BodeAnalyzer is deprecated; use FrequencyResponseAnalyzer", category=DeprecationWarning)
		super(BodeAnalyzer, self).__init__()
