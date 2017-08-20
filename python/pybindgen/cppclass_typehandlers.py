import warnings

from typehandlers.base import ForwardWrapperBase, ReverseWrapperBase, \
    Parameter, ReturnValue, TypeConfigurationError, NotSupportedError

import cppclass


###
### ------------ C++ class parameter type handlers ------------
###


def common_shared_object_return(value, py_name, cpp_class, code_block,
                                type_traits, caller_owns_return,
                                reference_existing_object, type_is_pointer):

    if type_is_pointer:
        value_value = '(*%s)' % value
        value_ptr = value
    else:
        value_ptr = '(&%s)' % value
        value_value = value
    def write_create_new_wrapper():
        """Code path that creates a new wrapper for the returned object"""

        ## Find out what Python wrapper to use, in case
        ## automatic_type_narrowing is active and we are not forced to
        ## make a copy of the object
        if (cpp_class.automatic_type_narrowing
            and (caller_owns_return or isinstance(cpp_class.memory_policy,
                                                  cppclass.ReferenceCountingPolicy))):

            typeid_map_name = cpp_class.get_type_narrowing_root().typeid_map_name
            wrapper_type = code_block.declare_variable(
                'PyTypeObject*', 'wrapper_type', '0')
            code_block.write_code(
                '%s = %s.lookup_wrapper(typeid(%s), &%s);'
                % (wrapper_type, typeid_map_name, value_value, cpp_class.pytypestruct))

        else:

            wrapper_type = '&'+cpp_class.pytypestruct

        ## Create the Python wrapper object
        if cpp_class.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'
        code_block.write_code(
            "%s = %s(%s, %s);" %
            (py_name, new_func, cpp_class.pystruct, wrapper_type))

        if cpp_class.allow_subclassing:
            code_block.write_code(
                "%s->inst_dict = NULL;" % (py_name,))

        ## Assign the C++ value to the Python wrapper
        if caller_owns_return:
            if type_traits.target_is_const:
                code_block.write_code("%s->obj = (%s *) (%s);" % (py_name, cpp_class.full_name, value_ptr))                
            else:
                code_block.write_code("%s->obj = %s;" % (py_name, value_ptr))
            code_block.write_code(
                "%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (py_name,))
        else:
            if not isinstance(cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                if reference_existing_object:
                    if type_traits.target_is_const:
                        code_block.write_code("%s->obj = (%s *) (%s);" % (py_name, cpp_class.full_name, value_ptr))
                    else:
                        code_block.write_code("%s->obj = %s;" % (py_name, value_ptr))
                    code_block.write_code(
                        "%s->flags = PYBINDGEN_WRAPPER_FLAG_OBJECT_NOT_OWNED;" % (py_name,))
                else:
                    # The PyObject creates its own copy
                    cpp_class.write_create_instance(code_block,
                                                         "%s->obj" % py_name,
                                                         value_value)
                    code_block.write_code(
                        "%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (py_name,))
                    cpp_class.write_post_instance_creation_code(code_block,
                                                                "%s->obj" % py_name,
                                                                value_value)
            else:
                ## The PyObject gets a new reference to the same obj
                code_block.write_code(
                    "%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (py_name,))
                cpp_class.memory_policy.write_incref(code_block, value_ptr)
                if type_traits.target_is_const:
                    code_block.write_code("%s->obj = (%s*) (%s);" %
                                                  (py_name, cpp_class.full_name, value_ptr))
                else:
                    code_block.write_code("%s->obj = %s;" % (py_name, value_ptr))

    ## closes def write_create_new_wrapper():

    if cpp_class.helper_class is None:
        try:
            cpp_class.wrapper_registry.write_lookup_wrapper(
                code_block, cpp_class.pystruct, py_name, value_ptr)
        except NotSupportedError:
            write_create_new_wrapper()
            cpp_class.wrapper_registry.write_register_new_wrapper(
                code_block, py_name, "%s->obj" % py_name)
        else:
            code_block.write_code("if (%s == NULL) {" % py_name)
            code_block.indent()
            write_create_new_wrapper()
            cpp_class.wrapper_registry.write_register_new_wrapper(
                code_block, py_name, "%s->obj" % py_name)
            code_block.unindent()

            # If we are already referencing the existing python wrapper,
            # we do not need a reference to the C++ object as well.
            if caller_owns_return and \
                    isinstance(cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                code_block.write_code("} else {")
                code_block.indent()
                cpp_class.memory_policy.write_decref(code_block, value_ptr)
                code_block.unindent()
                code_block.write_code("}")
            else:
                code_block.write_code("}")            
    else:
        # since there is a helper class, check if this C++ object is an instance of that class
        # http://stackoverflow.com/questions/579887/how-expensive-is-rtti/1468564#1468564
        code_block.write_code("if (typeid(%s).name() == typeid(%s).name())\n{"
                              % (value_value, cpp_class.helper_class.name))
        code_block.indent()

        # yes, this is an instance of the helper class; we can get
        # the existing python wrapper directly from the helper
        # class...
        if type_traits.target_is_const:
            const_cast_value = "const_cast<%s *>(%s) " % (cpp_class.full_name, value_ptr)
        else:
            const_cast_value = value_ptr
        code_block.write_code(
            "%s = reinterpret_cast< %s* >(reinterpret_cast< %s* >(%s)->m_pyself);"
            % (py_name, cpp_class.pystruct,
               cpp_class.helper_class.name, const_cast_value))

        code_block.write_code("%s->obj = %s;" % (py_name, const_cast_value))

        # We are already referencing the existing python wrapper,
        # so we do not need a reference to the C++ object as well.
        if caller_owns_return and \
                isinstance(cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
            cpp_class.memory_policy.write_decref(code_block, value_ptr)

        code_block.write_code("Py_INCREF(%s);" % py_name)
        code_block.unindent()
        code_block.write_code("} else {") # if (typeid(*(%s)) == typeid(%s)) { ...
        code_block.indent()

        # no, this is not an instance of the helper class, we may
        # need to create a new wrapper, or reference existing one
        # if the wrapper registry tells us there is one already.

        # first check in the wrapper registry...
        try:
            cpp_class.wrapper_registry.write_lookup_wrapper(
                code_block, cpp_class.pystruct, py_name, value_ptr)
        except NotSupportedError:
            write_create_new_wrapper()
            cpp_class.wrapper_registry.write_register_new_wrapper(
                code_block, py_name, "%s->obj" % py_name)
        else:
            code_block.write_code("if (%s == NULL) {" % py_name)
            code_block.indent()

            # wrapper registry told us there is no wrapper for
            # this instance => need to create new one
            write_create_new_wrapper()
            cpp_class.wrapper_registry.write_register_new_wrapper(
                code_block, py_name, "%s->obj" % py_name)
            code_block.unindent()

            # handle ownership rules...
            if caller_owns_return and \
                    isinstance(cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                code_block.write_code("} else {")
                code_block.indent()
                # If we are already referencing the existing python wrapper,
                # we do not need a reference to the C++ object as well.
                cpp_class.memory_policy.write_decref(code_block, value_ptr)
                code_block.unindent()
                code_block.write_code("}")
            else:
                code_block.write_code("}")            

        code_block.unindent()
        code_block.write_code("}") # closes: if (typeid(*(%s)) == typeid(%s)) { ... } else { ...



class CppClassParameterBase(Parameter):
    "Base class for all C++ Class parameter handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False, default_value=None):
        """
        :param ctype: C type, normally 'MyClass*'
        :param name: parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassParameterBase, self).__init__(
            ctype, name, direction, is_const, default_value)

        ## name of the PyFoo * variable used in parameter parsing
        self.py_name = None

        ## it True, this parameter is 'fake', and instead of being
        ## passed a parameter from python it is assumed to be the
        ## 'self' parameter of a method wrapper
        self.take_value_from_python_self = False


class CppClassReturnValueBase(ReturnValue):
    "Class return handlers -- base class"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance

    def __init__(self, ctype, is_const=False):
        super(CppClassReturnValueBase, self).__init__(ctype, is_const=is_const)
        ## name of the PyFoo * variable used in return value building
        self.py_name = None


class CppClassParameter(CppClassParameterBase):
    """
    Class parameter "by-value" handler
    """
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN]
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, cppclass.CppClass)

        if self.take_value_from_python_self:
            self.py_name = 'self'
            wrapper.call_params.append(
                '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
        else:
            implicit_conversion_sources = self.cpp_class.get_all_implicit_conversions()
            if not implicit_conversion_sources:
                if self.default_value is not None:
                    self.cpp_class.get_construct_name() # raises an exception if the class cannot be constructed
                    self.py_name = wrapper.declarations.declare_variable(
                        self.cpp_class.pystruct+'*', self.name, 'NULL')
                    wrapper.parse_params.add_parameter(
                        'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name, optional=True)
                    wrapper.call_params.append(
                        '(%s ? (*((%s *) %s)->obj) : %s)' % (self.py_name, self.cpp_class.pystruct, self.py_name, self.default_value))
                else:
                    self.py_name = wrapper.declarations.declare_variable(
                        self.cpp_class.pystruct+'*', self.name)
                    wrapper.parse_params.add_parameter(
                        'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
                    wrapper.call_params.append(
                        '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
            else:
                if self.default_value is None:
                    self.py_name = wrapper.declarations.declare_variable(
                        'PyObject*', self.name)
                    tmp_value_variable = wrapper.declarations.declare_variable(
                        self.cpp_class.full_name, self.name)
                    wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name)
                else:
                    self.py_name = wrapper.declarations.declare_variable(
                        'PyObject*', self.name, 'NULL')
                    tmp_value_variable = wrapper.declarations.declare_variable(
                        self.cpp_class.full_name, self.name)
                    wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name, optional=True)

                if self.default_value is None:
                    wrapper.before_call.write_code("if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                   "    %s = *((%s *) %s)->obj;" %
                                                   (self.py_name, self.cpp_class.pytypestruct,
                                                    tmp_value_variable,
                                                    self.cpp_class.pystruct, self.py_name))
                else:
                    wrapper.before_call.write_code(
                        "if (%s == NULL) {\n"
                        "    %s = %s;" %
                        (self.py_name, tmp_value_variable, self.default_value))
                    wrapper.before_call.write_code(
                        "} else if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                   "    %s = *((%s *) %s)->obj;" %
                                                   (self.py_name, self.cpp_class.pytypestruct,
                                                    tmp_value_variable,
                                                    self.cpp_class.pystruct, self.py_name))
                for conversion_source in implicit_conversion_sources:
                    wrapper.before_call.write_code("} else if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                   "    %s = *((%s *) %s)->obj;" %
                                                   (self.py_name, conversion_source.pytypestruct,
                                                    tmp_value_variable,
                                                    conversion_source.pystruct, self.py_name))
                wrapper.before_call.write_code("} else {\n")
                wrapper.before_call.indent()
                possible_type_names = ", ".join([cls.name for cls in [self.cpp_class] + implicit_conversion_sources])
                wrapper.before_call.write_code("PyErr_Format(PyExc_TypeError, \"parameter must an instance of one of the types (%s), not %%s\", %s->ob_type->tp_name);" % (possible_type_names, self.py_name))
                wrapper.before_call.write_error_return()
                wrapper.before_call.unindent()
                wrapper.before_call.write_code("}")

                wrapper.call_params.append(tmp_value_variable)

    def convert_c_to_python(self, wrapper):
        '''Write some code before calling the Python method.'''
        assert isinstance(wrapper, ReverseWrapperBase)

        self.py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        if self.cpp_class.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'
        wrapper.before_call.write_code(
            "%s = %s(%s, %s);" %
            (self.py_name, new_func, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        if self.cpp_class.allow_subclassing:
            wrapper.before_call.write_code(
                "%s->inst_dict = NULL;" % (self.py_name,))
        wrapper.before_call.write_code("%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (self.py_name,))

        self.cpp_class.write_create_instance(wrapper.before_call,
                                             "%s->obj" % self.py_name,
                                             self.value)
        self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, self.py_name,
                                                                   "%s->obj" % self.py_name)
        self.cpp_class.write_post_instance_creation_code(wrapper.before_call,
                                                         "%s->obj" % self.py_name,
                                                         self.value)

        wrapper.build_params.add_parameter("N", [self.py_name])


class CppClassRefParameter(CppClassParameterBase):
    "Class& handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_INOUT]

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False,
                 default_value=None, default_value_type=None):
        """
        :param ctype: C type, normally 'MyClass*'
        :param name: parameter name
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassRefParameter, self).__init__(
            ctype, name, direction, is_const, default_value)
        self.default_value_type = default_value_type
    
    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, cppclass.CppClass)

        if self.direction == Parameter.DIRECTION_IN:
            if self.take_value_from_python_self:
                self.py_name = 'self'
                wrapper.call_params.append(
                    '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
            else:
                implicit_conversion_sources = self.cpp_class.get_all_implicit_conversions()
                if not (implicit_conversion_sources and self.type_traits.target_is_const):
                    if self.default_value is not None:
                        self.py_name = wrapper.declarations.declare_variable(
                            self.cpp_class.pystruct+'*', self.name, 'NULL')

                        wrapper.parse_params.add_parameter(
                            'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name, optional=True)

                        if self.default_value_type is not None:
                            default_value_name = wrapper.declarations.declare_variable(
                                self.default_value_type, "%s_default" % self.name,
                                self.default_value)
                            wrapper.call_params.append(
                                '(%s ? (*((%s *) %s)->obj) : %s)' % (self.py_name, self.cpp_class.pystruct,
                                                                     self.py_name, default_value_name))
                        else:
                            self.cpp_class.get_construct_name() # raises an exception if the class cannot be constructed
                            wrapper.call_params.append(
                                '(%s ? (*((%s *) %s)->obj) : %s)' % (self.py_name, self.cpp_class.pystruct,
                                                                     self.py_name, self.default_value))
                    else:
                        self.py_name = wrapper.declarations.declare_variable(
                            self.cpp_class.pystruct+'*', self.name)
                        wrapper.parse_params.add_parameter(
                            'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
                        wrapper.call_params.append(
                            '*((%s *) %s)->obj' % (self.cpp_class.pystruct, self.py_name))
                else:
                    if self.default_value is not None:
                        warnings.warn("with implicit conversions, default value "
                                      "in C++ class reference parameters is ignored.")
                    self.py_name = wrapper.declarations.declare_variable(
                        'PyObject*', self.name)
                    tmp_value_variable = wrapper.declarations.declare_variable(
                        self.cpp_class.full_name, self.name)
                    wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name)

                    wrapper.before_call.write_code("if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                   "    %s = *((%s *) %s)->obj;" %
                                                   (self.py_name, self.cpp_class.pytypestruct,
                                                    tmp_value_variable,
                                                    self.cpp_class.pystruct, self.py_name))
                    for conversion_source in implicit_conversion_sources:
                        wrapper.before_call.write_code("} else if (PyObject_IsInstance(%s, (PyObject*) &%s)) {\n"
                                                       "    %s = *((%s *) %s)->obj;" %
                                                       (self.py_name, conversion_source.pytypestruct,
                                                        tmp_value_variable,
                                                        conversion_source.pystruct, self.py_name))
                    wrapper.before_call.write_code("} else {\n")
                    wrapper.before_call.indent()
                    possible_type_names = ", ".join([cls.name for cls in [self.cpp_class] + implicit_conversion_sources])
                    wrapper.before_call.write_code("PyErr_Format(PyExc_TypeError, \"parameter must an instance of one of the types (%s), not %%s\", %s->ob_type->tp_name);" % (possible_type_names, self.py_name))
                    wrapper.before_call.write_error_return()
                    wrapper.before_call.unindent()
                    wrapper.before_call.write_code("}")

                    wrapper.call_params.append(tmp_value_variable)

        elif self.direction == Parameter.DIRECTION_OUT:
            assert not self.take_value_from_python_self

            self.py_name = wrapper.declarations.declare_variable(
                self.cpp_class.pystruct+'*', self.name)

            if self.cpp_class.allow_subclassing:
                new_func = 'PyObject_GC_New'
            else:
                new_func = 'PyObject_New'
            wrapper.before_call.write_code(
                "%s = %s(%s, %s);" %
                (self.py_name, new_func, self.cpp_class.pystruct,
                 '&'+self.cpp_class.pytypestruct))
            if self.cpp_class.allow_subclassing:
                wrapper.after_call.write_code(
                    "%s->inst_dict = NULL;" % (self.py_name,))
            wrapper.after_call.write_code("%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (self.py_name,))

            self.cpp_class.write_create_instance(wrapper.before_call,
                                                 "%s->obj" % self.py_name,
                                                 '')
            self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, self.py_name,
                                                                       "%s->obj" % self.py_name)
            self.cpp_class.write_post_instance_creation_code(wrapper.before_call,
                                                             "%s->obj" % self.py_name,
                                                             '')
            wrapper.call_params.append('*%s->obj' % (self.py_name,))
            wrapper.build_params.add_parameter("N", [self.py_name])

        ## well, personally I think inout here doesn't make much sense
        ## (it's just plain confusing), but might as well support it..

        ## C++ class reference inout parameters allow "inplace"
        ## modifications, i.e. the object is not explicitly returned
        ## but is instead modified by the callee.
        elif self.direction == Parameter.DIRECTION_INOUT:
            assert not self.take_value_from_python_self

            self.py_name = wrapper.declarations.declare_variable(
                self.cpp_class.pystruct+'*', self.name)

            wrapper.parse_params.add_parameter(
                'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name)
            wrapper.call_params.append(
                '*%s->obj' % (self.py_name))

    def convert_c_to_python(self, wrapper):
        '''Write some code before calling the Python method.'''
        assert isinstance(wrapper, ReverseWrapperBase)

        self.py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        if self.cpp_class.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'
        wrapper.before_call.write_code(
            "%s = %s(%s, %s);" %
            (self.py_name, new_func, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        if self.cpp_class.allow_subclassing:
            wrapper.before_call.write_code(
                "%s->inst_dict = NULL;" % (self.py_name,))
        wrapper.before_call.write_code("%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (self.py_name,))

        if self.direction == Parameter.DIRECTION_IN:
            self.cpp_class.write_create_instance(wrapper.before_call,
                                                 "%s->obj" % self.py_name,
                                                 self.value)
            self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, self.py_name,
                                                                       "%s->obj" % self.py_name)
            self.cpp_class.write_post_instance_creation_code(wrapper.before_call,
                                                             "%s->obj" % self.py_name,
                                                             self.value)
            wrapper.build_params.add_parameter("N", [self.py_name])
        else:
            ## out/inout case:
            ## the callee receives a "temporary wrapper", which loses
            ## the ->obj pointer after the python call; this is so
            ## that the python code directly manipulates the object
            ## received as parameter, instead of a copy.
            if self.type_traits.target_is_const:
                value = "(%s*) (&(%s))" % (self.cpp_class.full_name, self.value)
            else:
                value = "&(%s)" % self.value
            wrapper.before_call.write_code(
                "%s->obj = %s;" % (self.py_name, value))
            wrapper.build_params.add_parameter("O", [self.py_name])
            wrapper.before_call.add_cleanup_code("Py_DECREF(%s);" % self.py_name)

            if self.cpp_class.has_copy_constructor:
                ## if after the call we notice the callee kept a reference
                ## to the pyobject, we then swap pywrapper->obj for a copy
                ## of the original object.  Else the ->obj pointer is
                ## simply erased (we never owned this object in the first
                ## place).
                wrapper.after_call.write_code(
                    "if (%s->ob_refcnt == 1)\n"
                    "    %s->obj = NULL;\n"
                    "else{\n" % (self.py_name, self.py_name))
                wrapper.after_call.indent()
                self.cpp_class.write_create_instance(wrapper.after_call,
                                                     "%s->obj" % self.py_name,
                                                     self.value)
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.after_call, self.py_name,
                                                                           "%s->obj" % self.py_name)
                self.cpp_class.write_post_instance_creation_code(wrapper.after_call,
                                                                 "%s->obj" % self.py_name,
                                                                 self.value)
                wrapper.after_call.unindent()
                wrapper.after_call.write_code('}')
            else:
                ## it's not safe for the python wrapper to keep a
                ## pointer to the object anymore; just set it to NULL.
                wrapper.after_call.write_code("%s->obj = NULL;" % (self.py_name,))


class CppClassReturnValue(CppClassReturnValueBase):
    "Class return handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    REQUIRES_ASSIGNMENT_CONSTRUCTOR = True

    def __init__(self, ctype, is_const=False):
        """override to fix the ctype parameter with namespace information"""
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassReturnValue, self).__init__(ctype, is_const=is_const)

    def get_c_error_return(self): # only used in reverse wrappers
        """See ReturnValue.get_c_error_return"""
        if self.type_traits.type_is_reference:
            raise NotSupportedError
        return "return %s();" % (self.cpp_class.full_name,)

    def convert_c_to_python(self, wrapper):
        """see ReturnValue.convert_c_to_python"""
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        self.py_name = py_name
        if self.cpp_class.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'
        wrapper.after_call.write_code(
            "%s = %s(%s, %s);" %
            (py_name, new_func, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
        if self.cpp_class.allow_subclassing:
            wrapper.after_call.write_code(
                "%s->inst_dict = NULL;" % (py_name,))
        wrapper.after_call.write_code("%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (py_name,))

        self.cpp_class.write_create_instance(wrapper.after_call,
                                             "%s->obj" % py_name,
                                             self.value)
        self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.after_call, py_name,
                                                                   "%s->obj" % py_name)
        self.cpp_class.write_post_instance_creation_code(wrapper.after_call,
                                                         "%s->obj" % py_name,
                                                         self.value)

        #...
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)

    def convert_python_to_c(self, wrapper):
        """see ReturnValue.convert_python_to_c"""
        if self.type_traits.type_is_reference:
            raise NotSupportedError
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', "tmp_%s" % self.cpp_class.name)
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name])
        if self.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
            wrapper.after_call.write_code('%s %s = *%s->obj;' %
                                          (self.cpp_class.full_name, self.value, name))
        else:
            wrapper.after_call.write_code('%s = *%s->obj;' % (self.value, name))


class CppClassRefReturnValue(CppClassReturnValueBase):
    "Class return handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    REQUIRES_ASSIGNMENT_CONSTRUCTOR = True

    def __init__(self, ctype, is_const=False, caller_owns_return=False, reference_existing_object=None,
                 return_internal_reference=None):
        #override to fix the ctype parameter with namespace information
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassRefReturnValue, self).__init__(ctype, is_const=is_const)
        self.reference_existing_object = reference_existing_object

        self.return_internal_reference = return_internal_reference
        if self.return_internal_reference:
            assert self.reference_existing_object is None
            self.reference_existing_object = True

        self.caller_owns_return = caller_owns_return

    def get_c_error_return(self): # only used in reverse wrappers
        """See ReturnValue.get_c_error_return"""
        if self.type_traits.type_is_reference:
            raise NotSupportedError
        return "return %s();" % (self.cpp_class.full_name,)

    def convert_c_to_python(self, wrapper):
        """see ReturnValue.convert_c_to_python"""
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        self.py_name = py_name

        if self.reference_existing_object or self.caller_owns_return:
            common_shared_object_return(self.value, py_name, self.cpp_class, wrapper.after_call,
                                        self.type_traits, self.caller_owns_return,
                                        self.reference_existing_object,
                                        type_is_pointer=False)
        else:

            if self.cpp_class.allow_subclassing:
                new_func = 'PyObject_GC_New'
            else:
                new_func = 'PyObject_New'
            wrapper.after_call.write_code(
                "%s = %s(%s, %s);" %
                (py_name, new_func, self.cpp_class.pystruct, '&'+self.cpp_class.pytypestruct))
            if self.cpp_class.allow_subclassing:
                wrapper.after_call.write_code(
                    "%s->inst_dict = NULL;" % (py_name,))
            wrapper.after_call.write_code("%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % (py_name,))

            self.cpp_class.write_create_instance(wrapper.after_call,
                                                 "%s->obj" % py_name,
                                                 self.value)
            self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.after_call, py_name,
                                                                       "%s->obj" % py_name)
            self.cpp_class.write_post_instance_creation_code(wrapper.after_call,
                                                             "%s->obj" % py_name,
                                                             self.value)

        #...
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)

    def convert_python_to_c(self, wrapper):
        """see ReturnValue.convert_python_to_c"""
        if self.type_traits.type_is_reference:
            raise NotSupportedError
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', "tmp_%s" % self.cpp_class.name)
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name])
        if self.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
            wrapper.after_call.write_code('%s %s = *%s->obj;' %
                                          (self.cpp_class.full_name, self.value, name))
        else:
            wrapper.after_call.write_code('%s = *%s->obj;' % (self.value, name))

    
class CppClassPtrParameter(CppClassParameterBase):
    "Class* handlers"
    CTYPES = []
    cpp_class = cppclass.CppClass('dummy') # CppClass instance
    DIRECTIONS = [Parameter.DIRECTION_IN,
                  Parameter.DIRECTION_OUT,
                  Parameter.DIRECTION_INOUT]
    SUPPORTS_TRANSFORMATIONS = True

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, transfer_ownership=None, custodian=None, is_const=False,
                 null_ok=False, default_value=None):
        """
        Type handler for a pointer-to-class parameter (MyClass*)

        :param ctype: C type, normally 'MyClass*'
        :param name: parameter name

        :param transfer_ownership: if True, the callee becomes
                  responsible for freeing the object.  If False, the
                  caller remains responsible for the object.  In
                  either case, the original object pointer is passed,
                  not a copy.  In case transfer_ownership=True, it is
                  invalid to perform operations on the object after
                  the call (calling any method will cause a null
                  pointer dereference and crash the program).

        :param custodian: if given, points to an object (custodian)
            that keeps the python wrapper for the
            parameter alive. Possible values are:
                       - None: no object is custodian;
                       - -1: the return value object;
                       - 0: the instance of the method in which
                            the ReturnValue is being used will become the
                            custodian;
                       - integer > 0: parameter number, starting at 1
                           (i.e. not counting the self/this parameter),
                           whose object will be used as custodian.

        :param is_const: if true, the parameter has a const attached to the leftmost

        :param null_ok: if true, None is accepted and mapped into a C NULL pointer

        :param default_value: default parameter value (as C expression
            string); probably, the only default value that makes sense
            here is probably 'NULL'.

        .. note::

            Only arguments which are instances of C++ classes
            wrapped by PyBindGen can be used as custodians.
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassPtrParameter, self).__init__(
            ctype, name, direction, is_const, default_value)

        if transfer_ownership is None and self.type_traits.target_is_const:
            transfer_ownership = False

        self.custodian = custodian
        self.transfer_ownership = transfer_ownership
        self.null_ok = null_ok

        if transfer_ownership is None:
            raise TypeConfigurationError("Missing transfer_ownership option")

    def convert_python_to_c(self, wrapper):
        "parses python args to get C++ value"
        assert isinstance(wrapper, ForwardWrapperBase)
        assert isinstance(self.cpp_class, cppclass.CppClass)

        if self.take_value_from_python_self:
            self.py_name = 'self'
            value_ptr = 'self->obj'
        else:
            self.py_name = wrapper.declarations.declare_variable(
                self.cpp_class.pystruct+'*', self.name,
                initializer=(self.default_value and 'NULL' or None))

            value_ptr = wrapper.declarations.declare_variable("%s*" % self.cpp_class.full_name,
                                                              "%s_ptr" % self.name)

            if self.null_ok:
                num = wrapper.parse_params.add_parameter('O', ['&'+self.py_name], self.name, optional=bool(self.default_value))

                wrapper.before_call.write_error_check(

                    "%s && ((PyObject *) %s != Py_None) && !PyObject_IsInstance((PyObject *) %s, (PyObject *) &%s)"
                    % (self.py_name, self.py_name, self.py_name, self.cpp_class.pytypestruct),

                    'PyErr_SetString(PyExc_TypeError, "Parameter %i must be of type %s");' % (num, self.cpp_class.name))

                wrapper.before_call.write_code("if (%(PYNAME)s) {\n"
                                               "    if ((PyObject *) %(PYNAME)s == Py_None)\n"
                                               "        %(VALUE)s = NULL;\n"
                                               "    else\n"
                                               "        %(VALUE)s = %(PYNAME)s->obj;\n"
                                               "} else {\n"
                                               "    %(VALUE)s = NULL;\n"
                                               "}" % dict(PYNAME=self.py_name, VALUE=value_ptr))

            else:

                wrapper.parse_params.add_parameter(
                    'O!', ['&'+self.cpp_class.pytypestruct, '&'+self.py_name], self.name, optional=bool(self.default_value))
                wrapper.before_call.write_code("%s = (%s ? %s->obj : NULL);" % (value_ptr, self.py_name, self.py_name))

        value = self.transformation.transform(self, wrapper.declarations, wrapper.before_call, value_ptr)
        wrapper.call_params.append(value)
        
        if self.transfer_ownership:
            if not isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                # if we transfer ownership, in the end we no longer own the object, so clear our pointer
                wrapper.after_call.write_code('if (%s) {' % self.py_name)
                wrapper.after_call.indent()
                self.cpp_class.wrapper_registry.write_unregister_wrapper(wrapper.after_call,
                                                                         '%s' % self.py_name,
                                                                         '%s->obj' % self.py_name)
                wrapper.after_call.write_code('%s->obj = NULL;' % self.py_name)
                wrapper.after_call.unindent()
                wrapper.after_call.write_code('}')
            else:
                wrapper.before_call.write_code("if (%s) {" % self.py_name)
                wrapper.before_call.indent()
                self.cpp_class.memory_policy.write_incref(wrapper.before_call, "%s->obj" % self.py_name)
                wrapper.before_call.unindent()
                wrapper.before_call.write_code("}")


    def convert_c_to_python(self, wrapper):
        """foo"""

        ## Value transformations
        value = self.transformation.untransform(
            self, wrapper.declarations, wrapper.after_call, self.value)

        ## declare wrapper variable
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        self.py_name = py_name

        def write_create_new_wrapper():
            """Code path that creates a new wrapper for the parameter"""

            ## Find out what Python wrapper to use, in case
            ## automatic_type_narrowing is active and we are not forced to
            ## make a copy of the object
            if (self.cpp_class.automatic_type_narrowing
                and (self.transfer_ownership or isinstance(self.cpp_class.memory_policy,
                                                           cppclass.ReferenceCountingPolicy))):

                typeid_map_name = self.cpp_class.get_type_narrowing_root().typeid_map_name
                wrapper_type = wrapper.declarations.declare_variable(
                    'PyTypeObject*', 'wrapper_type', '0')
                wrapper.before_call.write_code(
                    '%s = %s.lookup_wrapper(typeid(*%s), &%s);'
                    % (wrapper_type, typeid_map_name, value, self.cpp_class.pytypestruct))
            else:
                wrapper_type = '&'+self.cpp_class.pytypestruct

            ## Create the Python wrapper object
            if self.cpp_class.allow_subclassing:
                new_func = 'PyObject_GC_New'
            else:
                new_func = 'PyObject_New'
            wrapper.before_call.write_code(
                "%s = %s(%s, %s);" %
                (py_name, new_func, self.cpp_class.pystruct, wrapper_type))
            self.py_name = py_name

            if self.cpp_class.allow_subclassing:
                wrapper.before_call.write_code(
                    "%s->inst_dict = NULL;" % (py_name,))
            wrapper.before_call.write_code("%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % py_name)

            ## Assign the C++ value to the Python wrapper
            if self.transfer_ownership:
                wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
            else:
                if not isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                    ## The PyObject gets a temporary pointer to the
                    ## original value; the pointer is converted to a
                    ## copy in case the callee retains a reference to
                    ## the object after the call.

                    if self.direction == Parameter.DIRECTION_IN:
                        self.cpp_class.write_create_instance(wrapper.before_call,
                                                             "%s->obj" % self.py_name,
                                                             '*'+self.value)
                        self.cpp_class.write_post_instance_creation_code(wrapper.before_call,
                                                                         "%s->obj" % self.py_name,
                                                                         '*'+self.value)
                    else:
                        ## out/inout case:
                        ## the callee receives a "temporary wrapper", which loses
                        ## the ->obj pointer after the python call; this is so
                        ## that the python code directly manipulates the object
                        ## received as parameter, instead of a copy.
                        if self.type_traits.target_is_const:
                            unconst_value = "(%s*) (%s)" % (self.cpp_class.full_name, value)
                        else:
                            unconst_value = value
                        wrapper.before_call.write_code(
                            "%s->obj = %s;" % (self.py_name, unconst_value))
                        wrapper.build_params.add_parameter("O", [self.py_name])
                        wrapper.before_call.add_cleanup_code("Py_DECREF(%s);" % self.py_name)

                        if self.cpp_class.has_copy_constructor:
                            ## if after the call we notice the callee kept a reference
                            ## to the pyobject, we then swap pywrapper->obj for a copy
                            ## of the original object.  Else the ->obj pointer is
                            ## simply erased (we never owned this object in the first
                            ## place).

                            wrapper.after_call.write_code(
                                "if (%s->ob_refcnt == 1)\n"
                                "    %s->obj = NULL;\n"
                                "else {\n" % (self.py_name, self.py_name))
                            wrapper.after_call.indent()
                            self.cpp_class.write_create_instance(wrapper.after_call,
                                                                 "%s->obj" % self.py_name,
                                                                 '*'+value)
                            self.cpp_class.write_post_instance_creation_code(wrapper.after_call,
                                                                             "%s->obj" % self.py_name,
                                                                             '*'+value)
                            wrapper.after_call.unindent()
                            wrapper.after_call.write_code('}')
                        else:
                            ## it's not safe for the python wrapper to keep a
                            ## pointer to the object anymore; just set it to NULL.
                            wrapper.after_call.write_code("%s->obj = NULL;" % (self.py_name,))
                else:
                    ## The PyObject gets a new reference to the same obj
                    self.cpp_class.memory_policy.write_incref(wrapper.before_call, value)
                    if self.type_traits.target_is_const:
                        wrapper.before_call.write_code("%s->obj = (%s*) (%s);" %
                                                       (py_name, self.cpp_class.full_name, value))
                    else:
                        wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
        ## closes def write_create_new_wrapper():

        if self.cpp_class.helper_class is None:
            try:
                self.cpp_class.wrapper_registry.write_lookup_wrapper(
                    wrapper.before_call, self.cpp_class.pystruct, py_name, value)
            except NotSupportedError:
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, py_name,
                                                                           "%s->obj" % py_name)
            else:
                wrapper.before_call.write_code("if (%s == NULL)\n{" % py_name)
                wrapper.before_call.indent()
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, py_name,
                                                                           "%s->obj" % py_name)
                wrapper.before_call.unindent()
                wrapper.before_call.write_code('}')
            wrapper.build_params.add_parameter("N", [py_name])
        else:
            wrapper.before_call.write_code("if (typeid(*(%s)).name() == typeid(%s).name())\n{"
                                          % (value, self.cpp_class.helper_class.name))
            wrapper.before_call.indent()

            if self.type_traits.target_is_const:
                wrapper.before_call.write_code(
                    "%s = (%s*) (((%s*) ((%s*) %s))->m_pyself);"
                    % (py_name, self.cpp_class.pystruct,
                       self.cpp_class.helper_class.name, self.cpp_class.full_name, value))
                wrapper.before_call.write_code("%s->obj =  (%s*) (%s);" %
                                               (py_name, self.cpp_class.full_name, value))
            else:
                wrapper.before_call.write_code(
                    "%s = (%s*) (((%s*) %s)->m_pyself);"
                    % (py_name, self.cpp_class.pystruct,
                       self.cpp_class.helper_class.name, value))
                wrapper.before_call.write_code("%s->obj = %s;" % (py_name, value))
            wrapper.before_call.write_code("Py_INCREF(%s);" % py_name)
            wrapper.before_call.unindent()
            wrapper.before_call.write_code("} else {")
            wrapper.before_call.indent()

            try:
                self.cpp_class.wrapper_registry.write_lookup_wrapper(
                    wrapper.before_call, self.cpp_class.pystruct, py_name, value)
            except NotSupportedError:
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(
                    wrapper.before_call, py_name, "%s->obj" % py_name)
            else:
                wrapper.before_call.write_code("if (%s == NULL)\n{" % py_name)
                wrapper.before_call.indent()
                write_create_new_wrapper()
                self.cpp_class.wrapper_registry.write_register_new_wrapper(wrapper.before_call, py_name,
                                                                           "%s->obj" % py_name)
                wrapper.before_call.unindent()
                wrapper.before_call.write_code('}') # closes if (%s == NULL)

            wrapper.before_call.unindent()
            wrapper.before_call.write_code("}") # closes if (typeid(*(%s)) == typeid(%s))\n{
            wrapper.build_params.add_parameter("N", [py_name])
            



class CppClassPtrReturnValue(CppClassReturnValueBase):
    "Class* return handler"
    CTYPES = []
    SUPPORTS_TRANSFORMATIONS = True
    cpp_class = cppclass.CppClass('dummy') # CppClass instance

    def __init__(self, ctype, caller_owns_return=None, custodian=None,
                 is_const=False, reference_existing_object=None,
                 return_internal_reference=None):
        """
        :param ctype: C type, normally 'MyClass*'
        :param caller_owns_return: if true, ownership of the object pointer
                              is transferred to the caller

        :param custodian: bind the life cycle of the python wrapper
               for the return value object (ward) to that
               of the object indicated by this parameter
               (custodian). Possible values are:
                       - None: no object is custodian;
                       - 0: the instance of the method in which
                            the ReturnValue is being used will become the
                            custodian;
                       - integer > 0: parameter number, starting at 1
                          (i.e. not counting the self/this parameter),
                          whose object will be used as custodian.

        :param reference_existing_object: if true, ownership of the
                  pointed-to object remains to be the caller's, but we
                  do not make a copy. The callee gets a reference to
                  the existing object, but is not responsible for
                  freeing it.  Note that using this memory management
                  style is dangerous, as it exposes the Python
                  programmer to the possibility of keeping a reference
                  to an object that may have been deallocated in the
                  mean time.  Calling methods on such an object would
                  lead to a memory error.
                  
        :param return_internal_reference: like
            reference_existing_object, but additionally adds
            custodian/ward to bind the lifetime of the 'self' object
            (instance the method is bound to) to the lifetime of the
            return value.

        .. note::

           Only arguments which are instances of C++ classes
           wrapped by PyBindGen can be used as custodians.
        """
        if ctype == self.cpp_class.name:
            ctype = self.cpp_class.full_name
        super(CppClassPtrReturnValue, self).__init__(ctype, is_const=is_const)

        if caller_owns_return is None:
            # For "const Foo*", we assume caller_owns_return=False by default
            if self.type_traits.target_is_const:
                caller_owns_return = False

        self.caller_owns_return = caller_owns_return
        self.reference_existing_object = reference_existing_object
        self.return_internal_reference = return_internal_reference
        if self.return_internal_reference:
            assert self.reference_existing_object is None
            self.reference_existing_object = True
        self.custodian = custodian

        if self.caller_owns_return is None\
                and self.reference_existing_object is None:
            raise TypeConfigurationError("Either caller_owns_return or self.reference_existing_object must be given")


    def get_c_error_return(self): # only used in reverse wrappers
        """See ReturnValue.get_c_error_return"""
        return "return NULL;"

    def convert_c_to_python(self, wrapper):
        """See ReturnValue.convert_c_to_python"""

        ## Value transformations
        value = self.transformation.untransform(
            self, wrapper.declarations, wrapper.after_call, self.value)
        
        # if value is NULL, return None
        wrapper.after_call.write_code("if (!(%s)) {\n"
                                      "    Py_INCREF(Py_None);\n"
                                      "    return Py_None;\n"
                                      "}" % value)

        ## declare wrapper variable
        py_name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', 'py_'+self.cpp_class.name)
        self.py_name = py_name

        common_shared_object_return(value, py_name, self.cpp_class, wrapper.after_call,
                                    self.type_traits, self.caller_owns_return,
                                    self.reference_existing_object,
                                    type_is_pointer=True)

        # return the value
        wrapper.build_params.add_parameter("N", [py_name], prepend=True)
    

    def convert_python_to_c(self, wrapper):
        """See ReturnValue.convert_python_to_c"""
        name = wrapper.declarations.declare_variable(
            self.cpp_class.pystruct+'*', "tmp_%s" % self.cpp_class.name)
        wrapper.parse_params.add_parameter(
            'O!', ['&'+self.cpp_class.pytypestruct, '&'+name])

        value = self.transformation.transform(
            self, wrapper.declarations, wrapper.after_call, "%s->obj" % name)

        ## now the hairy part :)
        if self.caller_owns_return:
            if not isinstance(self.cpp_class.memory_policy, cppclass.ReferenceCountingPolicy):
                ## the caller receives a copy, if possible
                try:
                    self.cpp_class.write_create_instance(wrapper.after_call,
                                                         "%s" % self.value,
                                                         '*'+value)
                except CodeGenerationError:
                    copy_possible = False
                else:
                    copy_possible = True

                if copy_possible:
                    self.cpp_class.write_post_instance_creation_code(wrapper.after_call,
                                                                     "%s" % self.value,
                                                                     '*'+value)
                else:
                    # value = pyobj->obj; pyobj->obj = NULL;
                    wrapper.after_call.write_code(
                        "%s = %s;" % (self.value, value))
                    wrapper.after_call.write_code(
                        "%s = NULL;" % (value,))
            else:
                ## the caller gets a new reference to the same obj
                self.cpp_class.memory_policy.write_incref(wrapper.after_call, value)
                if self.type_traits.target_is_const:
                    wrapper.after_call.write_code(
                        "%s = const_cast< %s* >(%s);" %
                        (self.value, self.cpp_class.full_name, value))
                else:
                    wrapper.after_call.write_code(
                        "%s = %s;" % (self.value, value))
        else:
            ## caller gets a shared pointer
            ## but this is dangerous, avoid at all cost!!!
            wrapper.after_call.write_code(
                "// dangerous!\n%s = %s;" % (self.value, value))
            warnings.warn("Returning shared pointers is dangerous!"
                          "  The C++ API should be redesigned "
                          "to avoid this situation.")


##
##  Core of the custodians-and-wards implementation
##

def scan_custodians_and_wards(wrapper):
    """
    Scans the return value and parameters for custodian/ward options,
    converts them to add_custodian_and_ward API calls.  Wrappers that
    implement custodian_and_ward are: CppMethod, Function, and
    CppConstructor.
    """
    assert hasattr(wrapper, "add_custodian_and_ward")

    for num, param in enumerate(wrapper.parameters):
        custodian = getattr(param, 'custodian', None)
        if custodian is  not None:
            wrapper.add_custodian_and_ward(custodian, num+1)

    custodian = getattr(wrapper.return_value, 'custodian', None)
    if custodian is not None:
        wrapper.add_custodian_and_ward(custodian, -1)

    if getattr(wrapper.return_value, "return_internal_reference", False):
        wrapper.add_custodian_and_ward(-1, 0)



def _add_ward(code_block, custodian, ward):
    wards = code_block.declare_variable(
        'PyObject*', 'wards')
    code_block.write_code(
        "%(wards)s = PyObject_GetAttrString(%(custodian)s, (char *) \"__wards__\");"
        % vars())
    code_block.write_code(
        "if (%(wards)s == NULL) {\n"
        "    PyErr_Clear();\n"
        "    %(wards)s = PyList_New(0);\n"
        "    PyObject_SetAttrString(%(custodian)s, (char *) \"__wards__\", %(wards)s);\n"
        "}" % vars())
    code_block.write_code(
        "if (%(ward)s && !PySequence_Contains(%(wards)s, %(ward)s))\n"
        "    PyList_Append(%(wards)s, %(ward)s);" % dict(wards=wards, ward=ward))
    code_block.add_cleanup_code("Py_DECREF(%s);" % wards)
            

def _get_custodian_or_ward(wrapper, num):
    if num == -1:
        assert wrapper.return_value.py_name is not None
        return "((PyObject *) %s)" % wrapper.return_value.py_name
    elif num == 0:
        return "((PyObject *) self)"
    else:
        assert wrapper.parameters[num-1].py_name is not None
        return "((PyObject *) %s)" % wrapper.parameters[num-1].py_name


def implement_parameter_custodians_precall(wrapper):
    for custodian, ward, postcall in wrapper.custodians_and_wards:
        if not postcall:
            _add_ward(wrapper.before_call,
                      _get_custodian_or_ward(wrapper, custodian),
                      _get_custodian_or_ward(wrapper, ward))


def implement_parameter_custodians_postcall(wrapper):
    for custodian, ward, postcall in wrapper.custodians_and_wards:
        if postcall:
            _add_ward(wrapper.after_call,
                      _get_custodian_or_ward(wrapper, custodian),
                      _get_custodian_or_ward(wrapper, ward))
