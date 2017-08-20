"""
Add container iteration powers to wrapped C++ classes
"""

from typehandlers.base import ForwardWrapperBase
from typehandlers import codesink
from pytypeobject import PyTypeObject
import utils


class IterNextWrapper(ForwardWrapperBase):
    '''
    tp_iternext wrapper
    '''

    HAVE_RETURN_VALUE = True

    def __init__(self, container):
        """
        value_type -- a ReturnValue object handling the value type;
        container -- the L{Container}
        """
        super(IterNextWrapper, self).__init__(
            None, [], "return NULL;", "return NULL;", no_c_retval=True)
        assert isinstance(container, CppClassContainerTraits)
        self.container = container
        self.c_function_name = "_wrap_%s__tp_iternext" % (self.container.iter_pystruct)
        self.iter_variable_name = None
        self.reset_code_generation_state()

    def reset_code_generation_state(self):
        super(IterNextWrapper, self).reset_code_generation_state()
        self.iter_variable_name = self.declarations.declare_variable(
            "%s::%s" % (self.container.cppclass.full_name, self.container.iterator_type), 'iter')

    def generate_call(self):
        self.before_call.write_code("%s = *self->iterator;" % (self.iter_variable_name,))
        self.before_call.write_error_check(
            "%s == self->container->obj->%s()" % (self.iter_variable_name, self.container.end_method),
            "PyErr_SetNone(PyExc_StopIteration);")
        self.before_call.write_code("++(*self->iterator);")
        if self.container.key_type is None:
            self.container.value_type.value = "(*%s)" % self.iter_variable_name
            self.container.value_type.convert_c_to_python(self)
        else:
            self.container.value_type.value = "%s->second" % self.iter_variable_name
            self.container.value_type.convert_c_to_python(self)
            self.container.key_type.value = "%s->first" % self.iter_variable_name
            self.container.key_type.convert_c_to_python(self)

    def generate(self, code_sink):
        """
        code_sink -- a CodeSink instance that will receive the generated code
        """
        
        tmp_sink = codesink.MemoryCodeSink()
        self.generate_body(tmp_sink)
        code_sink.writeln("static PyObject* %s(%s *self)" % (self.c_function_name,
                                                             self.container.iter_pystruct))
        code_sink.writeln('{')
        code_sink.indent()
        tmp_sink.flush_to(code_sink)
        code_sink.unindent()
        code_sink.writeln('}')


class CppClassContainerTraits(object):
    def __init__(self, cppclass, value_type, begin_method='begin', end_method='end', iterator_type='iterator', is_mapping=False):
        """
        :param cppclass: the L{CppClass} object that receives the container traits

        :param value_type: a ReturnValue of the element type: note,
        for mapping containers, value_type is a tuple with two
        ReturnValue's: (key, element).
        """
        self.cppclass = cppclass
        self.begin_method = begin_method
        self.end_method = end_method
        self.iterator_type = iterator_type

        self.iter_pytype = PyTypeObject()
        self._iter_pystruct = None

        if is_mapping:
            (key_type, value_type) = value_type
            self.key_type = utils.eval_retval(key_type, self)
            self.value_type = utils.eval_retval(value_type, self)
        else:
            self.key_type = None
            self.value_type = utils.eval_retval(value_type, self)

    def get_iter_pystruct(self):
        return "%s_Iter" % self.cppclass.pystruct
    iter_pystruct = property(get_iter_pystruct)

    def get_iter_pytypestruct(self):
        return "%s_IterType" % self.cppclass.pystruct
    iter_pytypestruct = property(get_iter_pytypestruct)


    def generate_forward_declarations(self, code_sink, dummy_module):
        """
        Generates forward declarations for the instance and type
        structures.
        """

        # container iterator pystruct
        code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *container;
    %s::%s *iterator;
} %s;
    ''' % (self.cppclass.pystruct, self.cppclass.full_name, self.iterator_type, self.iter_pystruct))

        code_sink.writeln()
        code_sink.writeln('extern PyTypeObject %s;' % (self.iter_pytypestruct,))
        code_sink.writeln()

    def get_iter_python_name(self):
        return "%sIter" % self.cppclass.get_python_name()

    def get_iter_python_full_name(self, module):
        if self.cppclass.outer_class is None:
            mod_path = module.get_module_path()
            mod_path.append(self.get_iter_python_name())
            return '.'.join(mod_path)
        else:
            return '%s.%s' % (self.cppclass.outer_class.pytype.slots['tp_name'],
                              self.get_iter_python_name())


    def generate(self, code_sink, module, docstring=None):
        """Generates the class to a code sink"""

        ## --- register the iter type in the module ---
        module.after_init.write_code("/* Register the '%s' class iterator*/" % self.cppclass.full_name)
        module.after_init.write_error_check('PyType_Ready(&%s)' % (self.iter_pytypestruct,))

        if self.cppclass.outer_class is None:
            module.after_init.write_code(
                'PyModule_AddObject(m, (char *) \"%s\", (PyObject *) &%s);' % (
                self.get_iter_python_name(), self.iter_pytypestruct))
        else:
            module.after_init.write_code(
                'PyDict_SetItemString((PyObject*) %s.tp_dict, (char *) \"%s\", (PyObject *) &%s);' % (
                self.cppclass.outer_class.pytypestruct, self.cppclass.get_iter_python_name(), self.iter_pytypestruct))

        self._generate_gc_methods(code_sink)
        self._generate_destructor(code_sink)
        self._generate_iter_methods(code_sink)
        self._generate_type_structure(code_sink, module, docstring)
        
    def _generate_type_structure(self, code_sink, module, docstring):
        """generate the type structure"""
        self.iter_pytype.slots.setdefault("tp_basicsize", "sizeof(%s)" % (self.iter_pystruct,))
        self.iter_pytype.slots.setdefault("tp_flags", ("Py_TPFLAGS_DEFAULT|Py_TPFLAGS_HAVE_GC"))
        self.iter_pytype.slots.setdefault("typestruct", self.iter_pytypestruct)
        self.iter_pytype.slots.setdefault("tp_name", self.get_iter_python_full_name(module))
        if docstring:
            self.iter_pytype.slots.setdefault("tp_doc", '"%s"' % docstring)
        self.iter_pytype.generate(code_sink)

    def _get_iter_delete_code(self):
        delete_code = ("delete self->iterator;\n"
                       "    self->iterator = NULL;\n")
        return delete_code

    def _get_container_delete_code(self):
        delete_code = ("delete self->obj;\n"
                       "    self->obj = NULL;\n")
        return delete_code

    def _generate_gc_methods(self, code_sink):
        """Generate tp_clear and tp_traverse"""

        ## --- iterator tp_clear ---
        tp_clear_function_name = "%s__tp_clear" % (self.iter_pystruct,)
        self.iter_pytype.slots.setdefault("tp_clear", tp_clear_function_name )

        code_sink.writeln(r'''
