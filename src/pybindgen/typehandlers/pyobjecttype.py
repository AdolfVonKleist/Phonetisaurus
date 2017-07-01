# docstrings not neede here (the type handler doubleerfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue, Parameter, \
     ReverseWrapperBase, ForwardWrapperBase


class PyObjectParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['PyObject*']

    def __init__(self, ctype, name, transfer_ownership, is_const=False):
        """
        :param ctype: C type, normally 'PyObject*'
        :param name: parameter name
        :param transfer_ownership: this parameter transfer the ownership of
                              the pointed-to object to the called
                              function
        """
        super(PyObjectParam, self).__init__(
            ctype, name, direction=Parameter.DIRECTION_IN, is_const=is_const)
        self.transfer_ownership = transfer_ownership

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        if self.transfer_ownership:
            wrapper.build_params.add_parameter('N', [self.value])
        else:
            wrapper.build_params.add_parameter('O', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype_no_const, self.name)
        wrapper.parse_params.add_parameter('O', ['&'+name], self.name)
        wrapper.call_params.append(name)
        if self.transfer_ownership:
            wrapper.before_call.write_code("Py_INCREF((PyObject*) %s);" % name)


class PyObjectReturnValue(ReturnValue):

    CTYPES = ['PyObject*']

    def __init__(self, ctype, caller_owns_return, is_const=False):
        """
        :param ctype: C type, normally 'MyClass*'
        :param caller_owns_return: if true, ownership of the object pointer
                              is transferred to the caller
        """
        super(PyObjectReturnValue, self).__init__(ctype, is_const)
        self.caller_owns_return = caller_owns_return

    def get_c_error_return(self):
        return "return NULL;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("O", ["&"+self.value], prepend=True)
        if self.caller_owns_return:
            wrapper.after_call.write_code("Py_INCREF((PyObject*) %s);" % self.value)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter(
            (self.caller_owns_return and "N" or "O"),
            [self.value], prepend=True)
