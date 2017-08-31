"""
Wraps C++ class instance/static attributes.
"""

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase
from typehandlers import codesink
import settings
import utils


class PyGetter(ForwardWrapperBase):
    """generates a getter, for use in a PyGetSetDef table"""
    def generate(self, code_sink):
        """Generate the code of the getter to the given code sink"""
        raise NotImplementedError
    def generate_call(self):
        """(not actually called)"""
        raise AssertionError

class PySetter(ReverseWrapperBase):
    """generates a setter, for use in a PyGetSetDef table"""
    NO_GIL_LOCKING = True
    def generate(self, code_sink):
        """Generate the code of the setter to the given code sink"""
        raise NotImplementedError
    def generate_python_call(self):
        """(not actually called)"""
        raise AssertionError


class CppInstanceAttributeGetter(PyGetter):
    '''
    A getter for a C++ instance attribute.
    '''
    def __init__(self, value_type, class_, attribute_name, getter=None):
        """
        :param value_type: a ReturnValue object handling the value type;
        :param class_: the class (CppClass object)
        :param attribute_name: name of attribute
        :param getter: None, or name of a method of the class used to get the value
        """
        super(CppInstanceAttributeGetter, self).__init__(
            value_type, [], "return NULL;", "return NULL;", no_c_retval=True)
        self.class_ = class_
        self.attribute_name = attribute_name
        self.getter = getter
        self.c_function_name = "_wrap_%s__get_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
        if self.getter is None:
            value_type.value = "self->obj->%s" % self.attribute_name
        else:
            value_type.value = "self->obj->%s()" % self.getter

    def generate_call(self):
        "virtual method implementation; do not call"
        pass

    def generate(self, code_sink):
        """
        :param code_sink: a CodeSink instance that will receive the generated code
        """
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject* %s(%s *self, void * PYBINDGEN_UNUSED(closure))"
                          % (self.c_function_name, self.class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')


class CppStaticAttributeGetter(PyGetter):
    '''
    A getter for a C++ class static attribute.
    '''
    def __init__(self, value_type, class_, attribute_name):
        """
        :param value_type: a ReturnValue object handling the value type;
        :param c_value_expression: C value expression
        """
        super(CppStaticAttributeGetter, self).__init__(
            value_type, [], "return NULL;", "return NULL;", no_c_retval=True)
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__get_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
        value_type.value = "%s::%s" % (self.class_.full_name, self.attribute_name)

    def generate_call(self):
        "virtual method implementation; do not call"
        pass

    def generate(self, code_sink):
        """
        :param code_sink: a CodeSink instance that will receive the generated code
        """
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject* %s(PyObject * PYBINDGEN_UNUSED(obj),"
                          " void * PYBINDGEN_UNUSED(closure))"
                          % self.c_function_name)
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')




class CppInstanceAttributeSetter(PySetter):
    '''
    A setter for a C++ instance attribute.
    '''
    def __init__(self, value_type, class_, attribute_name, setter=None):
        """
        :param value_type: a ReturnValue object handling the value type;
        :param class_: the class (CppClass object)
        :param attribute_name: name of attribute
        :param setter: None, or name of a method of the class used to set the value
        """
        super(CppInstanceAttributeSetter, self).__init__(
            value_type, [], "return -1;")
        self.class_ = class_
        self.attribute_name = attribute_name
        self.setter = setter
        self.c_function_name = "_wrap_%s__set_%s" % (self.class_.pystruct,
                                                     self.attribute_name)

    def generate(self, code_sink):
        """
        :param code_sink: a CodeSink instance that will receive the generated code
        """

        self.declarations.declare_variable('PyObject*', 'py_retval')
        self.before_call.write_code(
            'py_retval = Py_BuildValue((char *) "(O)", value);')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')

        if self.setter is not None:
            ## if we have a setter method, redirect the value to a temporary variable
            if not self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
                value_var = self.declarations.declare_variable(self.return_value.ctype, 'tmp_value')
            else:
                value_var = self.declarations.reserve_variable('tmp_value')
            self.return_value.value = value_var
        else:
            ## else the value is written directly to a C++ instance attribute
            self.return_value.value = "self->obj->%s" % self.attribute_name
            self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR = False

        self.return_value.convert_python_to_c(self)

        parse_tuple_params = ['py_retval']
        params = self.parse_params.get_parameters()
        assert params[0][0] == '"'
        params[0] = '(char *) ' + params[0]
        parse_tuple_params.extend(params)
        self.before_call.write_error_check('!PyArg_ParseTuple(%s)' %
                                           (', '.join(parse_tuple_params),))

        if self.setter is not None:
            ## if we have a setter method, now is the time to call it
            self.after_call.write_code("self->obj->%s(%s);" % (self.setter, value_var))

        ## cleanup and return
        self.after_call.write_cleanup()
        self.after_call.write_code('return 0;')

        ## now generate the function itself
        code_sink.writeln("static int %s(%s *self, PyObject *value, void * PYBINDGEN_UNUSED(closure))"
                          % (self.c_function_name, self.class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()

        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

        code_sink.unindent()
        code_sink.writeln('}')


class CppStaticAttributeSetter(PySetter):
    '''
    A setter for a C++ class static attribute.
    '''
    def __init__(self, value_type, class_, attribute_name):
        """
        :param value_type: a ReturnValue object handling the value type;
        :param class_: the class (CppClass object)
        :param attribute_name: name of attribute
        """
        super(CppStaticAttributeSetter, self).__init__(
            value_type, [], "return -1;")
        self.class_ = class_
        self.attribute_name = attribute_name
        self.c_function_name = "_wrap_%s__set_%s" % (self.class_.pystruct,
                                                     self.attribute_name)
        value_type.value =  "%s::%s" % (self.class_.full_name, self.attribute_name)
        value_type.REQUIRES_ASSIGNMENT_CONSTRUCTOR = False

    def generate(self, code_sink):
        """
        :param code_sink: a CodeSink instance that will receive the generated code
        """

        self.declarations.declare_variable('PyObject*', 'py_retval')
        self.before_call.write_code(
            'py_retval = Py_BuildValue((char *) "(O)", value);')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')
        self.return_value.convert_python_to_c(self)
        parse_tuple_params = ['py_retval']
        params = self.parse_params.get_parameters()
        assert params[0][0] == '"'
        params[0] = '(char *) ' + params[0]
        parse_tuple_params.extend(params)
        self.before_call.write_error_check('!PyArg_ParseTuple(%s)' %
                                           (', '.join(parse_tuple_params),))
        ## cleanup and return
        self.after_call.write_cleanup()
        self.after_call.write_code('return 0;')

        ## now generate the function itself
        code_sink.writeln(("static int %s(%s * PYBINDGEN_UNUSED(dummy), "
                           "PyObject *value, void * PYBINDGEN_UNUSED(closure))")
                          % (self.c_function_name, self.class_.pystruct))
        code_sink.writeln('{')
        code_sink.indent()

        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

        code_sink.unindent()
        code_sink.writeln('}')


class PyMetaclass(object):
    """
    Class that generates a Python metaclass
    """
    def __init__(self, name, parent_metaclass_expr, getsets=None):
        """
        :param name: name of the metaclass (should normally end with Meta)
        :param parent_metaclass_expr: C expression that should give a
                                 pointer to the parent metaclass
                                 (should have a C type of
                                 PyTypeObject*)
        :param getsets: name of a PyGetSetDef C array variable, or None
        """
        assert getsets is None or isinstance(getsets, PyGetSetDef)
        assert isinstance(name, basestring)
        assert isinstance(parent_metaclass_expr, basestring)

        self.name = name
        prefix = settings.name_prefix.capitalize()
        self.pytypestruct = "Py%s%s_Type" % (prefix, self.name)
        self.parent_metaclass_expr = parent_metaclass_expr
        self.getsets = getsets

    def generate(self, code_sink, module):
        """
        Generate the metaclass to code_sink and register it in the module.
        """
        code_sink.writeln('''
PyTypeObject %(pytypestruct)s = {
	PyObject_HEAD_INIT(NULL)
	0,					/* ob_size */
	(char *) "%(name)s",		        /* tp_name */
	0,					/* tp_basicsize */
	0,					/* tp_itemsize */
	0,	 				/* tp_dealloc */
	0,					/* tp_print */
	0,					/* tp_getattr */
	0,					/* tp_setattr */
	0,					/* tp_compare */
	0,					/* tp_repr */
	0,					/* tp_as_number */
	0,					/* tp_as_sequence */
	0,		       			/* tp_as_mapping */
	0,					/* tp_hash */
	0,					/* tp_call */
	0,					/* tp_str */
	0,					/* tp_getattro */
	0,					/* tp_setattro */
	0,					/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT|Py_TPFLAGS_HAVE_GC|Py_TPFLAGS_BASETYPE, /* tp_flags */
 	0,					/* tp_doc */
	0,					/* tp_traverse */
 	0,					/* tp_clear */
	0,					/* tp_richcompare */
	0,					/* tp_weaklistoffset */
	0,					/* tp_iter */
	0,					/* tp_iternext */
	0,					/* tp_methods */
	0,					/* tp_members */
	%(getset)s,				/* tp_getset */
	0,					/* tp_base */
	0,					/* tp_dict */
	0,	                                /* tp_descr_get */
	0,  		                        /* tp_descr_set */
	0,					/* tp_dictoffset */
	0,					/* tp_init */
	0,					/* tp_alloc */
	0,					/* tp_new */
	0,               			/* tp_free */
        0,                                      /* tp_is_gc */
        0,                                      /* tp_bases */
        0,                                      /* tp_mro */
        0,                                      /* tp_cache */
        0,                                      /* tp_subclasses */
        0,                                      /* tp_weaklist */
        0                                       /* tp_del */
};
''' % dict(pytypestruct=self.pytypestruct, name=self.name,
           getset=(self.getsets and self.getsets.cname or '0')))

        module.after_init.write_code("""
%(pytypestruct)s.tp_base = %(parent_metaclass)s;
/* Some fields need to be manually inheritted from the parent metaclass */
%(pytypestruct)s.tp_traverse = %(parent_metaclass)s->tp_traverse;
%(pytypestruct)s.tp_clear = %(parent_metaclass)s->tp_clear;
%(pytypestruct)s.tp_is_gc = %(parent_metaclass)s->tp_is_gc;
/* PyType tp_setattro is too restrictive */
%(pytypestruct)s.tp_setattro = PyObject_GenericSetAttr;
PyType_Ready(&%(pytypestruct)s);
""" % dict(pytypestruct=self.pytypestruct, parent_metaclass=self.parent_metaclass_expr))
        


class PyGetSetDef(object):
    """
    Class that generates a PyGetSet table
    """
    def __init__(self, cname):
        """
        :param cname: C name of the getset table
        """
        self.cname = cname
        self.attributes = [] # (name, getter, setter)

    def empty(self):
        return len(self.attributes) == 0

    def add_attribute(self, name, getter, setter):
        """
        Add a new attribute
        :param name: attribute name
        :param getter: a PyGetter object, or None
        :param setter: a PySetter object, or None
        """
        assert getter is None or isinstance(getter, PyGetter)
        assert setter is None or isinstance(setter, PySetter)
        self.attributes.append((name, getter, setter))

    def generate(self, code_sink):
        """
        Generate the getset table, return the table C name or '0' if
        the table is empty
        """
        if not self.attributes:
            return '0'

        getsets = {} # attrname -> (getter, setter)
        for name, getter, setter in self.attributes:

            getter_name = 'NULL'
            if getter is not None:
                # getter.generate(code_sink)
                try:
                    utils.call_with_error_handling(getter.generate, (code_sink,), {}, getter)
                except utils.SkipWrapper:
                    pass
                else:
                    getter_name = getter.c_function_name

            setter_name = 'NULL'
            if setter is not None:
                #setter.generate(code_sink)
                try:
                    utils.call_with_error_handling(setter.generate, (code_sink,), {}, setter)
                except utils.SkipWrapper:
                    pass
                else:
                    setter_name = setter.c_function_name
            assert name not in getsets
            getsets[name] = (getter_name, setter_name)
        
        code_sink.writeln("static PyGetSetDef %s[] = {" % self.cname)
        code_sink.indent()
        for name, (getter_c_name, setter_c_name) in getsets.iteritems():
            code_sink.writeln('{')
            code_sink.indent()
            code_sink.writeln('(char*) "%s", /* attribute name */' % name)

            ## getter
            code_sink.writeln(
                '(getter) %s, /* C function to get the attribute */'
                % getter_c_name)

            ## setter
            code_sink.writeln(
                '(setter) %s, /* C function to set the attribute */'
                % setter_c_name)

            code_sink.writeln('NULL, /* optional doc string */')
            code_sink.writeln('NULL /* optional additional data '
                              'for getter and setter */')
            code_sink.unindent()
            code_sink.writeln('},')
        code_sink.writeln('{ NULL, NULL, NULL, NULL, NULL }')
        code_sink.unindent()
        code_sink.writeln('};')

        return self.cname
        
