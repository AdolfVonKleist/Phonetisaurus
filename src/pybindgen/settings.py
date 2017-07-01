# pylint: disable-msg=W0105

from wrapper_registry import NullWrapperRegistry, StdMapWrapperRegistry

"""

Global settings to the code generator.

"""

name_prefix = ''
"""
Prefix applied to global declarations, such as instance and type
structures.
"""

automatic_type_narrowing = False
"""
Default value for the automatic_type_narrowing parameter of C++ classes.
"""

allow_subclassing = False
"""
Allow generated classes to be subclassed by default.
"""

unblock_threads = False
"""
Generate code to support threads.
When True, by default methods/functions/constructors will unblock
threads around the funcion call, i.e. allows other Python threads to
run during the call.
"""


error_handler = None
"""
Custom error handling.
Error handler, or None.  When it is None, code generation exceptions
propagate to the caller.  Else it can be a
:class:`pybindgen.settings.ErrorHandler` subclass instance that handles the error.
"""

min_python_version=(2, 3)
"""
Minimum python version the generated code must support.
"""

wrapper_registry = NullWrapperRegistry
"""
A :class:`WrapperRegistry` subclass to use for creating
wrapper registries.  A wrapper registry ensures that at most one
python wrapper exists for each C/C++ object.
"""

deprecated_virtuals = None
"""
Prior to PyBindGen version 0.14, the code generated to handle C++
virtual methods required Python user code to define a _foo method in
order to implement the virtual method foo.  Since 0.14, PyBindGen
changed so that virtual method foo is implemented in Python by
defining a method foo, i.e. no underscore prefix is needed anymore.
Setting deprecated_virtuals to True will force the old virtual method
behaviour.  But this is really deprecated; newer code should set
deprecated_virtuals to False.
"""


gcc_rtti_abi_complete = True
"""
If True, and GCC >= 3 is detected at compile time, pybindgen will try
to use abi::__si_class_type_info to determine the closest registered
type for pointers to objects of unknown type.  Notably, Mac OS X Lion
has GCC > 3 but which breaks this internal API, in which case it
should be disabled (set this option to False).
"""

def _get_deprecated_virtuals():
    if deprecated_virtuals is None:
        import warnings
        warnings.warn("The option pybindgen.settings.deprecated_virtuals has not been set."
                      "  I am going to assume the value of False, change it to True if it breaks your APIs."
                      " The option will eventually disappear (the deprecated behaviour will eventually disappear).",
                      DeprecationWarning)
        return False
    return deprecated_virtuals


class ErrorHandler(object):
    def handle_error(self, wrapper, exception, traceback_):
        """
        Handles a code generation error.  Should return True to tell
        pybindgen to ignore the error and move on to the next wrapper.
        Returning False will cause pybindgen to allow the exception to
        propagate, thus aborting the code generation procedure.
        """
        raise NotImplementedError

