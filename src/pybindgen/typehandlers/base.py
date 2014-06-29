## -*- python -*-
## pylint: disable-msg=W0142,R0921

"""
Base classes for all parameter/return type handlers,
and base interfaces for wrapper generators.
"""

import codesink
import warnings
import ctypeparser
import logging
logger = logging.getLogger("pybindgen.typehandlers")


try:
    all
except NameError: # for compatibility with Python < 2.5
    def all(iterable):
        "Returns True if all elements are true"
        for element in iterable:
            if not element:
                return False
        return True
try: 
    set 
except NameError: 
    from sets import Set as set   # Python 2.3 fallback 




class CodegenErrorBase(Exception):
    pass

class NotSupportedError(CodegenErrorBase):
    """Exception that is raised when declaring an interface configuration
    that is not supported or not implemented."""

class CodeGenerationError(CodegenErrorBase):
    """Exception that is raised when wrapper generation fails for some reason."""

class TypeLookupError(CodegenErrorBase):
    """Exception that is raised when lookup of a type handler fails"""

class TypeConfigurationError(CodegenErrorBase):
    """Exception that is raised when a type handler does not find some
    information it needs, such as owernship transfer semantics."""


def join_ctype_and_name(ctype, name):
    """
    Utility method that joins a C type and a variable name into
    a single string

    >>> join_ctype_and_name('void*', 'foo')
    'void *foo'
    >>> join_ctype_and_name('void *', 'foo')
    'void *foo'
    >>> join_ctype_and_name("void**", "foo")
    'void **foo'
    >>> join_ctype_and_name("void **", "foo")
    'void **foo'
    >>> join_ctype_and_name('C*', 'foo')
    'C *foo'
    """
    if ctype[-1] == '*':
        for i in range(-1, -len(ctype) - 1, -1):
            if ctype[i] != '*':
                if ctype[i] == ' ':
                    return "".join([ctype[:i+1], ctype[i+1:], name])
                else:
                    return "".join([ctype[:i+1], ' ', ctype[i+1:], name])
        raise ValueError((ctype, name))
    else:
        return " ".join([ctype, name])


class CodeBlock(object):
    '''An intelligent code block that keeps track of cleanup actions.
    This object is to be used by TypeHandlers when generating code.'''

    class CleanupHandle(object):
        """Handle for some cleanup code"""
        __slots__ = ['code_block', 'position']
        def __init__(self, code_block, position):
            """Create a handle given code_block and position"""
            self.code_block = code_block
            self.position = position

        def __cmp__(self, other):
            comp = cmp(self.code_block, other.code_block)
            if comp:
                return comp
            return cmp(self.position, other.position)

        def cancel(self):
            """Cancel the cleanup code"""
            self.code_block.remove_cleanup_code(self)

        def get_position(self):
            "returns the cleanup code relative position"
            return self.position

    
    def __init__(self, error_return, declarations, predecessor=None):
        '''
        CodeBlock constructor

        >>> block = CodeBlock("return NULL;", DeclarationsScope())
        >>> block.write_code("foo();")
        >>> cleanup1 = block.add_cleanup_code("clean1();")
        >>> cleanup2 = block.add_cleanup_code("clean2();")
        >>> cleanup3 = block.add_cleanup_code("clean3();")
        >>> cleanup2.cancel()
        >>> block.write_error_check("error()", "error_clean()")
        >>> block.write_code("bar();")
        >>> block.write_cleanup()
        >>> print block.sink.flush().rstrip()
        foo();
        if (error()) {
            error_clean()
            clean3();
            clean1();
            return NULL;
        }
        bar();
        clean3();
        clean1();

        :param error_return: code that is generated on error conditions
                           (detected by write_error_check()); normally
                           it returns from the wrapper function,
                           e.g. return NULL;
        :param predecessor: optional predecessor code block; a
                          predecessor is used to search for additional
                          cleanup actions.        
        '''
        assert isinstance(declarations, DeclarationsScope)
        assert predecessor is None or isinstance(predecessor, CodeBlock)
        self.sink = codesink.MemoryCodeSink()
        self.predecessor = predecessor
        self._cleanup_actions = {}
        self._last_cleanup_position = 0
        self.error_return = error_return
        self.declarations = declarations

    def clear(self):
        self._cleanup_actions = {}
        self._last_cleanup_position = 0        
        self.sink = codesink.MemoryCodeSink()

    def declare_variable(self, type_, name, initializer=None, array=None):
        """
        Calls declare_variable() on the associated DeclarationsScope object.
        """
        if ':' in name:
            raise ValueError("invalid variable name: %s " % name)
        return self.declarations.declare_variable(type_, name, initializer, array)
        
    def write_code(self, code):
        '''Write out some simple code'''
        self.sink.writeln(code)

    def indent(self, level=4):
        '''Add a certain ammount of indentation to all lines written
        from now on and until unindent() is called'''
        self.sink.indent(level)

    def unindent(self):
        '''Revert indentation level to the value before last indent() call'''
        self.sink.unindent()

    def add_cleanup_code(self, cleanup_code):
        '''Add a chunk of code used to cleanup previously allocated resources

        Returns a handle used to cancel the cleanup code
        '''
        self._last_cleanup_position += 1
        handle = self.CleanupHandle(self, self._last_cleanup_position)
        self._cleanup_actions[handle.get_position()] = cleanup_code
        return handle

    def remove_cleanup_code(self, handle):
        '''Remove cleanup code previously added with add_cleanup_code()
        '''
        assert isinstance(handle, self.CleanupHandle)
        del self._cleanup_actions[handle.get_position()]

    def get_cleanup_code(self):
        '''return a new list with all cleanup actions, including the
        ones from predecessor code blocks; Note: cleanup actions are
        executed in reverse order than when they were added.'''
        cleanup = []
        items = self._cleanup_actions.items()
        items.sort()
        for dummy, code in items:
            cleanup.append(code)
        cleanup.reverse()
        if self.predecessor is not None:
            cleanup.extend(self.predecessor.get_cleanup_code())
        return cleanup

    def write_error_check(self, failure_expression, failure_cleanup=None):
        '''Add a chunk of code that checks for a possible error

        :param failure_expression: C boolean expression that is true when
                              an error occurred
        :param failure_cleanup: optional extra cleanup code to write only
                           for the the case when failure_expression is
                           true; this extra cleanup code comes before
                           all other cleanup code previously registered.
        '''
        self.sink.writeln("if (%s) {" % (failure_expression,))
        self.sink.indent()
        if failure_cleanup is not None:
            self.sink.writeln(failure_cleanup)
        self.write_error_return()
        self.sink.unindent()
        self.sink.writeln("}")

    def write_cleanup(self):
        """Write the current cleanup code."""
        for cleanup_action in self.get_cleanup_code():
            self.sink.writeln(cleanup_action)

    def write_error_return(self):
        '''Add a chunk of code that cleans up and returns an error.
        '''
        self.write_cleanup()
        self.sink.writeln(self.error_return)