static void
%s(%s *self)
{
    Py_CLEAR(self->container);
    %s
}
''' % (tp_clear_function_name, self.iter_pystruct, self._get_iter_delete_code()))

        ## --- iterator tp_traverse ---
        tp_traverse_function_name = "%s__tp_traverse" % (self.iter_pystruct,)
        self.iter_pytype.slots.setdefault("tp_traverse", tp_traverse_function_name )

        code_sink.writeln(r'''
static int
%s(%s *self, visitproc visit, void *arg)
{
    Py_VISIT((PyObject *) self->container);
    return 0;
}
''' % (tp_traverse_function_name, self.iter_pystruct))


    def _generate_destructor(self, code_sink):
        """Generate a tp_dealloc function and register it in the type"""

        # -- iterator --
        iter_tp_dealloc_function_name = "_wrap_%s__tp_dealloc" % (self.iter_pystruct,)
        code_sink.writeln(r'''
static void
%s(%s *self)
{
    Py_CLEAR(self->container);
    %s
    self->ob_type->tp_free((PyObject*)self);
}
''' % (iter_tp_dealloc_function_name, self.iter_pystruct, self._get_iter_delete_code()))

        self.iter_pytype.slots.setdefault("tp_dealloc", iter_tp_dealloc_function_name )


    def _generate_iter_methods(self, code_sink):

        container_tp_iter_function_name = "_wrap_%s__tp_iter" % (self.cppclass.pystruct,)
        iterator_tp_iter_function_name = "_wrap_%s__tp_iter" % (self.iter_pystruct,)
        subst_vars = {
            'CONTAINER_ITER_FUNC': container_tp_iter_function_name,
            'ITERATOR_ITER_FUNC': iterator_tp_iter_function_name,
            'PYSTRUCT': self.cppclass.pystruct,
            'ITER_PYSTRUCT': self.iter_pystruct,
            'ITER_PYTYPESTRUCT': self.iter_pytypestruct,
            'CTYPE': self.cppclass.full_name,
            'BEGIN_METHOD': self.begin_method,
            'ITERATOR_TYPE': self.iterator_type,
            }
        # -- container --
        code_sink.writeln(r'''
static PyObject*
%(CONTAINER_ITER_FUNC)s(%(PYSTRUCT)s *self)
{
    %(ITER_PYSTRUCT)s *iter = PyObject_GC_New(%(ITER_PYSTRUCT)s, &%(ITER_PYTYPESTRUCT)s);
    Py_INCREF(self);
    iter->container = self;
    iter->iterator = new %(CTYPE)s::%(ITERATOR_TYPE)s(self->obj->%(BEGIN_METHOD)s());
    return (PyObject*) iter;
}
''' % subst_vars)

        self.cppclass.pytype.slots.setdefault("tp_iter", container_tp_iter_function_name)
        

        # -- iterator --
        container_tp_iter_function_name = "_wrap_%s__tp_iter" % (self.cppclass.pystruct,)
        code_sink.writeln(r'''
static PyObject*
%(ITERATOR_ITER_FUNC)s(%(ITER_PYSTRUCT)s *self)
{
    Py_INCREF(self);
    return (PyObject*) self;
}
''' % subst_vars)

        self.iter_pytype.slots.setdefault("tp_iter", iterator_tp_iter_function_name)

        # -- iterator tp_iternext
        iternext = IterNextWrapper(self)
        iternext.generate(code_sink)
        self.iter_pytype.slots.setdefault("tp_iternext", iternext.c_function_name)
        

