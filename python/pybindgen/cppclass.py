from utils import any, mangle_name
import warnings
import traceback

from typehandlers.base import Parameter, ReturnValue, \
    join_ctype_and_name, CodeGenerationError, \
    param_type_matcher, return_type_matcher, CodegenErrorBase, \
    DeclarationsScope, CodeBlock

from typehandlers.codesink import NullCodeSink, MemoryCodeSink

from cppattribute import CppInstanceAttributeGetter, CppInstanceAttributeSetter, \
    CppStaticAttributeGetter, CppStaticAttributeSetter, \
    PyGetSetDef, PyMetaclass

from pytypeobject import PyTypeObject, PyNumberMethods, PySequenceMethods

import settings
import utils

from cppclass_container import CppClassContainerTraits

try:
    set
except NameError:
    from sets import Set as set

def _type_no_ref(value_type):
    if value_type.type_traits.type_is_reference:
        return str(value_type.type_traits.target)
    else:
        return str(value_type.type_traits.ctype_no_modifiers)


def get_python_to_c_converter(value, root_module, code_sink):
    if isinstance(value, CppClass):
        val_converter = root_module.generate_python_to_c_type_converter(value.ThisClassReturn(value.full_name), code_sink)
        val_name = value.full_name
    elif isinstance(value, ReturnValue):
        val_converter = root_module.generate_python_to_c_type_converter(value, code_sink)
        val_name = _type_no_ref(value)
    elif isinstance(value, Parameter):
        val_return_type = ReturnValue.new(value.ctype)
        val_converter = root_module.generate_python_to_c_type_converter(val_return_type, code_sink)
        val_name = _type_no_ref(value)
    else:
        raise ValueError, "Don't know how to convert %r" % (value,)
    return val_converter, val_name

def get_c_to_python_converter(value, root_module, code_sink):
    if isinstance(value, CppClass):
        val_converter = root_module.generate_c_to_python_type_converter(value.ThisClassReturn(value.full_name), code_sink)
        val_name = value.full_name
    elif isinstance(value, ReturnValue):
        val_converter = root_module.generate_c_to_python_type_converter(value, code_sink)
        val_name = _type_no_ref(value)
    elif isinstance(value, Parameter):
        val_return_type = ReturnValue.new(value.ctype)
        val_converter = root_module.generate_c_to_python_type_converter(val_return_type, code_sink)
        val_name = _type_no_ref(value)
    else:
        raise ValueError, "Don't know how to convert %s" % str(value)
    return val_converter, val_name

class MemoryPolicy(object):
    """memory management policy for a C++ class or C/C++ struct"""
    def __init__(self):
        if type(self) is MemoryPolicy:
            raise NotImplementedError("class is abstract")

    def get_free_code(self, object_expression):
        """
        Return a code statement to free an underlying C/C++ object.
        """
        raise NotImplementedError


class ReferenceCountingPolicy(MemoryPolicy):
    def write_incref(self, code_block, obj_expr):
        """
        Write code to increase the reference code of an object of this
        class (the real C++ class, not the wrapper).  Should only be
        called if the class supports reference counting, as reported
        by the attribute `CppClass.has_reference_counting`.
        """
        raise NotImplementedError

    def write_decref(self, code_block, obj_expr):
        """
        Write code to decrease the reference code of an object of this
        class (the real C++ class, not the wrapper).  Should only be
        called if the class supports reference counting, as reported
        by the attribute `CppClass.has_reference_counting`.
        """
        raise NotImplementedError


class ReferenceCountingMethodsPolicy(ReferenceCountingPolicy):
    def __init__(self, incref_method, decref_method, peekref_method=None):
        super(ReferenceCountingMethodsPolicy, self).__init__()
        self.incref_method = incref_method
        self.decref_method = decref_method
        self.peekref_method = peekref_method

    def write_incref(self, code_block, obj_expr):
        code_block.write_code('%s->%s();' % (obj_expr, self.incref_method))

    def write_decref(self, code_block, obj_expr):
        code_block.write_code('%s->%s();' % (obj_expr, self.decref_method))

    def get_free_code(self, obj_expr):
        return ('%s->%s();' % (obj_expr, self.decref_method))

    def __repr__(self):
        return 'cppclass.ReferenceCountingMethodsPolicy(incref_method=%r, decref_method=%r, peekref_method=%r)' \
            % (self.incref_method, self.decref_method, self.peekref_method)


class ReferenceCountingFunctionsPolicy(ReferenceCountingPolicy):
    def __init__(self, incref_function, decref_function, peekref_function=None):
        super(ReferenceCountingFunctionsPolicy, self).__init__()
        self.incref_function = incref_function
        self.decref_function = decref_function
        self.peekref_function = peekref_function

    def write_incref(self, code_block, obj_expr):
        code_block.write_code('%s(%s);' % (self.incref_function, obj_expr))

    def write_decref(self, code_block, obj_expr):
        code_block.write_code('%s(%s);' % (self.decref_function, obj_expr))

    def get_free_code(self, obj_expr):
        return ('%s(%s);' % (self.decref_function, obj_expr))

    def __repr__(self):
        return 'cppclass.ReferenceCountingFunctionsPolicy(incref_function=%r, decref_function=%r, peekref_function=%r)' \
            % (self.incref_function, self.decref_function, self.peekref_function)

class FreeFunctionPolicy(MemoryPolicy):
    def __init__(self, free_function):
        super(FreeFunctionPolicy, self).__init__()
        self.free_function = free_function

    def get_free_code(self, obj_expr):
        return ('%s(%s);' % (self.free_function, obj_expr))

    def __repr__(self):
        return 'cppclass.FreeFunctionPolicy(%r)' % self.free_function


def default_instance_creation_function(cpp_class, code_block, lvalue,
                                       parameters, construct_type_name):
    """
    Default "instance creation function"; it is called whenever a new
    C++ class instance needs to be created; this default
    implementation uses a standard C++ new allocator.

    :param cpp_class: the CppClass object whose instance is to be created
    :param code_block: CodeBlock object on which the instance creation code should be generated
    :param lvalue: lvalue expression that should hold the result in the end
    :param parameters: stringified list of parameters
    :param construct_type_name: actual name of type to be constructed (it is
                          not always the class name, sometimes it's
                          the python helper class)
    """
    assert lvalue
    assert not lvalue.startswith('None')
    if cpp_class.incomplete_type:
        raise CodeGenerationError("%s cannot be constructed (incomplete type)"
                                  % cpp_class.full_name)
    code_block.write_code(
        "%s = new %s(%s);" % (lvalue, construct_type_name, parameters))


class CppHelperClass(object):
    """
    Generates code for a C++ proxy subclass that takes care of
    forwarding virtual methods from C++ to Python.
    """

    def __init__(self, class_):
        """
        :param class_: original CppClass wrapper object
        """
        self.class_ = class_
        self.name = class_.pystruct + "__PythonHelper"
        self.virtual_parent_callers = {}
        self.virtual_proxies = []
        self.cannot_be_constructed = False
        self.custom_methods = []
        self.post_generation_code = []
        self.virtual_methods = []

    def add_virtual_method(self, method):
        assert method.is_virtual
        assert method.class_ is not None

        for existing in self.virtual_methods:
            if method.matches_signature(existing):
                return # don't re-add already existing method
        
        if isinstance(method, CppDummyMethod):
            if method.is_pure_virtual:
                self.cannot_be_constructed = True
        else:
            self.virtual_methods.append(method)
            if not method.is_pure_virtual:
                if settings._get_deprecated_virtuals():
                    vis = ['public', 'protected']
                else:
                    vis = ['protected']
                if method.visibility in vis:
                    parent_caller = CppVirtualMethodParentCaller(method)
                    #parent_caller.class_ = method.class_
                    parent_caller.helper_class = self
                    parent_caller.main_wrapper = method # XXX: need to explain this
                    self.add_virtual_parent_caller(parent_caller)

            proxy = CppVirtualMethodProxy(method)
            proxy.main_wrapper = method # XXX: need to explain this
            self.add_virtual_proxy(proxy)
        
        
    def add_virtual_parent_caller(self, parent_caller):
        """Add a new CppVirtualMethodParentCaller object to this helper class"""
        assert isinstance(parent_caller, CppVirtualMethodParentCaller)

        name = parent_caller.method_name
        try:
            overload = self.virtual_parent_callers[name]
        except KeyError:
            overload = CppOverloadedMethod(name)
            ## implicit conversions + virtual methods disabled
            ## temporarily until I can figure out how to fix the unit
            ## tests.
            overload.enable_implicit_conversions = False
            #overload.static_decl = False
            overload.pystruct = self.class_.pystruct
            self.virtual_parent_callers[name] = overload
            assert self.class_ is not None

        for existing in overload.wrappers:
            if parent_caller.matches_signature(existing):
                break # don't re-add already existing method
        else:
            overload.add(parent_caller)

    def add_custom_method(self, declaration, body=None):
        """
        Add a custom method to the helper class, given by a
        declaration line and a body.  The body can be None, in case
        the whole method definition is included in the declaration
        itself.
        """
        self.custom_methods.append((declaration, body))

    def add_post_generation_code(self, code):
        """
        Add custom code to be included right after the helper class is generated.
        """
        self.post_generation_code.append(code)

    def add_virtual_proxy(self, virtual_proxy):
        """Add a new CppVirtualMethodProxy object to this class"""
        assert isinstance(virtual_proxy, CppVirtualMethodProxy)
        self.virtual_proxies.append(virtual_proxy)

    def generate_forward_declarations(self, code_sink_param):
        """
        Generate the proxy class (declaration only) to a given code sink
        """
        code_sink = MemoryCodeSink()
        if self._generate_forward_declarations(code_sink):
            code_sink.flush_to(code_sink_param)
        else:
            self.cannot_be_constructed = True

    def _generate_forward_declarations(self, code_sink):
        """
        Generate the proxy class (declaration only) to a given code sink.

        Returns True if all is well, False if a pure virtual method
        was found that could not be generated.
        """
        code_sink.writeln("class %s : public %s\n{\npublic:" %
                          (self.name, self.class_.full_name))

        code_sink.indent()
        code_sink.writeln("PyObject *m_pyself;")

        if not self.class_.import_from_module:
            ## replicate the parent constructors in the helper class
            implemented_constructor_signatures = []
            for cons in self.class_.constructors:

                ## filter out duplicated constructors
                signature = [param.ctype for param in cons.parameters]
                if signature in implemented_constructor_signatures:
                    continue
                implemented_constructor_signatures.append(signature)

                params = [join_ctype_and_name(param.ctype, param.name)
                          for param in cons.parameters]
                code_sink.writeln("%s(%s)" % (self.name, ', '.join(params)))
                code_sink.indent()
                code_sink.writeln(": %s(%s), m_pyself(NULL)\n{}" %
                                  (self.class_.full_name,
                                   ', '.join([param.name for param in cons.parameters])))
                code_sink.unindent()
                code_sink.writeln()

        ## add the set_pyobj method
        code_sink.writeln("""
void set_pyobj(PyObject *pyobj)
{
    Py_XDECREF(m_pyself);
    Py_INCREF(pyobj);
    m_pyself = pyobj;
}
""")

        ## write a destructor
        code_sink.writeln("virtual ~%s()\n{" % self.name)
        code_sink.indent()
        code_sink.writeln("Py_CLEAR(m_pyself);")
        code_sink.unindent()
        code_sink.writeln("}\n")
            
        if not self.class_.import_from_module:
            ## write the parent callers (_name)
            for parent_caller in self.virtual_parent_callers.itervalues():
                #parent_caller.class_ = self.class_
                parent_caller.helper_class = self
                parent_caller.reset_code_generation_state()
                ## test code generation
                try:
                    try:
                        utils.call_with_error_handling(parent_caller.generate,
                                                       (NullCodeSink(),), {}, parent_caller)
                    except utils.SkipWrapper:
                        continue
                finally:
                    parent_caller.reset_code_generation_state()

                code_sink.writeln()
                parent_caller.generate_class_declaration(code_sink)

                for parent_caller_wrapper in parent_caller.wrappers:
                    parent_caller_wrapper.generate_parent_caller_method(code_sink)


            ## write the virtual proxies
            for virtual_proxy in self.virtual_proxies:
                #virtual_proxy.class_ = self.class_
                virtual_proxy.helper_class = self
                ## test code generation
                #virtual_proxy.class_ = self.class_
                #virtual_proxy.helper_class = self
                virtual_proxy.reset_code_generation_state()
                try:
                    try:
                        utils.call_with_error_handling(virtual_proxy.generate,
                                                       (NullCodeSink(),), {}, virtual_proxy)
                    except utils.SkipWrapper:
                        if virtual_proxy.method.is_pure_virtual:
                            return False
                        continue

                finally:
                    virtual_proxy.reset_code_generation_state()

                code_sink.writeln()
                virtual_proxy.generate_declaration(code_sink)

            for custom_declaration, dummy in self.custom_methods:
                code_sink.writeln(custom_declaration)

        code_sink.unindent()
        code_sink.writeln("};\n")

        if not self.class_.import_from_module:
            for code in self.post_generation_code:
                code_sink.writeln(code)
                code_sink.writeln()

        return True

    def generate(self, code_sink):
        """
        Generate the proxy class (virtual method bodies only) to a given code sink.
        returns pymethodef list of parent callers
        """
        if self.class_.import_from_module:
            return

        ## write the parent callers (_name)
        method_defs = []
        for name, parent_caller in self.virtual_parent_callers.iteritems():
            #parent_caller.class_ = self.class_
            parent_caller.helper_class = self
            code_sink.writeln()

            ## parent_caller.generate(code_sink)
            try:
                utils.call_with_error_handling(parent_caller.generate,
                                               (code_sink,), {}, parent_caller)
            except utils.SkipWrapper:
                continue
            if settings._get_deprecated_virtuals():
                parent_caller_name = '_'+name
            else:
                parent_caller_name = name
            method_defs.append(parent_caller.get_py_method_def(parent_caller_name))
                
        ## write the virtual proxies
        for virtual_proxy in self.virtual_proxies:
            #virtual_proxy.class_ = self.class_
            virtual_proxy.helper_class = self
            code_sink.writeln()

            ## virtual_proxy.generate(code_sink)
            try:
                utils.call_with_error_handling(virtual_proxy.generate,
                                               (code_sink,), {}, virtual_proxy)
            except utils.SkipWrapper:
                assert not virtual_proxy.method.is_pure_virtual
                continue

        for dummy, custom_body in self.custom_methods:
            if custom_body:
                code_sink.writeln(custom_body)
        
        return method_defs