class ParseTupleParameters(object):
    "Object to keep track of PyArg_ParseTuple (or similar) parameters"

    def __init__(self):
        """
        >>> tuple_params = ParseTupleParameters()
        >>> tuple_params.add_parameter('i', ['&foo'], 'foo')
        1
        >>> tuple_params.add_parameter('s', ['&bar'], 'bar', optional=True)
        2
        >>> tuple_params.get_parameters()
        ['"i|s"', '&foo', '&bar']
        >>> tuple_params.get_keywords()
        ['foo', 'bar']

        >>> tuple_params = ParseTupleParameters()
        >>> tuple_params.add_parameter('i', ['&foo'], 'foo')
        1
        >>> tuple_params.add_parameter('s', ['&bar'], 'bar', prepend=True)
        2
        >>> tuple_params.get_parameters()
        ['"si"', '&bar', '&foo']
        >>> tuple_params.get_keywords()
        ['bar', 'foo']

        >>> tuple_params = ParseTupleParameters()
        >>> tuple_params.add_parameter('i', ['&foo'])
        1
        >>> print tuple_params.get_keywords()
        None
        """
        self._parse_tuple_items = [] # (template, param_values, param_name, optional)

    def clear(self):
        self._parse_tuple_items = []
        
    def add_parameter(self, param_template, param_values, param_name=None,
                      prepend=False, optional=False):
        """
        Adds a new parameter specification

        :param param_template: template item, see documentation for
                          PyArg_ParseTuple for more information
        :param param_values: list of parameters, see documentation
                       for PyArg_ParseTuple for more information
        :param prepend: whether this parameter should be parsed first
        :param optional: whether the parameter is optional; note that after
                    the first optional parameter, all remaining
                    parameters must also be optional
        """
        assert isinstance(param_values, list)
        assert isinstance(param_template, str)
        item = (param_template, param_values, param_name, optional)
        if prepend:
            self._parse_tuple_items.insert(0, item)
        else:
            self._parse_tuple_items.append(item)
        return len(self._parse_tuple_items)

    def is_empty(self):
        return self.get_parameters() == ['""']

    def get_parameters(self):
        """
        returns a list of parameters to pass into a
        PyArg_ParseTuple-style function call, the first paramter in
        the list being the template string.
        """
        template = ['"']
        last_was_optional = False
        for (param_template, dummy,
             param_name, optional) in self._parse_tuple_items:
            if last_was_optional and not optional:
                raise ValueError("Error: optional parameter followed by a non-optional one (%r)"
                                 " (debug: self._parse_tuple_parameters=%r)" % (param_name, self._parse_tuple_items))
            if not last_was_optional and optional:
                template.append('|')
                last_was_optional = True
            template.append(param_template)
        template.append('"')
        params = [''.join(template)]
        for (dummy, param_values,
             dummy, dummy) in self._parse_tuple_items:
            params.extend(param_values)
        return params
        
    def get_keywords(self):
        """
        returns list of keywords (parameter names), or None if none of
        the parameters had a name; should only be called if names were
        given for all parameters or none of them.
        """
        keywords = []
        for (dummy, dummy, name, dummy) in self._parse_tuple_items:
            if name is None:
                if keywords:
                    raise ValueError("mixing parameters with and without keywords")
            else:
                keywords.append(name)
        if keywords:
            if len(keywords) != len(self._parse_tuple_items):
                raise ValueError("mixing parameters with and without keywords")
            return keywords
        else:
            return None


