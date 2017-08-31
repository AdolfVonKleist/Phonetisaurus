"""
The class PyTypeObject generates a PyTypeObject structure contents.
"""

class PyTypeObject(object):
    TEMPLATE = (
        'PyTypeObject %(typestruct)s = {\n'
        '    PyObject_HEAD_INIT(NULL)\n'
        '    0,                                 /* ob_size */\n'
        '    (char *) "%(tp_name)s",            /* tp_name */\n'
        '    %(tp_basicsize)s,                  /* tp_basicsize */\n'
        '    0,                                 /* tp_itemsize */\n'
        '    /* methods */\n'
        '    (destructor)%(tp_dealloc)s,        /* tp_dealloc */\n'
        '    (printfunc)0,                      /* tp_print */\n'
        '    (getattrfunc)%(tp_getattr)s,       /* tp_getattr */\n'
        '    (setattrfunc)%(tp_setattr)s,       /* tp_setattr */\n'
        '    (cmpfunc)%(tp_compare)s,           /* tp_compare */\n'
        '    (reprfunc)%(tp_repr)s,             /* tp_repr */\n'
        '    (PyNumberMethods*)%(tp_as_number)s,     /* tp_as_number */\n'
        '    (PySequenceMethods*)%(tp_as_sequence)s, /* tp_as_sequence */\n'
        '    (PyMappingMethods*)%(tp_as_mapping)s,   /* tp_as_mapping */\n'
        '    (hashfunc)%(tp_hash)s,             /* tp_hash */\n'
        '    (ternaryfunc)%(tp_call)s,          /* tp_call */\n'
        '    (reprfunc)%(tp_str)s,              /* tp_str */\n'
        '    (getattrofunc)%(tp_getattro)s,     /* tp_getattro */\n'
        '    (setattrofunc)%(tp_setattro)s,     /* tp_setattro */\n'
        '    (PyBufferProcs*)%(tp_as_buffer)s,  /* tp_as_buffer */\n'
        '    %(tp_flags)s,                      /* tp_flags */\n'
        '    %(tp_doc)s,                        /* Documentation string */\n'
        '    (traverseproc)%(tp_traverse)s,     /* tp_traverse */\n'
        '    (inquiry)%(tp_clear)s,             /* tp_clear */\n'
        '    (richcmpfunc)%(tp_richcompare)s,   /* tp_richcompare */\n'
        '    %(tp_weaklistoffset)s,             /* tp_weaklistoffset */\n'
        '    (getiterfunc)%(tp_iter)s,          /* tp_iter */\n'
        '    (iternextfunc)%(tp_iternext)s,     /* tp_iternext */\n'
        '    (struct PyMethodDef*)%(tp_methods)s, /* tp_methods */\n'
        '    (struct PyMemberDef*)0,              /* tp_members */\n'
        '    %(tp_getset)s,                     /* tp_getset */\n'
        '    NULL,                              /* tp_base */\n'
        '    NULL,                              /* tp_dict */\n'
        '    (descrgetfunc)%(tp_descr_get)s,    /* tp_descr_get */\n'
        '    (descrsetfunc)%(tp_descr_set)s,    /* tp_descr_set */\n'
        '    %(tp_dictoffset)s,                 /* tp_dictoffset */\n'
        '    (initproc)%(tp_init)s,             /* tp_init */\n'
        '    (allocfunc)%(tp_alloc)s,           /* tp_alloc */\n'
        '    (newfunc)%(tp_new)s,               /* tp_new */\n'
        '    (freefunc)%(tp_free)s,             /* tp_free */\n'
        '    (inquiry)%(tp_is_gc)s,             /* tp_is_gc */\n'
        '    NULL,                              /* tp_bases */\n'
        '    NULL,                              /* tp_mro */\n'
        '    NULL,                              /* tp_cache */\n'
        '    NULL,                              /* tp_subclasses */\n'
        '    NULL,                              /* tp_weaklist */\n'
        '    (destructor) NULL                  /* tp_del */\n'
        '};\n'
        )

    def __init__(self):
        self.slots = {}

    def generate(self, code_sink):
        """
        Generates the type structure.  All slots are optional except
        'tp_name', 'tp_basicsize', and the pseudo-slot 'typestruct'.
        """

        slots = dict(self.slots)

        slots.setdefault('tp_dealloc', 'NULL')
        slots.setdefault('tp_getattr', 'NULL')
        slots.setdefault('tp_setattr', 'NULL')
        slots.setdefault('tp_compare', 'NULL')
        slots.setdefault('tp_repr', 'NULL')
        slots.setdefault('tp_as_number', 'NULL')
        slots.setdefault('tp_as_sequence', 'NULL')
        slots.setdefault('tp_as_mapping', 'NULL')
        slots.setdefault('tp_hash', 'NULL')
        slots.setdefault('tp_call', 'NULL')
        slots.setdefault('tp_str', 'NULL')
        slots.setdefault('tp_getattro', 'NULL')
        slots.setdefault('tp_setattro', 'NULL')
        slots.setdefault('tp_as_buffer', 'NULL')
        slots.setdefault('tp_flags', 'Py_TPFLAGS_DEFAULT')
        slots.setdefault('tp_doc', 'NULL')
        slots.setdefault('tp_traverse', 'NULL')
        slots.setdefault('tp_clear', 'NULL')
        slots.setdefault('tp_richcompare', 'NULL')
        slots.setdefault('tp_weaklistoffset', '0')
        slots.setdefault('tp_iter', 'NULL')
        slots.setdefault('tp_iternext', 'NULL')
        slots.setdefault('tp_methods', 'NULL')
        slots.setdefault('tp_getset', 'NULL')
        slots.setdefault('tp_descr_get', 'NULL')
        slots.setdefault('tp_descr_set', 'NULL')
        slots.setdefault('tp_dictoffset', '0')
        slots.setdefault('tp_init', 'NULL')
        slots.setdefault('tp_alloc', 'PyType_GenericAlloc')
        slots.setdefault('tp_new', 'PyType_GenericNew')
        slots.setdefault('tp_free', '0')
        slots.setdefault('tp_is_gc', 'NULL')
        
        code_sink.writeln(self.TEMPLATE % slots)