class CppClass(object):
    """
    A CppClass object takes care of generating the code for wrapping a C++ class
    """

    def __init__(self, name, parent=None, incref_method=None, decref_method=None,
                 automatic_type_narrowing=None, allow_subclassing=None,
                 is_singleton=False, outer_class=None,
                 peekref_method=None,
                 template_parameters=(), custom_template_class_name=None,
                 incomplete_type=False, free_function=None,
                 incref_function=None, decref_function=None,
                 python_name=None, memory_policy=None,
                 foreign_cpp_namespace=None,
                 docstring=None,
                 custom_name=None,
                 import_from_module=None,
                 destructor_visibility='public'
                 ):
        """
        :param name: class name

        :param parent: optional parent class wrapper, or list of
                       parents.  Valid values are None, a CppClass
                       instance, or a list of CppClass instances.

        :param incref_method: (deprecated in favour of memory_policy) if the class supports reference counting, the
                         name of the method that increments the
                         reference count (may be inherited from parent
                         if not given)
        :param decref_method: (deprecated in favour of memory_policy) if the class supports reference counting, the
                         name of the method that decrements the
                         reference count (may be inherited from parent
                         if not given)
        :param automatic_type_narrowing: if True, automatic return type
                                    narrowing will be done on objects
                                    of this class and its descendants
                                    when returned by pointer from a
                                    function or method.
        :param allow_subclassing: if True, generated class wrappers will
                             allow subclassing in Python.
        :param is_singleton: if True, the class is considered a singleton,
                        and so the python wrapper will never call the
                        C++ class destructor to free the value.
        :param peekref_method: (deprecated in favour of memory_policy) if the class supports reference counting, the
                          name of the method that returns the current reference count.
        :param free_function: (deprecated in favour of memory_policy) name of C function used to deallocate class instances
        :param incref_function: (deprecated in favour of memory_policy) same as incref_method, but as a function instead of method
        :param decref_function: (deprecated in favour of memory_policy) same as decref_method, but as a function instead of method

        :param python_name: name of the class as it will appear from
             Python side.  This parameter is DEPRECATED in favour of
             custom_name.

        :param memory_policy: memory management policy; if None, it
            inherits from the parent class.  Only root classes can have a
            memory policy defined.
        :type memory_policy: L{MemoryPolicy}
        
        :param foreign_cpp_namespace: if set, the class is assumed to
            belong to the given C++ namespace, regardless of the C++
            namespace of the python module it will be added to.  For
            instance, this can be useful to wrap std classes, like
            std::ofstream, without having to create an extra python
            submodule.

        :param docstring: None or a string containing the docstring
            that will be generated for the class

        :param custom_name: an alternative name to give to this class
            at python-side; if omitted, the name of the class in the
            python module will be the same name as the class in C++
            (minus namespace).

        :param import_from_module: if not None, the type is imported
                    from a foreign Python module with the given name.
        """
        assert outer_class is None or isinstance(outer_class, CppClass)
        self.incomplete_type = incomplete_type
        self.outer_class = outer_class
        self._module = None
        self.name = name
        self.docstring = docstring
        self.mangled_name = None
        self.mangled_full_name = None
        self.template_parameters = template_parameters
        self.container_traits = None
        self.import_from_module = import_from_module
        assert destructor_visibility in ['public', 'private', 'protected']
        self.destructor_visibility = destructor_visibility

        self.custom_name = custom_name
        if custom_template_class_name:
            warnings.warn("Use the custom_name parameter.",
                          DeprecationWarning, stacklevel=2)
            self.custom_name = custom_template_class_name
        if python_name:
            warnings.warn("Use the custom_name parameter.",
                          DeprecationWarning, stacklevel=2)
            self.custom_name = python_name

        self.is_singleton = is_singleton
        self.foreign_cpp_namespace = foreign_cpp_namespace
        self.full_name = None # full name with C++ namespaces attached and template parameters
        self.methods = {} # name => OverloadedMethod
        self._dummy_methods = [] # methods that have parameter/retval binding problems
        self.nonpublic_methods = []
        self.constructors = [] # (name, wrapper) pairs
        self.pytype = PyTypeObject()
        self.slots = self.pytype.slots
        self.helper_class = None
        self.instance_creation_function = None
        self.post_instance_creation_function = None
        ## set to True when we become aware generating the helper
        ## class is not going to be possible
        self.helper_class_disabled = False
        self.cannot_be_constructed = '' # reason
        self.has_trivial_constructor = False
        self.has_copy_constructor = False
        self.has_output_stream_operator = False
        self._have_pure_virtual_methods = None
        self._wrapper_registry = None
        self.binary_comparison_operators = set()
        self.binary_numeric_operators = dict()
        self.inplace_numeric_operators = dict()
        self.unary_numeric_operators = dict()
        self.valid_sequence_methods = ("__len__", "__getitem__", "__setitem__")

        ## list of CppClasses from which a value of this class can be
        ## implicitly generated; corresponds to a
        ## operator ThisClass(); in the other class.
        self.implicitly_converts_from = []

        ## list of hook functions to call just prior to helper class
        ## code generation.
        self.helper_class_hooks = []

        self._pystruct = None #"***GIVE ME A NAME***"
        self.metaclass_name = "***GIVE ME A NAME***"
        self.pytypestruct = "***GIVE ME A NAME***"

        self.instance_attributes = PyGetSetDef("%s__getsets" % self._pystruct)
        self.static_attributes = PyGetSetDef("%s__getsets" % self.metaclass_name)

        if isinstance(parent, list):
            self.bases = list(parent)
            self.parent = self.bases[0]
        elif isinstance(parent, CppClass):
            self.parent = parent
            self.bases = [parent]
        elif parent is None:
            self.parent = None
            self.bases = []
        else:
            raise TypeError("'parent' must be None, CppClass instance, or a list of CppClass instances")

        if free_function:
            warnings.warn("Use FreeFunctionPolicy and memory_policy parameter.", DeprecationWarning)
            assert memory_policy is None
            memory_policy = FreeFunctionPolicy(free_function)
        elif incref_method:
            warnings.warn("Use ReferenceCountingMethodsPolicy and memory_policy parameter.", DeprecationWarning)
            assert memory_policy is None
            memory_policy = ReferenceCountingMethodsPolicy(incref_method, decref_method, peekref_method)
        elif incref_function:
            warnings.warn("Use ReferenceCountingFunctionsPolicy and memory_policy parameter.", DeprecationWarning)
            assert memory_policy is None
            memory_policy = ReferenceCountingFunctionsPolicy(incref_function, decref_function)

        if not self.bases:
            assert memory_policy is None or isinstance(memory_policy, MemoryPolicy)
            self.memory_policy = memory_policy
        else:
            for base in self.bases:
                if base.memory_policy is not None:
                    self.memory_policy = base.memory_policy
                    assert memory_policy is None, \
                        "changing memory policy from parent (%s) to child (%s) class not permitted" \
                        % (base.name, self.name)
                    break
            else:
                self.memory_policy = memory_policy

        if automatic_type_narrowing is None:
            if not self.bases:
                self.automatic_type_narrowing = settings.automatic_type_narrowing
            else:
                self.automatic_type_narrowing = self.parent.automatic_type_narrowing
        else:
            self.automatic_type_narrowing = automatic_type_narrowing

        if allow_subclassing is None:
            if self.parent is None:
                self.allow_subclassing = settings.allow_subclassing
            else:
                self.allow_subclassing = self.parent.allow_subclassing
        else:
            if any([p.allow_subclassing for p in self.bases]) and not allow_subclassing:
                raise ValueError("Cannot disable subclassing if a parent class allows it")
            else:
                self.allow_subclassing = allow_subclassing

        if self.destructor_visibility not in ['public', 'protected']:
            self.allow_subclassing = False

        self.typeid_map_name = None

        if name != 'dummy':
            ## register type handlers

            class ThisClassParameter(CppClassParameter):
                """Register this C++ class as pass-by-value parameter"""
                CTYPES = []
                cpp_class = self
            self.ThisClassParameter = ThisClassParameter
            try:
                param_type_matcher.register(name, self.ThisClassParameter)
            except ValueError:
                pass


            class ThisClassRefParameter(CppClassRefParameter):
                """Register this C++ class as pass-by-reference parameter"""
                CTYPES = []
                cpp_class = self
            self.ThisClassRefParameter = ThisClassRefParameter
            try:
                param_type_matcher.register(name+'&', self.ThisClassRefParameter)
            except ValueError:
                pass

            class ThisClassReturn(CppClassReturnValue):
                """Register this C++ class as value return"""
                CTYPES = []
                cpp_class = self
            self.ThisClassReturn = ThisClassReturn
            self.ThisClassRefReturn = ThisClassReturn
            try:
                return_type_matcher.register(name, self.ThisClassReturn)
                return_type_matcher.register(name, self.ThisClassRefReturn)
            except ValueError:
                pass

            class ThisClassPtrParameter(CppClassPtrParameter):
                """Register this C++ class as pass-by-pointer parameter"""
                CTYPES = []
                cpp_class = self
            self.ThisClassPtrParameter = ThisClassPtrParameter
            try:
                param_type_matcher.register(name+'*', self.ThisClassPtrParameter)
            except ValueError:
                pass

            class ThisClassPtrReturn(CppClassPtrReturnValue):
                """Register this C++ class as pointer return"""
                CTYPES = []
                cpp_class = self
            self.ThisClassPtrReturn = ThisClassPtrReturn
            try:
                return_type_matcher.register(name+'*', self.ThisClassPtrReturn)
            except ValueError:
                pass

            class ThisClassRefReturn(CppClassRefReturnValue):
                """Register this C++ class as reference return"""
                CTYPES = []
                cpp_class = self
            self.ThisClassRefReturn = ThisClassRefReturn
            try:
                return_type_matcher.register(name+'&', self.ThisClassRefReturn)
            except ValueError:
                pass

    def __repr__(self):
        return "<pybindgen.CppClass %r>" % self.full_name

    def add_container_traits(self, *args, **kwargs):
        assert self.container_traits is None
        self.container_traits = CppClassContainerTraits(self, *args, **kwargs)

    def add_binary_comparison_operator(self, operator):
        """
        Add support for a C++ binary comparison operator, such as == or <.

        The binary operator is assumed to operate with both operands
        of the type of the class, either by reference or by value.
        
        :param operator: string indicating the name of the operator to
            support, e.g. '=='
        """
        operator = utils.ascii(operator)
        if not isinstance(operator, str):
            raise TypeError("expected operator name as string")
        if operator not in ['==', '!=', '<', '<=', '>', '>=']:
            raise ValueError("The operator %r is invalid or not yet supported by PyBindGen" % (operator,))
        self.binary_comparison_operators.add(operator)

    def add_binary_numeric_operator(self, operator, result_cppclass=None,
                                    left_cppclass=None, right=None):
        """
        Add support for a C++ binary numeric operator, such as +, -, \\*, or /.

        :param operator: string indicating the name of the operator to
           support, e.g. '=='

        :param result_cppclass: the CppClass object of the result type, assumed to be this class if omitted
        :param left_cppclass: the CppClass object of the left operand type, assumed to be this class if omitted

        :param right: the type of the right parameter. Can be a
          CppClass, Parameter, or param spec. Assumed to be this class
          if omitted
        """
        operator = utils.ascii(operator)
        if not isinstance(operator, str):
            raise TypeError("expected operator name as string")
        if operator not in ['+', '-', '*', '/']:
            raise ValueError("The operator %r is invalid or not yet supported by PyBindGen" % (operator,))
        try:
            l = self.binary_numeric_operators[operator]
        except KeyError:
            l = []
            self.binary_numeric_operators[operator] = l
        if result_cppclass is None:
            result_cppclass = self
        if left_cppclass is None:
            left_cppclass = self

        if right is None:
            right = self
        elif isinstance(right, CppClass):
            pass
        else:
            if isinstance(right, str):
                right = utils.param(right, 'right')
            try:
                right = utils.eval_param(right, None)
            except utils.SkipWrapper:
                return

        op = (result_cppclass, left_cppclass, right)
        if op not in l:
            l.append(op)


    def add_inplace_numeric_operator(self, operator, right=None):
        """
        Add support for a C++ inplace numeric operator, such as +=, -=, \\*=, or /=.

        :param operator: string indicating the name of the operator to
           support, e.g. '+='

        :param right: the type of the right parameter. Can be a
          CppClass, Parameter, or param spec. Assumed to be this class
          if omitted
        """
        operator = utils.ascii(operator)
        if not isinstance(operator, str):
            raise TypeError("expected operator name as string")
        if operator not in ['+=', '-=', '*=', '/=']:
            raise ValueError("The operator %r is invalid or not yet supported by PyBindGen" % (operator,))
        try:
            l = self.inplace_numeric_operators[operator]
        except KeyError:
            l = []
            self.inplace_numeric_operators[operator] = l
        if right is None:
            right = self
        else:
            if isinstance(right, str):
                right = utils.param(right, 'right')
            try:
                right = utils.eval_param(right, None)
            except utils.SkipWrapper:
                return
        if right not in l:
            l.append((self, self, right))

    def add_unary_numeric_operator(self, operator, result_cppclass=None, left_cppclass=None):
        """
        Add support for a C++ unary numeric operators, currently only -.

        :param operator: string indicating the name of the operator to
          support, e.g. '-'

        :param result_cppclass: the CppClass object of the result type, assumed to be this class if omitted
        :param left_cppclass: the CppClass object of the left operand type, assumed to be this class if omitted
        """
        operator = utils.ascii(operator)
        if not isinstance(operator, str):
            raise TypeError("expected operator name as string")
        if operator not in ['-']:
            raise ValueError("The operator %r is invalid or not yet supported by PyBindGen" % (operator,))
        try:
            l = self.unary_numeric_operators[operator]
        except KeyError:
            l = []
            self.unary_numeric_operators[operator] = l
        if result_cppclass is None:
            result_cppclass = self
        if left_cppclass is None:
            left_cppclass = self
        op = (result_cppclass, left_cppclass)
        if op not in l:
            l.append(op)

    def add_class(self, *args, **kwargs):
        """
        Add a nested class.  See L{CppClass} for information about accepted parameters.
        """
        assert 'outer_class' not in kwargs
        kwargs['outer_class'] = self
        return self.module.add_class(*args, **kwargs)


    def add_enum(self, *args, **kwargs):
        """
        Add a nested enum.  See L{Enum} for information about accepted parameters.
        """
        assert 'outer_class' not in kwargs
        kwargs['outer_class'] = self
        return self.module.add_enum(*args, **kwargs)


    def get_mro(self):
        """
        Get the method resolution order (MRO) of this class.

        :return: an iterator that gives CppClass objects, from leaf to root class
        """
        to_visit = [self]
        visited = set()
        while to_visit:
            cls = to_visit.pop(0)
            visited.add(cls)
            yield cls
            for base in cls.bases:
                if base not in visited:
                    to_visit.append(base)

    def get_all_methods(self):
        """Returns an iterator to iterate over all methods of the class"""
        for overload in self.methods.itervalues():
            for method in overload.wrappers:
                yield method
        for method in self.nonpublic_methods:
            yield method

    def get_have_pure_virtual_methods(self):
        """
        Returns True if the class has pure virtual methods with no
        implementation (which would mean the type is not instantiable
        directly, only through a helper class).
        """
        if self._have_pure_virtual_methods is not None:
            return self._have_pure_virtual_methods
        mro = list(self.get_mro())
        mro_reversed = list(mro)
        mro_reversed.reverse()

        self._have_pure_virtual_methods = False
        for pos, cls in enumerate(mro_reversed):
            for method in list(cls.get_all_methods()) + cls._dummy_methods:
                if not isinstance(method, CppMethod):
                    continue

                if method.is_pure_virtual:
                    ## found a pure virtual method; now go see in the
                    ## child classes, check if any of them implements
                    ## this pure virtual method.
                    implemented = False
                    for child_cls in mro_reversed[pos+1:]:
                        for child_method in list(child_cls.get_all_methods()) + child_cls._dummy_methods:
                            if not isinstance(child_method, CppMethod):
                                continue
                            if not child_method.is_virtual:
                                continue
                            if not child_method.matches_signature(method):
                                continue
                            if not child_method.is_pure_virtual:
                                implemented = True
                            break
                        if implemented:
                            break
                    if not implemented:
                        self._have_pure_virtual_methods = True

        return self._have_pure_virtual_methods
                            
    have_pure_virtual_methods = property(get_have_pure_virtual_methods)


    def is_subclass(self, other):
        """Return True if this CppClass instance represents a class that is a
        subclass of another class represented by the CppClasss object \\`other\\'."""
        if not isinstance(other, CppClass):
            raise TypeError
        return other in self.get_mro()

    def add_helper_class_hook(self, hook):
        """
        Add a hook function to be called just prior to a helper class
        being generated.  The hook function applies to this class and
        all subclasses.  The hook function is called like this::
          hook_function(helper_class)
        """
        if not callable(hook):
            raise TypeError("hook function must be callable")
        self.helper_class_hooks.append(hook)
        
    def _get_all_helper_class_hooks(self):
        """
        Returns a list of all helper class hook functions, including
        the ones registered with parent classes.  Parent hooks will
        appear first in the list.
        """
        l = []
        for cls in self.get_mro():
            l = cls.helper_class_hooks + l
        return l

    def set_instance_creation_function(self, instance_creation_function):
        """Set a custom function to be called to create instances of this
        class and its subclasses.

        :param instance_creation_function: instance creation function; see
                                      default_instance_creation_function()
                                      for signature and example.
        """
        self.instance_creation_function = instance_creation_function

    def set_post_instance_creation_function(self, post_instance_creation_function):
        """Set a custom function to be called to add code after an
        instance is created (usually by the "instance creation
        function") and registered with the Python runtime.

        :param post_instance_creation_function: post instance creation function
        """
        self.post_instance_creation_function = post_instance_creation_function

    def get_instance_creation_function(self):
        for cls in self.get_mro():
            if cls.instance_creation_function is not None:
                return cls.instance_creation_function
        return default_instance_creation_function

    def get_post_instance_creation_function(self):
        for cls in self.get_mro():
            if cls.post_instance_creation_function is not None:
                return cls.post_instance_creation_function
        return None

    def write_create_instance(self, code_block, lvalue, parameters, construct_type_name=None):
        instance_creation_func = self.get_instance_creation_function()
        if construct_type_name is None:
            construct_type_name = self.get_construct_name()
        instance_creation_func(self, code_block, lvalue, parameters, construct_type_name)

    def write_post_instance_creation_code(self, code_block, lvalue, parameters, construct_type_name=None):
        post_instance_creation_func = self.get_post_instance_creation_function()
        if post_instance_creation_func is None:
            return
        if construct_type_name is None:
            construct_type_name = self.get_construct_name()
        post_instance_creation_func(self, code_block, lvalue, parameters, construct_type_name)

    def get_pystruct(self):
        if self._pystruct is None:
            raise ValueError
        return self._pystruct
    pystruct = property(get_pystruct)

    def get_construct_name(self):
        """Get a name usable for new %s construction, or raise
        CodeGenerationError if none found"""
        if self.cannot_be_constructed:
            raise CodeGenerationError("%s cannot be constructed (%s)" % (self.full_name, self.cannot_be_constructed))
        if self.have_pure_virtual_methods:
            raise CodeGenerationError("%s cannot be constructed (class has pure virtual methods)" % self.full_name)
        else:
            return self.full_name
        

    def implicitly_converts_to(self, other):
        """
        Declares that values of this class can be implicitly converted
        to another class; corresponds to a operator AnotherClass();
        special method.
        """
        assert isinstance(other, CppClass)
        other.implicitly_converts_from.append(self)

    def get_all_implicit_conversions(self):
        """
        Gets a new list of all other classes whose value can be implicitly
        converted to a value of this class.

        >>> Foo = CppClass("Foo")
        >>> Bar = CppClass("Bar")
        >>> Zbr = CppClass("Zbr")
        >>> Bar.implicitly_converts_to(Foo)
        >>> Zbr.implicitly_converts_to(Bar)
        >>> l = Foo.get_all_implicit_conversions()
        >>> l.sort(lambda cls1, cls2: cmp(cls1.name, cls2.name))
        >>> [cls.name for cls in l]
        ['Bar']
        """
        return list(self.implicitly_converts_from)