class BuildValueParameters(object):
    "Object to keep track of Py_BuildValue (or similar) parameters"

    def __init__(self):
        """
        >>> bld = BuildValueParameters()
        >>> bld.add_parameter('i', [123, 456])
        >>> bld.add_parameter('s', ["hello"])
        >>> bld.get_parameters()
        ['"is"', 123, 456, 'hello']
        >>> bld = BuildValueParameters()
        >>> bld.add_parameter('i', [123])
        >>> bld.add_parameter('s', ["hello"], prepend=True)
        >>> bld.get_parameters()
        ['"si"', 'hello', 123]
        """
        self._build_value_items = [] # (template, param_value, cleanup_handle)

    def clear(self):
        self._build_value_items = []

    def add_parameter(self, param_template, param_values,
                      prepend=False, cancels_cleanup=None):
        """
        Adds a new parameter to the Py_BuildValue (or similar) statement.

        :param param_template: template item, see documentation for
                          Py_BuildValue for more information
        :param param_values: list of C expressions to use as value, see documentation
                        for Py_BuildValue for more information
        :param prepend: whether this parameter should come first in the tuple being built
        :param cancels_cleanup: optional handle to a cleanup action,
                           that is removed after the call.  Typically
                           this is used for 'N' parameters, which
                           already consume an object reference
        """
        item = (param_template, param_values, cancels_cleanup)
        if prepend:
            self._build_value_items.insert(0, item)
        else:
            self._build_value_items.append(item)

    def get_parameters(self, force_tuple_creation=False):
        """returns a list of parameters to pass into a
        Py_BuildValue-style function call, the first paramter in
        the list being the template string.

        :param force_tuple_creation: if True, Py_BuildValue is
           instructed to always create a tuple, even for zero or 1
           values.
        """
        template = ['"']
        if force_tuple_creation:
            template.append('(')
        params = [None]
        for (param_template, param_values, dummy) in self._build_value_items:
            template.append(param_template)
            params.extend(param_values)
        if force_tuple_creation:
            template.append(')')
        template.append('"')
        params[0] = ''.join(template)
        return params

    def get_cleanups(self):
        """Get a list of handles to cleanup actions"""
        return [cleanup for (dummy, dummy, cleanup) in self._build_value_items]


class DeclarationsScope(object):
    """Manages variable declarations in a given scope."""

    def __init__(self, parent_scope=None):
        """
        Constructor

        >>> scope = DeclarationsScope()
        >>> scope.declare_variable('int', 'foo')
        'foo'
        >>> scope.declare_variable('char*', 'bar')
        'bar'
        >>> scope.declare_variable('int', 'foo')
        'foo2'
        >>> scope.declare_variable('int', 'foo', '1')
        'foo3'
        >>> scope.declare_variable('const char *', 'kwargs', '{"hello", NULL}', '[]')
        'kwargs'
        >>> print scope.get_code_sink().flush().rstrip()
        int foo;
        char *bar;
        int foo2;
        int foo3 = 1;
        const char *kwargs[] = {"hello", NULL};

        :param parent_scope: optional 'parent scope'; if given,
                        declarations in this scope will avoid clashing
                        with names in the parent scope, and vice
                        versa.
        """
        self._declarations = codesink.MemoryCodeSink()
        ## name -> number of variables with that name prefix
        if parent_scope is None:
            self.declared_variables = {}
        else:
            assert isinstance(parent_scope, DeclarationsScope)
            self.declared_variables = parent_scope.declared_variables

    def clear(self):
        self._declarations = codesink.MemoryCodeSink()
        self.declared_variables.clear()

    def declare_variable(self, type_, name, initializer=None, array=None):
        """Add code to declare a variable. Returns the actual variable
        name used (uses 'name' as base, with a number in case of conflict.)

        :param type_: C type name of the variable
        :param name: base name of the variable; actual name used can be
                slightly different in case of name conflict.
        :param initializer: optional, value to initialize the variable with
        :param array: optional, array size specifiction, e.g. '[]', or '[100]'
        """
        try:
            num = self.declared_variables[name]
        except KeyError:
            num = 0
        num += 1
        self.declared_variables[name] = num
        if num == 1:
            varname = name
        else:
            varname = "%s%i" % (name, num)
        decl = join_ctype_and_name(type_, varname)
        if array is not None:
            decl += array
        if initializer is not None:
            decl += ' = ' + initializer
        self._declarations.writeln(decl + ';')
        return varname

    def reserve_variable(self, name):
        """Reserve a variable name, to be used later.

        :param name: base name of the variable; actual name used can be
                slightly different in case of name conflict.
        """
        try:
            num = self.declared_variables[name]
        except KeyError:
            num = 0
        num += 1
        self.declared_variables[name] = num
        if num == 1:
            varname = name
        else:
            varname = "%s%i" % (name, num)
        return varname

    def get_code_sink(self):
        """Returns the internal MemoryCodeSink that holds all declararions."""
        return self._declarations



