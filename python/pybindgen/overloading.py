"""
C wrapper wrapper
"""
from typehandlers.base import TypeConfigurationError, CodeGenerationError, NotSupportedError
from typehandlers.base import ForwardWrapperBase
from typehandlers.codesink import NullCodeSink
import utils
import settings
import traceback
import sys

try: 
    set 
except NameError: 
    from sets import Set as set   # Python 2.3 fallback 


def isiterable(obj): 
    """Returns True if an object appears to be iterable"""
    return hasattr(obj, '__iter__') or isinstance(obj, basestring)

def vector_counter(vec):
    """
    >>> list(vector_counter([[1,2], ['a', 'b'], ['x', 'y']]))
    [[1, 'a', 'x'], [1, 'a', 'y'], [1, 'b', 'x'], [1, 'b', 'y'], [2, 'a', 'x'], [2, 'a', 'y'], [2, 'b', 'x'], [2, 'b', 'y']]
    """
    iters = [iter(l) for l in vec]
    values = [it.next() for it in iters[:-1]] + [vec[-1][0]]
    while 1:
        for idx in xrange(len(iters)-1, -1, -1):
            try:
                values[idx] = iters[idx].next()
            except StopIteration:
                iters[idx] = iter(vec[idx])
                values[idx] = iters[idx].next()
            else:
                break
        else:
            raise StopIteration
        yield list(values)

class OverloadedWrapper(object):
    """
    An object that aggregates a set of wrapper objects; it generates
    a single python wrapper wrapper that supports overloading,
    i.e. tries to parse parameters according to each individual
    Function parameter list, and uses the first wrapper that doesn't
    generate parameter parsing error.
    """

    RETURN_TYPE = NotImplemented
    ERROR_RETURN = NotImplemented

    def __init__(self, wrapper_name):
        """
        wrapper_name -- C/C++ name of the wrapper
        """
        self.wrappers = []
        self.all_wrappers = None
        self.wrapper_name = wrapper_name
        self.wrapper_actual_name = None
        self.wrapper_return = None
        self.wrapper_args = None
        self.pystruct = 'PyObject'
        #self.static_decl = True ## FIXME: unused?
