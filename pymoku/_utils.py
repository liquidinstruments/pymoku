from . import ValueOutOfRangeException, InvalidParameterException
import sys

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
        except (ValueError, TypeError):
            raise InvalidParameterException("Invalid parameter \'%s\': %s. Expected integer." % (desc, v))
    elif check_type == 'string':
        try:
            # Correct string check for Python 2.x
            if not isinstance(v, basestring):
                raise InvalidParameterException("Invalid parameter \'%s\': %s. Expected string." % (desc, v))
        except NameError:
            # Correct string check for Python 3.x
            if not isinstance(v, str):
                raise InvalidParameterException("Invalid parameter \'%s\': %s. Expected string." % (desc, v))
    elif check_type == 'float':
        try:
            float(v)
        except (ValueError, TypeError):
            raise InvalidParameterException("Invalid parameter \'%s\': %s %s. Expected floating-point number." % (desc, v, units))
    elif not isinstance(allowed, (list,tuple)) and (sys.version_info[0]==3 and not isinstance(allowed, range)):
        # This case enables the "allow" parameter to be specified using Python 3's built-in range function which returns a 'range' type object
        raise InvalidParameterException("Invalid parameter 'allowed': %s %s. Expected array, tuple or range type object." % (allowed,units))
    elif check_type == 'set':
        if not (v in allowed):
            raise InvalidParameterException("Invalid parameter \'%s\': %s. Valid set %s %s." % (desc, v, allowed, units))
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