class ReverseWrapperBase(object):
    """Generic base for all reverse wrapper generators.

    Reverse wrappers all have the following general structure in common:

     1. 'declarations' -- variable declarations; for compatibility with
        older C compilers it is very important that all declarations
        come before any simple statement.  Declarations can be added
        with the add_declaration() method on the 'declarations'
        attribute.  Two standard declarations are always predeclared:
        '<return-type> retval', unless return-type is void, and 'PyObject
        \\*py_retval';

     2. 'code before call' -- this is a code block dedicated to contain
        all code that is needed before calling into Python; code can be
        freely added to it by accessing the 'before_call' (a CodeBlock
        instance) attribute;

     3. 'call into python' -- this is realized by a
        PyObject_CallMethod(...) or similar Python API call; the list
        of parameters used in this call can be customized by accessing
        the 'build_params' (a BuildValueParameters instance) attribute;

     4. 'code after call' -- this is a code block dedicated to contain
        all code that must come after calling into Python; code can be
        freely added to it by accessing the 'after_call' (a CodeBlock
        instance) attribute;

     5. A 'return retval' statement (or just 'return' if return_value is void)

    """

    NO_GIL_LOCKING = False

    def __init__(self, return_value, parameters, error_return=None):
        '''
        Base constructor

        :param return_value: type handler for the return value
        :param parameters: a list of type handlers for the parameters

        '''

        assert isinstance(return_value, TypeHandler)
        assert isinstance(parameters, list)
        assert all([isinstance(param, Parameter) for param in parameters])

        self.return_value = return_value
        self.parameters = parameters

        if error_return is None:
            error_return = return_value.get_c_error_return()
        self.error_return = error_return
        self.declarations = DeclarationsScope()
        self.before_call = CodeBlock(error_return, self.declarations)
        self.after_call = CodeBlock(error_return, self.declarations,
                                    predecessor=self.before_call)
        self.build_params = BuildValueParameters()
        self.parse_params = ParseTupleParameters()
        self._generate_gil_code()

    def set_error_return(self, error_return):
        self.error_return = error_return
        self.before_call.error_return = error_return
        self.after_call.error_return = error_return

    def reset_code_generation_state(self):
        self.declarations.clear()
        self.before_call.clear()
        self.after_call.clear()
        self.build_params.clear()
        self.parse_params.clear()
        self._generate_gil_code()

    def _generate_gil_code(self):
        if self.NO_GIL_LOCKING:
            return
        ## reverse wrappers are called from C/C++ code, when the Python GIL may not be held...
        gil_state_var = self.declarations.declare_variable('PyGILState_STATE', '__py_gil_state')
        self.before_call.write_code('%s = (PyEval_ThreadsInitialized() ? PyGILState_Ensure() : (PyGILState_STATE) 0);'
                                    % gil_state_var)
        self.before_call.add_cleanup_code('if (PyEval_ThreadsInitialized())\n'
                                          '    PyGILState_Release(%s);' % gil_state_var)


    def generate_python_call(self):
        """Generates the code (into self.before_call) to call into
        Python, storing the result in the variable 'py_retval'; should
        also check for call error.
        """
        raise NotImplementedError

    def generate(self, code_sink, wrapper_name, decl_modifiers=('static',),
                 decl_post_modifiers=()):
        """Generate the wrapper

        :param code_sink: a CodeSink object that will receive the code
        :param wrapper_name: C/C++ identifier of the function/method to generate
        :param decl_modifiers: list of C/C++ declaration modifiers, e.g. 'static'
        """
        assert isinstance(decl_modifiers, (list, tuple))
        assert all([isinstance(mod, str) for mod in decl_modifiers])

        self.declarations.declare_variable('PyObject*', 'py_retval')
        if self.return_value.ctype != 'void' \
                and not self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR:
            self.declarations.declare_variable(self.return_value.ctype, 'retval')

        ## convert the input parameters
        for param in self.parameters:
            param.convert_c_to_python(self)

        ## generate_python_call should include something like
        ## self.after_call.write_error_check('py_retval == NULL')
        self.generate_python_call()

        ## convert the return value(s)
        self.return_value.convert_python_to_c(self)

        if self.parse_params.is_empty():
            self.before_call.write_error_check('py_retval != Py_None',
                                               'PyErr_SetString(PyExc_TypeError, "function/method should return None");')
        else:
            ## parse the return value
            ## this ensures that py_retval is always a tuple
            self.before_call.write_code('py_retval = Py_BuildValue((char*) "(N)", py_retval);')

            parse_tuple_params = ['py_retval']
            parse_params = self.parse_params.get_parameters()
            assert parse_params[0][0] == '"'
            parse_params[0] = '(char *) ' + parse_params[0]
            parse_tuple_params.extend(parse_params)
            self.before_call.write_error_check('!PyArg_ParseTuple(%s)' %
                                               (', '.join(parse_tuple_params),),
                                               failure_cleanup='PyErr_Print();')

        ## cleanup and return
        self.after_call.write_cleanup()
        if self.return_value.ctype == 'void':
            self.after_call.write_code('return;')
        else:
            self.after_call.write_code('return retval;')

        ## now write out the wrapper function itself

        ## open function
        retline = list(decl_modifiers)
        retline.append(self.return_value.ctype)
        code_sink.writeln(' '.join(retline))

        params_list = ', '.join([join_ctype_and_name(param.ctype, param.name)
                                 for param in self.parameters])
        code_sink.writeln("%s(%s)%s" % (wrapper_name, params_list,
                                        ' '.join([''] + list(decl_post_modifiers))))

        ## body
        code_sink.writeln('{')
        code_sink.indent()
        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

        ## close function
        code_sink.unindent()
        code_sink.writeln('}')



