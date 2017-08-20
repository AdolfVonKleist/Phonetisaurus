# docstrings not neede here (the type handler interfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue, Parameter, \
     ReverseWrapperBase, ForwardWrapperBase


class BoolParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['bool']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('N', ["PyBool_FromLong(%s)" % (self.value,)])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype_no_const, self.name)
        if self.default_value is None:
            py_name = wrapper.declarations.declare_variable('PyObject *', 'py_'+self.name)
        else:
            py_name = wrapper.declarations.declare_variable('PyObject *', 'py_'+self.name, 'NULL')
        wrapper.parse_params.add_parameter('O', ['&'+py_name], self.value, optional=(self.default_value is not None))
        if self.default_value:
            wrapper.before_call.write_code("%s = %s? (bool) PyObject_IsTrue(%s) : %s;" % (name, py_name, py_name, self.default_value))
        else:
            wrapper.before_call.write_code("%s = (bool) PyObject_IsTrue(%s);" % (name, py_name))
        wrapper.call_params.append(name)


class BoolReturn(ReturnValue):

    CTYPES = ['bool']

    def get_c_error_return(self):
        return "return false;"
    
    def convert_python_to_c(self, wrapper):
        py_name = wrapper.declarations.declare_variable('PyObject *', 'py_boolretval')
        wrapper.parse_params.add_parameter("O", ["&"+py_name], prepend=True)
        wrapper.after_call.write_code(
            "%s = PyObject_IsTrue(%s);" % (self.value, py_name))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter(
            "N", ["PyBool_FromLong(%s)" % self.value], prepend=True)


class BoolPtrParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['bool*']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter(
                'N', ["PyBool_FromLong(*%s)" % (self.value,)])
        if self.direction & self.DIRECTION_OUT:
            py_name = wrapper.declarations.declare_variable(
                'PyObject *', 'py_'+self.name)
            wrapper.parse_params.add_parameter("O", ["&"+py_name], self.value)
            wrapper.after_call.write_code(
                "*%s = PyObject_IsTrue(%s);" % (self.value, py_name,))

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'bool*'
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append('&'+name)
        if self.direction & self.DIRECTION_IN:
            py_name = wrapper.declarations.declare_variable("PyObject*", 'py_'+self.name)
            wrapper.parse_params.add_parameter("O", ["&"+py_name], self.value)
            wrapper.before_call.write_code(
                "%s = PyObject_IsTrue(%s);" % (name, py_name,))
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter(
                'N', ["PyBool_FromLong(%s)" % name])
        

class BoolRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['bool&']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter(
                'N', ["PyBool_FromLong(%s)" % (self.value,)])
        if self.direction & self.DIRECTION_OUT:
            py_name = wrapper.declarations.declare_variable(
                'PyObject *', 'py_'+self.name)
            wrapper.parse_params.add_parameter("O", ["&"+py_name], self.name)
            wrapper.after_call.write_code(
                "%s = PyObject_IsTrue(%s);" % (self.value, py_name,))

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'bool&'
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            py_name = wrapper.declarations.declare_variable("PyObject*", 'py_'+self.name)
            wrapper.parse_params.add_parameter("O", ["&"+py_name], self.value)
            wrapper.before_call.write_code(
                "%s = PyObject_IsTrue(%s);" % (name, py_name,))
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter(
                'N', ["PyBool_FromLong(%s)" % (name,)])
