# docstrings not neede here (the type handler interfaces are fully
# documented in base.py) pylint: disable-msg=C0111

from base import ReturnValue, PointerReturnValue, Parameter, PointerParameter, ReverseWrapperBase, ForwardWrapperBase


class CStringParam(PointerParameter):
    """
    >>> isinstance(Parameter.new('char*', 's'), CStringParam)
    True
    """

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['char*']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('s', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        if self.default_value is None:
            name = wrapper.declarations.declare_variable(self.ctype_no_const, self.name)
            wrapper.parse_params.add_parameter('s', ['&'+name], self.value)
        else:
            name = wrapper.declarations.declare_variable(self.ctype_no_const,
                                                         self.name, self.default_value)
            wrapper.parse_params.add_parameter('s', ['&'+name], self.value, optional=True)
        wrapper.call_params.append(name)


class CharParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['char']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        wrapper.build_params.add_parameter('c', [self.value])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable(self.ctype_no_const, self.name)
        wrapper.parse_params.add_parameter('c', ['&'+name], self.value)
        wrapper.call_params.append(name)


class StdStringParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['std::string']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
        len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
        wrapper.before_call.write_code(
            "%s = (%s).c_str();" % (ptr, self.value))
        wrapper.before_call.write_code(
            "%s = (%s).size();" % (len_, self.value))
        wrapper.build_params.add_parameter('s#', [ptr, len_])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        if self.default_value is None:
            name = wrapper.declarations.declare_variable("const char *", self.name)
            name_len = wrapper.declarations.declare_variable("Py_ssize_t", self.name+'_len')
            wrapper.parse_params.add_parameter('s#', ['&'+name, '&'+name_len], self.value)
            wrapper.call_params.append('std::string(%s, %s)' % (name, name_len))
        else:
            name = wrapper.declarations.declare_variable("const char *", self.name, 'NULL')
            name_len = wrapper.declarations.declare_variable("Py_ssize_t", self.name+'_len')
            wrapper.parse_params.add_parameter('s#', ['&'+name, '&'+name_len], self.value, optional=True)
            wrapper.call_params.append('(%s ? std::string(%s, %s) : %s)'
                                       % (name, name, name_len, self.default_value))


class StdStringRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['std::string&']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)

        ptr = None
        if self.direction & Parameter.DIRECTION_IN:
            ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
            len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.before_call.write_code(
                "%s = (%s).c_str();" % (ptr, self.value))
            wrapper.before_call.write_code(
                "%s = (%s).size();" % (len_, self.value))
            wrapper.build_params.add_parameter('s#', [ptr, len_])

        if self.direction & Parameter.DIRECTION_OUT:
            if ptr is None:
                ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
                len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.parse_params.add_parameter("s#", ['&'+ptr, '&'+len_], self.value)
            wrapper.after_call.write_code(
                "%s = std::string(%s, %s);" % (self.value, ptr, len_))

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("const char *", self.name)
        name_len = wrapper.declarations.declare_variable("Py_ssize_t", self.name+'_len')
        name_std = wrapper.declarations.declare_variable("std::string", self.name + '_std')
        wrapper.call_params.append(name_std)

        if self.direction & Parameter.DIRECTION_IN:
            wrapper.parse_params.add_parameter('s#', ['&'+name, '&'+name_len], self.value)
            wrapper.before_call.write_code('%s = std::string(%s, %s);' %
                                           (name_std, name, name_len))

        if self.direction & Parameter.DIRECTION_OUT:
            wrapper.build_params.add_parameter("s#", ['('+name_std+').c_str()', '('+name_std+').size()'])