class ForwardWrapperBase(object):
    """Generic base for all forward wrapper generators.

    Forward wrappers all have the following general structure in common:

     1. 'declarations' -- variable declarations; for compatibility
            with older C compilers it is very important that all
            declarations come before any simple statement.
            Declarations can be added with the add_declaration()
            method on the 'declarations' attribute.  Two standard
            declarations are always predeclared: '<return-type>
            retval', unless return-type is void, and 'PyObject
            \\*py_retval';

     2. 'code before parse' -- code before the
         PyArg_ParseTupleAndKeywords call; code can be freely added to
         it by accessing the 'before_parse' (a CodeBlock instance)
         attribute;

     3. A PyArg_ParseTupleAndKeywords call; uses items from the
         parse_params object;

     4. 'code before call' -- this is a code block dedicated to contain
         all code that is needed before calling the C function; code can be
         freely added to it by accessing the 'before_call' (a CodeBlock
         instance) attribute;

     5. 'call into C' -- this is realized by a C/C++ call; the list of
         parameters that should be used is in the 'call_params' wrapper
         attribute;

     6. 'code after call' -- this is a code block dedicated to contain
         all code that must come after calling into Python; code can be
         freely added to it by accessing the 'after_call' (a CodeBlock
         instance) attribute;

     7. A py_retval = Py_BuildValue(...) call; this call can be
        customized, so that out/inout parameters can add additional
        return values, by accessing the 'build_params' (a
        BuildValueParameters instance) attribute;

     8. Cleanup and return.

    Object constructors cannot return values, and so the step 7 is to
    be omitted for them.

    """

    PARSE_TUPLE = 1
    PARSE_TUPLE_AND_KEYWORDS = 2

    HAVE_RETURN_VALUE = False # change to true if the wrapper
                              # generates a return value even if the
                              # return_value attribute is None

    def __init__(self, return_value, parameters,
                 parse_error_return, error_return,
                 force_parse=None, no_c_retval=False,
                 unblock_threads=False):
        '''
        Base constructor

        :param return_value: type handler for the return value
        :param parameters: a list of type handlers for the parameters
        :param parse_error_return: statement to return an error during parameter parsing
        :param error_return: statement to return an error after parameter parsing
        :param force_parse: force generation of code to parse parameters even if there are none
        :param no_c_retval: force the wrapper to not have a C return value
        :param unblock_threads: generate code to unblock python threads during the C function call
        '''
        assert isinstance(return_value, ReturnValue) or return_value is None
        assert isinstance(parameters, list)
        assert all([isinstance(param, Parameter) for param in parameters])

        self.return_value = return_value
        self.parameters = parameters
        self.declarations = DeclarationsScope()
        self.before_parse = CodeBlock(parse_error_return, self.declarations)
        self.before_call = CodeBlock(parse_error_return, self.declarations,
                                     predecessor=self.before_parse)
        self.after_call = CodeBlock(error_return, self.declarations,
                                    predecessor=self.before_call)
        self.build_params = BuildValueParameters()
        self.parse_params = ParseTupleParameters()
        self.call_params = []
        self.force_parse = force_parse
        self.meth_flags = []
        self.unblock_threads = unblock_threads
        self.no_c_retval = no_c_retval
        self.overload_index = None
        self.deprecated = False

        # The following 3 variables describe the C wrapper function
        # prototype; do not confuse with the python function/method!
        self.wrapper_actual_name = None # name of the wrapper function/method
        self.wrapper_return = None # C type expression for the wrapper return
        self.wrapper_args = None # list of arguments to the wrapper function
        
        self._init_code_generation_state()

    def _init_code_generation_state(self):
        if self.return_value is not None or self.HAVE_RETURN_VALUE:
            self.declarations.declare_variable('PyObject*', 'py_retval')
        if (not self.no_c_retval and (self.return_value is not None or self.HAVE_RETURN_VALUE)
            and self.return_value.ctype != 'void'
            and not self.return_value.REQUIRES_ASSIGNMENT_CONSTRUCTOR):
            self.declarations.declare_variable(self.return_value.ctype_no_const, 'retval')

        self.declarations.reserve_variable('args')
        self.declarations.reserve_variable('kwargs')

    def reset_code_generation_state(self):
        self.declarations.clear()
        self.before_parse.clear()
        self.before_call.clear()
        self.after_call.clear()
        self.build_params.clear()
        self.parse_params.clear()
        self.call_params = []
        self.meth_flags = []

        self._init_code_generation_state()

    def set_parse_error_return(self, parse_error_return):
        self.before_parse.error_return = parse_error_return
        self.before_call.error_return = parse_error_return

    def generate_call(self):
        """Generates the code (into self.before_call) to call into
        Python, storing the result in the variable 'py_retval'; should
        also check for call error.
        """
        raise NotImplementedError

    def _before_call_hook(self):
        """
        Optional hook that lets subclasses add code after all
        parameters are parsed, but before the C function/method call.
        Subclasses may add code to self.before_call.
        """
        pass

    def _before_return_hook(self):
        """
        Optional hook that lets subclasses add code after all
        parameters are parsed and after the function C return value is
        processed, but after the python wrapper return value (py_ret)
        is built and returned.  Subclasses may add code to
        self.after_call, which will be placed before py_ret is
        created.
        """
        pass

    def write_open_wrapper(self, code_sink, add_static=False):
        assert self.wrapper_actual_name is not None
        assert self.wrapper_return is not None
        assert isinstance(self.wrapper_args, list)
        if add_static:
            code_sink.writeln("static " + self.wrapper_return)
        else:
            code_sink.writeln(self.wrapper_return)
        code_sink.writeln("%s(%s)" % (self.wrapper_actual_name, ', '.join(self.wrapper_args)))
        code_sink.writeln('{')
        code_sink.indent()

    def write_close_wrapper(self, code_sink):
        code_sink.unindent()
        code_sink.writeln('}')


    def generate_body(self, code_sink, gen_call_params=()):
        """Generate the wrapper function body
        code_sink -- a CodeSink object that will receive the code
        """

        if self.unblock_threads:
            py_thread_state = self.declarations.declare_variable("PyThreadState*", "py_thread_state", "NULL")
            self.after_call.write_code(
                "\nif (%s)\n"
                "     PyEval_RestoreThread(%s);\n" % (py_thread_state, py_thread_state))

        ## convert the input parameters
        for param in self.parameters:
            try:
                param.convert_python_to_c(self)
            except NotImplementedError:
                raise CodeGenerationError(
                    'convert_python_to_c method of parameter %s not implemented'
                    % (param.ctype,))

        if self.deprecated:
            if isinstance(self.deprecated, basestring):
                msg = self.deprecated
            else:
                msg = "Deprecated"
            self.before_call.write_error_check( 'PyErr_Warn(PyExc_DeprecationWarning, (char *) "%s")' % msg)

        self._before_call_hook()

        if self.unblock_threads:
            self.before_call.write_code(
                "\nif (PyEval_ThreadsInitialized ())\n"
                "     %s = PyEval_SaveThread();\n"
                % (py_thread_state, ))

        self.generate_call(*gen_call_params)

        params = self.parse_params.get_parameters()
        assert params[0][0] == '"'
        params_empty = (params == ['""'])
        params[0] = '(char *) ' + params[0]
        keywords = self.parse_params.get_keywords()
        if not params_empty or self.force_parse != None:
            self.meth_flags.append("METH_VARARGS")
            if keywords is None \
                    and self.force_parse != self.PARSE_TUPLE_AND_KEYWORDS:

                param_list = ['args'] + params
                self.before_parse.write_error_check('!PyArg_ParseTuple(%s)' %
                                                    (', '.join(param_list),))
            else:
                if keywords is None:
                    keywords = []
                keywords_var = self.declarations.declare_variable(
                    'const char *', 'keywords',
                    '{' + ', '.join(['"%s"' % kw for kw in keywords] + ['NULL']) + '}',
                     '[]')
                param_list = ['args', 'kwargs', params[0], '(char **) ' + keywords_var] + params[1:]
                self.before_parse.write_error_check('!PyArg_ParseTupleAndKeywords(%s)' %
                                                    (', '.join(param_list),))
                self.meth_flags.append("METH_KEYWORDS")
        else:
            self.meth_flags.append("METH_NOARGS")
        
        ## convert the return value(s)
        if self.return_value is None and not self.HAVE_RETURN_VALUE:

            assert self.build_params.get_parameters() == ['""'], \
                   "this wrapper is not supposed to return values"
            self._before_return_hook()
            self.after_call.write_cleanup()

        else:

            if self.return_value is not None:
                try:
                    self.return_value.convert_c_to_python(self)
                except NotImplementedError:
                    raise CodeGenerationError(
                        'convert_c_to_python method of return value %s not implemented'
                        % (self.return_value.ctype,))

            self._before_return_hook()

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

        ## now write out the wrapper function body itself
        self.declarations.get_code_sink().flush_to(code_sink)
        code_sink.writeln()
        self.before_parse.sink.flush_to(code_sink)
        self.before_call.sink.flush_to(code_sink)
        self.after_call.sink.flush_to(code_sink)

    def get_py_method_def_flags(self):
        """
        Get a list of PyMethodDef flags that should be used for this wrapper.
        """
        flags = set(self.meth_flags)
        if flags:
            return list(flags)

        tmp_sink = codesink.NullCodeSink()
        try:
