from . import ValueOutOfRangeException, InvalidParameterException

"""
	Global utility functions
"""
def str_to_val(valmap, key, param_description):
	"""
		Returns the mapped value of the input key string.

		If there is no such key, an error is raised with the given message.

		Helper function - enables mapping of client strings to bit/register values.
	"""
	try:
		return valmap[key.lower()]
	except KeyError:
		raise InvalidParameterException("Invalid %s : \'%s\'. Expected %s." % (param_description, key, valmap.keys()))

def check_parameter_valid(check_type, v, allowed=None, desc="", units="", allow_none=False):
	if allow_none and v is None:
		return

	if check_type == 'bool':
		if not isinstance(v, bool):
			raise InvalidParameterException("Invalid parameter \'%s\': %s. Expected boolean value [True, False]." % (desc, v))
	elif check_type == 'int':
		try:
			int(v)
		except ValueError, TypeError:
			raise InvalidParameterException("Invalid parameter \'%s\': %s. Expected integer." % (desc, v))
	elif check_type == 'float':
		try:
			float(v)
		except ValueError, TypeError:
			raise InvalidParameterException("Invalid parameter \'%s\': %s. Expected floating-point number." % (desc, v))
	elif not isinstance(allowed, (list,tuple)):
		raise InvalidParameterException("Invalid parameter 'allowed': %s. Expected array or tuple." % allowed)
	elif check_type == 'set':
		if not (v in allowed):
			raise InvalidParameterException("Invalid parameter \'%s\': %s. Valid set %s." % (desc, v, allowed))
	elif check_type == 'range':
		if not (len(allowed) == 2):
			raise InvalidParameterException("Invalid allowed range %s. Expected [MIN,MAX]." % allowed)
		elif isinstance(allowed, tuple) and not (v > allowed[0] and v < allowed[1]):
			raise ValueOutOfRangeException("Invalid parameter \'%s\': %s. Valid range (%s, %s) %s." % (desc, v, allowed[0], allowed[1], units))
		elif not ((v >= allowed[0]) and (v <= allowed[1])):
			raise ValueOutOfRangeException("Invalid parameter \'%s\': %s. Valid range [%s, %s] %s." % (desc, v, allowed[0], allowed[1], units))
	else:
		raise InvalidParameterException("Invalid parameter 'check_type': %s. Expected ['bool','set','range']." % check_type)

def formatted_timestamp():
	import time
	return time.strftime("%Y-%m-%d T %H:%M:%S %z")