#         self.enable_implicit_conversions = True
        
    def add(self, wrapper):
        """
        Add a wrapper to the overloaded wrapper
        wrapper -- a Wrapper object
        """
        assert isinstance(wrapper, ForwardWrapperBase)
        self.wrappers.append(wrapper)
        return wrapper

    def _normalize_py_method_flags(self):
        """
        Checks that if all overloaded wrappers have similar method
        flags, forcing similar flags if needed (via method.force_parse
        = ForwardWrapperBase.PARSE_TUPLE_AND_KEYWORDS)
        """

        if len(self.wrappers) == 1:
            return

        for wrapper in self.wrappers:
            wrapper.force_parse = ForwardWrapperBase.PARSE_TUPLE_AND_KEYWORDS
        
        # loop that keeps removing wrappers until all remaining wrappers have the same flags
        modified = True
        while modified:
            existing_flags = None
            modified = False
            for wrapper in self.wrappers:
                try:
                    wrapper_flags = utils.call_with_error_handling(
                        wrapper.get_py_method_def_flags, args=(), kwargs={}, wrapper=wrapper)
                except utils.SkipWrapper, ex:
                    modified = True
                    self.wrappers.remove(wrapper)
                    dummy1, dummy2, tb = sys.exc_info()
                    settings.error_handler.handle_error(wrapper, ex, tb)
                    break

                wrapper_flags = set(wrapper_flags)
                if existing_flags is None:
                    existing_flags = wrapper_flags
                else:
                    if wrapper_flags != existing_flags:
                        modified = True
                        self.wrappers.remove(wrapper)
                        tb = traceback.extract_stack()
                        settings.error_handler.handle_error(wrapper, ex, tb)
                        break

    def _compute_all_wrappers(self):
        """
        Computes all the wrappers that should be generated; this
        includes not only the regular overloaded wrappers but also
        additional wrappers created in runtime to fulfil implicit
        conversion requirements.  The resulting list is stored as
        self.all_wrappers
        """
        self.all_wrappers = list(self.wrappers)

    def generate(self, code_sink):
        """
        Generate all the wrappers plus the 'aggregator' wrapper to a code sink.
        """
        self._normalize_py_method_flags()
        self._compute_all_wrappers()
        if len(self.all_wrappers) == 0:
            raise utils.SkipWrapper
        elif len(self.all_wrappers) == 1 \
                and not getattr(self.all_wrappers[0], 'NEEDS_OVERLOADING_INTERFACE', False):
            ## special case when there's only one wrapper; keep
            ## simple things simple

            #self.all_wrappers[0].generate(code_sink)
            prototype_line = utils.call_with_error_handling(self.all_wrappers[0].generate,
                                                            (code_sink,), {}, self.all_wrappers[0])

            self.wrapper_actual_name = self.all_wrappers[0].wrapper_actual_name
            assert self.wrapper_actual_name is not None
            self.wrapper_return = self.all_wrappers[0].wrapper_return
            self.wrapper_args = self.all_wrappers[0].wrapper_args
        else:
            ## multiple overloaded wrappers case..
            flags = self.all_wrappers[0].get_py_method_def_flags()

            ## Generate the individual "low level" wrappers that handle a single prototype
            self.wrapper_actual_name = self.all_wrappers[0].wrapper_base_name
            delegate_wrappers = []
            for number, wrapper in enumerate(self.all_wrappers):
                ## enforce uniform method flags
                wrapper.force_parse = wrapper.PARSE_TUPLE_AND_KEYWORDS
                ## an extra parameter 'return_exception' is used to
                ## return parse error exceptions to the 'main wrapper'
                error_return = """{
    PyObject *exc_type, *traceback;
    PyErr_Fetch(&exc_type, return_exception, &traceback);
    Py_XDECREF(exc_type);
    Py_XDECREF(traceback);
}
%s""" % (self.ERROR_RETURN,)
                wrapper_name = "%s__%i" % (self.wrapper_actual_name, number)
                wrapper.set_parse_error_return(error_return)
                code_sink.writeln()

                # wrapper.generate(code_sink, wrapper_name,
                #                  extra_wrapper_params=["PyObject **return_exception"])
                try:
                    utils.call_with_error_handling(
                        wrapper.generate, args=(code_sink, wrapper_name),
                        kwargs=dict(extra_wrapper_params=["PyObject **return_exception"]),
                        wrapper=wrapper)
                except utils.SkipWrapper:
                    continue

                delegate_wrappers.append(wrapper.wrapper_actual_name)

            ## if all wrappers did not generate, then the overload
            ## aggregator wrapper should not be generated either..
            if not delegate_wrappers:
                raise utils.SkipWrapper
            
            ## Generate the 'main wrapper' that calls the other ones
            code_sink.writeln()
            self.wrapper_return = self.RETURN_TYPE
            self.wrapper_args = ['%s *self' % self.pystruct]
            if 'METH_VARARGS' in flags:
                self.wrapper_args.append('PyObject *args')
            if 'METH_KEYWORDS' in flags:
                self.wrapper_args.append('PyObject *kwargs')
            prototype_line = "%s %s(%s)" % (self.wrapper_return, self.wrapper_actual_name, ', '.join(self.wrapper_args))
            code_sink.writeln(prototype_line)
            code_sink.writeln('{')
            code_sink.indent()
            code_sink.writeln(self.RETURN_TYPE + ' retval;')
            code_sink.writeln('PyObject *error_list;')
            code_sink.writeln('PyObject *exceptions[%i] = {0,};' % len(delegate_wrappers))
            for number, delegate_wrapper in enumerate(delegate_wrappers):
                ## call the delegate wrapper
                args = ['self']
                if 'METH_VARARGS' in flags:
                    args.append('args')
                if 'METH_KEYWORDS' in flags:
                    args.append('kwargs')
                args.append('&exceptions[%i]' % number)
                code_sink.writeln("retval = %s(%s);" % (delegate_wrapper, ', '.join(args)))
                ## if no parse exception, call was successful:
                ## free previous exceptions and return the result
                code_sink.writeln("if (!exceptions[%i]) {" % number)
                code_sink.indent()
                for i in xrange(number):
                    code_sink.writeln("Py_DECREF(exceptions[%i]);" % i)
                code_sink.writeln("return retval;")
                code_sink.unindent()
                code_sink.writeln("}")

            ## If the following generated code is reached it means
            ## that all of our delegate wrappers had parsing errors:
            ## raise an appropriate exception, free the previous
            ## exceptions, and return NULL
            code_sink.writeln('error_list = PyList_New(%i);' % len(delegate_wrappers))
            for i in xrange(len(delegate_wrappers)):
                code_sink.writeln(
                    'PyList_SET_ITEM(error_list, %i, PyObject_Str(exceptions[%i]));'
                    % (i, i))
                code_sink.writeln("Py_DECREF(exceptions[%i]);" % i)
            code_sink.writeln('PyErr_SetObject(PyExc_TypeError, error_list);')
            code_sink.writeln("Py_DECREF(error_list);")
            code_sink.writeln(self.ERROR_RETURN)
            code_sink.unindent()
            code_sink.writeln('}')
            
        return prototype_line
        
    def get_py_method_def(self, name):
        """
        Returns an array element to use in a PyMethodDef table.
        Should only be called after code generation.

        name -- python wrapper/method name
        """
        if len(self.all_wrappers) == 1 \
                and not getattr(self.all_wrappers[0], 'NEEDS_OVERLOADING_INTERFACE', False):
            return self.all_wrappers[0].get_py_method_def(name)
        else:
            self._normalize_py_method_flags()
            flags = self.all_wrappers[0].get_py_method_def_flags()
            ## detect inconsistencies in flags; they must all be the same
            if __debug__:
                for func in self.all_wrappers:
                    try:
                        assert set(func.get_py_method_def_flags()) == set(flags),\
                            ("Expected PyMethodDef flags %r, got %r"
                             % (flags, func.get_py_method_def_flags()))
                    except (TypeConfigurationError,
                            CodeGenerationError,
                            NotSupportedError):
                        pass
            docstring = None # FIXME

            assert isinstance(self.wrapper_return, basestring)
            assert isinstance(self.wrapper_actual_name, basestring)
            assert isinstance(self.wrapper_args, list)

            return "{(char *) \"%s\", (PyCFunction) %s, %s, %s }," % \
                (name, self.wrapper_actual_name, '|'.join(flags),
                 (docstring is None and "NULL" or ('"'+docstring+'"')))

    def generate_declaration(self, code_sink):
        self.reset_code_generation_state()
        self._compute_all_wrappers()
        self.generate(NullCodeSink())
        assert isinstance(self.wrapper_return, basestring)
        assert isinstance(self.wrapper_actual_name, basestring)
        assert isinstance(self.wrapper_args, list)
        code_sink.writeln("%s %s(%s);" % (self.wrapper_return, self.wrapper_actual_name, ', '.join(self.wrapper_args)))
        self.reset_code_generation_state()

    def generate_class_declaration(self, code_sink):
        self.reset_code_generation_state()
        self._compute_all_wrappers()
        self.generate(NullCodeSink())
        assert isinstance(self.wrapper_return, basestring)
        assert isinstance(self.wrapper_actual_name, basestring)
        assert isinstance(self.wrapper_args, list)
        name = self.wrapper_actual_name.split('::')[-1]
        code_sink.writeln("static %s %s(%s);" % (self.wrapper_return, name, ', '.join(self.wrapper_args)))

        if len(self.all_wrappers) > 1:
            for wrapper in self.all_wrappers:
                name = wrapper.wrapper_actual_name.split('::')[-1]
                code_sink.writeln("static %s %s(%s);" % (wrapper.wrapper_return, name, ', '.join(wrapper.wrapper_args)))

        self.reset_code_generation_state()

    def reset_code_generation_state(self):
        self._compute_all_wrappers()
        for wrapper in self.all_wrappers:
            wrapper.reset_code_generation_state()

    def get_section(self):
        section = None
        if self.all_wrappers is None:
            self._compute_all_wrappers()
        for wrapper in self.all_wrappers:
            if section is None:
                section = wrapper.section
        return section

    section = property(get_section)


from cppclass import CppClassParameter, CppClassRefParameter

