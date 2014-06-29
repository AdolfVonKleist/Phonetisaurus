# docstrings not neede here (the type handler interfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue


class VoidReturn(ReturnValue):

    CTYPES = ['void']
    
    def get_c_error_return(self):
        return "return;"
    
    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("", [], prepend=True)

    def convert_c_to_python(self, wrapper):
        pass