#             try:
#                 self.generate_body(tmp_sink)
#             except CodegenErrorBase:
#                 return []
#             else:
#                 return list(set(self.meth_flags))
            self.generate_body(tmp_sink)
            return list(set(self.meth_flags))
        finally:
            self.reset_code_generation_state()


class TypeTransformation(object):
    """
    Type transformations are used to register handling of special
    types that are simple transformation over another type that is
    already registered.  This way, only the original type is
    registered, and the type transformation only does the necessary
    adjustments over the original type handler to make it handle the
    transformed type as well.

    This is typically used to get smart pointer templated types
    working.

    """

    def get_untransformed_name(self, name):
        """
        Given a transformed named, get the original C type name.
        E.g., given a smart pointer transformation, MySmartPointer::

          get_untransformed_name('MySmartPointer<Foo>') -> 'Foo\\*'
        """
        raise NotImplementedError

    def create_type_handler(self, type_handler_class, *args, **kwargs):
        """
        Given a type_handler class, create an instance with proper customization.

        :param type_handler_class: type handler class
        :param args: arguments
        :param kwargs: keywords arguments
        """
        raise NotImplementedError

    def transform(self, type_handler, declarations, code_block, value):
        """
        Transforms a value expression of the original type to an
        equivalent value expression in the transformed type.

        Example, with the transformation::
           'T\\*' -> 'boost::shared_ptr<T>'
        Then::
           transform(wrapper, 'foo') -> 'boost::shared_ptr<%s>(foo)' % type_handler.untransformed_ctype
        """
        raise NotImplementedError

    def untransform(self, type_handler, declarations, code_block, value):
        """
        Transforms a value expression of the transformed type to an
        equivalent value expression in the original type.

        Example, with the transformation::
          'T\\*' -> 'boost::shared_ptr<T>'
        Then::
           untransform(wrapper, 'foo') -> 'foo->get_pointer()'
        """
        raise NotImplementedError


class NullTypeTransformation(object):
    """
    Null type transformation, returns everything unchanged.
    """
    def get_untransformed_name(self, name):
        "identity transformation"
        return name
    def create_type_handler(self, type_handler_class, *args, **kwargs):
        "identity transformation"
        return type_handler_class(*args, **kwargs)
    def transform(self, type_handler, declarations, code_block, value):
        "identity transformation"
        return value
    def untransform(self, type_handler, declarations, code_block, value):
        "identity transformation"
        return value

class TypeHandler(object):
    SUPPORTS_TRANSFORMATIONS = False

    def __init__(self, ctype, is_const=False):
        if ctype is None:
            self.ctype = None
            self.untransformed_ctype = None
            self.type_traits = None
        else:
            if isinstance(ctype, ctypeparser.TypeTraits):
                self.type_traits = ctype
                if is_const:
                    warnings.warn("is_const is deprecated, put a 'const' in the C type instead.", DeprecationWarning)
                    if self.type_traits.type_is_pointer or self.type_traits.type_is_reference:
                        self.type_traits.make_target_const()
                    else:
                        self.type_traits.make_const()
            elif isinstance(ctype, basestring):
                if is_const:
                    warnings.warn("is_const is deprecated, put a 'const' in the C type instead.", DeprecationWarning)
                    self.type_traits = ctypeparser.TypeTraits('const %s' % ctype)
                else:
                    self.type_traits = ctypeparser.TypeTraits(ctype)
            else:
                raise TypeError
            self.ctype = str(self.type_traits.ctype)
        self.untransformed_ctype = self.ctype
        self.transformation = NullTypeTransformation()

    def _get_ctype_no_const(self):
        return str(self.type_traits.ctype_no_const)
    ctype_no_const = property(_get_ctype_no_const)

    def set_tranformation(self, transformation, untransformed_ctype):
        warnings.warn("Typo: set_tranformation -> set_transformation", DeprecationWarning, stacklevel=2)
        return self.set_transformation(transformation, untransformed_ctype)

    def set_transformation(self, transformation, untransformed_ctype):
        "Set the type transformation to use in this type handler"

        assert isinstance(transformation, TypeTransformation)
        assert untransformed_ctype != self.ctype
        assert isinstance(self.transformation, NullTypeTransformation)
        assert self.SUPPORTS_TRANSFORMATIONS

        self.transformation = transformation
        self.untransformed_ctype = untransformed_ctype


