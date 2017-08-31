# docstrings not needed here (the type handler interfaces are fully
# documented in base.py)
# pylint: disable-msg=C0111

import struct
assert struct.calcsize('i') == 4 # assumption is made that sizeof(int) == 4 for all platforms pybindgen runs on


from base import ReturnValue, Parameter, PointerParameter, PointerReturnValue, \
     ReverseWrapperBase, ForwardWrapperBase, TypeConfigurationError, NotSupportedError


class IntParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['int', 'int32_t']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('i', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype_no_const, self.name, self.default_value)
        wrapper.parse_params.add_parameter('i', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.call_params.append(name)


class UnsignedIntParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['unsigned int', 'uint32_t']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('N', ["PyLong_FromUnsignedLong(%s)" % self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable('unsigned int', self.name, self.default_value)
        wrapper.parse_params.add_parameter('I', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.call_params.append(name)


class UnsignedIntPtrParam(PointerParameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT, Parameter.DIRECTION_INOUT]
    CTYPES = ['unsigned int*', 'uint32_t*']

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False,
                 default_value=None, transfer_ownership=False, array_length=None):
        super(UnsignedIntPtrParam, self).__init__(ctype, name, direction, is_const, default_value, transfer_ownership)
        self.array_length = array_length
        if transfer_ownership:
            raise NotSupportedError("%s: transfer_ownership=True not yet implemented." % ctype)

    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('I', ['*'+self.value])

        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter('I', [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'unsigned int*'
        if self.array_length is None:
            name = wrapper.declarations.declare_variable(str(self.type_traits.target), self.name)
            wrapper.call_params.append('&'+name)
            if self.direction & self.DIRECTION_IN:
                wrapper.parse_params.add_parameter('I', ['&'+name], self.name)
            if self.direction & self.DIRECTION_OUT:
                wrapper.build_params.add_parameter('I', [name])

        else: # complicated code path to deal with arrays...

            name = wrapper.declarations.declare_variable(str(self.type_traits.target), self.name, array="[%i]" % self.array_length)
            py_list = wrapper.declarations.declare_variable("PyObject*", "py_list")
            idx = wrapper.declarations.declare_variable("int", "idx")
            wrapper.call_params.append(name)
            if self.direction & self.DIRECTION_IN:
                elem = wrapper.declarations.declare_variable("PyObject*", "element")
                wrapper.parse_params.add_parameter('O!', ['&PyList_Type', '&'+py_list], self.name)
                wrapper.before_call.write_error_check(
                        'PyList_Size(%s) != %i' % (py_list, self.array_length),
                        'PyErr_SetString(PyExc_TypeError, "Parameter `%s\' must be a list of %i ints/longs");'
                        % (self.name, self.array_length))

                wrapper.before_call.write_code(
                    "for (%s = 0; %s < %i; %s++) {" % (idx, idx, self.array_length, idx))
                wrapper.before_call.indent()

                wrapper.before_call.write_code("%(elem)s = PyList_GET_ITEM(%(py_list)s, %(idx)s);" % vars())
                wrapper.before_call.write_error_check(
                        '!(PyInt_Check(%(elem)s) || PyLong_Check(%(elem)s))',
                        'PyErr_SetString(PyExc_TypeError, "Parameter `%s\' must be a list of %i ints / longs");'
                        % (self.name, self.array_length))
                wrapper.before_call.write_code("%(name)s[%(idx)s] = PyLong_AsUnsignedInt(%(elem)s);" % vars())

                wrapper.before_call.unindent()
                wrapper.before_call.write_code('}')

            if self.direction & self.DIRECTION_OUT:
                wrapper.after_call.write_code("%s = PyList_New(%i);" % (py_list, self.array_length))

                wrapper.after_call.write_code(
                    "for (%s = 0; %s < %i; %s++) {" % (idx, idx, self.array_length, idx))
                wrapper.after_call.indent()
                wrapper.after_call.write_code("PyList_SET_ITEM(%(py_list)s, %(idx)s, PyLong_FromUnsignedLong(%(name)s[%(idx)s]));"
                                              % vars())
                wrapper.after_call.unindent()
                wrapper.after_call.write_code('}')

                wrapper.build_params.add_parameter("N", [py_list])

class IntReturn(ReturnValue):

    CTYPES = ['int', 'int32_t']

    def get_c_error_return(self):
        return "return INT_MIN;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("i", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("i", [self.value], prepend=True)


class UnsignedIntReturn(ReturnValue):

    CTYPES = ['unsigned int', 'uint32_t']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("I", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter('N', ["PyLong_FromUnsignedLong(%s)" % self.value], prepend=True)


class IntPtrParam(PointerParameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['int*']

    def __init__(self, ctype, name, direction=None, is_const=None, transfer_ownership=None):
        if direction is None:
            if is_const:
                direction = Parameter.DIRECTION_IN
            else:
                raise TypeConfigurationError("direction not given")
        
        super(IntPtrParam, self).__init__(ctype, name, direction, is_const, transfer_ownership)

    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('i', ['*'+self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("i", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append('&'+name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('i', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("i", [name])
        


class IntRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['int&']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('i', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("i", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'int&'
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('i', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("i", [name])

class UnsignedIntRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['unsigned int&', 'unsigned &']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('I', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("I", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'int&'
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('I', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("I", [name])



class UInt16Return(ReturnValue):

    CTYPES = ['uint16_t', 'unsigned short', 'unsigned short int', 'short unsigned int']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        tmp_var = wrapper.declarations.declare_variable("int", "tmp")
        wrapper.parse_params.add_parameter("i", ["&"+tmp_var], prepend=True)
        wrapper.after_call.write_error_check('%s > 0xffff' % tmp_var,
                                             'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.after_call.write_code(
            "%s = %s;" % (self.value, tmp_var))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("i", [self.value], prepend=True)


class Int16Return(ReturnValue):

    CTYPES = ['int16_t', 'short', 'short int']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        tmp_var = wrapper.declarations.declare_variable("int", "tmp")
        wrapper.parse_params.add_parameter("i", ["&"+tmp_var], prepend=True)
        wrapper.after_call.write_error_check('%s > 32767 || %s < -32768' % (tmp_var, tmp_var),
                                             'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.after_call.write_code(
            "%s = %s;" % (self.value, tmp_var))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("i", [self.value], prepend=True)


class UInt16Param(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['uint16_t', 'unsigned short', 'unsigned short int']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('i', ["(int) "+self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("int", self.name, self.default_value)
        wrapper.parse_params.add_parameter('i', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.before_call.write_error_check('%s > 0xffff' % name,
                                              'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.call_params.append(name)

class UInt16RefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_INOUT, Parameter.DIRECTION_OUT]
    CTYPES = ['uint16_t&', 'unsigned short&', 'unsigned short int&', 'short unsigned&', 'short unsigned int&']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('H', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("H", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('H', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("H", [name])



class Int16Param(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['int16_t', 'short', 'short int']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('i', ["(int) "+self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("int", self.name, self.default_value)
        wrapper.parse_params.add_parameter('i', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.before_call.write_error_check('%s > 0x7fff' % name,
                                              'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.call_params.append(name)


class Int16RefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_INOUT, Parameter.DIRECTION_OUT]
    CTYPES = ['int16_t&', 'short&', 'short int&']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('h', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("h", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('h', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("h", [name])


class UInt8Param(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['uint8_t', 'unsigned char', 'char unsigned']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('i', ["(int) "+self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("int", self.name, self.default_value)
        wrapper.parse_params.add_parameter('i', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.before_call.write_error_check('%s > 0xff' % name,
                                              'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.call_params.append(name)

class UInt8RefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_INOUT, Parameter.DIRECTION_OUT]
    CTYPES = ['uint8_t&', 'unsigned char&', 'char unsigned&']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('B', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("B", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('B', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("B", [name])



class UInt8Return(ReturnValue):

    CTYPES = ['uint8_t', 'unsigned char', 'char unsigned']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        tmp_var = wrapper.declarations.declare_variable("int", "tmp")
        wrapper.parse_params.add_parameter("i", ["&"+tmp_var], prepend=True)
        wrapper.after_call.write_error_check('%s > 0xff' % tmp_var,
                                             'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.after_call.write_code(
            "%s = %s;" % (self.value, tmp_var))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("i", ['(int)' + self.value], prepend=True)

class Int8Param(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['int8_t', 'signed char', 'char signed']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('i', ["(int) "+self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("int", self.name, self.default_value)
        wrapper.parse_params.add_parameter('i', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.before_call.write_error_check('%s > 0x7f' % name,
                                              'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.call_params.append(name)

class Int8RefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_INOUT, Parameter.DIRECTION_OUT]
    CTYPES = ['int8_t&', 'signed char &', 'char signed&']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('b', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("b", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('b', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("b", [name])

class Int8Return(ReturnValue):

    CTYPES = ['int8_t', 'signed char']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        tmp_var = wrapper.declarations.declare_variable("int", "tmp")
        wrapper.parse_params.add_parameter("i", ["&"+tmp_var], prepend=True)
        wrapper.after_call.write_error_check('%s > 128 || %s < -127' % (tmp_var, tmp_var),
                                             'PyErr_SetString(PyExc_ValueError, "Out of range");')
        wrapper.after_call.write_code(
            "%s = %s;" % (self.value, tmp_var))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("i", [self.value], prepend=True)



class UnsignedLongLongParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['unsigned long long', 'uint64_t', 'unsigned long long int', 'long long unsigned int', 'long long unsigned']

    def get_ctype_without_ref(self):
        return str(self.type_traits.ctype_no_const)

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('K', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.get_ctype_without_ref(), self.name, self.default_value)
        wrapper.parse_params.add_parameter('K', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.call_params.append(name)

class UnsignedLongLongRefParam(UnsignedLongLongParam):
    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['unsigned long long&', 'uint64_t&', 'long long unsigned int&']

    def get_ctype_without_ref(self):
        assert self.type_traits.target is not None
        return str(self.type_traits.target)

class UnsignedLongLongReturn(ReturnValue):

    CTYPES = ['unsigned long long', 'uint64_t', 'long long unsigned int']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("K", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("K", [self.value], prepend=True)


class UnsignedLongParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['unsigned long', 'unsigned long int', 'long unsigned', 'long unsigned int']

    def get_ctype_without_ref(self):
        return str(self.type_traits.ctype_no_const)

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('k', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.get_ctype_without_ref(), self.name, self.default_value)
        wrapper.parse_params.add_parameter('k', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.call_params.append(name)

class UnsignedLongRefParam(UnsignedLongParam):
    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['unsigned long&', 'long unsigned&', 'long unsigned int&', 'unsigned long int&']

    def get_ctype_without_ref(self):
        assert self.type_traits.target is not None
        return str(self.type_traits.target)

class UnsignedLongReturn(ReturnValue):

    CTYPES = ['unsigned long', 'long unsigned int']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("k", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("k", [self.value], prepend=True)

class LongParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['signed long', 'signed long int', 'long', 'long int', 'long signed', 'long signed int']

    def get_ctype_without_ref(self):
        return str(self.type_traits.ctype_no_const)

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('l', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.get_ctype_without_ref(), self.name, self.default_value)
        wrapper.parse_params.add_parameter('l', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.call_params.append(name)

class LongRefParam(LongParam):
    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['signed long&', 'long signed&', 'long&', 'long int&', 'long signed int&', 'signed long int&']

    def get_ctype_without_ref(self):
        assert self.type_traits.target is not None
        return str(self.type_traits.target)

class LongReturn(ReturnValue):

    CTYPES = ['signed long', 'long signed int', 'long', 'long int']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("l", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("l", [self.value], prepend=True)


class SizeTReturn(ReturnValue):

    CTYPES = ['size_t', 'std::size_t']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        # using the intermediate variable is not always necessary but
        # it's safer this way in case of weird platforms where
        # sizeof(size_t) != sizeof(unsigned PY_LONG_LONG).
        name = wrapper.declarations.declare_variable("unsigned PY_LONG_LONG", "retval_tmp", self.value)
        wrapper.parse_params.add_parameter("K", ["&"+name], prepend=True)
        wrapper.after_call.write_code("retval = %s;" % (name))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("K", ["((unsigned PY_LONG_LONG) %s)" % self.value], prepend=True)


class SizeTParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['size_t', 'std::size_t']

    def get_ctype_without_ref(self):
        return str(self.type_traits.ctype_no_const)

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('K', ["((unsigned PY_LONG_LONG) %s)" % self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("unsigned PY_LONG_LONG", self.name, self.default_value)
        wrapper.parse_params.add_parameter('K', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.call_params.append(name)



class LongLongParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['long long', 'int64_t', 'long long int']

    def get_ctype_without_ref(self):
        return str(self.type_traits.ctype_no_const)

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('L', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.get_ctype_without_ref(), self.name, self.default_value)
        wrapper.parse_params.add_parameter('L', ['&'+name], self.name, optional=bool(self.default_value))
        wrapper.call_params.append(name)


class LongLongRefParam(LongLongParam):
    DIRECTIONS = [Parameter.DIRECTION_IN] # other directions not yet implemented
    CTYPES = ['long long&', 'int64_t&', 'long long int&']

    def get_ctype_without_ref(self):
        assert self.type_traits.target is not None
        return str(self.type_traits.target)

class LongLongReturn(ReturnValue):

    CTYPES = ['long long', 'int64_t', 'long long int']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("L", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("L", [self.value], prepend=True)


class Int8PtrParam(PointerParameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['int8_t*']

    def __init__(self, ctype, name, direction=None, is_const=None, default_value=None, transfer_ownership=None):
        if direction is None:
            if is_const:
                direction = Parameter.DIRECTION_IN
            else:
                raise TypeConfigurationError("direction not given")
        
        super(Int8PtrParam, self).__init__(ctype, name, direction, is_const, default_value, transfer_ownership)
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('b', ['*'+self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("b", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable('int8_t', self.name)
        wrapper.call_params.append('&'+name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('b', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("b", [name])

class UInt8PtrParam(PointerParameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['uint8_t*']

    def __init__(self, ctype, name, direction=None, is_const=None, default_value=None, transfer_ownership=None):
        if direction is None:
            if is_const:
                direction = Parameter.DIRECTION_IN
            else:
                raise TypeConfigurationError("direction not given")
        
        super(UInt8PtrParam, self).__init__(ctype, name, direction, is_const, default_value, transfer_ownership)
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('B', ['*'+self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("B", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable('uint8_t', self.name)
        wrapper.call_params.append('&'+name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('B', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("B", [name])



class UnsignedInt16PtrParam(PointerParameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT, Parameter.DIRECTION_INOUT]
    CTYPES = ['unsigned short int*', 'uint16_t*']

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False,
                 default_value=None, transfer_ownership=False):
        super(UnsignedInt16PtrParam, self).__init__(ctype, name, direction, is_const, default_value, transfer_ownership)
        if transfer_ownership:
            raise NotSupportedError("%s: transfer_ownership=True not yet implemented." % ctype)

    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('H', ['*'+self.value])

        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter('H', [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        name = wrapper.declarations.declare_variable(str(self.type_traits.target), self.name)
        wrapper.call_params.append('&'+name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('H', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter('H', [name])