class PyNumberMethods(object):
    TEMPLATE = (
        'static PyNumberMethods %(variable)s = {\n'
	'    (binaryfunc) %(nb_add)s,\n'
	'    (binaryfunc) %(nb_subtract)s,\n'
	'    (binaryfunc) %(nb_multiply)s,\n'
	'    (binaryfunc) %(nb_divide)s,\n'
	'    (binaryfunc) %(nb_remainder)s,\n'
	'    (binaryfunc) %(nb_divmod)s,\n'
	'    (ternaryfunc) %(nb_power)s,\n'
	'    (unaryfunc) %(nb_negative)s,\n'
	'    (unaryfunc) %(nb_positive)s,\n'
	'    (unaryfunc) %(nb_absolute)s,\n'
	'    (inquiry) %(nb_nonzero)s,\n'
	'    (unaryfunc) %(nb_invert)s,\n'
	'    (binaryfunc) %(nb_lshift)s,\n'
	'    (binaryfunc) %(nb_rshift)s,\n'
	'    (binaryfunc) %(nb_and)s,\n'
	'    (binaryfunc) %(nb_xor)s,\n'
	'    (binaryfunc) %(nb_or)s,\n'
	'    (coercion) %(nb_coerce)s,\n'
	'    (unaryfunc) %(nb_int)s,\n'
	'    (unaryfunc) %(nb_long)s,\n'
	'    (unaryfunc) %(nb_float)s,\n'
	'    (unaryfunc) %(nb_oct)s,\n'
	'    (unaryfunc) %(nb_hex)s,\n'
	'    /* Added in release 2.0 */\n'
	'    (binaryfunc) %(nb_inplace_add)s,\n'
	'    (binaryfunc) %(nb_inplace_subtract)s,\n'
	'    (binaryfunc) %(nb_inplace_multiply)s,\n'
	'    (binaryfunc) %(nb_inplace_divide)s,\n'
	'    (binaryfunc) %(nb_inplace_remainder)s,\n'
	'    (ternaryfunc) %(nb_inplace_power)s,\n'
	'    (binaryfunc) %(nb_inplace_lshift)s,\n'
	'    (binaryfunc) %(nb_inplace_rshift)s,\n'
	'    (binaryfunc) %(nb_inplace_and)s,\n'
	'    (binaryfunc) %(nb_inplace_xor)s,\n'
	'    (binaryfunc) %(nb_inplace_or)s,\n'
        '\n'
	'    /* Added in release 2.2 */\n'
	'    /* The following require the Py_TPFLAGS_HAVE_CLASS flag */\n'
	'    (binaryfunc) %(nb_floor_divide)s,\n'
	'    (binaryfunc) %(nb_true_divide)s,\n'
	'    (binaryfunc) %(nb_inplace_floor_divide)s,\n'
	'    (binaryfunc) %(nb_inplace_true_divide)s,\n'
        '\n'
        '#if PY_VERSION_HEX >= 0x020500F0\n'
	'    /* Added in release 2.5 */\n'
	'    (unaryfunc) %(nb_index)s,\n'
        '\n'
        '#endif\n'
        '};\n'
        )

    def __init__(self):
        self.slots = {}

    def generate(self, code_sink):
        """
        Generates the structure.  All slots are optional except 'variable'.
        """

        slots = dict(self.slots)

	slots.setdefault('nb_add', 'NULL')
	slots.setdefault('nb_subtract', 'NULL')
	slots.setdefault('nb_multiply', 'NULL')
	slots.setdefault('nb_divide', 'NULL')
	slots.setdefault('nb_remainder', 'NULL')
	slots.setdefault('nb_divmod', 'NULL')
	slots.setdefault('nb_power', 'NULL')
	slots.setdefault('nb_negative', 'NULL')
	slots.setdefault('nb_positive', 'NULL')
	slots.setdefault('nb_absolute', 'NULL')
	slots.setdefault('nb_nonzero', 'NULL')
	slots.setdefault('nb_invert', 'NULL')
	slots.setdefault('nb_lshift', 'NULL')
	slots.setdefault('nb_rshift', 'NULL')
	slots.setdefault('nb_and', 'NULL')
	slots.setdefault('nb_xor', 'NULL')
        slots.setdefault('nb_or', 'NULL')
	slots.setdefault('nb_coerce', 'NULL')
	slots.setdefault('nb_int', 'NULL')
	slots.setdefault('nb_long', 'NULL')
	slots.setdefault('nb_float', 'NULL')
	slots.setdefault('nb_oct', 'NULL')
	slots.setdefault('nb_hex', 'NULL')
	slots.setdefault('nb_inplace_add', 'NULL')
	slots.setdefault('nb_inplace_subtract', 'NULL')
	slots.setdefault('nb_inplace_multiply', 'NULL')
	slots.setdefault('nb_inplace_divide', 'NULL')
	slots.setdefault('nb_inplace_remainder', 'NULL')
	slots.setdefault('nb_inplace_power', 'NULL')
	slots.setdefault('nb_inplace_lshift', 'NULL')
	slots.setdefault('nb_inplace_rshift', 'NULL')
	slots.setdefault('nb_inplace_and', 'NULL')
	slots.setdefault('nb_inplace_xor', 'NULL')
	slots.setdefault('nb_inplace_or', 'NULL')
	slots.setdefault('nb_floor_divide', 'NULL')
	slots.setdefault('nb_true_divide', 'NULL')
	slots.setdefault('nb_inplace_floor_divide', 'NULL')
	slots.setdefault('nb_inplace_true_divide', 'NULL')
	slots.setdefault('nb_index', 'NULL')

        code_sink.writeln(self.TEMPLATE % slots)