class ReturnValue(TypeHandler):
    '''Abstract base class for all classes dedicated to handle
    specific return value types'''

    ## list of C type names it can handle
    CTYPES = []

    ## whether it supports type transformations
    SUPPORTS_TRANSFORMATIONS = False
    
    REQUIRES_ASSIGNMENT_CONSTRUCTOR = False

    class __metaclass__(type):
        "Metaclass for automatically registering parameter type handlers"
        def __init__(mcs, name, bases, dict_):
            "metaclass __init__"
            type.__init__(mcs, name, bases, dict_)
            if __debug__:
                try:
                    iter(mcs.CTYPES)
                except TypeError:
                    print "ERROR: missing CTYPES on class ", mcs
            for ctype in mcs.CTYPES:
                return_type_matcher.register(ctype, mcs)

    #@classmethod
    def new(cls, *args, **kwargs):
        """
        >>> import inttype
        >>> isinstance(ReturnValue.new('int'), inttype.IntReturn)
        True
        """
        if cls is ReturnValue:
            ctype = args[0]
            type_handler_class, transformation, type_traits = \
                return_type_matcher.lookup(ctype)
            assert type_handler_class is not None
            if transformation is None:
                args = list(args)
                args[0] = type_traits
                args = tuple(args)
                try:
                    return type_handler_class(*args, **kwargs)
                except TypeError, ex:
                    warnings.warn("Exception %r in type handler %s constructor" % (str(ex), type_handler_class))
                    raise
            else:
                return transformation.create_type_handler(type_handler_class, *args, **kwargs)
        else:
            return cls(*args, **kwargs)

    new = classmethod(new)

    def __init__(self, ctype, is_const=False):
        '''
        Creates a return value object

        Keywork Arguments:

        :param ctype: actual C/C++ type being used
        '''
        if type(self) is ReturnValue:
            raise TypeError('ReturnValue is an abstract class; use ReturnValue.new(...)')
        super(ReturnValue, self).__init__(ctype, is_const)
        self.value = 'retval'

    def get_c_error_return(self):
        '''Return a "return <value>" code string, for use in case of error'''
        raise NotImplementedError

    def convert_python_to_c(self, wrapper):
        '''
        Writes code to convert the Python return value into the C "retval" variable.
        '''
        raise NotImplementedError
        #assert isinstance(wrapper, ReverseWrapperBase)

    def convert_c_to_python(self, wrapper):
        '''
        Writes code to convert the C return value the Python return.
        '''
        raise NotImplementedError
        #assert isinstance(wrapper, ReverseWrapperBase)

ReturnValue.CTYPES = NotImplemented

class PointerReturnValue(ReturnValue):
    """Base class for all pointer-to-something handlers"""
    CTYPES = []
    def __init__(self, ctype, is_const=False, caller_owns_return=None):
        super(PointerReturnValue, self).__init__(ctype, is_const)
        self.call_owns_return = caller_owns_return

PointerReturnValue.CTYPES = NotImplemented


class Parameter(TypeHandler):
    '''Abstract base class for all classes dedicated to handle specific parameter types'''

    ## bit mask values
    DIRECTION_IN = 1
    DIRECTION_OUT = 2
    DIRECTION_INOUT = DIRECTION_IN|DIRECTION_OUT

    ## list of possible directions for this type
    DIRECTIONS = NotImplemented
    ## whether it supports type transformations
    SUPPORTS_TRANSFORMATIONS = False
    ## list of C type names it can handle
    CTYPES = []

    def _direction_value_to_name(cls, value):
        if value == cls.DIRECTION_IN:
            return "DIRECTION_IN"
        elif value == cls.DIRECTION_OUT:
            return "DIRECTION_OUT"
        elif value == cls.DIRECTION_INOUT:
            return "DIRECTION_INOUT"
        else:
            return "(invalid %r)" % value
    _direction_value_to_name = classmethod(_direction_value_to_name)

    class __metaclass__(type):
        "Metaclass for automatically registering parameter type handlers"
        def __init__(mcs, name, bases, dict_):
            "metaclass __init__"
            type.__init__(mcs, name, bases, dict_)
            if __debug__:
                try:
                    iter(mcs.CTYPES)
                except TypeError:
                    print "ERROR: missing CTYPES on class ", mcs
            for ctype in mcs.CTYPES:
                param_type_matcher.register(ctype, mcs)

    #@classmethod
    def new(cls, *args, **kwargs):
        """
        >>> import inttype
        >>> isinstance(Parameter.new('int', 'name'), inttype.IntParam)
        True
        """
        if cls is Parameter:
            # support calling Parameter("typename", ...)
            ctype = args[0]
            type_handler_class, transformation, type_traits = \
                param_type_matcher.lookup(ctype)
            assert type_handler_class is not None
            if transformation is None:
                args = list(args)
                args[0] = type_traits
                args = tuple(args)
                try:
                    return type_handler_class(*args, **kwargs)
                except TypeError, ex:
                    warnings.warn("Exception %r in type handler %s constructor" % (str(ex), type_handler_class))
                    raise
            else:
                return transformation.create_type_handler(type_handler_class, *args, **kwargs)
        else:
            return cls(*args, **kwargs)

    new = classmethod(new)

    def __init__(self, ctype, name, direction=DIRECTION_IN, is_const=False, default_value=None):
        '''
        Creates a parameter object

        :param ctype: actual C/C++ type being used
        :param name: parameter name
        :param direction: direction of the parameter transfer, valid values
                     are DIRECTION_IN, DIRECTION_OUT, and
                     DIRECTION_IN|DIRECTION_OUT
        '''
        if type(self) is Parameter:
            raise TypeError('Parameter is an abstract class; use Parameter.new(...)')
        super(Parameter, self).__init__(ctype, is_const)
        self.name = name
        assert direction in self.DIRECTIONS, \
            "Error: requested direction %s for type handler %r (ctype=%r), but it only supports directions %r"\
            % (self._direction_value_to_name(direction), type(self), self.ctype,
               [self._direction_value_to_name(d) for d in self.DIRECTIONS])
        self.direction = direction
        self.value = name
        self.default_value = default_value

    def convert_c_to_python(self, wrapper):
        '''Write some code before calling the Python method.'''
        #assert isinstance(wrapper, ReverseWrapperBase)
        raise NotImplementedError

    def convert_python_to_c(self, wrapper):
        '''Write some code before calling the C method.'''
        #assert isinstance(wrapper, ReverseWrapperBase)
        raise NotImplementedError

