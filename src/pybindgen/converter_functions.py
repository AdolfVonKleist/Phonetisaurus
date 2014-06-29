"""
Generates simple converter functions that convert a single value from
python to C or C to python.  These can be useful in certain
specialized contexts, such as converting list elements.
"""

from typehandlers.base import ReverseWrapperBase, ForwardWrapperBase
from typehandlers import ctypeparser

class PythonToCConverter(ReverseWrapperBase):
    '''
    Utility function that converts a single Python object into a C
    value.  The generated function can be used as a 'converter
    function' with the O& converter of PyArg_ParseTuple*.
    '''
    NO_GIL_LOCKING = True

    def __init__(self, value_type, c_function_name):
        """
        value_type -- a ReturnValue object handling the value type;
        class_ -- the class (CppClass object)
        attribute_name -- name of attribute
        getter -- None, or name of a method of the class used to get the value
        """
        self.c_function_name = c_function_name

        if value_type.type_traits.type_is_reference:
            value_type.type_traits = ctypeparser.TypeTraits(str(value_type.type_traits.target))
        value_type.ctype = str(value_type.ctype)

        self.type_no_ref = str(value_type.type_traits.ctype_no_modifiers)
        super(PythonToCConverter, self).__init__(value_type, [], error_return="return 0;")

    def generate_python_call(self):
        pass

    def generate(self, code_sink, wrapper_name, dummy_decl_modifiers=('static',),
                 dummy_decl_post_modifiers=()):
        """
        code_sink -- a CodeSink instance that will receive the generated code
        """
        
        self.declarations.declare_variable('PyObject*', 'py_retval')
        self.before_call.write_code(
            'py_retval = Py_BuildValue((char *) "(O)", value);')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')

        save_return_value_value = self.return_value.value
        save_return_value_REQUIRES_ASSIGNMENT_CONSTRUCTOR = self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR
        self.return_value.value = "*address"
        self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR = False
        try:
            self.return_value.convert_python_to_c(self)
        finally:
            self.return_value.value = save_return_value_value
            self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR = save_return_value_REQUIRES_ASSIGNMENT_CONSTRUCTOR

        parse_tuple_params = ['py_retval']
        params = self.parse_params.get_parameters()
        assert params[0][0] == '"'
        params[0] = '(char *) ' + params[0]
        parse_tuple_params.extend(params)
        self.before_call.write_error_check('!PyArg_ParseTuple(%s)' %
                                           (', '.join(parse_tuple_params),))

        ## cleanup and return
        self.after_call.write_cleanup()
        self.after_call.write_code('return 1;')

        ## now generate the function itself
        code_sink.writeln("int %s(PyObject *value, %s *address)"
                          % (wrapper_name, self.type_no_ref))
        code_sink.writeln('{')
        code_sink.indent()

        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

        code_sink.unindent()
        code_sink.writeln('}')

    def get_prototype(self):
        return "int %s(PyObject *value, %s *address)" % (self.c_function_name, self.type_no_ref)



class CToPythonConverter(ForwardWrapperBase):
    '''
    Utility function that converts a C value to a PyObject*.
    '''

    def __init__(self, value_type, c_function_name):
        """
        value_type -- a ReturnValue object handling the value type;
        class_ -- the class (CppClass object)
        attribute_name -- name of attribute
        getter -- None, or name of a method of the class used to get the value
        """
        super(CToPythonConverter, self).__init__(value_type, [], parse_error_return="return 0;", error_return="return 0;",
                                                 no_c_retval=True)
        self.c_function_name = c_function_name
        self.unblock_threads = False

    def generate(self, code_sink):

        save_return_value_value = self.return_value.value
        self.return_value.value = "*cvalue"
        try:
            self.return_value.convert_c_to_python(self)
        finally:
            self.return_value.value = save_return_value_value

        code_sink.writeln(self.get_prototype())
        code_sink.writeln("{")
        code_sink.indent()


        params = self.build_params.get_parameters()
        if params:
            if params == ['""']:
                self.after_call.write_code('Py_INCREF(Py_None);')
                self.after_call.write_code('py_retval = Py_None;')
            else:
                assert params[0][0] == '"'
                params[0] = "(char *) " + params[0]
                self.after_call.write_code('py_retval = Py_BuildValue(%s);' %
                                           (', '.join(params),))

        ## cleanup and return
        self.after_call.write_cleanup()
        self.after_call.write_code('return py_retval;')

        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_parse.sink.flush_to(code_sink)
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln("}")

    def get_prototype(self):
        return "PyObject* %s(%s *cvalue)" % (self.c_function_name, self.return_value.ctype)