class PySequenceMethods(object):
    TEMPLATE = '''
static PySequenceMethods %(variable)s = {
    (lenfunc) %(sq_length)s,
    (binaryfunc) %(sq_concat)s,
    (ssizeargfunc) %(sq_repeat)s,
    (ssizeargfunc) %(sq_item)s,
    (ssizessizeargfunc) %(sq_slice)s,
    (ssizeobjargproc) %(sq_ass_item)s,
    (ssizessizeobjargproc) %(sq_ass_slice)s,
    (objobjproc) %(sq_contains)s,
    /* Added in release 2.0 */
    (binaryfunc) %(sq_inplace_concat)s,
    (ssizeargfunc) %(sq_inplace_repeat)s,
};

'''

    FUNCTION_TEMPLATES = {
        "sq_length" : '''
static Py_ssize_t
%(wrapper_name)s (%(py_struct)s *py_self)
{
    PyObject *py_result;
    Py_ssize_t result;

    py_result = %(method_name)s(py_self);
    if (py_result == NULL) {
        return -1;
    }
    result = PyInt_AsSsize_t(py_result);
    Py_DECREF(py_result);
    return result;
}

''',

        # This hacky version is necessary 'cause if we're calling a function rather than a method
        # or an overloaded wrapper the args parameter gets tacked into the call sequence.
        "sq_length_ARGS" : '''
static Py_ssize_t
%(wrapper_name)s (%(py_struct)s *py_self)
{
    PyObject *py_result;
    PyObject *args;
    Py_ssize_t result;

    args = PyTuple_New (0);
    py_result = %(method_name)s(py_self, args, NULL);
    Py_DECREF(args);
    if (py_result == NULL) {
        return -1;
    }
    result = PyInt_AsSsize_t(py_result);
    Py_DECREF(py_result);
    return result;
}

''',

        "sq_item" : '''
static PyObject*
%(wrapper_name)s (%(py_struct)s *py_self, Py_ssize_t py_i)
{
    PyObject *result;
    PyObject *args;

    args = Py_BuildValue("(i)", py_i);
    result = %(method_name)s(py_self, args, NULL);
    Py_DECREF(args);
    if (PyErr_ExceptionMatches(PyExc_IndexError) ||
        PyErr_ExceptionMatches(PyExc_StopIteration)) {
        Py_XDECREF(result);
        return NULL;
    } else {
        return result;
    }
}


''',

        "sq_ass_item" : '''
static int
%(wrapper_name)s (%(py_struct)s *py_self, Py_ssize_t py_i, PyObject *py_val)
{
    PyObject *result;
    PyObject *args;

    args = Py_BuildValue("(iO)", py_i, py_val);
    result = %(method_name)s(py_self, args, NULL);
    Py_DECREF(args);
    if (result == NULL) {
        return -1;
    } else {
        Py_DECREF(result);
        return 0;
    }
}

''',
        }

    def __init__(self):
        self.slots = {}

    def generate(self, code_sink):
        """
        Generates the structure.  All slots are optional except 'variable'.
        """

        slots = dict(self.slots)

	slots.setdefault('sq_length', 'NULL')
	slots.setdefault('sq_concat', 'NULL')
	slots.setdefault('sq_repeat', 'NULL')
	slots.setdefault('sq_item', 'NULL')
	slots.setdefault('sq_slice', 'NULL')
	slots.setdefault('sq_ass_item', 'NULL')
	slots.setdefault('sq_ass_slice', 'NULL')
	slots.setdefault('sq_contains', 'NULL')
	slots.setdefault('sq_inplace_concat', 'NULL')
	slots.setdefault('sq_inplace_repeat', 'NULL')

        code_sink.writeln(self.TEMPLATE % slots)

