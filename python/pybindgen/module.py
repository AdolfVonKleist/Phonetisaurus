"""
Objects that represent -- and generate code for -- C/C++ Python extension modules.

Modules and Sub-modules
=======================

A L{Module} object takes care of generating the code for a Python
module.  The way a Python module is organized is as follows.  There is
one "root" L{Module} object. There can be any number of
L{SubModule}s. Sub-modules themselves can have additional sub-modules.
Calling L{Module.generate} on the root module will trigger code
generation for the whole module, not only functions and types, but
also all its sub-modules.

In Python, a sub-module will appear as a I{built-in} Python module
that is available as an attribute of its parent module.  For instance,
a module I{foo} having a sub-module I{xpto} appears like this::

    |>>> import foo
    |>>> foo.xpto
    |<module 'foo.xpto' (built-in)>

Modules and C++ namespaces
==========================

Modules can be associated with specific C++ namespaces.  This means,
for instance, that any C++ class wrapped inside that module must
belong to that C++ namespace.  Example::

    |>>> from cppclass import *
    |>>> mod = Module("foo", cpp_namespace="::foo")
    |>>> mod.add_class("Bar")
    |<pybindgen.CppClass 'foo::Bar'>

When we have a toplevel C++ namespace which contains another nested
namespace, we want to wrap the nested namespace as a Python
sub-module.  The method L{ModuleBase.add_cpp_namespace} makes it easy
to create sub-modules for wrapping nested namespaces.  For instance::

    |>>> from cppclass import *
    |>>> mod = Module("foo", cpp_namespace="::foo")
    |>>> submod = mod.add_cpp_namespace('xpto')
    |>>> submod.add_class("Bar")
    |<pybindgen.CppClass 'foo::xpto::Bar'>

"""

from function import Function, OverloadedFunction, CustomFunctionWrapper
from typehandlers.base import CodeBlock, DeclarationsScope, ReturnValue, TypeHandler
from typehandlers.codesink import MemoryCodeSink, CodeSink, FileCodeSink, NullCodeSink
from cppclass import CppClass
from cppexception import CppException
from enum import Enum
from container import Container
from converter_functions import PythonToCConverter, CToPythonConverter
import utils
import warnings
import traceback


class MultiSectionFactory(object):
    """
    Abstract base class for objects providing support for
    multi-section code generation, i.e., splitting the generated C/C++
    code into multiple files.  The generated code will generally have
    the following structure:

       1. For each section there is one source file specific to that section;

       2. There is a I{main} source file, e.g. C{foomodule.cc}.  Code
       that does not belong to any section will be included in this
       main file;

       3. Finally, there is a common header file, (e.g. foomodule.h),
       which is included by the main file and section files alike.
       Typically this header file contains function prototypes and
       type definitions.

    @see: L{Module.generate}

    """
    def get_section_code_sink(self, section_name):
        """
        Create and/or return a code sink for a given section.

        :param section_name: name of the section
        :return: a L{CodeSink} object that will receive generated code belonging to the section C{section_name}
        """
        raise NotImplementedError
    def get_main_code_sink(self):
        """
        Create and/or return a code sink for the main file.
        """
        raise NotImplementedError
    def get_common_header_code_sink(self):
        """
        Create and/or return a code sink for the common header.
        """
        raise NotImplementedError
    def get_common_header_include(self):
        """
        Return the argument for an #include directive to include the common header.

        :returns: a string with the header name, including surrounding
        "" or <>.  For example, '"foomodule.h"'.
        """
        raise NotImplementedError


class _SinkManager(object):
    """
    Internal abstract base class for bridging differences between
    multi-file and single-file code generation.
    """
    def get_code_sink_for_wrapper(self, wrapper):
        """
        :param wrapper: wrapper object
        :returns: (body_code_sink, header_code_sink) 
        """
        raise NotImplementedError
    def get_includes_code_sink(self):
        raise NotImplementedError
    def get_main_code_sink(self):
        raise NotImplementedError
    def close(self):
        raise NotImplementedError