class StdStringPtrParam(PointerParameter):

    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['std::string*']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        ptr = None
        if self.direction & Parameter.DIRECTION_IN:
            ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
            len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.before_call.write_code(
                "%s = %s->c_str();" % (ptr, self.value))
            wrapper.before_call.write_code(
                "%s = %s->size();" % (len_, self.value))
            wrapper.build_params.add_parameter('s#', [ptr, len_])

        if self.direction & Parameter.DIRECTION_OUT:
            if ptr is None:
                ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
                len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.parse_params.add_parameter("s#", ['&'+ptr, '&'+len_], self.value)
            wrapper.after_call.write_code(
                "*%s = std::string(%s, %s);" % (self.value, ptr, len_))
        if self.transfer_ownership:
            wrapper.after_call.write_code("delete %s;" % (self.value,))
            

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        assert self.default_value is None, "default_value not implemented yet"
        name = wrapper.declarations.declare_variable("const char *", self.name)
        name_len = wrapper.declarations.declare_variable("Py_ssize_t", self.name+'_len')
        if self.transfer_ownership:
            name_std = wrapper.declarations.declare_variable("std::string*", self.name + '_std', 'new std::string')
            wrapper.call_params.append('%s' % name_std)
            name_std_value = '*' + name_std
        else:
            name_std = wrapper.declarations.declare_variable("std::string", self.name + '_std')
            wrapper.call_params.append('&%s' % name_std)
            name_std_value = name_std

        if self.direction & Parameter.DIRECTION_IN:
            wrapper.parse_params.add_parameter('s#', ['&'+name, '&'+name_len], self.value)
            wrapper.before_call.write_code('%s = std::string(%s, %s);' %
                                           (name_std_value, name, name_len))

        if self.direction & Parameter.DIRECTION_OUT:
            wrapper.build_params.add_parameter("s#", ['('+name_std_value+').c_str()', '('+name_std_value+').size()'])


class CharReturn(ReturnValue):

    CTYPES = ['char']

    def get_c_error_return(self):
        return "return '\\0';"

    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("c", ['&'+self.value], prepend=True)

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("c", ["(int) %s" % self.value])


class CStringReturn(PointerReturnValue):
    """
    >>> isinstance(ReturnValue.new('char*'), CStringReturn)
    True
    """

    CTYPES = ['char*']

    def get_c_error_return(self):
        return "return NULL;"

    def convert_python_to_c(self, wrapper):
        wrapper.parse_params.add_parameter("s", ['&'+self.value])

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("s", [self.value])


class StdStringReturn(ReturnValue):

    CTYPES = ['std::string']

    def get_c_error_return(self):
        return "return std::string();"
    
    def convert_python_to_c(self, wrapper):
        ptr = wrapper.declarations.declare_variable("const char *", "retval_ptr")
        len_ = wrapper.declarations.declare_variable("Py_ssize_t", "retval_len")
        wrapper.parse_params.add_parameter("s#", ['&'+ptr, '&'+len_])
        wrapper.after_call.write_code(
            "%s = std::string(%s, %s);" % (self.value, ptr, len_))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("s#", ['(%s).c_str()' % self.value,
                                                  '(%s).size()' % self.value],
                                           prepend=True)



class GlibStringParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['Glib::ustring']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
        len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
        wrapper.before_call.write_code(
            "%s = (%s).c_str();" % (ptr, self.value))
        wrapper.before_call.write_code(
            "%s = (%s).bytes();" % (len_, self.value))
        wrapper.build_params.add_parameter('s#', [ptr, len_])

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        if self.default_value is None:
            name = wrapper.declarations.declare_variable("const char *", self.name)
            wrapper.parse_params.add_parameter('et', ['"utf-8"', '&'+name], self.value)
            wrapper.call_params.append('Glib::ustring(%s)' % (name))
        else:
            name = wrapper.declarations.declare_variable("const char *", self.name, 'NULL')
            wrapper.parse_params.add_parameter('et', ['"utf-8"', '&'+name], self.value, optional=True)
            wrapper.call_params.append('(%s ? Glib::ustring(%s) : %s)'
                                       % (name, name, self.default_value))


