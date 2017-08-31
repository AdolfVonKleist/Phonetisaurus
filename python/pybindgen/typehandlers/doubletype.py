# docstrings not neede here (the type handler doubleerfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue, Parameter, \
     ReverseWrapperBase, ForwardWrapperBase


class DoubleParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['double']

    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('d', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype_no_const, self.name, self.default_value)
        wrapper.parse_params.add_parameter('d', ['&'+name], self.value, optional=bool(self.default_value))
        wrapper.call_params.append(name)


class DoubleReturn(ReturnValue):

    CTYPES = ['double']

    def get_c_error_return(self):
        return "return 0;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("d", ["&"+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("d", [self.value], prepend=True)


class DoublePtrParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['double*']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('d', ['*'+self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("d", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'double*'
        name = wrapper.declarations.declare_variable(self.ctype_no_const[:-1], self.name)
        wrapper.call_params.append('&'+name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('d', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("d", [name])
        


class DoubleRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['double&']
    
    def convert_c_to_python(self, wrapper):
        if self.direction & self.DIRECTION_IN:
            wrapper.build_params.add_parameter('d', [self.value])
        if self.direction & self.DIRECTION_OUT:
            wrapper.parse_params.add_parameter("d", [self.value], self.name)

    def convert_python_to_c(self, wrapper):
        #assert self.ctype == 'double&'
        name = wrapper.declarations.declare_variable('double', self.name)
        wrapper.call_params.append(name)
        if self.direction & self.DIRECTION_IN:
            wrapper.parse_params.add_parameter('d', ['&'+name], self.name)
        if self.direction & self.DIRECTION_OUT:
            wrapper.build_params.add_parameter("d", [name])