class _MultiSectionSinkManager(_SinkManager):
    """
    Sink manager that deals with multi-section code generation.
    """
    def __init__(self, multi_section_factory):
        super(_MultiSectionSinkManager, self).__init__()
        self.multi_section_factory = multi_section_factory
        utils.write_preamble(self.multi_section_factory.get_common_header_code_sink())
        self.multi_section_factory.get_main_code_sink().writeln(
            "#include %s" % self.multi_section_factory.get_common_header_include())
        self._already_initialized_sections = {}
        self._already_initialized_sections['__main__'] = True

    def get_code_sink_for_wrapper(self, wrapper):
        header_sink = self.multi_section_factory.get_common_header_code_sink()
        section = getattr(wrapper, "section", None)
        if section is None:
            return self.multi_section_factory.get_main_code_sink(), header_sink
        else:
            section_sink = self.multi_section_factory.get_section_code_sink(section)
            if section not in self._already_initialized_sections:
                self._already_initialized_sections[section] = True
                section_sink.writeln("#include %s" % self.multi_section_factory.get_common_header_include())
            return section_sink, header_sink
    def get_includes_code_sink(self):
        return self.multi_section_factory.get_common_header_code_sink()
    def get_main_code_sink(self):
        return self.multi_section_factory.get_main_code_sink()
    def close(self):
        pass

class _MonolithicSinkManager(_SinkManager):
    """
    Sink manager that deals with single-section monolithic code generation.
    """
    def __init__(self, code_sink):
        super(_MonolithicSinkManager, self).__init__()
        self.final_code_sink = code_sink
        self.null_sink = NullCodeSink()
        self.includes = MemoryCodeSink()
        self.code_sink = MemoryCodeSink()

        utils.write_preamble(code_sink)
    def get_code_sink_for_wrapper(self, dummy_wrapper):
        return self.code_sink, self.code_sink
    def get_includes_code_sink(self):
        return self.includes
    def get_main_code_sink(self):
        return self.code_sink
    def close(self):
        self.includes.flush_to(self.final_code_sink)
        self.code_sink.flush_to(self.final_code_sink)


