# docstrings not neede here (the type handler floaterfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue, Parameter, \
     ReverseWrapperBase, ForwardWrapperBase


class FloatParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['float']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('f', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype_no_const, self.name)
        wrapper.parse_params.add_parameter('f', ['&'+name], self.value)
        wrapper.call_params.append(name)


class FloatReturn(ReturnValue):

    CTYPES = ['float']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("f", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("f", [self.value], prepend=True)


class FloatPtrParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['float*']

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False, default_value=None, array_length=None):
        super(FloatPtrParam, self).__init__(ctype, name, direction, is_const, default_value)
        self.array_length = array_length
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('f', ['*'+self.value])

        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("f", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'float*'
        if self.array_length is None:
            name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
            wrapper.call_params.append('&'+name)
            if self.direction & self.DIRECTION_IN:
                wrapper.parse_params.add_parameter('f', ['&'+name], self.name)
            if self.direction & self.DIRECTION_OUT:
                wrapper.build_params.add_parameter("f", [name])
        else:
            name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name, array="[%i]" % self.array_length)
            py_list = wrapper.declarations.declare_variable("PyObject*", "py_list")
            idx = wrapper.declarations.declare_variable("int", "idx")
            wrapper.call_params.append(name)
            if self.direction & self.DIRECTION_IN:
                elem = wrapper.declarations.declare_variable("PyObject*", "element")
                wrapper.parse_params.add_parameter('O!', ['&PyList_Type', '&'+py_list], self.name)
                wrapper.before_call.write_error_check(
                        'PyList_Size(%s) != %i' % (py_list, self.array_length),
                        'PyErr_SetString(PyExc_TypeError, "Parameter `%s\' must be a list of %i floats");'
                        % (self.name, self.array_length))

                wrapper.before_call.write_code(
                    "for (%s = 0; %s < %i; %s++) {" % (idx, idx, self.array_length, idx))
                wrapper.before_call.indent()

                wrapper.before_call.write_code("%(elem)s = PyList_GET_ITEM(%(py_list)s, %(idx)s);" % vars())
                wrapper.before_call.write_error_check(
                        '!PyFloat_Check(element)',
                        'PyErr_SetString(PyExc_TypeError, "Parameter `%s\' must be a list of %i floats");'
                        % (self.name, self.array_length))
                wrapper.before_call.write_code("%(name)s[%(idx)s] = (float) PyFloat_AsDouble(%(elem)s);" % vars())

                wrapper.before_call.unindent()
                wrapper.before_call.write_code('}')

            if self.direction & self.DIRECTION_OUT:
                wrapper.after_call.write_code("%s = PyList_New(%i);" % (py_list, self.array_length))

                wrapper.after_call.write_code(
                    "for (%s = 0; %s < %i; %s++) {" % (idx, idx, self.array_length, idx))
                wrapper.after_call.indent()
                wrapper.after_call.write_code("PyList_SET_ITEM(%(py_list)s, %(idx)s, PyFloat_FromDouble(%(name)s[%(idx)s]));" % vars())
                wrapper.after_call.unindent()
                wrapper.after_call.write_code('}')

                wrapper.build_params.add_parameter("N", [py_list])


class FloatRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['float&']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('f', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("f", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'float&'
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('f', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("f", [name])
