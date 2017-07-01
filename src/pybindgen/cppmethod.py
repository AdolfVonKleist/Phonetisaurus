"""
Wrap C++ class methods and constructods.
"""

import warnings
import traceback
from copy import copy

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase, \
    join_ctype_and_name, CodeGenerationError
from typehandlers.base import ReturnValue, Parameter
from typehandlers import codesink
import overloading
import settings
import utils
from cppexception import CppException


class CppMethod(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C++ class method
    """

    def __init__(self, method_name, return_value, parameters, is_static=False,
                 template_parameters=(), is_virtual=None, is_const=False,
                 unblock_threads=None, is_pure_virtual=False,
                 custom_template_method_name=None, visibility='public',
                 custom_name=None, deprecated=False, docstring=None, throw=()):
        """
        Create an object the generates code to wrap a C++ class method.

        :param return_value: the method return value
        :type  return_value: L{ReturnValue}

        :param method_name: name of the method

        :param parameters: the method parameters
        :type parameters: list of :class:`pybindgen.typehandlers.base.Parameter`

        :param is_static: whether it is a static method

        :param template_parameters: optional list of template parameters needed to invoke the method
        :type template_parameters: list of strings, each element a template parameter expression

        :param is_virtual: whether the method is virtual (pure or not)

        :param is_const: whether the method has a const modifier on it

        :param unblock_threads: whether to release the Python GIL
            around the method call or not.  If None or omitted, use
            global settings.  Releasing the GIL has a small
            performance penalty, but is recommended if the method is
            expected to take considerable time to complete, because
            otherwise no other Python thread is allowed to run until
            the method completes.

        :param is_pure_virtual: whether the method is defined as "pure
          virtual", i.e. virtual method with no default implementation
          in the class being wrapped.

        :param custom_name: alternate name to give to the method, in python side.

        :param custom_template_method_name: (deprecated) same as parameter 'custom_name'.

        :param visibility: visibility of the method within the C++ class
        :type visibility: a string (allowed values are 'public', 'protected', 'private')

        :param deprecated: deprecation state for this API:
          - False: Not deprecated
          - True: Deprecated
          - "message": Deprecated, and deprecation warning contains the given message

        :param throw: list of C++ exceptions that the function may throw
        :type throw: list of L{CppException}
        """
        self.stack_where_defined = traceback.extract_stack()

        ## backward compatibility check
        if isinstance(return_value, str) and isinstance(method_name, ReturnValue):
            warnings.warn("CppMethod has changed API; see the API documentation (but trying to correct...)",
                          DeprecationWarning, stacklevel=2)
            method_name, return_value = return_value, method_name

        # bug 399870
        if is_virtual is None:
            is_virtual = is_pure_virtual
            
        if return_value is None:
            return_value = ReturnValue.new('void')

        if unblock_threads is None:
            unblock_threads = settings.unblock_threads

        assert visibility in ['public', 'protected', 'private']
        self.visibility = visibility
        self.method_name = method_name
        self.is_static = is_static
        self.is_virtual = is_virtual
        self.is_pure_virtual = is_pure_virtual
        self.is_const = is_const
        self.template_parameters = template_parameters

        self.custom_name = (custom_name or custom_template_method_name)

        #self.static_decl = True
        self._class = None
        self._helper_class = None
        self.docstring = docstring
        self.wrapper_base_name = None
        self.wrapper_actual_name = None
        self.return_value = None
        self.parameters = None

        return_value = utils.eval_retval(return_value, self)
        parameters = [utils.eval_param(param, self) for param in parameters]

        super(CppMethod, self).__init__(
            return_value, parameters,
            "return NULL;", "return NULL;",
            unblock_threads=unblock_threads)
        self.deprecated = deprecated

        for t in throw:
            assert isinstance(t, CppException)
        self.throw = list(throw)

        self.custodians_and_wards = [] # list of (custodian, ward, postcall)
        cppclass_typehandlers.scan_custodians_and_wards(self)


    def add_custodian_and_ward(self, custodian, ward, postcall=None):
        """Add a custodian/ward relationship to the method wrapper

        A custodian/ward relationship is one where one object
        (custodian) keeps a references to another object (ward), thus
        keeping it alive.  When the custodian is destroyed, the
        reference to the ward is released, allowing the ward to be
        freed if no other reference to it is being kept by the user
        code.  Please note that custodian/ward manages the lifecycle
        of Python wrappers, not the C/C++ objects referenced by the
        wrappers.  In most cases, the wrapper owns the C/C++ object,
        and so the lifecycle of the C/C++ object is also managed by
        this.  However, there are cases when a Python wrapper does not
        own the underlying C/C++ object, only references it.

        The custodian and ward objects are indicated by an integer
        with the following meaning:
          - C{-1}: the return value of the function
          - C{0}: the instance of the method (self)
          - value > 0: the nth parameter of the function, starting at 1

        :parameter custodian: number of the object that assumes the role of custodian
        :parameter ward: number of the object that assumes the role of ward

        :parameter postcall: if True, the relationship is added after
             the C function call, if False it is added before the
             call.  If not given, the value False is assumed if the
             return value is not involved, else postcall=True is used.
        """
        if custodian == -1 or ward == -1:
            if postcall is None:
                postcall = True
            if not postcall:
                raise TypeConfigurationError("custodian/ward policy must be postcall "
                                             "when a return value is involved")
        else:
            if postcall is None:
                postcall = False
        self.custodians_and_wards.append((custodian, ward, postcall))


    def set_helper_class(self, helper_class):
        "Set the C++ helper class, which is used for overriding virtual methods"
        self._helper_class = helper_class
        self.wrapper_base_name = "%s::_wrap_%s" % (self._helper_class.name, self.method_name)
    def get_helper_class(self):
        "Get the C++ helper class, which is used for overriding virtual methods"
        return self._helper_class
    helper_class = property(get_helper_class, set_helper_class)


    def matches_signature(self, other):
        if self.mangled_name != other.mangled_name:
            return False
        if len(self.parameters) != len(other.parameters):
            return False
        for param1, param2 in zip(self.parameters, other.parameters):
            if param1.ctype != param2.ctype:
                return False
        if bool(self.is_const) != bool(other.is_const):
            return False
        return True

    def set_custom_name(self, custom_name):
        if custom_name is None:
            self.mangled_name = utils.get_mangled_name(self.method_name, self.template_parameters)
        else:
            self.mangled_name = custom_name

    custom_name = property(None, set_custom_name)

    def clone(self):
        """Creates a semi-deep copy of this method wrapper.  The returned
        method wrapper clone contains copies of all parameters, so
        they can be modified at will.
        """
        meth = CppMethod(self.method_name,
                         self.return_value,
                         [copy(param) for param in self.parameters],
                         is_static=self.is_static,
                         template_parameters=self.template_parameters,
                         is_virtual=self.is_virtual,
                         is_pure_virtual=self.is_pure_virtual,
                         is_const=self.is_const,
                         visibility=self.visibility)
        meth._class = self._class
        meth.docstring = self.docstring
        meth.wrapper_base_name = self.wrapper_base_name
        meth.wrapper_actual_name = self.wrapper_actual_name
        return meth

    def set_class(self, class_):
        """set the class object this method belongs to"""
        self._class = class_
        self.wrapper_base_name = "_wrap_%s_%s" % (
            class_.pystruct, self.mangled_name)
    def get_class(self):
        """get the class object this method belongs to"""
        return self._class
    class_ = property(get_class, set_class)

    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        #assert isinstance(class_, CppClass)
        if class_ is None:
            class_ = self._class
        if self.template_parameters:
            template_params = '< %s >' % ', '.join(self.template_parameters)
        else:
            template_params = ''


        if self.return_value.ctype == 'void':
            retval_assign = ''
        else:
            if self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
                retval_assign = '%s retval = ' % (self.return_value.ctype,)
            else:
                retval_assign = 'retval = '

        if class_.helper_class is not None and self.is_virtual and not self.is_pure_virtual\
                and not settings._get_deprecated_virtuals():
            helper = self.before_call.declare_variable(type_="%s *" % class_.helper_class.name,
                                                       name="helper_class",
                                                       initializer=(
                    "dynamic_cast<%s*> (self->obj)" % class_.helper_class.name))
        else:
            helper = None

        if self.is_static:
            method = '%s::%s%s' % (class_.full_name, self.method_name, template_params)
        else:
            method = 'self->obj->%s%s' % (self.method_name, template_params)

        if self.throw:
            self.before_call.write_code('try\n{')
            self.before_call.indent()

        if self.is_static:
            self.before_call.write_code(retval_assign + (
                    '%s::%s%s(%s);' % (class_.full_name,
                                       self.method_name, template_params,
                                       ", ".join(self.call_params))))
        else:
            if helper is None:
                self.before_call.write_code(retval_assign + (
                        'self->obj->%s%s(%s);' % (self.method_name, template_params,
                                                  ", ".join(self.call_params))))
            else:
                self.before_call.write_code(retval_assign + (
                        '(%s == NULL)? (self->obj->%s%s(%s)) : (self->obj->%s::%s%s(%s));'
                        % (helper,

                           self.method_name, template_params,
                           ", ".join(self.call_params),
                           
                           class_.full_name, self.method_name, template_params,
                           ", ".join(self.call_params)
                           )))

        if self.throw:
            for exc in self.throw:
                self.before_call.unindent()
                self.before_call.write_code('} catch (%s const &exc) {' % exc.full_name)
                self.before_call.indent()
                self.before_call.write_cleanup()
                exc.write_convert_to_python(self.before_call, 'exc')
                self.before_call.write_code('return NULL;')
            self.before_call.unindent()
            self.before_call.write_code('}')

    def _before_call_hook(self):
        "hook that post-processes parameters and check for custodian=<n> CppClass parameters"
        cppclass_typehandlers.implement_parameter_custodians_precall(self)

    def _before_return_hook(self):
        """hook that post-processes parameters and check for custodian=<n>
        CppClass parameters"""
        cppclass_typehandlers.implement_parameter_custodians_postcall(self)

    def _get_pystruct(self):
        # When a method is used in the context of a helper class, we
        # should use the pystruct of the helper class' class.
        #
        # self.class_: original base class where the method is defined
        # self._helper_class.class_: subclass that is inheriting the method
        #
        if self._helper_class is None:
            return self.class_.pystruct
        else:
            return self._helper_class.class_.pystruct

    def get_wrapper_signature(self, wrapper_name, extra_wrapper_params=()):
        flags = self.get_py_method_def_flags()

        self.wrapper_actual_name = wrapper_name
        self.wrapper_return = "PyObject *"
        if 'METH_STATIC' in flags:
            _self_name = 'PYBINDGEN_UNUSED(dummy)'
        else:
            _self_name = 'self'

#         if extra_wrapper_params:
#             extra = ', '.join([''] + list(extra_wrapper_params))
#         else:
#             extra = ''

        if 'METH_VARARGS' in flags:
            if 'METH_KEYWORDS' in flags:
                self.wrapper_args = ["%s *%s" % (self._get_pystruct(), _self_name),
                                     "PyObject *args", "PyObject *kwargs"]
            else:
                assert not extra_wrapper_params, \
                    "extra_wrapper_params can only be used with"\
                    " full varargs/kwargs wrappers"
                self.wrapper_args = ["%s *%s" % (self._get_pystruct(), _self_name),
                                     "PyObject *args"]
        else:
            assert not extra_wrapper_params, \
                "extra_wrapper_params can only be used with full varargs/kwargs wrappers"
            if 'METH_STATIC' in flags:
                self.wrapper_args = ['void']
            else:
                self.wrapper_args = ["%s *%s" % (self._get_pystruct(), _self_name)]
        self.wrapper_args.extend(extra_wrapper_params)

        return self.wrapper_return, "%s(%s)" % (self.wrapper_actual_name, ', '.join(self.wrapper_args))

    def generate(self, code_sink, wrapper_name=None, extra_wrapper_params=()):
        """
        Generates the wrapper code
        code_sink -- a CodeSink instance that will receive the generated code
        method_name -- actual name the method will get
        extra_wrapper_params -- extra parameters the wrapper function should receive

        Returns the corresponding PyMethodDef entry string.
        """

        if self.throw: # Bug #780945
            self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR = False
            self.reset_code_generation_state()

        class_ = self.class_
        #assert isinstance(class_, CppClass)
        tmp_sink = codesink.MemoryCodeSink()

        self.generate_body(tmp_sink, gen_call_params=[class_])

        if wrapper_name is None:
            self.wrapper_actual_name = self.wrapper_base_name
        else:
            self.wrapper_actual_name = wrapper_name

        self.get_wrapper_signature(self.wrapper_actual_name, extra_wrapper_params)
        self.write_open_wrapper(code_sink)#, add_static=self.static_decl)
        tmp_sink.flush_to(code_sink)
        self.write_close_wrapper(code_sink)

    def get_py_method_def_flags(self):
        "Get the PyMethodDef flags suitable for this method"
        flags = super(CppMethod, self).get_py_method_def_flags()
        if self.is_static:
            flags.append('METH_STATIC')
        return flags

    def get_py_method_def(self, method_name):
        "Get the PyMethodDef entry suitable for this method"
        flags = self.get_py_method_def_flags()
        return "{(char *) \"%s\", (PyCFunction) %s, %s, %s }," % \
               (method_name, self.wrapper_actual_name, '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))

    def __str__(self):
        
        if self.class_ is None:
            cls_name = "???"
        else:
            cls_name = self.class_.full_name
        if self.is_const:
            const = ' const'
        else:
            const = ''
        if self.is_virtual:
            virtual = "virtual "
        else:
            virtual = ''
        if self.is_pure_virtual:
            pure_virtual = " = 0"
        else:
            pure_virtual = ''
        
        if self.return_value is None:
            retval = "retval?"
        else:
            retval = self.return_value.ctype

        if self.parameters is None:
            params = 'params?'
        else:
            params = ', '.join(["%s %s" % (param.ctype, param.name) for param in self.parameters])

        return ("%s: %s%s %s::%s (%s)%s%s;" %
                (self.visibility, virtual, retval, cls_name, self.method_name,
                 params, const, pure_virtual))


class CppOverloadedMethod(overloading.OverloadedWrapper):
    "Support class for overloaded methods"
    RETURN_TYPE = 'PyObject *'
    ERROR_RETURN = 'return NULL;'



class DummyReturnValue(ReturnValue):
    CTYPES = []
    """
    A 'dummy' return value object used for modelling methods that have
    incomplete or incorrect parameters or return values.
    """
    def __init__(self, arg):
        """
        Accepts either a ReturnValue object or a tuple as sole
        parameter.  In case it's a tuple, it is assumed to be a retval
        spec (\\*args, \\*\\*kwargs).
        """
        if isinstance(arg, ReturnValue):
            super(DummyReturnValue, self).__init__(arg.ctype)
        else:
            args, kwargs = utils.parse_retval_spec(arg)
            super(DummyReturnValue, self).__init__(args[0])
    def convert_c_to_python(self, wrapper):
        raise TypeError("this is a DummyReturnValue")
    def convert_python_to_c(self, wrapper):
        raise TypeError("this is a DummyReturnValue")
    def get_c_error_return(self):
        return ''


class DummyParameter(Parameter):
    CTYPES = []
    DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT, Parameter.DIRECTION_INOUT]
    """
    A 'dummy' parameter object used for modelling methods that have
    incomplete or incorrect parameters or return values.
    """
    def __init__(self, arg):
        """
        Accepts either a Parameter object or a tuple as sole
        parameter.  In case it's a tuple, it is assumed to be a retval
        spec (\\*args, \\*\\*kwargs).
        """
        if isinstance(arg, ReturnValue):
            super(DummyParameter, self).__init__(arg.ctype)
        else:
            args, kwargs = utils.parse_param_spec(arg)
            super(DummyParameter, self).__init__(args[0], args[1])

    def convert_c_to_python(self, wrapper):
        raise TypeError("this is a DummyParameter")
    def convert_python_to_c(self, wrapper):
        raise TypeError("this is a DummyParameter")


class CppDummyMethod(CppMethod):
    """
    A 'dummy' method; cannot be generated due to incomple or incorrect
    parameters, but is added to the class to model the missing method.
    """

    def __init__(self, method_name, return_value, parameters, *args, **kwargs):
        return_value = DummyReturnValue(return_value)
        parameters = [DummyParameter(p) for p in parameters]
        super(CppDummyMethod, self).__init__(method_name, return_value, parameters, *args, **kwargs)


class CppConstructor(ForwardWrapperBase):
    """
    Class that generates a wrapper to a C++ class constructor.  Such
    wrapper is used as the python class __init__ method.
    """

    def __init__(self, parameters, unblock_threads=None, visibility='public', deprecated=False, throw=()):
        """

        :param parameters: the constructor parameters

        :param deprecated: deprecation state for this API: False=Not
           deprecated; True=Deprecated; "message"=Deprecated, and
           deprecation warning contains the given message

        :param throw: list of C++ exceptions that the constructor may throw

        :type throw: list of :class:`pybindgen.cppexception.CppException`
        """
        self.stack_where_defined = traceback.extract_stack()
        if unblock_threads is None:
            unblock_threads = settings.unblock_threads

        parameters = [utils.eval_param(param, self) for param in parameters]

        super(CppConstructor, self).__init__(
            None, parameters,
            "return -1;", "return -1;",
            force_parse=ForwardWrapperBase.PARSE_TUPLE_AND_KEYWORDS,
            unblock_threads=unblock_threads)
        self.deprecated = deprecated
        assert visibility in ['public', 'protected', 'private']
        self.visibility = visibility
        self.wrapper_base_name = None
        self.wrapper_actual_name = None
        self._class = None

        for t in throw:
            assert isinstance(t, CppException)
        self.throw = list(throw)

        self.custodians_and_wards = [] # list of (custodian, ward, postcall)
        cppclass_typehandlers.scan_custodians_and_wards(self)


    def add_custodian_and_ward(self, custodian, ward, postcall=None):
        """Add a custodian/ward relationship to the constructor wrapper

        A custodian/ward relationship is one where one object
        (custodian) keeps a references to another object (ward), thus
        keeping it alive.  When the custodian is destroyed, the
        reference to the ward is released, allowing the ward to be
        freed if no other reference to it is being kept by the user
        code.  Please note that custodian/ward manages the lifecycle
        of Python wrappers, not the C/C++ objects referenced by the
        wrappers.  In most cases, the wrapper owns the C/C++ object,
        and so the lifecycle of the C/C++ object is also managed by
        this.  However, there are cases when a Python wrapper does not
        own the underlying C/C++ object, only references it.

        The custodian and ward objects are indicated by an integer
        with the following meaning:
          - C{0}: the object being constructed (self)
          - value > 0: the nth parameter of the function, starting at 1

        :parameter custodian: number of the object that assumes the role of custodian
        :parameter ward: number of the object that assumes the role of ward

        :parameter postcall: if True, the relationship is added after
             the C function call, if False it is added before the
             call.  If not given, the value False is assumed if the
             return value is not involved, else postcall=True is used.
        """
        if custodian == -1 or ward == -1:
            if postcall is None:
                postcall = True
            if not postcall:
                raise TypeConfigurationError("custodian/ward policy must be postcall "
                                             "when a return value is involved")
        else:
            if postcall is None:
                postcall = False
        self.custodians_and_wards.append((custodian, ward, postcall))


    def clone(self):
        """
        Creates a semi-deep copy of this constructor wrapper.  The
        returned constructor wrapper clone contains copies of all
        parameters, so they can be modified at will.
        """
        meth = type(self)([copy(param) for param in self.parameters])
        meth._class = self._class
        meth.wrapper_base_name = self.wrapper_base_name
        meth.wrapper_actual_name = self.wrapper_actual_name
        return meth

    def set_class(self, class_):
        "Set the class wrapper object (CppClass)"
        self._class = class_
        self.wrapper_base_name = "_wrap_%s__tp_init" % (
            class_.pystruct,)
    def get_class(self):
        "Get the class wrapper object (CppClass)"
        return self._class
    class_ = property(get_class, set_class)
    
    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        if class_ is None:
            class_ = self._class

        if self.throw:
            self.before_call.write_code('try\n{')
            self.before_call.indent()

        #assert isinstance(class_, CppClass)
        if class_.helper_class is None:
            class_.write_create_instance(self.before_call, "self->obj", ", ".join(self.call_params))
            class_.write_post_instance_creation_code(self.before_call, "self->obj", ", ".join(self.call_params))
            self.before_call.write_code("self->flags = PYBINDGEN_WRAPPER_FLAG_NONE;")
        else:
            ## We should only create a helper class instance when
            ## being called from a user python subclass.
            self.before_call.write_code("if (self->ob_type != &%s)" % class_.pytypestruct)
            self.before_call.write_code("{")
            self.before_call.indent()

            class_.write_create_instance(self.before_call, "self->obj", ", ".join(self.call_params),
                                         class_.helper_class.name)
            self.before_call.write_code("self->flags = PYBINDGEN_WRAPPER_FLAG_NONE;")
            self.before_call.write_code('((%s*) self->obj)->set_pyobj((PyObject *)self);'
                                        % class_.helper_class.name)
            class_.write_post_instance_creation_code(self.before_call, "self->obj", ", ".join(self.call_params),
                                                     class_.helper_class.name)

            self.before_call.unindent()
            self.before_call.write_code("} else {")
            self.before_call.indent()

            self.before_call.write_code("// visibility: %r" % self.visibility)
            try:
                if self.visibility not in ['public']:
                    raise CodeGenerationError("private/protected constructor")
                class_.get_construct_name()
            except CodeGenerationError:
                self.before_call.write_code('PyErr_SetString(PyExc_TypeError, "class \'%s\' '
                                            'cannot be constructed");' % class_.name)
                self.before_call.write_code('return -1;')
            else:
                class_.write_create_instance(self.before_call, "self->obj", ", ".join(self.call_params))
                self.before_call.write_code("self->flags = PYBINDGEN_WRAPPER_FLAG_NONE;")
                class_.write_post_instance_creation_code(self.before_call, "self->obj", ", ".join(self.call_params))

            self.before_call.unindent()
            self.before_call.write_code("}")

        if self.throw:
            for exc in self.throw:
                self.before_call.unindent()
                self.before_call.write_code('} catch (%s const &exc) {' % exc.full_name)
                self.before_call.indent()
                self.before_call.write_cleanup()
                exc.write_convert_to_python(self.before_call, 'exc')
                self.before_call.write_code('return -1;')
            self.before_call.unindent()
            self.before_call.write_code('}')

    def _before_call_hook(self):
        "hook that post-processes parameters and check for custodian=<n> CppClass parameters"
        cppclass_typehandlers.implement_parameter_custodians_precall(self)

    def _before_return_hook(self):
        "hook that post-processes parameters and check for custodian=<n> CppClass parameters"
        cppclass_typehandlers.implement_parameter_custodians_postcall(self)

    def generate(self, code_sink, wrapper_name=None, extra_wrapper_params=()):
        """
        Generates the wrapper code
        :param code_sink: a CodeSink instance that will receive the generated code
        :returns: the wrapper function name.

        """

        if self.visibility == 'private':
            raise utils.SkipWrapper("Class %r has a private constructor ->"
                                    " cannot generate a constructor for it" % self._class.full_name)
        elif self.visibility == 'protected':
            if self._class.helper_class is None:
                raise utils.SkipWrapper("Class %r has a protected constructor and no helper class"
                                        " -> cannot generate a constructor for it" % self._class.full_name)

        #assert isinstance(class_, CppClass)
        tmp_sink = codesink.MemoryCodeSink()

        assert self._class is not None
        self.generate_body(tmp_sink, gen_call_params=[self._class])

        assert ((self.parse_params.get_parameters() == ['""'])
                or self.parse_params.get_keywords() is not None), \
               ("something went wrong with the type handlers;"
                " constructors need parameter names, "
                "yet no names were given for the class %s constructor"
                % self._class.name)

        if wrapper_name is None:
            self.wrapper_actual_name = self.wrapper_base_name
        else:
            self.wrapper_actual_name = wrapper_name

        self.wrapper_return = 'static int'
        self.wrapper_args = ["%s *self" % self._class.pystruct,
                             "PyObject *args", "PyObject *kwargs"]
        self.wrapper_args.extend(extra_wrapper_params)

        self.write_open_wrapper(code_sink)
        tmp_sink.flush_to(code_sink)
        code_sink.writeln('return 0;')
        self.write_close_wrapper(code_sink)

    def __str__(self):
        if not hasattr(self, '_class'):
            return object.__str__(self)

        if self._class is None:
            cls_name = "???"
        else:
            cls_name = self._class.full_name
        
        if self.return_value is None:
            retval = "retval?"
        else:
            retval = self.return_value.ctype

        if self.parameters is None:
            params = 'params?'
        else:
            params = ', '.join(["%s %s" % (param.ctype, param.name) for param in self.parameters])

        return ("%s: %s %s::%s (%s);" %
                (self.visibility, retval, cls_name, cls_name, params))


class CppFunctionAsConstructor(CppConstructor):
    """
    Class that generates a wrapper to a C/C++ function that appears as a contructor.
    """
    def __init__(self, c_function_name, return_value, parameters, unblock_threads=None):
        """
        :param c_function_name: name of the C/C++ function; FIXME: for
           now it is implied that this function returns a pointer to
           the a class instance with caller_owns_return=True
           semantics.

        :param return_value: function return value type
        :type return_value: L{ReturnValue}

        :param parameters: the function/constructor parameters
        :type parameters: list of L{Parameter}

        """
        self.stack_where_defined = traceback.extract_stack()
        if unblock_threads is None:
            unblock_threads = settings.unblock_threads

        parameters = [utils.eval_param(param, self) for param in parameters]
        super(CppFunctionAsConstructor, self).__init__(parameters)
        self.c_function_name = c_function_name
        self.function_return_value = return_value

    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        if class_ is None:
            class_ = self._class
        #assert isinstance(class_, CppClass)
        assert class_.helper_class is None
        ## FIXME: check caller_owns_return in self.function_return_value
        self.before_call.write_code("self->obj = %s(%s);" %
                                    (self.c_function_name, ", ".join(self.call_params)))
        self.before_call.write_code("self->flags = PYBINDGEN_WRAPPER_FLAG_NONE;")


class CppOverloadedConstructor(overloading.OverloadedWrapper):
    "Support class for overloaded constructors"
    RETURN_TYPE = 'int'
    ERROR_RETURN = 'return -1;'


class CppNoConstructor(ForwardWrapperBase):
    """

    Class that generates a constructor that raises an exception saying
    that the class has no constructor.

    """

    def __init__(self, reason):
        """
        :param reason: string indicating reason why the class cannot be constructed.
        """
        self.stack_where_defined = traceback.extract_stack()
        super(CppNoConstructor, self).__init__(
            None, [],
            "return -1;", "return -1;")
        self.reason = reason

    def generate_call(self):
        "dummy method, not really called"
        pass
    
    def generate(self, code_sink, class_):
        """
        Generates the wrapper code

        :param code_sink: a CodeSink instance that will receive the generated code
        :param class_: the c++ class wrapper the method belongs to

        Returns the wrapper function name.
        """
        #assert isinstance(class_, CppClass)

        self.wrapper_actual_name = "_wrap_%s__tp_init" % (
            class_.pystruct,)
        self.wrapper_return = 'static int'
        self.wrapper_args = ["void"]

        self.write_open_wrapper(code_sink)

        code_sink.writeln('PyErr_SetString(PyExc_TypeError, "class \'%s\' '
                          'cannot be constructed (%s)");' % (class_.name, self.reason))
        code_sink.writeln('return -1;')

        self.write_close_wrapper(code_sink)


class CppVirtualMethodParentCaller(CppMethod):
    """
    Class that generates a wrapper that calls a virtual method default
    implementation in a parent base class.
    """

    def __init__(self, method, unblock_threads=None):
        super(CppVirtualMethodParentCaller, self).__init__(
            method.method_name, method.return_value, method.parameters, unblock_threads=unblock_threads)
        #self.static_decl = False
        self.method = method

    def get_class(self):
        return self.method.class_
    class_ = property(get_class)

    #def set_class(self, class_):
    #    "Set the class wrapper object (CppClass)"
    #    self._class = class_

    def generate_declaration(self, code_sink, extra_wrapper_parameters=()):
        ## We need to fake generate the code (and throw away the
        ## result) only in order to obtain correct method signature.
        self.reset_code_generation_state()
        self.generate(codesink.NullCodeSink(), extra_wrapper_params=extra_wrapper_parameters)
        assert isinstance(self.wrapper_return, str)
        assert isinstance(self.wrapper_actual_name, str)
        assert isinstance(self.wrapper_args, list)
        code_sink.writeln('%s %s(%s);' % (self.wrapper_return, self.wrapper_actual_name, ', '.join(self.wrapper_args)))
        self.reset_code_generation_state()

    def generate_class_declaration(self, code_sink, extra_wrapper_parameters=()):
        ## We need to fake generate the code (and throw away the
        ## result) only in order to obtain correct method signature.
        self.reset_code_generation_state()
        self.generate(codesink.NullCodeSink(), extra_wrapper_params=extra_wrapper_parameters)
        assert isinstance(self.wrapper_return, str)
        assert isinstance(self.wrapper_actual_name, str)
        assert isinstance(self.wrapper_args, list)
        dummy_cls, name = self.wrapper_actual_name.split('::')
        code_sink.writeln('static %s %s(%s);' % (self.wrapper_return, name, ', '.join(self.wrapper_args)))
        self.reset_code_generation_state()

    def generate_parent_caller_method(self, code_sink):
        ## generate a '%s__parent_caller' method (static methods
        ## cannot "conquer" 'protected' access type, only regular
        ## instance methods).
        code_sink.writeln('inline %s %s__parent_caller(%s)' % (
                self.return_value.ctype,
                self.method_name,
                ', '.join([join_ctype_and_name(param.ctype, param.name) for param in self.parameters])
                ))
        if self.return_value.ctype == 'void':
            code_sink.writeln('{ %s::%s(%s); }' % (self.method.class_.full_name, self.method_name,
                                                   ', '.join([param.name for param in self.parameters])))
        else:
            code_sink.writeln('{ return %s::%s(%s); }' % (self.method.class_.full_name, self.method_name,
                                                          ', '.join([param.name for param in self.parameters])))        


    def generate_call(self, class_=None):
        "virtual method implementation; do not call"
        class_ = self.class_
        helper = self.before_call.declare_variable(
            type_=('%s*' % self._helper_class.name),
            name='helper',
            initializer=("dynamic_cast< %s* >(self->obj)" %  self._helper_class.name))
        method = '%s->%s__parent_caller' % (helper, self.method_name)
        self.before_call.write_error_check(
            "%s == NULL" % helper,
            'PyErr_SetString(PyExc_TypeError, "Method %s of class %s is protected and can only be called by a subclass");'
            % (self.method_name, self.class_.name))
        
        if self.return_value.ctype == 'void':
            self.before_call.write_code(
                '%s(%s);' %
                (method, ", ".join(self.call_params)))
        else:
            if self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
                self.before_call.write_code(
                    '%s retval = %s(%s);' %
                    (self.return_value.ctype, method, ", ".join(self.call_params)))
            else:
                self.before_call.write_code(
                    'retval = %s(%s);' %
                    (method, ", ".join(self.call_params)))

    def get_py_method_def(self, method_name=None):
        "Get the PyMethodDef entry suitable for this method"

        assert self.wrapper_actual_name == self.wrapper_base_name, \
            "wrapper_actual_name=%r but wrapper_base_name=%r" % \
            (self.wrapper_actual_name, self.wrapper_base_name)
        assert self._helper_class is not None
        if method_name is None:
            method_name = self.method_name
        flags = self.get_py_method_def_flags()
        return "{(char *) \"%s\", (PyCFunction) %s, %s, %s }," % \
               (method_name,
                self.wrapper_actual_name,#'::'.join((self._helper_class.name, self.wrapper_actual_name)),
                '|'.join(flags),
                (self.docstring is None and "NULL" or ('"'+self.docstring+'"')))

    def clone(self):
        """
        Creates a semi-deep copy of this method wrapper.  The returned
        method wrapper clone contains copies of all parameters, so
        they can be modified at will.
        """
        meth = CppVirtualMethodParentCaller(
            self.return_value,
            self.method_name,
            [copy(param) for param in self.parameters])
        #meth._class = self._class
        meth.method = self.method
        meth._helper_class = self._helper_class
        meth.docstring = self.docstring
        meth.wrapper_base_name = self.wrapper_base_name
        meth.wrapper_actual_name = self.wrapper_actual_name
        return meth


class CppVirtualMethodProxy(ReverseWrapperBase):
    """
    Class that generates a proxy virtual method that calls a similarly named python method.
    """

    def __init__(self, method):
        self.stack_where_defined = traceback.extract_stack()
        super(CppVirtualMethodProxy, self).__init__(method.return_value, method.parameters)
        self.method_name = method.method_name
        self.method = method
        self._helper_class = None

    def get_class(self):
        "Get the class wrapper object (CppClass)"
        return self.method.class_
    class_ = property(get_class)

    def set_helper_class(self, helper_class):
        "Set the C++ helper class, which is used for overriding virtual methods"
        self._helper_class = helper_class
        self.wrapper_base_name = "_wrap_%s" % self.method_name
    def get_helper_class(self):
        "Get the C++ helper class, which is used for overriding virtual methods"
        return self._helper_class
    helper_class = property(get_helper_class, set_helper_class)


    def generate_python_call(self):
        """code to call the python method"""
        if settings._get_deprecated_virtuals():
            params = ['m_pyself', '(char *) "_%s"' % self.method_name]
        else:
            params = ['m_pyself', '(char *) "%s"' % self.method_name]
        build_params = self.build_params.get_parameters()
        if build_params[0][0] == '"':
            build_params[0] = '(char *) ' + build_params[0]
        params.extend(build_params)
        self.before_call.write_code('py_retval = PyObject_CallMethod(%s);'
                                    % (', '.join(params),))
        self.before_call.write_error_check('py_retval == NULL', failure_cleanup='PyErr_Print();')
        self.before_call.add_cleanup_code('Py_DECREF(py_retval);')

    def generate_declaration(self, code_sink):
        if self.method.is_const:
            decl_post_modifiers = ' const'
        else:
            decl_post_modifiers = ''

        if self.method.throw:
            decl_post_modifiers += " throw (%s)" % (', '.join([ex.full_name for ex in self.method.throw]),)

        params_list = ', '.join([join_ctype_and_name(param.ctype, param.name)
                                 for param in self.parameters])
        code_sink.writeln("virtual %s %s(%s)%s;" %
                          (self.return_value.ctype, self.method_name, params_list,
                           decl_post_modifiers))


    def generate(self, code_sink):
        """generates the proxy virtual method"""
        if self.method.is_const:
            decl_post_modifiers = ['const']
        else:
            decl_post_modifiers = []

        if self.method.throw:
            decl_post_modifiers.append("throw (%s)" % (', '.join([ex.full_name for ex in self.method.throw]),))

        ## if the python subclass doesn't define a virtual method,
        ## just chain to parent class and don't do anything else
        call_params = ', '.join([param.name for param in self.parameters])
        py_method = self.declarations.declare_variable('PyObject*', 'py_method')
        if settings._get_deprecated_virtuals():
            self.before_call.write_code('%s = PyObject_GetAttrString(m_pyself, (char *) "_%s"); PyErr_Clear();'
                                        % (py_method, self.method_name))
        else:
            self.before_call.write_code('%s = PyObject_GetAttrString(m_pyself, (char *) "%s"); PyErr_Clear();'
                                        % (py_method, self.method_name))
        self.before_call.add_cleanup_code('Py_XDECREF(%s);' % py_method)
        
        self.before_call.write_code(
            r'if (%s == NULL || %s->ob_type == &PyCFunction_Type) {' % (py_method, py_method))
        if self.return_value.ctype == 'void':
            if not (self.method.is_pure_virtual or self.method.visibility == 'private'):
                self.before_call.write_code(r'    %s::%s(%s);'
                                            % (self.class_.full_name, self.method_name, call_params))
            self.before_call.write_cleanup()
            self.before_call.write_code(r'    return;')
        else:
            if self.method.is_pure_virtual or self.method.visibility == 'private':
                if isinstance(self.return_value, cppclass.CppClassReturnValue) \
                        and self.return_value.cpp_class.has_trivial_constructor:
                    pass
                else:
                    self.set_error_return('''
PyErr_Print();
Py_FatalError("Error detected, but parent virtual is pure virtual or private virtual, "
              "and return is a class without trival constructor");''')
            else:
                self.set_error_return("return %s::%s(%s);"
                                      % (self.class_.full_name, self.method_name, call_params))
            self.before_call.indent()
            self.before_call.write_cleanup()
            self.before_call.write_code(self.error_return)
            self.before_call.unindent()
        self.before_call.write_code('}')

        ## Set "m_pyself->obj = this" around virtual method call invocation
        self_obj_before = self.declarations.declare_variable(
            '%s*' % self.class_.full_name, 'self_obj_before')
        self.before_call.write_code("%s = reinterpret_cast< %s* >(m_pyself)->obj;" %
                                    (self_obj_before, self.class_.pystruct))
        if self.method.is_const:
            this_expression = ("const_cast< %s* >((const %s*) this)" %
                               (self.class_.full_name, self.class_.full_name))
        else:
            this_expression = "(%s*) this" % (self.class_.full_name)
        self.before_call.write_code("reinterpret_cast< %s* >(m_pyself)->obj = %s;" %
                                    (self.class_.pystruct, this_expression))
        self.before_call.add_cleanup_code("reinterpret_cast< %s* >(m_pyself)->obj = %s;" %
                                          (self.class_.pystruct, self_obj_before))
        
        super(CppVirtualMethodProxy, self).generate(
            code_sink, '::'.join((self._helper_class.name, self.method_name)),
            decl_modifiers=[],
            decl_post_modifiers=decl_post_modifiers)


    def __str__(self):
        return str(self.method)


class CustomCppMethodWrapper(CppMethod):
    """
    Adds a custom method wrapper.  The custom wrapper must be
    prepared to support overloading, i.e. it must have an additional
    "PyObject \\*\\*return_exception" parameter, and raised exceptions
    must be returned by this parameter.
    """

    NEEDS_OVERLOADING_INTERFACE = True

    def __init__(self, method_name, wrapper_name, wrapper_body=None,
                 flags=('METH_VARARGS', 'METH_KEYWORDS')):
        super(CustomCppMethodWrapper, self).__init__(method_name, ReturnValue.new('void'), [])
        self.wrapper_base_name = wrapper_name
        self.wrapper_actual_name = wrapper_name
        self.meth_flags = list(flags)
        self.wrapper_body = wrapper_body


    def generate(self, code_sink, dummy_wrapper_name=None, extra_wrapper_params=()):
        assert extra_wrapper_params == ["PyObject **return_exception"]

        self.wrapper_args = ["%s *self" % self.class_.pystruct, "PyObject *args", "PyObject *kwargs", "PyObject **return_exception"]
        self.wrapper_return = "PyObject *"
        if self.wrapper_body is not None:
            code_sink.writeln(self.wrapper_body)
        else:
            self.generate_declaration(code_sink, extra_wrapper_parameters=extra_wrapper_params)

    def generate_declaration(self, code_sink, extra_wrapper_parameters=()):
        assert isinstance(self.wrapper_return, str)
        assert isinstance(self.wrapper_actual_name, str)
        assert isinstance(self.wrapper_args, list)
        code_sink.writeln('%s %s(%s);' % (self.wrapper_return, self.wrapper_actual_name, ', '.join(self.wrapper_args)))

    def generate_call(self, *args, **kwargs):
        pass



class CustomCppConstructorWrapper(CppConstructor):
    """
    Adds a custom constructor wrapper.  The custom wrapper must be
    prepared to support overloading, i.e. it must have an additional
    \\"PyObject \\*\\*return_exception\\" parameter, and raised exceptions
    must be returned by this parameter.
    """

    NEEDS_OVERLOADING_INTERFACE = True

    def __init__(self, wrapper_name, wrapper_body):
        super(CustomCppConstructorWrapper, self).__init__([])
        self.wrapper_base_name = wrapper_name
        self.wrapper_actual_name = wrapper_name
        self.wrapper_body = wrapper_body

    def generate(self, code_sink, dummy_wrapper_name=None, extra_wrapper_params=()):
        assert extra_wrapper_params == ["PyObject **return_exception"]
        code_sink.writeln(self.wrapper_body)
        return ("int %s (%s *self, PyObject *args, PyObject *kwargs, PyObject **return_exception)"
                % (self.wrapper_actual_name, self.class_.pystruct))

    def generate_call(self, *args, **kwargs):
        pass

import cppclass
import cppclass_typehandlers