class ModuleBase(dict):
    """
    ModuleBase objects can be indexed dictionary style to access contained types.  Example::

      >>> from enum import Enum
      >>> from cppclass import CppClass
      >>> m = Module("foo", cpp_namespace="foo")
      >>> subm = m.add_cpp_namespace("subm")
      >>> c1 = m.add_class("Bar")
      >>> c2 = subm.add_class("Zbr")
      >>> e1 = m.add_enum("En1", ["XX"])
      >>> e2 = subm.add_enum("En2", ["XX"])
      >>> m["Bar"] is c1
      True
      >>> m["foo::Bar"] is c1
      True
      >>> m["En1"] is e1
      True
      >>> m["foo::En1"] is e1
      True
      >>> m["badname"]
      Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
      KeyError: 'badname'
      >>> m["foo::subm::Zbr"] is c2
      True
      >>> m["foo::subm::En2"] is e2
      True

    """

    def __init__(self, name, parent=None, docstring=None, cpp_namespace=None):
        """
        Note: this is an abstract base class, see L{Module}

        :param name: module name
        :param parent: parent L{module<Module>} (i.e. the one that contains this submodule) or None if this is a root module
        :param docstring: docstring to use for this module
        :param cpp_namespace: C++ namespace prefix associated with this module
        :return: a new module object
        """
        super(ModuleBase, self).__init__()
        self.parent = parent
        self.docstring = docstring
        self.submodules = []
        self.enums = []
        self.typedefs = [] # list of (wrapper, alias) tuples
        self._forward_declarations_declared = False

        self.cpp_namespace = cpp_namespace
        if self.parent is None:
            error_return = 'return;'
            self.after_forward_declarations = MemoryCodeSink()
        else:
            self.after_forward_declarations = None
            self.parent.submodules.append(self)
            error_return = 'return NULL;'

        self.prefix = None
        self.init_function_name = None
        self._name = None
        self.name = name

        path = self.get_namespace_path()
        if path and path[0] == '::':
            del path[0]
        self.cpp_namespace_prefix = '::'.join(path)

        self.declarations = DeclarationsScope()
        self.functions = {} # name => OverloadedFunction
        self.classes = []
        self.containers = []
        self.exceptions = []
        self.before_init = CodeBlock(error_return, self.declarations)
        self.after_init = CodeBlock(error_return, self.declarations,
                                    predecessor=self.before_init)
        self.c_function_name_transformer = None
        self.set_strip_prefix(name + '_')
        if parent is None:
            self.header = MemoryCodeSink()
            self.body = MemoryCodeSink()
            self.one_time_definitions = {}
            self.includes = []
        else:
            self.header = parent.header
            self.body = parent.body
            self.one_time_definitions = parent.one_time_definitions
            self.includes = parent.includes

        self._current_section = '__main__'

    def get_current_section(self):
        return self.get_root()._current_section
    current_section = property(get_current_section)

    def begin_section(self, section_name):
        """
        Declare that types and functions registered with the module in
        the future belong to the section given by that section_name
        parameter, until a matching end_section() is called.

        .. note::

          :meth:`begin_section`/:meth:`end_section` are silently ignored
          unless a :class:`MultiSectionFactory` object is used as code
          generation output.
        """
        if self.current_section != '__main__':
            raise ValueError("begin_section called while current section not ended")
        if section_name == '__main__':
            raise ValueError ("__main__ not allowed as section name")
        assert self.parent is None
        self._current_section = section_name
        
    def end_section(self, section_name):
        """
        Declare the end of a section, i.e. further types and functions
        will belong to the main module.

        :param section_name: name of section; must match the one in
           the previous :meth:`begin_section` call.
        """
        assert self.parent is None
        if self._current_section != section_name:
            raise ValueError("end_section called for wrong section: expected %r, got %r"
                             % (self._current_section, section_name))
        self._current_section = '__main__'

    def get_name(self):
        return self._name

    def set_name(self, name):
        self._name = name

        if self.parent is None:
            self.prefix = self.name.replace('.', '_')
            self.init_function_name = "init%s" % (self.name.split('.')[-1],)
        else:
            self.prefix = self.parent.prefix + "_" + self.name
            self.init_function_name = "init%s" % (self.prefix,)
    
    name = property(get_name, set_name)

    def get_submodule(self, submodule_name):
        "get a submodule by its name"
        for submodule in self.submodules:
            if submodule.name == submodule_name:
                return submodule
        raise ValueError("submodule %s not found" % submodule_name)
        
    def get_root(self):
        ":return: the root :class:`Module` (even if it is self)"
        root = self
        while root.parent is not None:
            root = root.parent
        return root

    def set_strip_prefix(self, prefix):
        """Sets the prefix string to be used when transforming a C
        function name into the python function name; the given prefix
        string is removed from the C function name."""

        def strip_prefix(c_name):
            """A C funtion name transformer that simply strips a
            common prefix from the name"""
            if c_name.startswith(prefix):
                return c_name[len(prefix):]
            else:
                return c_name
        self.c_function_name_transformer = strip_prefix

    def set_c_function_name_transformer(self, transformer):
        """Sets the function to be used when transforming a C function
        name into the python function name; the given given function
        is called like this::

          python_name = transformer(c_name)
        """
        self.c_function_name_transformer = transformer

    def add_include(self, include):
        """
        Adds an additional include directive, needed to compile this python module

        :param include: the name of the header file to include, including
                   surrounding "" or <>.
        """
        include = utils.ascii(include)
        assert include.startswith('"') or include.startswith('<')
        assert include.endswith('"') or include.endswith('>')
        if include not in self.includes:
            self.includes.append(include)

    def _add_function_obj(self, wrapper):
        assert isinstance(wrapper, Function)
        name = utils.ascii(wrapper.custom_name)
        if name is None:
            name = self.c_function_name_transformer(wrapper.function_name)
            name = utils.get_mangled_name(name, wrapper.template_parameters)
        try:
            overload = self.functions[name]
        except KeyError:
            overload = OverloadedFunction(name)
            self.functions[name] = overload
        wrapper.module = self
        wrapper.section = self.current_section
        overload.add(wrapper)

    def add_function(self, *args, **kwargs):
        """
        Add a function to the module/namespace. See the documentation for
        :meth:`Function.__init__` for information on accepted parameters.
        """
        if len(args) >= 1 and isinstance(args[0], Function):
            func = args[0]
            warnings.warn("add_function has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
            if len(args) == 2:
                func.custom_name = args[1]
            elif 'name' in kwargs:
                assert len(args) == 1
                func.custom_name = kwargs['name']
            else:
                assert len(args) == 1
                assert len(kwargs) == 0
        else:
            try:
                func = Function(*args, **kwargs)
            except utils.SkipWrapper:
                return None
        self._add_function_obj(func)
        return func

    def add_custom_function_wrapper(self, *args, **kwargs):
        """
        Add a function, using custom wrapper code, to the module/namespace. See the documentation for
        :class:`pybindgen.function.CustomFunctionWrapper` for information on accepted parameters.
        """
        try:
            func = CustomFunctionWrapper(*args, **kwargs)
        except utils.SkipWrapper:
            return None
        self._add_function_obj(func)
        return func

    def register_type(self, name, full_name, type_wrapper):
        """
        Register a type wrapper with the module, for easy access in
        the future.  Normally should not be called by the programmer,
        as it is meant for internal pybindgen use and called automatically.
        
        :param name: type name without any C++ namespace prefix, or None
        :param full_name: type name with a C++ namespace prefix, or None
        :param type_wrapper: the wrapper object for the type (e.g. L{CppClass} or L{Enum})
        """
        module = self
        if name:
            module[name] = type_wrapper
        if full_name:
            while module is not None:
                module[full_name] = type_wrapper
                module = module.parent

    def _add_class_obj(self, class_):
        """
        Add a class to the module.

        :param class_: a CppClass object
        """
        assert isinstance(class_, CppClass)
        class_.module = self
        class_.section = self.current_section
        self.classes.append(class_)
        self.register_type(class_.name, class_.full_name, class_)

    def add_class(self, *args, **kwargs):
        """
        Add a class to the module. See the documentation for
        L{CppClass.__init__} for information on accepted parameters.
        """
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], CppClass):
            cls = args[0]
            warnings.warn("add_class has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
        else:
            cls = CppClass(*args, **kwargs)
        self._add_class_obj(cls)
        return cls

    def add_struct(self, *args, **kwargs):
        """
        Add a struct to the module.

        In addition to the parameters accepted by
        L{CppClass.__init__}, this method accepts the following
        keyword parameters:

          - no_constructor (bool): if True, the structure will not
            have a constructor by default (if omitted, it will be
            considered to have a trivial constructor).

          - no_copy (bool): if True, the structure will not
            have a copy constructor by default (if omitted, it will be
            considered to have a simple copy constructor).

        """

        try:
            no_constructor = kwargs['no_constructor']
        except KeyError:
            no_constructor = False
        else:
            del kwargs['no_constructor']

        try:
            no_copy = kwargs['no_copy']
        except KeyError:
            no_copy = False
        else:
            del kwargs['no_copy']
        
        struct = CppClass(*args, **kwargs)
        struct.stack_where_defined = traceback.extract_stack()
        self._add_class_obj(struct)
        if not no_constructor:
            struct.add_constructor([])
        if not no_copy:
            struct.add_copy_constructor()
        return struct


    def add_cpp_namespace(self, name):
        """
        Add a nested module namespace corresponding to a C++
        namespace.  If the requested namespace was already added, the
        existing module is returned instead of creating a new one.

        :param name: name of C++ namespace (just the last component,
        not full scoped name); this also becomes the name of the
        submodule.

        :return: a L{SubModule} object that maps to this namespace.
        """
        name = utils.ascii(name)
        try:
            return self.get_submodule(name)
        except ValueError:
            module = SubModule(name, parent=self, cpp_namespace=name)
            module.stack_where_defined = traceback.extract_stack()
            return module

    def _add_enum_obj(self, enum):
        """
        Add an enumeration.
        """
        assert isinstance(enum, Enum)
        self.enums.append(enum)
        enum.module = self
        enum.section = self.current_section
        self.register_type(enum.name, enum.full_name, enum)

    def add_enum(self, *args, **kwargs):
        """
        Add an enumeration to the module. See the documentation for
        L{Enum.__init__} for information on accepted parameters.
        """
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], Enum):
            enum = args[0]
            warnings.warn("add_enum has changed API; see the API documentation",
                          DeprecationWarning, stacklevel=2)
        else:
            enum = Enum(*args, **kwargs)
        enum.stack_where_defined = traceback.extract_stack()
        self._add_enum_obj(enum)
        return enum


    def _add_container_obj(self, container):
        """
        Add a container to the module.

        :param container: a L{Container} object
        """
        assert isinstance(container, Container)
        container.module = self
        container.section = self.current_section
        self.containers.append(container)
        self.register_type(container.name, container.full_name, container)

    def add_container(self, *args, **kwargs):
        """
        Add a container to the module. See the documentation for
        L{Container.__init__} for information on accepted parameters.
        """
        try:
            container = Container(*args, **kwargs)
        except utils.SkipWrapper:
            return None
        container.stack_where_defined = traceback.extract_stack()
        self._add_container_obj(container)
        return container

    def _add_exception_obj(self, exc):
        assert isinstance(exc, CppException)
        exc.module = self
        exc.section = self.current_section
        self.exceptions.append(exc)
        self.register_type(exc.name, exc.full_name, exc)

    def add_exception(self, *args, **kwargs):
        """
        Add a C++ exception to the module. See the documentation for
        L{CppException.__init__} for information on accepted parameters.
        """
        exc = CppException(*args, **kwargs)
        self._add_exception_obj(exc)
        return exc

    def declare_one_time_definition(self, definition_name):
        """
        Internal helper method for code geneneration to coordinate
        generation of code that can only be defined once per compilation unit

        (note: assuming here one-to-one mapping between 'module' and
        'compilation unit').

        :param definition_name: a string that uniquely identifies the code
        definition that will be added.  If the given definition was
        already declared KeyError is raised.
        
        >>> module = Module('foo')
        >>> module.declare_one_time_definition("zbr")
        >>> module.declare_one_time_definition("zbr")
        Traceback (most recent call last):
        ...
        KeyError: 'zbr'
        >>> module.declare_one_time_definition("bar")
        """
        definition_name = utils.ascii(definition_name)
        if definition_name in self.one_time_definitions:
            raise KeyError(definition_name)
        self.one_time_definitions[definition_name] = None

    def generate_forward_declarations(self, code_sink):
        """(internal) generate forward declarations for types"""
        assert not self._forward_declarations_declared
        if self.classes or self.containers or self.exceptions:
            code_sink.writeln('/* --- forward declarations --- */')
            code_sink.writeln()

        for class_ in [c for c in self.classes if c.import_from_module]:
            class_.generate_forward_declarations(code_sink, self)

        for class_ in [c for c in self.classes if not c.import_from_module]:
            class_.generate_forward_declarations(code_sink, self)

        for container in self.containers:
            container.generate_forward_declarations(code_sink, self)
        for exc in self.exceptions:
            exc.generate_forward_declarations(code_sink, self)
        ## recurse to submodules
        for submodule in self.submodules:
            submodule.generate_forward_declarations(code_sink)
        self._forward_declarations_declared = True

    def get_module_path(self):
        """Get the full [module, submodule, submodule,...] path """
        names = [self.name]
        parent = self.parent
        while parent is not None:
            names.insert(0, parent.name)
            parent = parent.parent
        return names

    def get_namespace_path(self):
        """Get the full [root_namespace, namespace, namespace,...] path (C++)"""
        if not self.cpp_namespace:
            names = []
        else:
            if self.cpp_namespace == '::':
                names = []
            else:
                names = self.cpp_namespace.split('::')
                if not names[0]:
                    del names[0]
        parent = self.parent
        while parent is not None:
            if parent.cpp_namespace and parent.cpp_namespace != '::':
                parent_names = parent.cpp_namespace.split('::')
                if not parent_names[0]:
                    del parent_names[0]
                names = parent_names + names
            parent = parent.parent
        return names

    def do_generate(self, out, module_file_base_name=None):
        """(internal) Generates the module."""
        assert isinstance(out, _SinkManager)

        if self.parent is None:
            ## generate the include directives (only the root module)

            forward_declarations_sink = MemoryCodeSink()

            if not self._forward_declarations_declared:
                self.generate_forward_declarations(forward_declarations_sink)
                self.after_forward_declarations.flush_to(forward_declarations_sink)

            if self.parent is None:
                for include in self.includes:
                    out.get_includes_code_sink().writeln("#include %s" % include)
                self.includes = None

            forward_declarations_sink.flush_to(out.get_includes_code_sink())

        else:
            assert module_file_base_name is None, "only root modules can generate with alternate module_file_base_name"

        ## generate the submodules
        for submodule in self.submodules:
            submodule.do_generate(out)

        m = self.declarations.declare_variable('PyObject*', 'm')
        assert m == 'm'
        if module_file_base_name is None:
            mod_init_name = '.'.join(self.get_module_path())
        else:
            mod_init_name = module_file_base_name
        self.before_init.write_code(
            "m = Py_InitModule3((char *) \"%s\", %s_functions, %s);"
            % (mod_init_name, self.prefix,
               self.docstring and '"'+self.docstring+'"' or 'NULL'))
        self.before_init.write_error_check("m == NULL")

        main_sink = out.get_main_code_sink()

        ## generate the function wrappers
        py_method_defs = []
        if self.functions:
            main_sink.writeln('/* --- module functions --- */')
            main_sink.writeln()
            for func_name, overload in self.functions.iteritems():
                sink, header_sink = out.get_code_sink_for_wrapper(overload)
                sink.writeln()
                try:
                    utils.call_with_error_handling(overload.generate, (sink,), {}, overload)
                except utils.SkipWrapper:
                    continue
                try:
                    utils.call_with_error_handling(overload.generate_declaration, (main_sink,), {}, overload)
                except utils.SkipWrapper:
                    continue
                
                sink.writeln()
                py_method_defs.append(overload.get_py_method_def(func_name))
                del sink

        ## generate the function table
        main_sink.writeln("static PyMethodDef %s_functions[] = {"
                          % (self.prefix,))
        main_sink.indent()
        for py_method_def in py_method_defs:
            main_sink.writeln(py_method_def)
        main_sink.writeln("{NULL, NULL, 0, NULL}")
        main_sink.unindent()
        main_sink.writeln("};")

        ## generate the classes
        if self.classes:
            main_sink.writeln('/* --- classes --- */')
            main_sink.writeln()
            for class_ in [c for c in self.classes if c.import_from_module]:
                sink, header_sink = out.get_code_sink_for_wrapper(class_)
                sink.writeln()
                class_.generate(sink, self)
                sink.writeln()
            for class_ in [c for c in self.classes if not c.import_from_module]:
                sink, header_sink = out.get_code_sink_for_wrapper(class_)
                sink.writeln()
                class_.generate(sink, self)
                sink.writeln()

        ## generate the containers
        if self.containers:
            main_sink.writeln('/* --- containers --- */')
            main_sink.writeln()
            for container in self.containers:
                sink, header_sink = out.get_code_sink_for_wrapper(container)
                sink.writeln()
                container.generate(sink, self)
                sink.writeln()

        ## generate the exceptions
        if self.exceptions:
            main_sink.writeln('/* --- exceptions --- */')
            main_sink.writeln()
            for exc in self.exceptions:
                sink, header_sink = out.get_code_sink_for_wrapper(exc)
                sink.writeln()
                exc.generate(sink, self)
                sink.writeln()

        # typedefs
        for (wrapper, alias) in self.typedefs:
            if isinstance(wrapper, CppClass):
                cls = wrapper
                cls.generate_typedef(self, alias)

        ## generate the enums
        if self.enums:
            main_sink.writeln('/* --- enumerations --- */')
            main_sink.writeln()
            for enum in self.enums:
                sink, header_sink = out.get_code_sink_for_wrapper(enum)
                sink.writeln()
                enum.generate(sink)
                enum.generate_declaration(header_sink, self)
                sink.writeln()

        ## register the submodules
        if self.submodules:
            submodule_var = self.declarations.declare_variable('PyObject*', 'submodule')
        for submodule in self.submodules:
            self.after_init.write_code('%s = %s();' % (
                    submodule_var, submodule.init_function_name))
            self.after_init.write_error_check('%s == NULL' % submodule_var)
            self.after_init.write_code('Py_INCREF(%s);' % (submodule_var,))
            self.after_init.write_code('PyModule_AddObject(m, (char *) "%s", %s);'
                                       % (submodule.name, submodule_var,))

        ## flush the header section
        self.header.flush_to(out.get_includes_code_sink())

        ## flush the body section
        self.body.flush_to(main_sink)

        ## now generate the module init function itself
        main_sink.writeln()
        if self.parent is None:
            main_sink.writeln('''
PyMODINIT_FUNC
#if defined(__GNUC__) && __GNUC__ >= 4
__attribute__ ((visibility("default")))
#endif''')
        else:
            main_sink.writeln("static PyObject *")
        if module_file_base_name is None:
            main_sink.writeln("%s(void)" % (self.init_function_name,))
        else:
            main_sink.writeln("init%s(void)" % (module_file_base_name,))
        main_sink.writeln('{')
        main_sink.indent()
        self.declarations.get_code_sink().flush_to(main_sink)
        self.before_init.sink.flush_to(main_sink)
        self.after_init.write_cleanup()
        self.after_init.sink.flush_to(main_sink)
        if self.parent is not None:
            main_sink.writeln("return m;")
        main_sink.unindent()
        main_sink.writeln('}')


    def __repr__(self):
        return "<pybindgen.module.Module %r>" % self.name

    def add_typedef(self, wrapper, alias):
        """
        Declares an equivalent to a typedef in C::
          typedef Foo Bar;

        :param wrapper: the wrapper object to alias (Foo in the example)
        :param alias: name of the typedef alias

        @note: only typedefs for CppClass objects have been
        implemented so far; others will be implemented in the future.
        """
        assert isinstance(wrapper, CppClass)
        alias = utils.ascii(alias)
        self.typedefs.append((wrapper, alias))
        self.register_type(alias, alias, wrapper)
        wrapper.register_alias(alias)
        full_name = '::'.join(self.get_namespace_path() + [alias])
        wrapper.register_alias(full_name)


