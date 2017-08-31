"""
Wraps enumerations
"""

from typehandlers import inttype
from typehandlers.base import return_type_matcher, param_type_matcher
from cppclass import CppClass

class Enum(object):
    """
    Class that adds support for a C/C++ enum type
    """
    def __init__(self, name, values, values_prefix='', cpp_namespace=None, outer_class=None,
                 import_from_module=None):
        """
        Creates a new enum wrapper, which should be added to a module with module.add_enum().

        :param name: C name of the enum type
        :param values: a list of strings with all enumeration value names, or list of (name, C-value-expr) tuples.
        :param values_prefix: prefix to add to value names, or None
        :param cpp_namespace: optional C++ namespace identifier, or None.
                         Note: this namespace is *in addition to*
                         whatever namespace of the module the enum
                         belongs to.  Typically this parameter is to
                         be used when wrapping enums declared inside
                         C++ classes.
        :param import_from_module: if not None, the enum is defined in
            another module, this parameter gives the name of the module
        """
        assert isinstance(name, basestring)
        assert '::' not in name
        assert outer_class is None or isinstance(outer_class, CppClass)
        self.outer_class = outer_class
        for val in values:
            if not isinstance(val, (basestring, tuple)):
                raise TypeError

        #if not name:
        #    raise ValueError
        self.name = name
        self.full_name = None
        self.values = list(values)
        self.values_prefix = values_prefix
        self.cpp_namespace = cpp_namespace
        self._module = None
        self.ThisEnumParameter = None
        self.ThisEnumReturn = None
        self.import_from_module = import_from_module

    def get_module(self):
        """Get the Module object this class belongs to"""
        return self._module

    def set_module(self, module):
        """Set the Module object this class belongs to; can only be set once"""
        assert self._module is None
        self._module = module

        if not self.name:
            return

        if self.outer_class is None:
            if self._module.cpp_namespace_prefix:
                if self._module.cpp_namespace_prefix == '::':
                    self.full_name = '::' + self.name
                else:
                    self.full_name = self._module.cpp_namespace_prefix + '::' + self.name
            else:
                self.full_name = self.name
        else:
            self.full_name = '::'.join([self.outer_class.full_name, self.name])

        ## Register type handlers for the enum type
        assert self.name
        assert self.full_name
        class ThisEnumParameter(inttype.IntParam):
            CTYPES = []
            full_type_name = self.full_name
            def __init__(self, ctype, name, *args, **kwargs):
                super(ThisEnumParameter, self).__init__(self.full_type_name, name, *args, **kwargs)

        class ThisEnumReturn(inttype.IntReturn):
            CTYPES = []
            full_type_name = self.full_name
            def __init__(self, ctype, *args, **kwargs):
                super(ThisEnumReturn, self).__init__(self.full_type_name, *args, **kwargs)

        class ThisEnumRefParameter(inttype.IntRefParam):
            CTYPES = []
            full_type_name = self.full_name + " &"
            def __init__(self, ctype, name, *args, **kwargs):
                super(ThisEnumRefParameter, self).__init__(self.full_type_name, name, *args, **kwargs)

        class ThisEnumPtrParameter(inttype.IntPtrParam):
            CTYPES = []
            full_type_name = self.full_name + " *"
            def __init__(self, ctype, name, *args, **kwargs):
                super(ThisEnumPtrParameter, self).__init__(self.full_type_name, name, *args, **kwargs)

        self.ThisEnumParameter = ThisEnumParameter
        self.ThisEnumReturn = ThisEnumReturn
        self.ThisEnumRefParameter = ThisEnumRefParameter
        self.ThisEnumPtrParameter = ThisEnumPtrParameter

        param_type_matcher.register(self.full_name, self.ThisEnumParameter)
        return_type_matcher.register(self.full_name, self.ThisEnumReturn)
        param_type_matcher.register(self.full_name + ' &', self.ThisEnumRefParameter)
        param_type_matcher.register(self.full_name + ' *', self.ThisEnumPtrParameter)

        if self.name != self.full_name:
            try:
                param_type_matcher.register(self.name, self.ThisEnumParameter)
            except ValueError:
                pass
            try:
                return_type_matcher.register(self.name, self.ThisEnumReturn)
            except ValueError:
                pass
            try:
                param_type_matcher.register(self.name+' &', self.ThisEnumRefParameter)
            except ValueError:
                pass
            try:
                param_type_matcher.register(self.name+' *', self.ThisEnumPtrParameter)
            except ValueError:
                pass


    module = property(get_module, set_module)

    def generate(self, unused_code_sink):
        if self.import_from_module:
            return #........ RET

        module = self.module
        if self.outer_class is None:
            namespace = []
            if module.cpp_namespace_prefix:
                namespace.append(module.cpp_namespace_prefix)
            if self.cpp_namespace:
                namespace.append(self.cpp_namespace)
            for value in self.values:
                if isinstance(value, tuple):
                    name, real_value = value
                    module.after_init.write_code(
                        "PyModule_AddIntConstant(m, (char *) \"%s\", %s);" % (name, real_value))
                else:
                    module.after_init.write_code(
                        "PyModule_AddIntConstant(m, (char *) \"%s\", %s);"
                        % (value, '::'.join(namespace + [self.values_prefix + value])))
        else:
            module.after_init.write_code("{")
            module.after_init.indent()
            module.after_init.write_code("PyObject *tmp_value;")
            for value in self.values:
                if isinstance(value, tuple):
                    value_name, value_str = value
                else:
                    value_name = value
                    value_str = "%s::%s" % (self.outer_class.full_name, value)
                module.after_init.write_code(
                    ' // %s\n'
                    'tmp_value = PyInt_FromLong(%s);\n'
                    'PyDict_SetItemString((PyObject*) %s.tp_dict, \"%s\", tmp_value);\n'
                    'Py_DECREF(tmp_value);'
                    % (
                    value_str, value_str, self.outer_class.pytypestruct, value_name))
            module.after_init.unindent()
            module.after_init.write_code("}")

    def generate_declaration(self, sink, module):
        pass