Parameter.CTYPES = NotImplemented

class PointerParameter(Parameter):
    """Base class for all pointer-to-something handlers"""

    CTYPES = []

    def __init__(self, ctype, name, direction=Parameter.DIRECTION_IN, is_const=False, default_value=None,
                 transfer_ownership=False):
        super(PointerParameter, self).__init__(ctype, name, direction, is_const, default_value)
        self.transfer_ownership = transfer_ownership

PointerParameter.CTYPES = NotImplemented


class TypeMatcher(object):
    """
    Type matcher object: maps C type names to classes that handle
    those types.
    """
    
    def __init__(self):
        """Constructor"""
        self._types = {}
        self._transformations = []
        self._type_aliases = {}
        self._type_aliases_rev = {}


    def register_transformation(self, transformation):
        "Register a type transformation object"
        assert isinstance(transformation, TypeTransformation)
        self._transformations.append(transformation)

    def register(self, name, type_handler):
        """Register a new handler class for a given C type

        :param name: C type name

        :param type_handler: class to handle this C type
        """
        name = ctypeparser.normalize_type_string(name)
        if name in self._types:
            raise ValueError("return type %s already registered" % (name,))
        self._types[name] = type_handler

    def _raw_lookup_with_alias_support(self, name):
        already_tried = []
        return self._raw_lookup_with_alias_support_recursive(name, already_tried)

    def _raw_lookup_with_alias_support_recursive(self, name, already_tried):
        try:
            return self._types[name]
        except KeyError:
            aliases_to_try = []
            try:
                aliases_to_try.append(self._type_aliases[name])
            except KeyError:
                pass
            try:
                aliases_to_try.append(self._type_aliases_rev[name])
            except KeyError:
                pass
            for alias in aliases_to_try:
                if alias in already_tried:
                    continue
                already_tried.append(name)
                #if 'Time' in name or 'Time' in alias:
                #    import sys
                #    print >> sys.stderr, "**** trying name %r in place of %r" % (alias, name)
                return self._raw_lookup_with_alias_support_recursive(alias, already_tried)
            raise KeyError
        
    def lookup(self, name):
        """
        lookup(name) -> type_handler, type_transformation, type_traits

        :param name: C type name, possibly transformed (e.g. MySmartPointer<Foo> looks up Foo*)
        :returns: a handler with the given ctype name, or raises KeyError.

        Supports type transformations.

        """
        logger.debug("TypeMatcher.lookup(%r)", name)
        given_type_traits = ctypeparser.TypeTraits(name)
        noconst_name = str(given_type_traits.ctype_no_modifiers)
        tried_names = [noconst_name]
        try:
            rv = self._raw_lookup_with_alias_support(noconst_name), None, given_type_traits
        except KeyError:
            logger.debug("try to lookup type handler for %r => failure", name)
            ## Now try all the type transformations
            for transf in self._transformations:
                untransformed_name = transf.get_untransformed_name(name)
                if untransformed_name is None:
                    continue
                untransformed_type_traits = ctypeparser.TypeTraits(untransformed_name)
                untransformed_name = str(untransformed_type_traits.ctype_no_modifiers)
                try:
                    rv = self._raw_lookup_with_alias_support(untransformed_name), transf, untransformed_type_traits
                except KeyError:
                    logger.debug("try to lookup type handler for %r => failure (%r)", untransformed_name)
                    tried_names.append(untransformed_name)
                    continue
                else:
                    logger.debug("try to lookup type handler for %r => success (%r)", untransformed_name, rv)
                    return rv
            else:
                #if 'Time' in name:
                #    existing = [k for k in self._types.iterkeys() if 'Time' in k]
                #    existing.sort()
                #    raise TypeLookupError((tried_names, existing, self._type_aliases))
                #else:
                raise TypeLookupError(tried_names)
        else:
            logger.debug("try to lookup type handler for %r => success (%r)", name, rv)
            return rv
    
    def items(self):
        "Returns an iterator over all registered items"
        return self._types.iteritems()

    def add_type_alias(self, from_type_name, to_type_name):
        from_type_name_normalized = str(ctypeparser.TypeTraits(from_type_name).ctype)
        to_type_name_normalized = str(ctypeparser.TypeTraits(to_type_name).ctype)
        self._type_aliases[to_type_name_normalized] = from_type_name_normalized
        self._type_aliases_rev[from_type_name_normalized] = to_type_name_normalized

return_type_matcher = TypeMatcher()
param_type_matcher = TypeMatcher()

def add_type_alias(from_type_name, to_type_name):
    return_type_matcher.add_type_alias(from_type_name, to_type_name)
    param_type_matcher.add_type_alias(from_type_name, to_type_name)