class Module(ModuleBase):
    def __init__(self, name, docstring=None, cpp_namespace=None):
        """
        :param name: module name
        :param docstring: docstring to use for this module
        :param cpp_namespace: C++ namespace prefix associated with this module
        """
        super(Module, self).__init__(name, docstring=docstring, cpp_namespace=cpp_namespace)

    def generate(self, out, module_file_base_name=None):
        """Generates the module

        :type out: a file object, L{FileCodeSink}, or L{MultiSectionFactory}

        :param module_file_base_name: base name of the module file.
        This is useful when we want to produce a _foo module that will
        be imported into a foo module, to avoid making all types
        docstrings contain _foo.Xpto instead of foo.Xpto.
        """
        if isinstance(out, file):
            out = FileCodeSink(out)
        if isinstance(out, CodeSink):
            sink_manager = _MonolithicSinkManager(out)
        elif isinstance(out, MultiSectionFactory):
            sink_manager = _MultiSectionSinkManager(out)
        else:
            raise TypeError
        self.do_generate(sink_manager, module_file_base_name)
        sink_manager.close()

    def get_python_to_c_type_converter_function_name(self, value_type):
        """
        Internal API, do not use.
        """
        assert isinstance(value_type, TypeHandler)
        ctype = value_type.ctype
        mangled_ctype = utils.mangle_name(ctype)
        converter_function_name = "_wrap_convert_py2c__%s" % mangled_ctype
        return converter_function_name

    def generate_python_to_c_type_converter(self, value_type, code_sink):
        """
        Generates a python-to-c converter function for a given type
        and returns the name of the generated function.  If called
        multiple times with the same name only the first time is the
        converter function generated.
        
        Use: this method is to be considered pybindgen internal, used
        by code generation modules.

        :type value_type: L{ReturnValue}
        :type code_sink: L{CodeSink}
        :returns: name of the converter function
        """
        assert isinstance(value_type, TypeHandler)
        converter_function_name = self.get_python_to_c_type_converter_function_name(value_type)
        try:
            self.declare_one_time_definition(converter_function_name)
        except KeyError:
            return converter_function_name
        else:
            converter = PythonToCConverter(value_type, converter_function_name)
            self.header.writeln("\n%s;\n" % converter.get_prototype())
            code_sink.writeln()
            converter.generate(code_sink, converter_function_name)
            code_sink.writeln()
            return converter_function_name


    def get_c_to_python_type_converter_function_name(self, value_type):
        """
        Internal API, do not use.
        """
        assert isinstance(value_type, TypeHandler)
        ctype = value_type.ctype
        mangled_ctype = utils.mangle_name(ctype)
        converter_function_name = "_wrap_convert_c2py__%s" % mangled_ctype
        return converter_function_name

    def generate_c_to_python_type_converter(self, value_type, code_sink):
        """
        Generates a c-to-python converter function for a given type
        and returns the name of the generated function.  If called
        multiple times with the same name only the first time is the
        converter function generated.
        
        Use: this method is to be considered pybindgen internal, used
        by code generation modules.

        :type value_type: L{ReturnValue}
        :type code_sink: L{CodeSink}
        :returns: name of the converter function
        """
        assert isinstance(value_type, TypeHandler)
        converter_function_name = self.get_c_to_python_type_converter_function_name(value_type)
        try:
            self.declare_one_time_definition(converter_function_name)
        except KeyError:
            return converter_function_name
        else:
            converter = CToPythonConverter(value_type, converter_function_name)
            self.header.writeln("\n%s;\n" % converter.get_prototype())
            code_sink.writeln()
            converter.generate(code_sink)
            code_sink.writeln()
            return converter_function_name


class SubModule(ModuleBase):
    def __init__(self, name, parent, docstring=None, cpp_namespace=None):
        """
        :param parent: parent L{module<Module>} (i.e. the one that contains this submodule)
        :param name: name of the submodule
        :param docstring: docstring to use for this module
        :param cpp_namespace: C++ namespace component associated with this module
        """
        super(SubModule, self).__init__(name, parent, docstring=docstring, cpp_namespace=cpp_namespace)