class GlibStringRefParam(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['Glib::ustring&']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)

        ptr = None
        if self.direction & Parameter.DIRECTION_IN:
            ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
            len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.before_call.write_code(
                "%s = (%s).c_str();" % (ptr, self.value))
            wrapper.before_call.write_code(
                "%s = (%s).bytes();" % (len_, self.value))
            wrapper.build_params.add_parameter('s#', [ptr, len_])

        if self.direction & Parameter.DIRECTION_OUT:
            if ptr is None:
                ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
            wrapper.parse_params.add_parameter("et", ['"utf-8"', '&'+ptr], self.value)
            wrapper.after_call.write_code(
                "%s = Glib::ustring(%s);" % (self.value, ptr))

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        name = wrapper.declarations.declare_variable("const char *", self.name)
        name_std = wrapper.declarations.declare_variable("Glib::ustring", self.name + '_std')
        wrapper.call_params.append(name_std)

        if self.direction & Parameter.DIRECTION_IN:
            wrapper.parse_params.add_parameter('et', ['"utf-8"', '&'+name], self.value)
            wrapper.before_call.write_code('%s = Glib::ustring(%s);' %
                                           (name_std, name))

        if self.direction & Parameter.DIRECTION_OUT:
            wrapper.build_params.add_parameter("s#", ['('+name_std+').c_str()', '('+name_std+').bytes()'])


class GlibStringPtrParam(PointerParameter):

    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_IN|Parameter.DIRECTION_OUT]
    CTYPES = ['Glib::ustring*']
    
    def convert_c_to_python(self, wrapper):
        assert isinstance(wrapper, ReverseWrapperBase)
        ptr = None
        if self.direction & Parameter.DIRECTION_IN:
            ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
            len_ = wrapper.declarations.declare_variable("Py_ssize_t", self.name + "_len")
            wrapper.before_call.write_code(
                "%s = %s->c_str();" % (ptr, self.value))
            wrapper.before_call.write_code(
                "%s = %s->bytes();" % (len_, self.value))
            wrapper.build_params.add_parameter('s#', [ptr, len_])

        if self.direction & Parameter.DIRECTION_OUT:
            if ptr is None:
                ptr = wrapper.declarations.declare_variable("const char *", self.name + "_ptr")
            wrapper.parse_params.add_parameter("et", ['"utf-8"', '&'+ptr], self.value)
            wrapper.after_call.write_code(
                "*%s = Glib::ustring(%s);" % (self.value, ptr))
        if self.transfer_ownership:
            wrapper.after_call.write_code("delete %s;" % (self.value,))
            

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)
        assert self.default_value is None, "default_value not implemented yet"
        name = wrapper.declarations.declare_variable("const char *", self.name)
        if self.transfer_ownership:
            name_std = wrapper.declarations.declare_variable("Glib::ustring*", self.name + '_std', 'new Glib::ustring')
            wrapper.call_params.append('%s' % name_std)
            name_std_value = '*' + name_std
        else:
            name_std = wrapper.declarations.declare_variable("Glib::ustring", self.name + '_std')
            wrapper.call_params.append('&%s' % name_std)
            name_std_value = name_std

        if self.direction & Parameter.DIRECTION_IN:
            wrapper.parse_params.add_parameter('et', ['"utf-8"', '&'+name], self.value)
            wrapper.before_call.write_code('%s = Glib::ustring(%s);' %
                                           (name_std_value, name))

        if self.direction & Parameter.DIRECTION_OUT:
            wrapper.build_params.add_parameter("s#", ['('+name_std_value+').c_str()', '('+name_std_value+').bytes()'])


class GlibStringReturn(ReturnValue):

    CTYPES = ['Glib::ustring']

    def get_c_error_return(self):
        return "return Glib::ustring();"
    
    def convert_python_to_c(self, wrapper):
        ptr = wrapper.declarations.declare_variable("const char *", "retval_ptr")
        wrapper.parse_params.add_parameter("et", ['"utf-8"', '&'+ptr])
        wrapper.after_call.write_code(
            "%s = Glib::ustring(%s);" % (self.value, ptr))

    def convert_c_to_python(self, wrapper):
        wrapper.build_params.add_parameter("s#", ['(%s).c_str()' % self.value,
                                                  '(%s).bytes()' % self.value],
                                           prepend=True)