#         classes = []
#         to_visit = list(self.implicitly_converts_from)
#         while to_visit:
#             source = to_visit.pop(0)
#             if source in classes or source is self:
#                 continue
#             classes.append(source)
#             to_visit.extend(source.implicitly_converts_from)
#         return classes

    def _update_names(self):
        
        prefix = settings.name_prefix.capitalize()

        if self.outer_class is None:
            if self.foreign_cpp_namespace:
                self.full_name = self.foreign_cpp_namespace + '::' + self.name
            else:
                if self._module.cpp_namespace_prefix:
                    if self._module.cpp_namespace_prefix == '::':
                        self.full_name = '::' + self.name
                    else:
                        self.full_name = self._module.cpp_namespace_prefix + '::' + self.name
                else:
                    self.full_name = self.name
        else:
            assert not self.foreign_cpp_namespace
            self.full_name = '::'.join([self.outer_class.full_name, self.name])

        def make_upper(s):
            if s and s[0].islower():
                return s[0].upper()+s[1:]
            else:
                return s

        def mangle(name):
            return mangle_name(name)
        
        def flatten(name):
            "make a name like::This look LikeThis"
            return ''.join([make_upper(mangle(s)) for s in name.split('::')])

        self.mangled_name = flatten(self.name)
        self.mangled_full_name = flatten(self.full_name)

        if self.template_parameters:
            self.full_name += "< %s >" % (', '.join(self.template_parameters))
            mangled_template_params = '__' + '_'.join([flatten(s) for s in self.template_parameters])
            self.mangled_name += mangled_template_params
            self.mangled_full_name += mangled_template_params

        self._pystruct = "Py%s%s" % (prefix, self.mangled_full_name)
        self.metaclass_name = "%sMeta" % self.mangled_full_name
        self.pytypestruct = "Py%s%s_Type" % (prefix,  self.mangled_full_name)

        self.instance_attributes.cname = "%s__getsets" % self._pystruct
        self.static_attributes.cname = "%s__getsets" % self.metaclass_name

        ## re-register the class type handlers, now with class full name
        self.register_alias(self.full_name)

        if self.get_type_narrowing_root() is self:
            self.typeid_map_name = "%s__typeid_map" % self.pystruct
        else:
            self.typeid_map_name = None

    def register_alias(self, alias):
        """Re-register the class with another base name, in addition to any
        registrations that might have already been done."""

        self.module.register_type(None, alias, self)

        self.ThisClassParameter.CTYPES.append(alias)
        try:
            param_type_matcher.register(alias, self.ThisClassParameter)
        except ValueError: pass
        
        self.ThisClassRefParameter.CTYPES.append(alias+'&')
        try:
            param_type_matcher.register(alias+'&', self.ThisClassRefParameter)
        except ValueError: pass
        
        self.ThisClassReturn.CTYPES.append(alias)
        try:
            return_type_matcher.register(alias, self.ThisClassReturn)
        except ValueError: pass
        
        self.ThisClassPtrParameter.CTYPES.append(alias+'*')
        try:
            param_type_matcher.register(alias+'*', self.ThisClassPtrParameter)
        except ValueError: pass
        
        self.ThisClassPtrReturn.CTYPES.append(alias+'*')
        try:
            return_type_matcher.register(alias+'*', self.ThisClassPtrReturn)
        except ValueError: pass

        self.ThisClassRefReturn.CTYPES.append(alias)
        try:
            return_type_matcher.register(alias+'&', self.ThisClassRefReturn)
        except ValueError: pass

        
    def get_module(self):
        """Get the Module object this class belongs to"""
        return self._module

    def set_module(self, module):
        """Set the Module object this class belongs to"""
        self._module = module
        self._update_names()

    module = property(get_module, set_module)


    def inherit_default_constructors(self):
        """inherit the default constructors from the parentclass according to C++
        language rules"""
        for base in self.bases:
            for cons in base.constructors:
                if len(cons.parameters) == 0:
                    self.add_constructor([], visibility=cons.visibility)
                elif (len(cons.parameters) == 1
                      and isinstance(cons.parameters[0], self.parent.ThisClassRefParameter)):
                    self.add_constructor([self.ThisClassRefParameter()], visibility=cons.visibility)

    def get_helper_class(self):
        """gets the "helper class" for this class wrapper, creating it if necessary"""
        for cls in self.get_mro():
            if cls.helper_class_disabled:
                return None
        if not self.allow_subclassing:
            return None
        if self.helper_class is None:
            if not self.is_singleton:
                self.helper_class = CppHelperClass(self)
                self.module.add_include('<typeinfo>')
        return self.helper_class
    
    def get_type_narrowing_root(self):
        """Find the root CppClass along the subtree of all parent classes that
        have automatic_type_narrowing=True Note: multiple inheritance
        not implemented"""
        if not self.automatic_type_narrowing:
            return None
        root = self
        while (root.parent is not None
               and root.parent.automatic_type_narrowing):
            root = root.parent
        return root

    def _register_typeid(self, module):
        """register this class with the typeid map root class"""
        root = self.get_type_narrowing_root()
        module.after_init.write_code("%s.register_wrapper(typeid(%s), &%s);"
                                     % (root.typeid_map_name, self.full_name, self.pytypestruct))

    def _generate_typeid_map(self, code_sink, module):
        """generate the typeid map and fill it with values"""
        try:
            module.declare_one_time_definition("TypeIDMap")
        except KeyError:
            pass
        else:
            code_sink.writeln('''

#include <map>
#include <string>
#include <typeinfo>
#if defined(__GNUC__) && __GNUC__ >= 3
# include <cxxabi.h>
#endif

#define PBG_TYPEMAP_DEBUG 0

namespace pybindgen {

class TypeMap
{
   std::map<std::string, PyTypeObject *> m_map;

public:

   TypeMap() {}

   void register_wrapper(const std::type_info &cpp_type_info, PyTypeObject *python_wrapper)
   {

#if PBG_TYPEMAP_DEBUG
   std::cerr << "register_wrapper(this=" << this << ", type_name=" << cpp_type_info.name()
             << ", python_wrapper=" << python_wrapper->tp_name << ")" << std::endl;
#endif

       m_map[std::string(cpp_type_info.name())] = python_wrapper;
   }

''')

            if settings.gcc_rtti_abi_complete:
                code_sink.writeln('''
   PyTypeObject * lookup_wrapper(const std::type_info &cpp_type_info, PyTypeObject *fallback_wrapper)
   {

#if PBG_TYPEMAP_DEBUG
   std::cerr << "lookup_wrapper(this=" << this << ", type_name=" << cpp_type_info.name() << ")" << std::endl;
#endif

       PyTypeObject *python_wrapper = m_map[cpp_type_info.name()];
       if (python_wrapper)
           return python_wrapper;
       else {
#if defined(__GNUC__) && __GNUC__ >= 3

           // Get closest (in the single inheritance tree provided by cxxabi.h)
           // registered python wrapper.
           const abi::__si_class_type_info *_typeinfo =
               dynamic_cast<const abi::__si_class_type_info*> (&cpp_type_info);
#if PBG_TYPEMAP_DEBUG
          std::cerr << "  -> looking at C++ type " << _typeinfo->name() << std::endl;
#endif
           while (_typeinfo && (python_wrapper = m_map[std::string(_typeinfo->name())]) == 0) {
               _typeinfo = dynamic_cast<const abi::__si_class_type_info*> (_typeinfo->__base_type);
#if PBG_TYPEMAP_DEBUG
               std::cerr << "  -> looking at C++ type " << _typeinfo->name() << std::endl;
#endif
           }

#if PBG_TYPEMAP_DEBUG
          if (python_wrapper) {
              std::cerr << "  -> found match " << std::endl;
          } else {
              std::cerr << "  -> return fallback wrapper" << std::endl;
          }
#endif

           return python_wrapper? python_wrapper : fallback_wrapper;

#else // non gcc 3+ compilers can only match against explicitly registered classes, not hidden subclasses
           return fallback_wrapper;
#endif
       }
   }
};

}
''')
            else:
                code_sink.writeln('''
   PyTypeObject * lookup_wrapper(const std::type_info &cpp_type_info, PyTypeObject *fallback_wrapper)
   {

#if PBG_TYPEMAP_DEBUG
   std::cerr << "lookup_wrapper(this=" << this << ", type_name=" << cpp_type_info.name() << ")" << std::endl;
#endif

       PyTypeObject *python_wrapper = m_map[cpp_type_info.name()];
       return python_wrapper? python_wrapper : fallback_wrapper;
   }
};

}
''')
        

        if self.import_from_module:
            code_sink.writeln("\nextern pybindgen::TypeMap *_%s;\n" % self.typeid_map_name)
            code_sink.writeln("#define %s (*_%s)\n" % (self.typeid_map_name, self.typeid_map_name))
        else:
            code_sink.writeln("\nextern pybindgen::TypeMap %s;\n" % self.typeid_map_name)

    def _add_method_obj(self, method):
        """
        Add a method object to the class.  For internal use.

        :param method: a L{CppMethod} or L{Function} instance that can generate the method wrapper
        """
        if isinstance(method, CppMethod):
            name = method.mangled_name
        elif isinstance(method, function.Function):
            name = method.custom_name
            assert isinstance(method.parameters[0], CppClassParameterBase)
            assert method.parameters[0].cpp_class is self, \
                "expected first parameter to be of class %s, but it is of class %s" % \
                (self.full_name, method.parameters[0].cpp_class.full_name)
            method.parameters[0].take_value_from_python_self = True
            method.module = self.module
            method.is_virtual = False
            method.is_pure_virtual = False
            method.self_parameter_pystruct = self.pystruct
            method.visibility = 'public'
            method.force_parse = method.PARSE_TUPLE_AND_KEYWORDS
        else:
            raise TypeError
        
        method.class_ = self

        if method.visibility == 'protected' and not method.is_virtual:
            helper_class = self.get_helper_class()
            if helper_class is not None:
                parent_caller = CppVirtualMethodParentCaller(method)
                parent_caller.helper_class = helper_class
                parent_caller.main_wrapper = method
                helper_class.add_virtual_parent_caller(parent_caller)
        elif method.visibility == 'public':
            if name == '__call__': # needs special handling
                method.force_parse = method.PARSE_TUPLE_AND_KEYWORDS

            try:
                overload = self.methods[name]
            except KeyError:
                overload = CppOverloadedMethod(name)
                overload.pystruct = self.pystruct
                self.methods[name] = overload

            ## add it....
            try:
                utils.call_with_error_handling(overload.add, (method,), {}, method)
            except utils.SkipWrapper:
                return


            # Grr! I hate C++.  Overloading + inheritance = disaster!
            # So I ended up coding something which C++ does not in
            # fact support, but I feel bad to just throw away my good
            # code due to a C++ fault, so I am leaving here the code
            # disabled.  Maybe some future C++ version will come along
            # and fix this problem, who knows :P
            if 0:
                # due to a limitation of the pybindgen overloading
                # strategy, we need to re-wrap for this class all
                # methods with the same name and different signature
                # from parent classes.
                overload._compute_all_wrappers()
                if isinstance(method, CppMethod):
                    mro = self.get_mro()
                    mro.next() # skip 'self'
                    for cls in mro:
                        try:
                            parent_overload = cls.methods[name]
                        except KeyError:
                            continue
                        parent_overload._compute_all_wrappers()
                        for parent_method in parent_overload.all_wrappers:
                            already_exists = False
                            for existing_method in overload.all_wrappers:
                                if existing_method.matches_signature(parent_method):
                                    already_exists = True
                                    break
                            if not already_exists:
                                new_method = parent_method.clone()
                                new_method.class_ = self
                                overload.add(new_method)
            
        else:
            self.nonpublic_methods.append(method)
        if method.is_virtual:
            self._have_pure_virtual_methods = None
            helper_class = self.get_helper_class()
            if helper_class is not None:
                helper_class.add_virtual_method(method)

    def add_method(self, *args, **kwargs):
        """
        Add a method to the class. See the documentation for
        L{CppMethod.__init__} for information on accepted parameters.
        """

        ## <compat>
        if len(args) >= 1 and isinstance(args[0], CppMethod):
            meth = args[0]
            warnings.warn("add_method has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
            if len(args) == 2:
                meth.custom_name = args[1]
            elif 'name' in kwargs:
                assert len(args) == 1
                meth.custom_name = kwargs['name']
            else:
                assert len(args) == 1
                assert len(kwargs) == 0
        elif len(args) >= 1 and isinstance(args[0], function.Function):
            meth = args[0]
            warnings.warn("add_method has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
            if len(args) == 2:
                meth.custom_name = args[1]
            elif 'name' in kwargs:
                assert len(args) == 1
                meth.custom_name = kwargs['name']
            else:
                assert len(args) == 1
                assert len(kwargs) == 0
        ## </compat>

        else:
            try:
                meth = CppMethod(*args, **kwargs)
            except utils.SkipWrapper:
                if kwargs.get('is_virtual', False):
                    ## if the method was supposed to be virtual, this
                    ## is a very important fact that needs to be
                    ## recorded in the class, even if the method is
                    ## not wrapped.
                    method = CppDummyMethod(*args, **kwargs)
                    method.class_ = self
                    self._dummy_methods.append(method)
                    self._have_pure_virtual_methods = None
                    helper_class = self.get_helper_class()
                    if helper_class is not None:
                        helper_class.add_virtual_method(method)
                        if helper_class.cannot_be_constructed:
                            self.helper_class = None
                            self.helper_class_disabled = True

                return None
        self._add_method_obj(meth)
        return meth

    def add_function_as_method(self, *args, **kwargs):
        """
        Add a function as method of the class. See the documentation for
        L{Function.__init__} for information on accepted parameters.
        TODO: explain the implicit first function parameter
        """
        try:
            meth = function.Function(*args, **kwargs)
        except utils.SkipWrapper:
            return None
        self._add_method_obj(meth)
        return meth

    def add_custom_method_wrapper(self, *args, **kwargs):
        """
        Adds a custom method wrapper. See L{CustomCppMethodWrapper} for more information.
        """
        try:
            meth = CustomCppMethodWrapper(*args, **kwargs)
        except utils.SkipWrapper:
            return None
        self._add_method_obj(meth)
        return meth

    def set_helper_class_disabled(self, flag=True):
        self.helper_class_disabled = flag
        if flag:
            self.helper_class = None

    def set_cannot_be_constructed(self, reason):
        assert isinstance(reason, basestring)
        self.cannot_be_constructed = reason

    def _add_constructor_obj(self, wrapper):
        """
        Add a constructor to the class.

        :param wrapper: a CppConstructor instance
        """
        assert isinstance(wrapper, CppConstructor)
        wrapper.set_class(self)
        self.constructors.append(wrapper)
        if not wrapper.parameters:
            self.has_trivial_constructor = True # FIXME: I don't remember what is this used for anymore, maybe remove
        if len(wrapper.parameters) == 1 and isinstance(wrapper.parameters[0], (CppClassRefParameter, CppClassParameter)) \
                and wrapper.parameters[0].cpp_class is self and wrapper.visibility == 'public':
            self.has_copy_constructor = True

    def add_output_stream_operator(self):
        """
        Add str() support based on C++ output stream operator.

        Calling this method enables wrapping of an assumed to be defined operator function::

             std::ostream & operator << (std::ostream &, MyClass const &);

        The wrapper will be registered as an str() python operator,
        and will call the C++ operator function to convert the value
        to a string.
        """
        self.has_output_stream_operator = True
        self.module.add_include("<ostream>")
        self.module.add_include("<sstream>")

    def add_constructor(self, *args, **kwargs):
        """
        Add a constructor to the class. See the documentation for
        L{CppConstructor.__init__} for information on accepted parameters.
        """

        ## <compat>
        if len(args) == 1 and isinstance(args[0], CppConstructor):
            warnings.warn("add_constructor has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
            constructor = args[0]
        elif len(args) == 1 and isinstance(args[0], function.Function):
            warnings.warn("add_constructor has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
            func = args[0]
            constructor = CppFunctionAsConstructor(func.function_name, func.parameters)
            constructor.module = self.module
        ## </compat>
        else:
            try:
                constructor = CppConstructor(*args, **kwargs)
            except utils.SkipWrapper:
                return None
        self._add_constructor_obj(constructor)
        return constructor

    def add_copy_constructor(self):
        """
        Utility method to add a 'copy constructor' method to this class.
        """
        try:
            constructor = CppConstructor([self.ThisClassRefParameter("const %s &" % self.full_name,
                                                                     'ctor_arg')])
        except utils.SkipWrapper:
            return None
        self._add_constructor_obj(constructor)
        return constructor

    def add_function_as_constructor(self, *args, **kwargs):
        """
        Wrap a function that behaves as a constructor to the class. See the documentation for
        L{CppFunctionAsConstructor.__init__} for information on accepted parameters.
        """
        try:
            constructor = CppFunctionAsConstructor(*args, **kwargs)
        except utils.SkipWrapper:
            return None
        self._add_constructor_obj(constructor)
        return constructor

    def add_static_attribute(self, name, value_type, is_const=False):
        """
        :param value_type: a ReturnValue object
        :param name: attribute name (i.e. the name of the class member variable)
        :param is_const: True if the attribute is const, i.e. cannot be modified
        """

        ## backward compatibility check
        if isinstance(value_type, str) and isinstance(name, ReturnValue):
            warnings.warn("add_static_attribute has changed API; see the API documentation (but trying to correct...)",
                          DeprecationWarning, stacklevel=2)
            value_type, name = name, value_type

        try:
            value_type = utils.eval_retval(value_type, None)
        except utils.SkipWrapper:
            return

        assert isinstance(value_type, ReturnValue)
        getter = CppStaticAttributeGetter(value_type, self, name)
        getter.stack_where_defined = traceback.extract_stack()
        if is_const:
            setter = None
        else:
            setter = CppStaticAttributeSetter(value_type, self, name)
            setter.stack_where_defined = traceback.extract_stack()
        self.static_attributes.add_attribute(name, getter, setter)

    def add_instance_attribute(self, name, value_type, is_const=False,
                               getter=None, setter=None):
        """
        :param value_type: a ReturnValue object
        :param name: attribute name (i.e. the name of the class member variable)
        :param is_const: True if the attribute is const, i.e. cannot be modified
        :param getter: None, or name of a method of this class used to get the value
        :param setter: None, or name of a method of this class used to set the value
        """

        ## backward compatibility check
        if isinstance(value_type, str) and isinstance(name, ReturnValue):
            warnings.warn("add_static_attribute has changed API; see the API documentation (but trying to correct...)",
                          DeprecationWarning, stacklevel=2)
            value_type, name = name, value_type

        try:
            value_type = utils.eval_retval(value_type, None)
        except utils.SkipWrapper:
            return

        assert isinstance(value_type, ReturnValue)
        getter_wrapper = CppInstanceAttributeGetter(value_type, self, name, getter=getter)
        getter_wrapper.stack_where_defined = traceback.extract_stack()
        if is_const:
            setter_wrapper = None
            assert setter is None
        else:
            setter_wrapper = CppInstanceAttributeSetter(value_type, self, name, setter=setter)
            setter_wrapper.stack_where_defined = traceback.extract_stack()
        self.instance_attributes.add_attribute(name, getter_wrapper, setter_wrapper)


    def _inherit_helper_class_parent_virtuals(self):
        """
        Given a class containing a helper class, add all virtual
        methods from the all parent classes of this class.
        """
        mro = self.get_mro()
        mro.next() # skip 'self'
        for cls in mro:
            for method in cls.get_all_methods():
                if not method.is_virtual:
                    continue
                method = method.clone()
                self.helper_class.add_virtual_method(method)

    def _get_wrapper_registry(self):
        # there is one wrapper registry object per root class only,
        # which is used for all subclasses.
        if self.parent is None:
            if self._wrapper_registry is None:
                self._wrapper_registry = settings.wrapper_registry(self.pystruct)
            return self._wrapper_registry
        else:
            return self.parent._get_wrapper_registry()
    wrapper_registry = property(_get_wrapper_registry)

    def generate_forward_declarations(self, code_sink, module):
        """
        Generates forward declarations for the instance and type
        structures.
        """

        if self.allow_subclassing:
            code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *obj;
    PyObject *inst_dict;
    PyBindGenWrapperFlags flags:8;
} %s;
    ''' % (self.full_name, self.pystruct))

        else:

            code_sink.writeln('''
typedef struct {
    PyObject_HEAD
    %s *obj;
    PyBindGenWrapperFlags flags:8;
} %s;
    ''' % (self.full_name, self.pystruct))

        code_sink.writeln()

        if self.import_from_module:
            code_sink.writeln('extern PyTypeObject *_%s;' % (self.pytypestruct,))
            code_sink.writeln('#define %s (*_%s)' % (self.pytypestruct, self.pytypestruct))
        else:
            code_sink.writeln('extern PyTypeObject %s;' % (self.pytypestruct,))
            if not self.static_attributes.empty():
                code_sink.writeln('extern PyTypeObject Py%s_Type;' % (self.metaclass_name,))

        code_sink.writeln()

        if self.helper_class is not None:
            self._inherit_helper_class_parent_virtuals()
            for hook in self._get_all_helper_class_hooks():
                hook(self.helper_class)
            self.helper_class.generate_forward_declarations(code_sink)
            if self.helper_class.cannot_be_constructed:
                self.helper_class = None
                self.helper_class_disabled = True
        if self.have_pure_virtual_methods and self.helper_class is None:
            self.cannot_be_constructed = "have pure virtual methods but no helper class"

        if self.typeid_map_name is not None:
            self._generate_typeid_map(code_sink, module)

        if self.container_traits is not None:
            self.container_traits.generate_forward_declarations(code_sink, module)

        if self.parent is None:
            self.wrapper_registry.generate_forward_declarations(code_sink, module, self.import_from_module)

    def get_python_name(self):
        if self.template_parameters:
            if self.custom_name is None:
                class_python_name = self.mangled_name
            else:
                class_python_name = self.custom_name
        else:
            if self.custom_name is None:
                class_python_name = self.name
            else:
                class_python_name = self.custom_name
        return class_python_name

    def _generate_import_from_module(self, code_sink, module):
        if module.parent is None:
            error_retcode = ""
        else:
            error_retcode = "NULL"
        
        # TODO: skip this step if the requested typestructure is never used
        if ' named ' in self.import_from_module:
            module_name, type_name = self.import_from_module.split(" named ")
        else:
            module_name, type_name = self.import_from_module, self.name
        code_sink.writeln("PyTypeObject *_%s;" % self.pytypestruct)
        module.after_init.write_code("/* Import the %r class from module %r */" % (self.full_name, self.import_from_module))
        module.after_init.write_code("{"); module.after_init.indent()
        module.after_init.write_code("PyObject *module = PyImport_ImportModule((char*) \"%s\");" % module_name)
        module.after_init.write_code(
            "if (module == NULL) {\n"
            "    return %s;\n"
            "}" % (error_retcode,))

        module.after_init.write_code("_%s = (PyTypeObject*) PyObject_GetAttrString(module, (char*) \"%s\");\n"
                                     % (self.pytypestruct, self.get_python_name()))
        module.after_init.write_code("if (PyErr_Occurred()) PyErr_Clear();")

        if self.typeid_map_name is not None:
            code_sink.writeln("pybindgen::TypeMap *_%s;" % self.typeid_map_name)
            module.after_init.write_code("/* Import the %r class type map from module %r */" % (self.full_name, self.import_from_module))
            module.after_init.write_code("PyObject *_cobj = PyObject_GetAttrString(module, (char*) \"_%s\");"
                                         % (self.typeid_map_name))
            module.after_init.write_code("if (_cobj == NULL) {\n"
                                         "    _%s = new pybindgen::TypeMap;\n"
                                         "    PyErr_Clear();\n"
                                         "} else {\n"
                                         "    _%s = reinterpret_cast<pybindgen::TypeMap*> (PyCObject_AsVoidPtr (_cobj));\n"
                                         "    Py_DECREF(_cobj);\n"
                                         "}"
                                         % (self.typeid_map_name, self.typeid_map_name))        

        if self.parent is None:
            self.wrapper_registry.generate_import(code_sink, module.after_init, "module")

        module.after_init.unindent(); module.after_init.write_code("}")

        if self.helper_class is not None:
            self.helper_class.generate(code_sink)


    def generate(self, code_sink, module):
        """Generates the class to a code sink"""

        if self.import_from_module:
            self._generate_import_from_module(code_sink, module)
            return # .......................... RETURN

        if self.typeid_map_name is not None:
            code_sink.writeln("\npybindgen::TypeMap %s;\n" % self.typeid_map_name)
            module.after_init.write_code("PyModule_AddObject(m, (char *) \"_%s\", PyCObject_FromVoidPtr(&%s, NULL));"
                                         % (self.typeid_map_name, self.typeid_map_name))

        if self.automatic_type_narrowing:
            self._register_typeid(module)

        if self.parent is None:
            self.wrapper_registry.generate(code_sink, module)

        if self.helper_class is not None:
            parent_caller_methods = self.helper_class.generate(code_sink)
        else:
            parent_caller_methods = []

        ## generate getsets
        instance_getsets = self.instance_attributes.generate(code_sink)
        self.slots.setdefault("tp_getset", instance_getsets)
        static_getsets = self.static_attributes.generate(code_sink)

        ## --- register the class type in the module ---
        module.after_init.write_code("/* Register the '%s' class */" % self.full_name)

        ## generate a metaclass if needed
        if static_getsets == '0':
            metaclass = None
        else:
            if self.parent is None:
                parent_typestruct = 'PyBaseObject_Type'
            else:
                parent_typestruct = self.parent.pytypestruct
            metaclass = PyMetaclass(self.metaclass_name,
                                    "%s.ob_type" % parent_typestruct,
                                    self.static_attributes)
            metaclass.generate(code_sink, module)

        if self.parent is not None:
            assert isinstance(self.parent, CppClass)
            module.after_init.write_code('%s.tp_base = &%s;' %
                                         (self.pytypestruct, self.parent.pytypestruct))
            if len(self.bases) > 1:
                module.after_init.write_code('%s.tp_bases = PyTuple_New(%i);' % (self.pytypestruct, len(self.bases),))
                for basenum, base in enumerate(self.bases):
                    module.after_init.write_code('    Py_INCREF((PyObject *) &%s);' % (base.pytypestruct,))
                    module.after_init.write_code('    PyTuple_SET_ITEM(%s.tp_bases, %i, (PyObject *) &%s);'
                                                 % (self.pytypestruct, basenum, base.pytypestruct))

        if metaclass is not None:
            module.after_init.write_code('%s.ob_type = &%s;' %
                                         (self.pytypestruct, metaclass.pytypestruct))

        module.after_init.write_error_check('PyType_Ready(&%s)'
                                          % (self.pytypestruct,))

        class_python_name = self.get_python_name()

        if self.outer_class is None:
            module.after_init.write_code(
                'PyModule_AddObject(m, (char *) \"%s\", (PyObject *) &%s);' % (
                class_python_name, self.pytypestruct))
        else:
            module.after_init.write_code(
                'PyDict_SetItemString((PyObject*) %s.tp_dict, (char *) \"%s\", (PyObject *) &%s);' % (
                self.outer_class.pytypestruct, class_python_name, self.pytypestruct))

        have_constructor = self._generate_constructor(code_sink)

        self._generate_methods(code_sink, parent_caller_methods)

        if self.allow_subclassing:
            self._generate_gc_methods(code_sink)

        self._generate_destructor(code_sink, have_constructor)

        if self.has_output_stream_operator:
            self._generate_str(code_sink)
        
        #self._generate_tp_hash(code_sink)
        #self._generate_tp_compare(code_sink)

        if self.slots.get("tp_richcompare", "NULL") == "NULL":
            self.slots["tp_richcompare"] = self._generate_tp_richcompare(code_sink)

        if self.binary_numeric_operators or self.inplace_numeric_operators:
            self.slots["tp_as_number"] = self._generate_number_methods(code_sink)

        if self.have_sequence_methods():
            self.slots["tp_as_sequence"] = self._generate_sequence_methods(code_sink)

        if self.container_traits is not None:
            self.container_traits.generate(code_sink, module)

        self._generate_type_structure(code_sink, self.docstring)

    def _generate_number_methods(self, code_sink):
        number_methods_var_name = "%s__py_number_methods" % (self.mangled_full_name,)

        pynumbermethods = PyNumberMethods()
        pynumbermethods.slots['variable'] = number_methods_var_name

        # iterate over all types and request generation of the
        # convertion functions for that type (so that those functions
        # are not generated in the middle of one of the wrappers we
        # are about to generate)
        root_module = self.module.get_root()
        for dummy_op_symbol, op_types in self.binary_numeric_operators.iteritems():
            for (retval, left, right) in op_types:
                get_c_to_python_converter(retval, root_module, code_sink)
                get_python_to_c_converter(left, root_module, code_sink)
                get_python_to_c_converter(right, root_module, code_sink)

        for dummy_op_symbol, op_types in self.inplace_numeric_operators.iteritems():
            for (retval, left, right) in op_types:
                get_python_to_c_converter(left, root_module, code_sink)
                get_python_to_c_converter(right, root_module, code_sink)
                get_c_to_python_converter(retval, root_module, code_sink)

        for dummy_op_symbol, op_types in self.unary_numeric_operators.iteritems():
            for (retval, left) in op_types:
                get_c_to_python_converter(retval, root_module, code_sink)
                get_python_to_c_converter(left, root_module, code_sink)

        def try_wrap_operator(op_symbol, slot_name):
            if op_symbol in self.binary_numeric_operators:
                op_types = self.binary_numeric_operators[op_symbol]
            elif op_symbol in self.inplace_numeric_operators:
                op_types = self.inplace_numeric_operators[op_symbol]
            else:
                return

            wrapper_name = "%s__%s" % (self.mangled_full_name, slot_name)
            pynumbermethods.slots[slot_name] = wrapper_name
            code_sink.writeln(("static PyObject*\n"
                               "%s (PyObject *py_left, PyObject *py_right)\n"
                               "{") % wrapper_name)
            code_sink.indent()
            for (retval, left, right) in op_types:
                retval_converter, retval_name = get_c_to_python_converter(retval, root_module, code_sink)
                left_converter, left_name = get_python_to_c_converter(left, root_module, code_sink)
                right_converter, right_name = get_python_to_c_converter(right, root_module, code_sink)

                code_sink.writeln("{")
                code_sink.indent()
                
                code_sink.writeln("%s left;" % left_name)
                code_sink.writeln("%s right;" % right_name)
                
                code_sink.writeln("if (%s(py_left, &left) && %s(py_right, &right)) {" % (left_converter, right_converter))
                code_sink.indent()
                code_sink.writeln("%s result = (left %s right);" % (retval_name, op_symbol))
                code_sink.writeln("return %s(&result);" % retval_converter)
                code_sink.unindent()
                code_sink.writeln("}")
                code_sink.writeln("PyErr_Clear();")

                code_sink.unindent()
                code_sink.writeln("}")
                
            code_sink.writeln("Py_INCREF(Py_NotImplemented);")
            code_sink.writeln("return Py_NotImplemented;")
            code_sink.unindent()
            code_sink.writeln("}")

        def try_wrap_unary_operator(op_symbol, slot_name):
            if op_symbol in self.unary_numeric_operators:
                op_types = self.unary_numeric_operators[op_symbol]
            else:
                return

            wrapper_name = "%s__%s" % (self.mangled_full_name, slot_name)
            pynumbermethods.slots[slot_name] = wrapper_name
            code_sink.writeln(("static PyObject*\n"
                               "%s (PyObject *py_self)\n"
                               "{") % wrapper_name)
            code_sink.indent()
            for (retval, left) in op_types:
                retval_converter, retval_name = get_c_to_python_converter(retval, root_module, code_sink)
                left_converter, left_name = get_python_to_c_converter(left, root_module, code_sink)

                code_sink.writeln("{")
                code_sink.indent()
                
                code_sink.writeln("%s self;" % left_name)
                
                code_sink.writeln("if (%s(py_self, &self)) {" % (left_converter))
                code_sink.indent()
                code_sink.writeln("%s result = %s(self);" % (retval_name, op_symbol))
                code_sink.writeln("return %s(&result);" % retval_converter)
                code_sink.unindent()
                code_sink.writeln("}")
                code_sink.writeln("PyErr_Clear();")

                code_sink.unindent()
                code_sink.writeln("}")
                
            code_sink.writeln("Py_INCREF(Py_NotImplemented);")
            code_sink.writeln("return Py_NotImplemented;")
            code_sink.unindent()
            code_sink.writeln("}")

        try_wrap_operator('+', 'nb_add')
        try_wrap_operator('-', 'nb_subtract')
        try_wrap_operator('*', 'nb_multiply')
        try_wrap_operator('/', 'nb_divide')
        
        try_wrap_operator('+=', 'nb_inplace_add')
        try_wrap_operator('-=', 'nb_inplace_subtract')
        try_wrap_operator('*=', 'nb_inplace_multiply')
        try_wrap_operator('/=', 'nb_inplace_divide')

        try_wrap_unary_operator('-', 'nb_negative')

        pynumbermethods.generate(code_sink)
        return '&' + number_methods_var_name
        
    def _generate_sequence_methods(self, code_sink):
        sequence_methods_var_name = "%s__py_sequence_methods" % (self.mangled_full_name,)

        pysequencemethods = PySequenceMethods()
        pysequencemethods.slots['variable'] = sequence_methods_var_name

        root_module = self.module.get_root()
        self_converter = root_module.generate_python_to_c_type_converter(self.ThisClassReturn(self.full_name), code_sink)

        def try_wrap_sequence_method(py_name, slot_name):
            if py_name in self.methods:
                numwraps = len(self.methods[py_name].wrappers)
                some_wrapper_is_function = max([isinstance(x, function.Function) for x in self.methods[py_name].wrappers])
                meth_wrapper_actual_name = self.methods[py_name].wrapper_actual_name
                wrapper_name = "%s__%s" % (self.mangled_full_name, slot_name)
                pysequencemethods.slots[slot_name] = wrapper_name
                if py_name == "__len__" and (numwraps > 1 or some_wrapper_is_function):
                    template = pysequencemethods.FUNCTION_TEMPLATES[slot_name + "_ARGS"]
                else:
                    template = pysequencemethods.FUNCTION_TEMPLATES[slot_name]
                code_sink.writeln(template % {'wrapper_name'   : wrapper_name,
                                              'py_struct'      : self._pystruct,
                                              'method_name'    : meth_wrapper_actual_name})
                return

        for (py_name, slot_name) in [("__len__", "sq_length"),
                                     ("__getitem__", "sq_item"),
                                     ("__setitem__", "sq_ass_item")]:
            try_wrap_sequence_method(py_name, slot_name)
            

        pysequencemethods.generate(code_sink)
        return '&' + sequence_methods_var_name
        
    def have_sequence_methods(self):
        """Determine if this object has sequence methods registered."""
        for x in self.valid_sequence_methods:
            if x in self.methods:
                return True
        return False

    def _generate_type_structure(self, code_sink, docstring):
        """generate the type structure"""
        self.slots.setdefault("tp_basicsize",
                              "sizeof(%s)" % (self.pystruct,))
        tp_flags = set(['Py_TPFLAGS_DEFAULT'])
        if self.allow_subclassing:
            tp_flags.add("Py_TPFLAGS_HAVE_GC")
            tp_flags.add("Py_TPFLAGS_BASETYPE")
            self.slots.setdefault("tp_dictoffset",
                                  "offsetof(%s, inst_dict)" % self.pystruct)
        else:
            self.slots.setdefault("tp_dictoffset", "0")
        if self.binary_numeric_operators:
            tp_flags.add("Py_TPFLAGS_CHECKTYPES")            
        self.slots.setdefault("tp_flags", '|'.join(tp_flags))
        self.slots.setdefault("tp_doc", (docstring is None and 'NULL'
                                         or "\"%s\"" % (docstring,)))
        dict_ = self.slots
        dict_.setdefault("typestruct", self.pytypestruct)

        if self.outer_class is None:
            mod_path = self._module.get_module_path()
            mod_path.append(self.mangled_name)
            dict_.setdefault("tp_name", '.'.join(mod_path))
        else:
            dict_.setdefault("tp_name", '%s.%s' % (self.outer_class.slots['tp_name'], self.name))

        ## tp_call support
        try:
            call_method = self.methods['__call__']
        except KeyError:
            pass
        else:
            dict_.setdefault("tp_call", call_method.wrapper_actual_name)

        self.pytype.generate(code_sink)


    def _generate_constructor(self, code_sink):
        """generate the constructor, if any"""
        have_constructor = True
        if self.constructors and ((not self.cannot_be_constructed) or self.helper_class is not None
                                  and not self.helper_class.cannot_be_constructed):
            code_sink.writeln()
            overload = CppOverloadedConstructor(None)
            self.constructors_overload = overload
            overload.pystruct = self.pystruct
            for constructor in self.constructors:
                try:
                    overload.add(constructor)
                except CodegenErrorBase:
                    continue
            if overload.wrappers:
                try:
                    overload.generate(code_sink)
                except utils.SkipWrapper:
                    constructor = None
                    have_constructor = False
                else:
                    constructor = overload.wrapper_actual_name
                    code_sink.writeln()
            else:
                constructor = None
                have_constructor = False
        else:
            ## In C++, and unlike Python, constructors with
            ## parameters are not automatically inheritted by
            ## subclasses.  We must generate a 'no constructor'
            ## tp_init to prevent this type from inheriting a
            ## tp_init that will allocate an instance of the
            ## parent class instead of this class.
            code_sink.writeln()            
            wrapper = CppNoConstructor(self.cannot_be_constructed)
            wrapper.generate(code_sink, self)
            constructor = wrapper.wrapper_actual_name
            have_constructor = False
            code_sink.writeln()

        self.slots.setdefault("tp_init", (constructor is None and "NULL"
                                          or constructor))
        return have_constructor

    def _generate_copy_method(self, code_sink):
        construct_name = self.get_construct_name()
        copy_wrapper_name = '_wrap_%s__copy__' % self.pystruct
        code_sink.writeln('''
static PyObject*\n%s(%s *self)
{
''' % (copy_wrapper_name, self.pystruct))
        code_sink.indent()

        declarations = DeclarationsScope()
        code_block = CodeBlock("return NULL;", declarations)

        if self.allow_subclassing:
            new_func = 'PyObject_GC_New'
        else:
            new_func = 'PyObject_New'

        py_copy = declarations.declare_variable("%s*" % self.pystruct, "py_copy")
        code_block.write_code("%s = %s(%s, %s);" %
                              (py_copy, new_func, self.pystruct, '&'+self.pytypestruct))
        code_block.write_code("%s->obj = new %s(*self->obj);" % (py_copy, construct_name))
        if self.allow_subclassing:
            code_block.write_code("%s->inst_dict = NULL;" % py_copy)
        code_block.write_code("%s->flags = PYBINDGEN_WRAPPER_FLAG_NONE;" % py_copy)

        self.wrapper_registry.write_register_new_wrapper(code_block, py_copy, "%s->obj" % py_copy)

        code_block.write_code("return (PyObject*) %s;" % py_copy)

        declarations.get_code_sink().flush_to(code_sink)

        code_block.write_cleanup()
        code_block.sink.flush_to(code_sink)

        code_sink.unindent()
        code_sink.writeln("}")
        code_sink.writeln()
        return copy_wrapper_name

    def _generate_MI_parent_methods(self, code_sink):
        methods = {}
        mro = self.get_mro()
        mro.next()
        for base in mro:
            for method_name, parent_overload in base.methods.iteritems():

                # skip methods registered via special type slots, not method table
                if method_name in ['__call__', "__len__", "__getitem__", "__setitem__"]:
                    continue

                try:
                    overload = methods[method_name]
                except KeyError:
                    overload = CppOverloadedMethod(method_name)
                    overload.pystruct = self.pystruct
                    methods[method_name] = overload

                for parent_wrapper in parent_overload.wrappers:

                    if parent_wrapper.visibility != 'public':
                        continue

                    # the method may have been re-defined as private in our class
                    private = False
                    for leaf_wrapper in self.nonpublic_methods:
                        if leaf_wrapper.matches_signature(parent_wrapper):
                            private = True
                            break
                    if private:
                        continue

                    # the method may have already been wrapped in our class
                    already_wrapped = False
                    try:
                        overload = self.methods[method_name]
                    except KeyError:
                        pass
                    else:
                        for leaf_wrapper in overload.wrappers:
                            if leaf_wrapper.matches_signature(parent_wrapper):
                                already_wrapped = True
                                break
                    if already_wrapped:
                        continue

                    wrapper = parent_wrapper.clone()
                    wrapper.original_class = base
                    wrapper.class_ = self
                    overload.add(wrapper)

        method_defs = []
        for method_name, overload in methods.iteritems():
            if not overload.wrappers:
                continue

            classes = []
            for wrapper in overload.wrappers:
                if wrapper.original_class not in classes:
                    classes.append(wrapper.original_class)
            if len(classes) > 1:
                continue # overloading with multiple base classes is just too confusing

            try:
                utils.call_with_error_handling(overload.generate, (code_sink,), {}, overload)
            except utils.SkipWrapper:
                continue
            code_sink.writeln()
            method_defs.append(overload.get_py_method_def(method_name))
        return method_defs

    def _generate_methods(self, code_sink, parent_caller_methods):
        """generate the method wrappers"""
        method_defs = []
        for meth_name, overload in self.methods.iteritems():
            code_sink.writeln()
            #overload.generate(code_sink)
            try:
                utils.call_with_error_handling(overload.generate, (code_sink,), {}, overload)
            except utils.SkipWrapper:
                continue
            # skip methods registered via special type slots, not method table
            if meth_name not in ['__call__', "__len__",
                                 "__getitem__", "__setitem__"]:
                method_defs.append(overload.get_py_method_def(meth_name))
            code_sink.writeln()
        method_defs.extend(parent_caller_methods)

        if len(self.bases) > 1: # https://bugs.launchpad.net/pybindgen/+bug/563786
            method_defs.extend(self._generate_MI_parent_methods(code_sink))

        if self.has_copy_constructor:
            try:
                copy_wrapper_name = utils.call_with_error_handling(self._generate_copy_method, (code_sink,), {}, self)
            except utils.SkipWrapper:
                pass
            else:
                method_defs.append('{(char *) "__copy__", (PyCFunction) %s, METH_NOARGS, NULL},' % copy_wrapper_name)

        ## generate the method table
        code_sink.writeln("static PyMethodDef %s_methods[] = {" % (self.pystruct,))
        code_sink.indent()
        for methdef in method_defs:
            code_sink.writeln(methdef)
        code_sink.writeln("{NULL, NULL, 0, NULL}")
        code_sink.unindent()
        code_sink.writeln("};")
        self.slots.setdefault("tp_methods", "%s_methods" % (self.pystruct,))

    def _get_delete_code(self):
        if self.is_singleton:
            delete_code = ''
        else:
            if self.memory_policy is not None:
                delete_code = ("if (self->obj) {\n"
                               "    %s *tmp = self->obj;\n"
                               "    self->obj = NULL;\n"
                               "    %s\n"
                               "}"
                               % (self.full_name, self.memory_policy.get_free_code('tmp')))
            else:
                if self.incomplete_type:
                    raise CodeGenerationError("Cannot finish generating class %s: "
                                              "type is incomplete, but no free/unref_function defined"
                                              % self.full_name)
                if self.destructor_visibility == 'public':
                    delete_code = ("    %s *tmp = self->obj;\n"
                                   "    self->obj = NULL;\n"
                                   "    if (!(self->flags&PYBINDGEN_WRAPPER_FLAG_OBJECT_NOT_OWNED)) {\n"
                                   "        delete tmp;\n"
                                   "    }" % (self.full_name,))
                else:
                    delete_code = ("    self->obj = NULL;\n")
        return delete_code

    def _generate_gc_methods(self, code_sink):
        """Generate tp_clear and tp_traverse"""

        ## --- tp_clear ---
        tp_clear_function_name = "%s__tp_clear" % (self.pystruct,)
        self.slots.setdefault("tp_clear", tp_clear_function_name )
        delete_code = self._get_delete_code()
        code_sink.writeln(r'''
static void
%s(%s *self)
{
    Py_CLEAR(self->inst_dict);
    %s
}
''' % (tp_clear_function_name, self.pystruct, delete_code))

        ## --- tp_traverse ---
        tp_traverse_function_name = "%s__tp_traverse" % (self.pystruct,)
        self.slots.setdefault("tp_traverse", tp_traverse_function_name )

        if self.helper_class is None:
            visit_self = ''
        else:
            if not isinstance(self.memory_policy, ReferenceCountingMethodsPolicy) or self.memory_policy.peekref_method is None:
                peekref_code = ''
            else:
                peekref_code = " && self->obj->%s() == 1" % self.memory_policy.peekref_method
            visit_self = '''
    if (self->obj && typeid(*self->obj).name() == typeid(%s).name() %s)
        Py_VISIT((PyObject *) self);
''' % (self.helper_class.name, peekref_code)

        code_sink.writeln(r'''
static int
%s(%s *self, visitproc visit, void *arg)
{
    Py_VISIT(self->inst_dict);
    %s
    return 0;
}
''' % (tp_traverse_function_name, self.pystruct, visit_self))

    def _generate_str(self, code_sink):
        """Generate a tp_str function and register it in the type"""

        tp_str_function_name = "_wrap_%s__tp_str" % (self.pystruct,)
        self.slots.setdefault("tp_str", tp_str_function_name )

        code_sink.writeln('''

static PyObject *
%s(%s *self)
{
    std::ostringstream oss;
    oss << *self->obj;
    return PyString_FromString(oss.str ().c_str ());
}

''' % (tp_str_function_name, self.pystruct))

    def _generate_tp_hash(self, code_sink):
        """generates a tp_hash function, which returns a hash of the self->obj pointer"""

        tp_hash_function_name = "_wrap_%s__tp_hash" % (self.pystruct,)
        self.slots.setdefault("tp_hash", tp_hash_function_name )

        code_sink.writeln('''

static long
%s(%s *self)
{
    return (long) self->obj;
}

''' % (tp_hash_function_name, self.pystruct))

    def _generate_tp_compare(self, code_sink):
        """generates a tp_compare function, which compares the ->obj pointers"""

        tp_compare_function_name = "_wrap_%s__tp_compare" % (self.pystruct,)
        self.slots.setdefault("tp_compare", tp_compare_function_name )

        code_sink.writeln('''

static int
%s(%s *self, %s *other)
{
    if (self->obj == other->obj) return 0;
    if (self->obj > other->obj)  return -1;
    return 1;
}

''' % (tp_compare_function_name, self.pystruct, self.pystruct))
        

    def _generate_destructor(self, code_sink, have_constructor):
        """Generate a tp_dealloc function and register it in the type"""

        ## don't generate destructor if overridden by user
        if "tp_dealloc" in self.slots:
            return

        tp_dealloc_function_name = "_wrap_%s__tp_dealloc" % (self.pystruct,)
        code_sink.writeln(r'''
static void
%s(%s *self)
{''' % (tp_dealloc_function_name, self.pystruct))
        code_sink.indent()

        code_block = CodeBlock("PyErr_Print(); return;", DeclarationsScope())

        self.wrapper_registry.write_unregister_wrapper(code_block, 'self', 'self->obj')

        if self.allow_subclassing:
            code_block.write_code("%s(self);" % self.slots["tp_clear"])
        else:
            code_block.write_code(self._get_delete_code())

        code_block.write_code('self->ob_type->tp_free((PyObject*)self);')

        code_block.write_cleanup()
        
        code_block.declarations.get_code_sink().flush_to(code_sink)
        code_block.sink.flush_to(code_sink)

        code_sink.unindent()
        code_sink.writeln('}\n')

        self.slots.setdefault("tp_dealloc", tp_dealloc_function_name )


    def _generate_tp_richcompare(self, code_sink):
        tp_richcompare_function_name = "_wrap_%s__tp_richcompare" % (self.pystruct,)

        code_sink.writeln("static PyObject*\n%s (%s *PYBINDGEN_UNUSED(self), %s *other, int opid)"
                          % (tp_richcompare_function_name, self.pystruct, self.pystruct))
        code_sink.writeln("{")
        code_sink.indent()

        code_sink.writeln("""
if (!PyObject_IsInstance((PyObject*) other, (PyObject*) &%s)) {
    Py_INCREF(Py_NotImplemented);
    return Py_NotImplemented;
}""" % self.pytypestruct)

        code_sink.writeln("switch (opid)\n{")

        def wrap_operator(name, opid_code):
            code_sink.writeln("case %s:" % opid_code)
            code_sink.indent()
            if name in self.binary_comparison_operators:
                code_sink.writeln("if (*self->obj %(OP)s *other->obj) {\n"
                                  "    Py_INCREF(Py_True);\n"
                                  "    return Py_True;\n"
                                  "} else {\n"
                                  "    Py_INCREF(Py_False);\n"
                                  "    return Py_False;\n"
                                  "}" % dict(OP=name))
            else:
                code_sink.writeln("Py_INCREF(Py_NotImplemented);\n"
                                  "return Py_NotImplemented;")
            code_sink.unindent()
        
        wrap_operator('<', 'Py_LT')
        wrap_operator('<=', 'Py_LE')
        wrap_operator('==', 'Py_EQ')
        wrap_operator('!=', 'Py_NE')
        wrap_operator('>=', 'Py_GE')
        wrap_operator('>', 'Py_GT')

        code_sink.writeln("} /* closes switch (opid) */")

        code_sink.writeln("Py_INCREF(Py_NotImplemented);\n"
                          "return Py_NotImplemented;")

        code_sink.unindent()
        code_sink.writeln("}\n")

        return tp_richcompare_function_name

    def generate_typedef(self, module, alias):
        """
        Generates the appropriate Module code to register the class
        with a new name in that module (typedef alias).
        """
        module.after_init.write_code(
            'PyModule_AddObject(m, (char *) \"%s\", (PyObject *) &%s);' % (
                alias, self.pytypestruct))
        


from cppclass_typehandlers import CppClassParameter, CppClassRefParameter, \
    CppClassReturnValue, CppClassRefReturnValue, CppClassPtrParameter, CppClassPtrReturnValue, CppClassParameterBase
import function

from cppmethod import CppMethod, CppConstructor, CppNoConstructor, CppFunctionAsConstructor, \
    CppOverloadedMethod, CppOverloadedConstructor, \
    CppVirtualMethodParentCaller, CppVirtualMethodProxy, CustomCppMethodWrapper, \
    CppDummyMethod

