#!/usr/bin/python
# -*- coding: utf-8 -*-

DEBUG = False

import sys
import os.path
import warnings
import re
import pygccxml
from pygccxml import parser
from pygccxml import declarations
from module import Module
from typehandlers.codesink import FileCodeSink, CodeSink, NullCodeSink
import typehandlers.base
from typehandlers.base import ctypeparser
from typehandlers.base import ReturnValue, Parameter, TypeLookupError, TypeConfigurationError, NotSupportedError
from pygccxml.declarations.enumeration import enumeration_t
from cppclass import CppClass, ReferenceCountingMethodsPolicy, FreeFunctionPolicy, ReferenceCountingFunctionsPolicy
from cppexception import CppException
from pygccxml.declarations import type_traits
from pygccxml.declarations import cpptypes
from pygccxml.declarations import calldef
from pygccxml.declarations import templates
from pygccxml.declarations import container_traits
from pygccxml.declarations.declaration import declaration_t
from pygccxml.declarations.class_declaration import class_declaration_t, class_t
import settings
import utils

#from pygccxml.declarations.calldef import \
#    destructor_t, constructor_t, member_function_t
from pygccxml.declarations.variable import variable_t


###
### some patched pygccxml functions, from the type_traits module
###
def remove_pointer(type):
    """removes pointer from the type definition

    If type is not pointer type, it will be returned as is.
    """
    #nake_type = remove_alias( type )
    nake_type = type
    if not type_traits.is_pointer( nake_type ):
        return type
    elif isinstance( nake_type, cpptypes.volatile_t ) and isinstance( nake_type.base, cpptypes.pointer_t ):
        return cpptypes.volatile_t( nake_type.base.base )
    elif isinstance( nake_type, cpptypes.const_t ) and isinstance( nake_type.base, cpptypes.pointer_t ):
        return cpptypes.const_t( nake_type.base.base )
    elif isinstance(nake_type, cpptypes.compound_t) and isinstance( nake_type.base, cpptypes.calldef_type_t ):
        return type
    else:
        if isinstance(nake_type, cpptypes.compound_t):
            return nake_type.base
        else:
            return nake_type

def remove_reference(type):
    """removes reference from the type definition

    If type is not reference type, it will be returned as is.
    """
    #nake_type = remove_alias( type )
    nake_type = type
    if not type_traits.is_reference( nake_type ):
        return type
    else:
        if isinstance(nake_type, cpptypes.compound_t):
            return nake_type.base
        else:
            return nake_type

def remove_const(type):
    """removes const from the type definition

    If type is not const type, it will be returned as is
    """

    #nake_type = remove_alias( type )
    nake_type = type
    if not type_traits.is_const( nake_type ):
        return type
    else:
        if isinstance(nake_type, cpptypes.compound_t):
            return nake_type.base
        else:
            return nake_type
###
### end of patched pygccxml functions
###


## --- utility ---

import pygccxml.declarations.type_traits
def find_declaration_from_name(global_ns, declaration_name):
    decl = pygccxml.declarations.type_traits.impl_details.find_value_type(global_ns, declaration_name)
    return decl


class ModuleParserWarning(Warning):
    """
    Base class for all warnings reported here.
    """
class NotSupportedWarning(ModuleParserWarning):
    """
    Warning for pybindgen GccxmlParser, to report something pybindgen does not support.
    """
class WrapperWarning(ModuleParserWarning):
    """
    Warning for pybindgen GccxmlParser, to be used when a C++
    definition cannot be converted to a pybindgen wrapper.
    """
class AnnotationsWarning(ModuleParserWarning):
    """
    Warning for pybindgen GccxmlParser to report a problem in annotations.
    """

## ------------------------

class ErrorHandler(settings.ErrorHandler):
    def handle_error(self, wrapper, exception, traceback_):
        if hasattr(wrapper, "gccxml_definition"):
            definition = wrapper.gccxml_definition
        elif hasattr(wrapper, "main_wrapper"):
            try:
                definition = wrapper.main_wrapper.gccxml_definition
            except AttributeError:
                definition = None
        else:
            definition = None

        if definition is None:
            print >> sys.stderr, "exception %r in wrapper %s" % (exception, wrapper)
        else:
            warnings.warn_explicit("exception %r in wrapper for %s"
                                   % (exception, definition),
                                   WrapperWarning, definition.location.file_name,
                                   definition.location.line)
        return True
settings.error_handler = ErrorHandler()

def normalize_name(decl_string):
    return ctypeparser.normalize_type_string(decl_string)

def normalize_class_name(class_name, module_namespace):
    class_name = utils.ascii(class_name)
    if not class_name.startswith(module_namespace):
        class_name = module_namespace + class_name
    class_name = normalize_name(class_name)
    return class_name


def _pygen_kwargs(kwargs):
    l = []
    for key, val in kwargs.iteritems():
        if isinstance(val, (CppClass, CppException)):
            l.append("%s=root_module[%r]" % (key, utils.ascii(val.full_name)))
        else:
            if key == 'throw':
                l.append("throw=[%s]" % (', '.join(["root_module[%r]" % utils.ascii(t.full_name) for t in val])))
            elif key == 'parent' and isinstance(val, list):
                l.append("parent=[%s]" % (', '.join(["root_module[%r]" % utils.ascii(cls.full_name) for cls in val])))
            else:
                l.append("%s=%r" % (key, val))
    return l

def _pygen_args_kwargs(args, kwargs):
    return ", ".join([repr(arg) for arg in args] + _pygen_kwargs(kwargs))

def _pygen_args_kwargs_dict(args, kwargs):
    l = [repr(arg) for arg in args]
    if kwargs:
        l.append("dict(%s)" % ', '.join(_pygen_kwargs(kwargs)))
    return ", ".join(l)

def _pygen_retval(args, kwargs):
    if len(args) == 1 and len(kwargs) == 0:
        return repr(args[0])
    return "retval(%s)" % _pygen_args_kwargs(args, kwargs)

def _pygen_param(args, kwargs):
    return "param(%s)" % _pygen_args_kwargs(args, kwargs)


class GccXmlTypeRegistry(object):
    def __init__(self, root_module):
        """
        :param root_module: the root L{Module} object
        """
        assert isinstance(root_module, Module)
        assert root_module.parent is None
        self.root_module = root_module
        self.ordered_classes = [] # registered classes list, by registration order
        self._root_ns_rx = re.compile(r"(^|\s)(::)")
    
    def class_registered(self, cpp_class):
        assert isinstance(cpp_class, (CppClass, CppException))
        self.ordered_classes.append(cpp_class)

#     def get_type_traits(self, type_info):
#         #assert isinstance(type_info, cpptypes.type_t)

#         debug = False #('int64_t' in type_info.decl_string)
#         if debug:
#             print >> sys.stderr, "***** type traits for %r" % (type_info.decl_string, )

#         is_const = False
#         is_reference = False
#         is_pointer = 0
#         pointer_or_ref_count = 0
#         inner_const = False
#         while 1:
#             prev_type_info = type_info
#             if type_traits.is_pointer(type_info):
#                 is_pointer += 1
#                 type_info = remove_pointer(type_info)
#                 pointer_or_ref_count += 1
#             elif type_traits.is_const(type_info):
#                 type_info = remove_const(type_info)
#                 if pointer_or_ref_count == 0:
#                     is_const = True
#                 elif pointer_or_ref_count == 1:
#                     inner_const = True
#                 else:
#                     warnings.warn("multiple consts not handled")
#             elif type_traits.is_reference(type_info):
#                 warnings.warn("multiple &'s not handled")
#                 is_reference = True
#                 type_info = remove_reference(type_info)
#                 pointer_or_ref_count += 1
#             else:
#                 break
#             if type_info is prev_type_info:
#                 break

#         type_name = normalize_name(type_info.partial_decl_string)
#         try:
#             cpp_type = self.root_module[type_name]
#         except KeyError:
#             cpp_type = type_name

#         if not isinstance(cpp_type, CppClass):
#             cpp_type = type_name

#         if debug:
#             print >> sys.stderr, "*** > return ", repr((cpp_type, is_const, is_pointer, is_reference))
#         return (cpp_type, is_const, inner_const, is_pointer, is_reference)

    def _fixed_std_type_name(self, type_name):
        type_name = utils.ascii(type_name)
        decl = self._root_ns_rx.sub('', type_name)
        return decl
        
    def lookup_return(self, type_info, annotations={}):
        kwargs = {}
        for name, value in annotations.iteritems():
            if name == 'caller_owns_return':
                kwargs['caller_owns_return'] = annotations_scanner.parse_boolean(value)
            elif name == 'reference_existing_object':
                kwargs['reference_existing_object'] = annotations_scanner.parse_boolean(value)
            elif name == 'return_internal_reference':
                kwargs['return_internal_reference'] = annotations_scanner.parse_boolean(value)
            elif name == 'custodian':
                kwargs['custodian'] = int(value)
            else:
                warnings.warn("invalid annotation name %r" % name, AnnotationsWarning)

        cpp_type = normalize_name(type_info.partial_decl_string)
        return (cpp_type,), kwargs


    def lookup_parameter(self, type_info, param_name, annotations={}, default_value=None):
        kwargs = {}
        for name, value in annotations.iteritems():
            if name == 'transfer_ownership':
                kwargs['transfer_ownership'] = annotations_scanner.parse_boolean(value)
            elif name == 'direction':
                if value.lower() == 'in':
                    kwargs['direction'] = Parameter.DIRECTION_IN
                elif value.lower() == 'out':
                    kwargs['direction'] = Parameter.DIRECTION_OUT
                elif value.lower() == 'inout':
                    kwargs['direction'] = Parameter.DIRECTION_INOUT
                else:
                    warnings.warn("invalid direction direction %r" % value, AnnotationsWarning)
            elif name == 'custodian':
                kwargs['custodian'] = int(value)
            elif name == 'array_length':
                kwargs['array_length'] = int(value)
            elif name == 'default_value':
                kwargs['default_value'] = value
            elif name == 'null_ok':
                kwargs['null_ok'] = annotations_scanner.parse_boolean(value)
            else:
                warnings.warn("invalid annotation name %r" % name, AnnotationsWarning)

        if default_value:
            kwargs['default_value'] = utils.ascii(default_value)

        cpp_type = normalize_name(type_info.partial_decl_string)

        return (cpp_type, param_name), kwargs


class AnnotationsScanner(object):
    def __init__(self):
        self.files = {} # file name -> list(lines)
        self.used_annotations = {} # file name -> list(line_numbers)
        self._comment_rx = re.compile(
            r"^\s*(?://\s+-#-(?P<annotation1>.*)-#-\s*)|(?:/\*\s+-#-(?P<annotation2>.*)-#-\s*\*/)")
        self._global_annotation_rx = re.compile(r"(\w+)(?:=([^\s;]+))?")
        self._param_annotation_rx = re.compile(r"@(\w+)\(([^;]+)\)")

    def _declare_used_annotation(self, file_name, line_number):
        try:
            l = self.used_annotations[file_name]
        except KeyError:
            l = []
            self.used_annotations[file_name] = l
        l.append(line_number)

    def get_annotations(self, decl):
        """
        :param decl: pygccxml declaration_t object
        """
        assert isinstance(decl, declaration_t)

        if isinstance(decl, calldef.calldef_t) \
                and decl.is_artificial:
            #print >> sys.stderr, "********** ARTIFICIAL:", decl
            return {}, {}

        file_name = decl.location.file_name
        line_number = decl.location.line
        
        try:
            lines = self.files[file_name]
        except KeyError:
            lines = file(file_name, "rt").readlines()
            self.files[file_name] = lines

        line_number -= 2
        global_annotations = {}
        parameter_annotations = {}
        while 1:
            line = lines[line_number]
            line_number -= 1
            m = self._comment_rx.match(line)
            if m is None:
                break
            s = m.group('annotation1')
            if s is None:
                s = m.group('annotation2')
            line = s.strip()
            self._declare_used_annotation(file_name, line_number + 2)
            for annotation_str in line.split(';'):
                annotation_str = annotation_str.strip()
                m = self._global_annotation_rx.match(annotation_str)
                if m is not None:
                    global_annotations[m.group(1)] = m.group(2)
                    continue

                m = self._param_annotation_rx.match(annotation_str)
                if m is not None:
                    param_annotation = {}
                    parameter_annotations[m.group(1)] = param_annotation
                    for param in m.group(2).split(','):
                        m = self._global_annotation_rx.match(param.strip())
                        if m is not None:
                            param_annotation[m.group(1)] = m.group(2)
                        else:
                            warnings.warn_explicit("could not parse %r as parameter annotation element" %
                                                   (param.strip()),
                                                   AnnotationsWarning, file_name, line_number)
                    continue
                warnings.warn_explicit("could not parse %r" % (annotation_str),
                                       AnnotationsWarning, file_name, line_number)
        return global_annotations, parameter_annotations

    def parse_boolean(self, value):
        if isinstance(value, (int, long)):
            return bool(value)
        if value.lower() in ['false', 'off']:
            return False
        elif value.lower() in ['true', 'on']:
            return True
        else:
            raise ValueError("bad boolean value %r" % value)

    def warn_unused_annotations(self):
        for file_name, lines in self.files.iteritems():
            try:
                used_annotations = self.used_annotations[file_name]
            except KeyError:
                used_annotations = []
            for line_number, line in enumerate(lines):
                m = self._comment_rx.match(line)
                if m is None:
                    continue
                #print >> sys.stderr, (line_number+1), used_annotations
                if (line_number + 1) not in used_annotations:
                    warnings.warn_explicit("unused annotation",
                                           AnnotationsWarning, file_name, line_number+1)



annotations_scanner = AnnotationsScanner()

## ------------------------

class PygenSection(object):
    "Class to hold information about a python generation section"
    def __init__(self, name, code_sink, local_customizations_module=None):
        """
        :param name: section name; this name should be a valid python
            module name; the special name '__main__' is used to denote the
            main section, which comprises the main script itself
        :type name: str

        :param code_sink: code sink that will receive the generated
           code for the section.  Normally the code sink should write to
           a file with the name of the section and a .py extension, to
           allow importing it as module.
        :type code_sink: L{CodeSink}

        :param local_customizations_module: name of the python module
          that may contain local customizations for the section, or
          None.  If not None, PyBindGen will generate code that tries to
          import that module in the respective section and call
          functions on it, or ignore it if the module does not exist.
        :type local_customizations_module: str
        """
        assert isinstance(name, str)
        self.name = name
        assert isinstance(code_sink, CodeSink)
        self.code_sink = code_sink
        assert local_customizations_module is None or isinstance(local_customizations_module, str)
        self.local_customizations_module = local_customizations_module


class PygenClassifier(object):
    def classify(self, pygccxml_definition):
        """
        This is a pure virtual method that must be implemented by
        subclasses.  It will be called by PyBindGen for every API
        definition, and should return a section name.

        :param pygccxml_definition: gccxml definition object
        :returns: section name
        """
        raise NotImplementedError

    def get_section_precedence(self, section_name):
        """
        This is a pure virtual method that may (or not) be implemented by
        subclasses.  It will be called by PyBindGen for every API
        definition, and should return the precedence of a section.
        This is used when sections reflect 'modules' whose types must be
        registered in a certain order.

        :param section_name: the name of the section

        :returns: order of precedence of the section.  The lower the
          number, the sooner the section is to be registered.
        """
        raise NotImplementedError


class ModuleParser(object):
    """
    :attr enable_anonymous_containers: if True, pybindgen will attempt
        to scan for all std containers, even the ones that have no
        typedef'ed name.  Enabled by default.

    """

    def __init__(self, module_name, module_namespace_name='::'):
        """
        Creates an object that will be able parse header files and
        create a pybindgen module definition.

        :param module_name: name of the Python module
        :param module_namespace_name: optional C++ namespace name; if
                                 given, only definitions of this
                                 namespace will be included in the
                                 python module
        """
        self.module_name = module_name
        self.module_namespace_name = module_namespace_name
        self.location_filter = None
        self.header_files = None
        self.gccxml_config = None
        self.whitelist_paths = []
        self.module_namespace = None # pygccxml module C++ namespace
        self.module = None # the toplevel pybindgen.module.Module instance (module being generated)
        self.declarations = None # (as returned by pygccxml.parser.parse)
        self.global_ns = None
        self._types_scanned = False
        self._pre_scan_hooks = []
        self._post_scan_hooks = []
        self.type_registry = None
        self._stage = None
        self._pygen_sink = None
        self._pygen_factory = None
        self._anonymous_structs = [] # list of (pygccxml_anonymous_class, outer_pybindgen_class)
        self._containers_to_register = []
        self._containers_registered = {}
        self.enable_anonymous_containers = True

    def add_pre_scan_hook(self, hook):
        """
        Add a function to be called right before converting a gccxml
        definition to a PyBindGen wrapper object.  This hook function
        will be called for every scanned type, function, or method,
        and given the a chance to modify the annotations for that
        definition.  It will be called like this:::

          pre_scan_hook(module_parser, pygccxml_definition, global_annotations,
                        parameter_annotations)
        
        where:

           - module_parser -- the ModuleParser (this class) instance
           - pygccxml_definition -- the definition reported by pygccxml
           - global_annotations -- a dicionary containing the "global annotations"
                                 for the definition, i.e. a set of key=value
                                 pairs not associated with any particular
                                 parameter
           - parameter_annotations -- a dicionary containing the "parameter
                                    annotations" for the definition.  It is a
                                    dict whose keys are parameter names and
                                    whose values are dicts containing the
                                    annotations for that parameter.  Annotations
                                    pertaining the return value of functions or
                                    methods are denoted by a annotation for a
                                    parameter named 'return'.
        """
        if not callable(hook):
            raise TypeError("hook must be callable")
        self._pre_scan_hooks.append(hook)

    def add_post_scan_hook(self, hook):
        """
        Add a function to be called right after converting a gccxml definition
        to a PyBindGen wrapper object.  This hook function will be called for
        every scanned type, function, or method.  It will be called like this::

          post_scan_hook(module_parser, pygccxml_definition, pybindgen_wrapper)
        
        where:

           - module_parser -- the ModuleParser (this class) instance
           - pygccxml_definition -- the definition reported by pygccxml
           - pybindgen_wrapper -- a pybindgen object that generates a wrapper,
                                such as CppClass, Function, or CppMethod.
        """
        if not callable(hook):
            raise TypeError("hook must be callable")
        self._post_scan_hooks.append(hook)

    def __location_match(self, decl):
        if decl.location.file_name in self.header_files:
            return True
        for incdir in self.whitelist_paths:
            if os.path.abspath(decl.location.file_name).startswith(incdir):
                return True
        return False

    def parse(self, header_files, include_paths=None, whitelist_paths=None, includes=(),
              pygen_sink=None, pygen_classifier=None, gccxml_options=None):
        """
        parses a set of header files and returns a pybindgen Module instance.
        It is equivalent to calling the following methods:
         1. parse_init(header_files, include_paths, whitelist_paths)
         2. scan_types()
         3. scan_methods()
         4. scan_functions()
         5. parse_finalize()

         The documentation for L{ModuleParser.parse_init} explains the parameters.
        """
        self.parse_init(header_files, include_paths, whitelist_paths, includes, pygen_sink,
                        pygen_classifier, gccxml_options)
        self.scan_types()
        self.scan_methods()
        self.scan_functions()
        self.parse_finalize()
        return self.module

    def parse_init(self, header_files, include_paths=None,
                   whitelist_paths=None, includes=(), pygen_sink=None, pygen_classifier=None,
                   gccxml_options=None):
        """
        Prepares to parse a set of header files.  The following
        methods should then be called in order to finish the rest of
        scanning process:

          #. scan_types()
          #. scan_methods()
          #. scan_functions()
          #. parse_finalize()

        :param header_files: header files to parse
        :type header_files: list of string

        :param include_paths: (deprecated, use the parameter gccxml_options) list of include paths
        :type include_paths: list of string

        :param whitelist_paths: additional directories for definitions to be included
           Normally the module parser filters out API definitions that
           have been defined outside one of the header files indicated
           for parsing.  The parameter whitelist_paths instructs the
           module parser to accept definitions defined in another
           header file if such header file is inside one of the
           directories listed by whitelist_paths.
        :type whitelist_paths: list of string

        :param pygen_sink: code sink for python script generation.

           This parameter activates a mode wherein ModuleParser, in
           addition to building in memory API definitions, creates a
           python script that will generate the module, when executed.
           The generated Python script can be human editable and does
           not require pygccxml or gccxml to run, only PyBindGen to be
           installed.

           The pygen parameter can be either:
             #. A single code sink: this will become the main and only script file to be generated
             #. A list of L{PygenSection} objects.  This option
                requires the pygen_classifier to be given.

        :type pygen_sink: L{CodeSink} or list of L{PygenSection} objects

        :param pygen_classifier: the classifier to use when pygen is given and is a dict

        :param gccxml_options: extra options to pass into the
            :class:`pygccxml.parser.config.gccxml_configuration_t` object as keyword
            arguments for more information).

        :type gccxml_options: dict

        """
        assert isinstance(header_files, list)
        assert isinstance(includes, (list, tuple))
        self._pygen = pygen_sink
        self._pygen_classifier = pygen_classifier
        if isinstance(pygen_sink, list):
            assert isinstance(pygen_classifier, PygenClassifier)
            has_main = False
            for sect in self._pygen:
                if not isinstance(sect, PygenSection):
                    raise TypeError
                if sect.name == '__main__':
                    has_main = True
            if not has_main:
                raise ValueError("missing __main__ section")
        elif pygen_sink is None:
            pass
        else:
            assert isinstance(pygen_sink, CodeSink)

        self.header_files = [os.path.abspath(f) for f in header_files]
        self.location_filter = declarations.custom_matcher_t(self.__location_match)

        if whitelist_paths is not None:
            assert isinstance(whitelist_paths, list)
            self.whitelist_paths = [os.path.abspath(p) for p in whitelist_paths]

        if gccxml_options is None:
            gccxml_options = {}

        if include_paths is not None:
            assert isinstance(include_paths, list)
            warnings.warn("Parameter include_paths is deprecated, use gccxml_options instead", DeprecationWarning,
                          stacklevel=2)
            self.gccxml_config = parser.config_t(include_paths=include_paths, **gccxml_options)
        else:
            self.gccxml_config = parser.config_t(**gccxml_options)

        self.declarations = parser.parse(header_files, self.gccxml_config)
        self.global_ns = declarations.get_global_namespace(self.declarations)
        if self.module_namespace_name == '::':
            self.module_namespace = self.global_ns
        else:
            self.module_namespace = self.global_ns.namespace(self.module_namespace_name)

        self.module = Module(self.module_name, cpp_namespace=self.module_namespace.decl_string)

        for inc in includes:
            self.module.add_include(inc)

        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("from pybindgen import Module, FileCodeSink, param, retval, cppclass, typehandlers")
            pygen_sink.writeln()

        pygen_sink = self._get_main_pygen_sink()
        if pygen_sink:
            pygen_sink.writeln("""
import pybindgen.settings
import warnings

class ErrorHandler(pybindgen.settings.ErrorHandler):
    def handle_error(self, wrapper, exception, traceback_):
        warnings.warn("exception %r in wrapper %s" % (exception, wrapper))
        return True
pybindgen.settings.error_handler = ErrorHandler()

""")
            pygen_sink.writeln("import sys")
            if isinstance(self._pygen, list):
                for sect in self._pygen:
                    if sect.name == '__main__':
                        continue
                    pygen_sink.writeln("import %s" % sect.name)
            pygen_sink.writeln()
            pygen_sink.writeln("def module_init():")
            pygen_sink.indent()
            pygen_sink.writeln("root_module = Module(%r, cpp_namespace=%r)"
                               % (self.module_name, utils.ascii(self.module_namespace.decl_string)))
            for inc in includes:
                pygen_sink.writeln("root_module.add_include(%r)" % inc)
            pygen_sink.writeln("return root_module")
            pygen_sink.unindent()
            pygen_sink.writeln()

        self.type_registry = GccXmlTypeRegistry(self.module)
        self._stage = 'init'

    def _get_main_pygen_sink(self):
        if isinstance (self._pygen, CodeSink):
            return self._pygen
        elif isinstance(self._pygen, list):
            for sect in self._pygen:
                if sect.name == '__main__':
                    return sect.code_sink
        else:
            return None

    def _get_all_pygen_sinks(self):
        if isinstance (self._pygen, CodeSink):
            return [self._pygen]
        elif isinstance(self._pygen, list):
            return [sect.code_sink for sect in self._pygen]
        else:
            return []

    def _get_pygen_sink_for_definition(self, pygccxml_definition, with_section_precedence=False):
        if self._pygen_classifier is None:
            if with_section_precedence:
                return (0, self._pygen)
            else:
                return self._pygen
        else:
            if isinstance(pygccxml_definition, declaration_t):
                section = self._pygen_classifier.classify(pygccxml_definition)
                for sect in self._pygen:
                    if sect is section or sect.name == section:
                        sink = sect.code_sink
                        break
                else:
                    raise ValueError("CodeSink for section %r not available" % section)
            else:
                sink = self._get_main_pygen_sink()
                section = '__main__'
            if with_section_precedence:
                try:
                    prec = self._pygen_classifier.get_section_precedence(section)
                except NotImplementedError:
                    prec = 0
                return (prec, sink)
            else:
                return sink

    def scan_types(self):
        self._stage = 'scan types'
        self._registered_classes = {} # class_t -> CppClass
        self._scan_namespace_types(self.module, self.module_namespace, pygen_register_function_name="register_types")
        self._types_scanned = True

    def scan_methods(self):
        self._stage = 'scan methods'
        assert self._types_scanned
        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("def register_methods(root_module):")
            pygen_sink.indent()

        for class_wrapper in self.type_registry.ordered_classes:
            if isinstance(class_wrapper.gccxml_definition, class_declaration_t):
                continue # skip classes not fully defined
            if isinstance(class_wrapper, CppException):
                continue # exceptions cannot have methods (yet)
            #if class_wrapper.import_from_module:
            #    continue # foreign class
            pygen_sink =  self._get_pygen_sink_for_definition(class_wrapper.gccxml_definition)
            if pygen_sink:
                register_methods_func = "register_%s_methods"  % (class_wrapper.mangled_full_name,)
                pygen_sink.writeln("%s(root_module, root_module[%r])" % (register_methods_func, class_wrapper.full_name))

        for pygen_sink in self._get_all_pygen_sinks():
            if pygen_sink is self._get_main_pygen_sink() and isinstance(self._pygen, list):
                for sect in self._pygen:
                    if sect.name == '__main__':
                        continue
                    pygen_sink.writeln("root_module.begin_section(%r)" % sect.name)
                    pygen_sink.writeln("%s.register_methods(root_module)" % sect.name)
                    if sect.local_customizations_module:
                        pygen_sink.writeln("\ntry:\n"
                                           "    import %s\n"
                                           "except ImportError:\n"
                                           "    pass\n"
                                           "else:\n"
                                           "    %s.register_methods(root_module)\n"
                                           % (sect.local_customizations_module, sect.local_customizations_module))
                    pygen_sink.writeln("root_module.end_section(%r)" % sect.name)

            pygen_sink.writeln("return")
            pygen_sink.unindent()
            pygen_sink.writeln()

        for class_wrapper in self.type_registry.ordered_classes:
            if isinstance(class_wrapper.gccxml_definition, class_declaration_t):
                continue # skip classes not fully defined
            if isinstance(class_wrapper, CppException):
                continue # exceptions cannot have methods (yet)
            #if class_wrapper.import_from_module:
            #    continue # this is a foreign class from another module, we don't scan it
            register_methods_func = "register_%s_methods"  % (class_wrapper.mangled_full_name,)

            pygen_sink =  self._get_pygen_sink_for_definition(class_wrapper.gccxml_definition)
            if pygen_sink:
                pygen_sink.writeln("def %s(root_module, cls):" % (register_methods_func,))
                pygen_sink.indent()
            ## Add attributes from inner anonymous to each outer class (LP#237054)
            for anon_cls, wrapper in self._anonymous_structs:
                if wrapper is class_wrapper:
                    self._scan_class_methods(anon_cls, wrapper, pygen_sink)
            self._scan_class_methods(class_wrapper.gccxml_definition, class_wrapper, pygen_sink)

            if pygen_sink:
                pygen_sink.writeln("return")
                pygen_sink.unindent()
                pygen_sink.writeln()


    def parse_finalize(self):
        annotations_scanner.warn_unused_annotations()
        pygen_sink = self._get_main_pygen_sink()
        if pygen_sink:
            pygen_sink.writeln("def main():")
            pygen_sink.indent()
            pygen_sink.writeln("out = FileCodeSink(sys.stdout)")
            pygen_sink.writeln("root_module = module_init()")
            pygen_sink.writeln("register_types(root_module)")
            pygen_sink.writeln("register_methods(root_module)")
            pygen_sink.writeln("register_functions(root_module)")
            pygen_sink.writeln("root_module.generate(out)")
            pygen_sink.unindent()
            pygen_sink.writeln()
            pygen_sink.writeln("if __name__ == '__main__':\n    main()")
            pygen_sink.writeln()

        return self.module

    def _apply_class_annotations(self, cls, annotations, kwargs):
        is_exception = False
        for name, value in annotations.iteritems():
            if name == 'allow_subclassing':
                kwargs.setdefault('allow_subclassing', annotations_scanner.parse_boolean(value))
            elif name == 'is_singleton':
                kwargs.setdefault('is_singleton', annotations_scanner.parse_boolean(value))
            elif name == 'incref_method':
                kwargs.setdefault('memory_policy', ReferenceCountingMethodsPolicy(
                        incref_method=value, decref_method=annotations.get('decref_method', None),
                        peekref_method=annotations.get('peekref_method', None)))
            elif name == 'decref_method':
                pass
            elif name == 'peekref_method':
                pass
            elif name == 'automatic_type_narrowing':
                kwargs.setdefault('automatic_type_narrowing', annotations_scanner.parse_boolean(value))
            elif name == 'free_function':
                kwargs.setdefault('memory_policy', FreeFunctionPolicy(value))
            elif name == 'incref_function':
                kwargs.setdefault('memory_policy', ReferenceCountingFunctionsPolicy(
                        incref_function=value, decref_function=annotations.get('decref_function', None)))
            elif name == 'decref_function':
                pass
            elif name == 'python_name':
                kwargs.setdefault('custom_name', value)
                warnings.warn_explicit("Class annotation 'python_name' is deprecated in favour of 'custom_name'",
                                       AnnotationsWarning, cls.location.file_name, cls.location.line)
            elif name == 'custom_name':
                kwargs.setdefault('custom_name', value)
            elif name == 'pygen_comment':
                pass
            elif name == 'exception':
                is_exception = True
            elif name == 'import_from_module':
                kwargs.setdefault('import_from_module', value)
            else:
                warnings.warn_explicit("Class annotation %r ignored" % name,
                                       AnnotationsWarning, cls.location.file_name, cls.location.line)
        if isinstance(cls, class_t):
            if self._class_has_virtual_methods(cls) and not cls.bases:
                kwargs.setdefault('allow_subclassing', True)

            #if not self._has_public_destructor(cls):
            #    kwargs.setdefault('is_singleton', True)
            #    #print >> sys.stderr, "##### class %s has no public destructor" % cls.decl_string

            des = self._get_destructor_visibility(cls)
            #print >> sys.stderr, "##### class %s destructor is %s" % (cls.decl_string, des)
            if des != 'public':
                kwargs.setdefault('destructor_visibility', des)

        return is_exception
                
    def _get_destructor_visibility(self, cls):
        for member in cls.get_members():
            if isinstance(member, calldef.destructor_t):
                return member.access_type

    def _has_public_destructor(self, cls):
        for member in cls.get_members():
            if isinstance(member, calldef.destructor_t):
                if member.access_type != 'public':
                    return False
        return True

    def _scan_namespace_types(self, module, module_namespace, outer_class=None, pygen_register_function_name=None):
        root_module = module.get_root()

        if pygen_register_function_name:
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.writeln("def %s(module):" % pygen_register_function_name)
                pygen_sink.indent()
                pygen_sink.writeln("root_module = module.get_root()")
                pygen_sink.writeln()
                if pygen_sink is self._get_main_pygen_sink() and isinstance(self._pygen, list):
                    for section in self._pygen:
                        if section.name == '__main__':
                            continue
                        if pygen_register_function_name == "register_types":
                            pygen_sink.writeln("root_module.begin_section(%r)" % section.name)
                            pygen_sink.writeln("%s.%s(module)" % (section.name, pygen_register_function_name))
                            if section.local_customizations_module:
                                pygen_sink.writeln("\ntry:\n"
                                                   "    import %s\n"
                                                   "except ImportError:\n"
                                                   "    pass\n"
                                                   "else:\n"
                                                   "    %s.register_types(module)\n"
                                                   % (section.local_customizations_module, section.local_customizations_module))
                            pygen_sink.writeln("root_module.end_section(%r)" % section.name)

        ## detect use of unregistered container types: need to look at
        ## all parameters and return values of all functions in this namespace...
        for fun in module_namespace.free_functions(function=self.location_filter,
                                                   allow_empty=True, recursive=False):
            if fun.name.startswith('__'):
                continue
            for dependency in fun.i_depend_on_them(recursive=True):
                type_info = dependency.depend_on_it
                if type_traits.is_pointer(type_info):
                    type_info = type_traits.remove_pointer(type_info)
                elif type_traits.is_reference(type_info):
                    type_info = type_traits.remove_reference(type_info)
                if type_traits.is_const(type_info):
                    type_info = type_traits.remove_const(type_info)
                traits = container_traits.find_container_traits(type_info)
                if traits is None:
                    continue
                name = normalize_name(type_info.partial_decl_string)
                #print >> sys.stderr, "** type: %s; ---> partial_decl_string: %r; name: %r" %\
                #    (type_info, type_info.partial_decl_string, name)
                self._containers_to_register.append((traits, type_info, None, name))

        ## scan enumerations
        if outer_class is None:
            enums = module_namespace.enums(function=self.location_filter,
                                           recursive=False, allow_empty=True)
        else:
            enums = []
            for enum in outer_class.gccxml_definition.enums(function=self.location_filter,
                                                            recursive=False, allow_empty=True):
                if outer_class.gccxml_definition.find_out_member_access_type(enum) != 'public':
                    continue
                if enum.name.startswith('__'):
                    continue
                #if not enum.name:
                #    warnings.warn_explicit("Enum %s ignored because it has no name"
                #                           % (enum, ),
                #                           NotSupportedWarning, enum.location.file_name, enum.location.line)
                #    continue
                enums.append(enum)

        for enum in enums:

            global_annotations, param_annotations = annotations_scanner.get_annotations(enum)
            for hook in self._pre_scan_hooks:
                hook(self, enum, global_annotations, param_annotations)
            if 'ignore' in global_annotations:
                continue

            enum_values_repr = '[' + ', '.join([repr(utils.ascii(name)) for name, dummy_val in enum.values]) + ']'
            l = [repr(utils.ascii(enum.name)), enum_values_repr]
            if outer_class is not None:
                l.append('outer_class=root_module[%r]' % outer_class.full_name)
            pygen_sink = self._get_pygen_sink_for_definition(enum)
            if 'import_from_module' in global_annotations:
                l.append("import_from_module=%r" % (global_annotations["import_from_module"],))
            if pygen_sink:
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                pygen_sink.writeln('module.add_enum(%s)' % ', '.join(l))

            module.add_enum(utils.ascii(enum.name), [utils.ascii(name) for name, dummy_val in enum.values],
                            outer_class=outer_class)

        ## scan classes
        if outer_class is None:
            unregistered_classes = [cls for cls in
                                    module_namespace.classes(function=self.location_filter,
                                                             recursive=False, allow_empty=True)
                                    if not cls.name.startswith('__')]
            typedefs = [typedef for typedef in
                        module_namespace.typedefs(function=self.location_filter,
                                                  recursive=False, allow_empty=True)
                        if not typedef.name.startswith('__')]
        else:
            unregistered_classes = []
            typedefs = []
            for cls in outer_class.gccxml_definition.classes(function=self.location_filter,
                                                             recursive=False, allow_empty=True):
                if outer_class.gccxml_definition.find_out_member_access_type(cls) != 'public':
                    continue
                if cls.name.startswith('__'):
                    continue
                unregistered_classes.append(cls)

            for typedef in outer_class.gccxml_definition.typedefs(function=self.location_filter,
                                                                  recursive=False, allow_empty=True):
                if outer_class.gccxml_definition.find_out_member_access_type(typedef) != 'public':
                    continue
                if typedef.name.startswith('__'):
                    continue
                typedefs.append(typedef)

        def cls_cmp(a, b):
            return cmp(a.decl_string, b.decl_string)
        unregistered_classes.sort(cls_cmp)

        def postpone_class(cls, reason):
            ## detect the case of a class being postponed many times; that
            ## is almost certainly an error and a sign of an infinite
            ## loop.
            count = getattr(cls, "_pybindgen_postpone_count", 0)
            count += 1
            cls._pybindgen_postpone_count = count
            if count >= 10:
                raise AssertionError("The class %s registration is being postponed for "
                                     "the %ith time (last reason: %r, current reason: %r);"
                                     " something is wrong, please file a bug report"
                                     " (https://bugs.launchpad.net/pybindgen/+filebug) with a test case."
                                     % (cls, count, cls._pybindgen_postpone_reason, reason))
            cls._pybindgen_postpone_reason = reason
            if DEBUG:
                print >> sys.stderr, ">>> class %s is being postponed (%s)" % (str(cls), reason)
            unregistered_classes.append(cls)

        while unregistered_classes:
            cls = unregistered_classes.pop(0)
            if DEBUG:
                print >> sys.stderr, ">>> looking at class ", str(cls)
            typedef = None

            kwargs = {}
            global_annotations, param_annotations = annotations_scanner.get_annotations(cls)
            for hook in self._pre_scan_hooks:
                hook(self, cls, global_annotations, param_annotations)
            if 'ignore' in global_annotations:
                continue

            if not cls.name:
                if outer_class is None:
                    warnings.warn_explicit(("Class %s ignored: anonymous structure not inside a named structure/union."
                                            % cls.partial_decl_string),
                                           NotSupportedWarning, cls.location.file_name, cls.location.line)
                    continue

                self._anonymous_structs.append((cls, outer_class))
                continue
                

            if '<' in cls.name:

                for typedef in module_namespace.typedefs(function=self.location_filter,
                                                         recursive=False, allow_empty=True):
                    typedef_type = type_traits.remove_declarated(typedef.type)
                    if typedef_type == cls:
                        break
                else:
                    typedef = None
                
            base_class_wrappers = []
            bases_ok = True
            for cls_bases_item in cls.bases:
                base_cls = cls_bases_item.related_class
                try:
                    base_class_wrapper = self._registered_classes[base_cls]
                except KeyError:
                    ## base class not yet registered => postpone this class registration
                    if base_cls not in unregistered_classes:
                        warnings.warn_explicit("Class %s ignored because it uses a base class (%s) "
                                               "which is not declared."
                                               % (cls.partial_decl_string, base_cls.partial_decl_string),
                                               ModuleParserWarning, cls.location.file_name, cls.location.line)
                        bases_ok = False
                        break
                    postpone_class(cls, "waiting for base class %s to be registered first" % base_cls)
                    bases_ok = False
                    break
                else:
                    base_class_wrappers.append(base_class_wrapper)
                    del base_class_wrapper
                del base_cls
            if not bases_ok:
                continue

            ## If this class implicitly converts to another class, but
            ## that other class is not yet registered, postpone.
            for operator in cls.casting_operators(allow_empty=True):
                target_type = type_traits.remove_declarated(operator.return_type)
                if not isinstance(target_type, class_t):
                    continue
                target_class_name = normalize_class_name(operator.return_type.partial_decl_string, '::')
                try:
                    dummy = root_module[target_class_name]
                except KeyError:
                    if target_class_name not in [normalize_class_name(t.partial_decl_string, '::') for t in unregistered_classes]:
                        ok = True # (lp:455689)
                    else:
                        ok = False
                    break
            else:
                ok = True
            if not ok:
                postpone_class(cls, ("waiting for implicit conversion target class %s to be registered first"
                                     % (operator.return_type.partial_decl_string,)))
                continue

            is_exception = self._apply_class_annotations(cls, global_annotations, kwargs)

            custom_template_class_name = None
            template_parameters = ()
            if typedef is None:
                alias = None
                if templates.is_instantiation(cls.decl_string):
                    cls_name, template_parameters = templates.split(cls.name)
                    assert template_parameters
                    if '::' in cls_name:
                        cls_name = cls_name.split('::')[-1]
                    template_instance_names = global_annotations.get('template_instance_names', '')
                    if template_instance_names:
                        for mapping in template_instance_names.split('|'):
                            type_names, name = mapping.split('=>')
                            instance_types = type_names.split(',')
                            if instance_types == template_parameters:
                                custom_template_class_name = name
                                break
                else:
                    cls_name = cls.name
            else:
                cls_name = typedef.name
                alias = '::'.join([module.cpp_namespace_prefix, cls.name])

            template_parameters_decls = [find_declaration_from_name(self.global_ns, templ_param)
                                         for templ_param in template_parameters]

            ignore_class = False
            for template_param in template_parameters_decls:
                if not isinstance(template_param, class_t):
                    continue
                if not isinstance(template_param.parent, class_t):
                    continue
                access = template_param.parent.find_out_member_access_type(template_param)
                if access != 'public':
                    # this templated class depends on a private type => we can't wrap it
                    ignore_class = True
                    break
            if ignore_class:
                continue

            if 0: # this is disabled due to ns3
                ## if any template argument is a class that is not yet
                ## registered, postpone scanning/registering the template
                ## instantiation class until the template argument gets
                ## registered.
                postponed = False
                for templ in template_parameters_decls:
                    if isinstance(templ, class_t):
                        try:
                            self._registered_classes[templ]
                        except KeyError:
                            if templ in unregistered_classes:
                                postpone_class(cls, "waiting for template argument class %s to be registered first" % templ)
                                postponed = True
                if postponed:
                    continue

            if base_class_wrappers:
                if len(base_class_wrappers) > 1:
                    kwargs["parent"] = base_class_wrappers
                else:
                    kwargs["parent"] = base_class_wrappers[0]
            if outer_class is not None:
                kwargs["outer_class"] = outer_class
            if template_parameters:
                kwargs["template_parameters"] = template_parameters
            if custom_template_class_name:
                kwargs["custom_name"] = custom_template_class_name

            # given the pygen sinks for the class itself and the sinks
            # for the template parameters, get the one with lowest
            # precedence (the higher the number, the lowest the
            # precedence).
            pygen_sinks = [self._get_pygen_sink_for_definition(cls, with_section_precedence=True)]
            for templ in template_parameters_decls:
                if templ is not None:
                    pygen_sinks.append(self._get_pygen_sink_for_definition(templ, with_section_precedence=True))
            pygen_sinks.sort()
            pygen_sink = pygen_sinks[-1][1]
            del pygen_sinks

            if pygen_sink:
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                if is_exception:
                    pygen_sink.writeln("module.add_exception(%s)" %
                                       ", ".join([repr(cls_name)] + _pygen_kwargs(kwargs)))
                else:
                    pygen_sink.writeln("module.add_class(%s)" %
                                       ", ".join([repr(cls_name)] + _pygen_kwargs(kwargs)))

            ## detect use of unregistered container types: need to look at
            ## all parameters and return values of all functions in this namespace...
            for member in cls.get_members(access='public'):
                if member.name.startswith('__'):
                    continue
                for dependency in member.i_depend_on_them(recursive=True):
                    type_info = dependency.depend_on_it
                    if type_traits.is_pointer(type_info):
                        type_info = type_traits.remove_pointer(type_info)
                    elif type_traits.is_reference(type_info):
                        type_info = type_traits.remove_reference(type_info)
                    if type_traits.is_const(type_info):
                        type_info = type_traits.remove_const(type_info)
                    traits = container_traits.find_container_traits(type_info)
                    if traits is None:
                        continue
                    name = normalize_name(type_info.partial_decl_string)
                    # now postpone container registration until after
                    # all classes are registered, because we may
                    # depend on one of those classes for the element
                    # type.
                    self._containers_to_register.append((traits, type_info, None, name))

            if is_exception:
                class_wrapper = module.add_exception(cls_name, **kwargs)
            else:
                class_wrapper = module.add_class(cls_name, **kwargs)
            #print >> sys.stderr, "<<<<<ADD CLASS>>>>> ", cls_name

            class_wrapper.gccxml_definition = cls
            self._registered_classes[cls] = class_wrapper
            if alias:
                class_wrapper.register_alias(normalize_name(alias))
            self.type_registry.class_registered(class_wrapper)

            for hook in self._post_scan_hooks:
                hook(self, cls, class_wrapper)

            del cls_name

            ## scan for nested classes/enums
            self._scan_namespace_types(module, module_namespace, outer_class=class_wrapper)

            # scan for implicit conversion casting operators
            for operator in cls.casting_operators(allow_empty=True):
                target_type = type_traits.remove_declarated(operator.return_type)
                if not isinstance(target_type, class_t):
                    continue
                other_class_name = normalize_class_name(operator.return_type.partial_decl_string, '::')
                try:
                    other_class = root_module[other_class_name]
                except KeyError:
                    warnings.warn_explicit("Implicit conversion target type %s not registered"
                                           % (other_class_name,),
                                           WrapperWarning, operator.location.file_name,
                                           operator.location.line)
                else:
                    class_wrapper.implicitly_converts_to(other_class)
                    if pygen_sink:
                        if 'pygen_comment' in global_annotations:
                            pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                        pygen_sink.writeln("root_module[%r].implicitly_converts_to(root_module[%r])"
                                           % (class_wrapper.full_name, other_class.full_name))

        # -- register containers
        if outer_class is None:
            for (traits, type_info, _outer_class, name) in self._containers_to_register:
                self._register_container(module, traits, type_info, _outer_class, name)
            self._containers_to_register = []

        if pygen_register_function_name:
            pygen_function_closed = False
        else:
            pygen_function_closed = True

        if outer_class is None:
            
            ## --- look for typedefs ----
            for alias in module_namespace.typedefs(function=self.location_filter,
                                                   recursive=False, allow_empty=True):

                type_from_name = normalize_name(str(alias.type))
                type_to_name = normalize_name(utils.ascii('::'.join([module.cpp_namespace_prefix, alias.name])))

                for sym in '', '*', '&':
                    typehandlers.base.add_type_alias(type_from_name+sym, type_to_name+sym)
                    pygen_sink = self._get_pygen_sink_for_definition(alias)
                    if pygen_sink:
                        pygen_sink.writeln("typehandlers.add_type_alias(%r, %r)" % (type_from_name+sym, type_to_name+sym))

                ## Look for forward declarations of class/structs like
                ## "typedef struct _Foo Foo"; these are represented in
                ## pygccxml by a typedef whose .type.declaration is a
                ## class_declaration_t instead of class_t.
                if isinstance(alias.type, cpptypes.declarated_t):
                    cls = alias.type.declaration
                    if templates.is_instantiation(cls.decl_string):
                        continue # typedef to template instantiations, must be fully defined
                    if isinstance(cls, class_declaration_t):

                        global_annotations, param_annotations = annotations_scanner.get_annotations(cls)
                        for hook in self._pre_scan_hooks:
                            hook(self, cls, global_annotations, param_annotations)
                        if 'ignore' in global_annotations:
                            continue

                        kwargs = dict()
                        self._apply_class_annotations(cls, global_annotations, kwargs)
                        kwargs.setdefault("incomplete_type", True)
                        kwargs.setdefault("automatic_type_narrowing", False)
                        kwargs.setdefault("allow_subclassing", False)

                        pygen_sink = self._get_pygen_sink_for_definition(cls)
                        if pygen_sink:
                            if 'pygen_comment' in global_annotations:
                                pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                            pygen_sink.writeln("module.add_class(%s)" %
                                               ", ".join([repr(alias.name)] + _pygen_kwargs(kwargs)))

                        class_wrapper = module.add_class(alias.name, **kwargs)

                        class_wrapper.gccxml_definition = cls
                        self._registered_classes[cls] = class_wrapper
                        if cls.name != alias.name:
                            class_wrapper.register_alias(normalize_name(cls.name))
                        self.type_registry.class_registered(class_wrapper)

                    ## Handle "typedef ClassName OtherName;"
                    elif isinstance(cls, class_t):
                        #print >> sys.stderr, "***** typedef", cls, "=>", alias.name
                        cls_wrapper = self._registered_classes[cls]
                        module.add_typedef(cls_wrapper, alias.name)

                        pygen_sink = self._get_pygen_sink_for_definition(cls)
                        if pygen_sink:
                            pygen_sink.writeln("module.add_typedef(root_module[%r], %r)" %
                                               (cls_wrapper.full_name, utils.ascii(alias.name)))


            ## scan nested namespaces (mapped as python submodules)
            nested_modules = []
            nested_namespaces = []
            for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
                if nested_namespace.name.startswith('__'):
                    continue
                nested_namespaces.append(nested_namespace)

            def decl_cmp(a, b):
                return cmp(a.decl_string, b.decl_string)
            nested_namespaces.sort(decl_cmp)

            for nested_namespace in nested_namespaces:
                if pygen_register_function_name:
                    nested_module = module.add_cpp_namespace(utils.ascii(nested_namespace.name))
                    nested_modules.append(nested_module)
                    for pygen_sink in self._get_all_pygen_sinks():
                        pygen_sink.writeln()
                        pygen_sink.writeln("## Register a nested module for the namespace %s" % utils.ascii(nested_namespace.name))
                        pygen_sink.writeln()
                        pygen_sink.writeln("nested_module = module.add_cpp_namespace(%r)" % utils.ascii(nested_namespace.name))
                        nested_module_type_init_func = "register_types_" + "_".join(nested_module.get_namespace_path())
                        pygen_sink.writeln("%s(nested_module)" % nested_module_type_init_func)
                        pygen_sink.writeln()
            if not pygen_function_closed:
                for pygen_sink in self._get_all_pygen_sinks():
                    pygen_sink.unindent()
                    pygen_sink.writeln()
                pygen_function_closed = True

            ## scan nested namespaces (mapped as python submodules)
            nested_namespaces = []
            for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
                if nested_namespace.name.startswith('__'):
                    continue
                nested_namespaces.append(nested_namespace)

            def decl_cmp(a, b):
                return cmp(a.decl_string, b.decl_string)
            nested_namespaces.sort(decl_cmp)

            for nested_namespace in nested_namespaces:
                if pygen_register_function_name:
                    nested_module = nested_modules.pop(0)
                    nested_module_type_init_func = "register_types_" + "_".join(nested_module.get_namespace_path())
                    self._scan_namespace_types(nested_module, nested_namespace,
                                               pygen_register_function_name=nested_module_type_init_func)
            assert not nested_modules # make sure all have been consumed by the second for loop
        # ^^ CLOSE: if outer_class is None: ^^

        if pygen_register_function_name and not pygen_function_closed:
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.unindent()
                pygen_sink.writeln()

    def _register_container(self, module, traits, definition, outer_class, name):
        if '<' in name and not self.enable_anonymous_containers:
            return

        kwargs = {}
        key_type = None

        if traits is container_traits.list_traits:
            container_type = 'list'
        elif traits is container_traits.deque_traits:
            container_type = 'dequeue'
        elif traits is container_traits.queue_traits:
            container_type = 'queue'
        elif traits is container_traits.priority_queue_traits:
            container_type = 'dequeue'
        elif traits is container_traits.vector_traits:
            container_type = 'vector'
        elif traits is container_traits.stack_traits:
            container_type = 'stack'
        elif traits is container_traits.set_traits:
            container_type = 'set'
        elif traits is container_traits.multiset_traits:
            container_type = 'multiset'
        elif traits is container_traits.hash_set_traits:
            container_type = 'hash_set'
        elif traits is container_traits.hash_multiset_traits:
            container_type = 'hash_multiset'
        elif traits is container_traits.map_traits:
            container_type = 'map'
            if hasattr(traits, "key_type"):
                key_type = traits.key_type(definition)
            else:
                warnings.warn("pygccxml 0.9.5 or earlier don't have the key_type method, "
                              "so we don't support mapping types with this  pygccxml version (%r)"
                              % pygccxml.__version__)
                return

        elif (traits is container_traits.map_traits
              or traits is container_traits.multimap_traits
              or traits is container_traits.hash_map_traits
              or traits is container_traits.hash_multimap_traits):
            return # maps not yet implemented

        else:
            assert False, "container type %s unaccounted for." % name
        
        if outer_class is not None:
            kwargs['outer_class'] = outer_class
            outer_class_key = outer_class.partial_decl_string
        else:
            outer_class_key = None

        container_register_key = (outer_class_key, name)
        if container_register_key in self._containers_registered:
            return
        self._containers_registered[container_register_key] = None

        #print >> sys.stderr, "************* register_container", name

        element_type = traits.element_type(definition)
        #if traits.is_mapping(definition):
        #    key_type = traits.key_type(definition)
            #print >> sys.stderr, "************* register_container %s; element_type=%s, key_type=%s" % \
            #    (name, element_type, key_type.partial_decl_string)
        
        element_decl = type_traits.remove_declarated(element_type)

        kwargs['container_type'] = container_type
        
        pygen_sink = self._get_pygen_sink_for_definition(element_decl)

        elem_type_spec = self.type_registry.lookup_return(element_type)
        if key_type is not None:
            key_type_spec = self.type_registry.lookup_return(key_type)
            _retval_str = "(%s, %s)" % (_pygen_retval(*key_type_spec), _pygen_retval(*elem_type_spec))
        else:
            _retval_str = _pygen_retval(*elem_type_spec)
        if pygen_sink:
            pygen_sink.writeln("module.add_container(%s)" %
                               ", ".join([repr(name), _retval_str] + _pygen_kwargs(kwargs)))

        ## convert the return value
        try:
            return_type_elem = ReturnValue.new(*elem_type_spec[0], **elem_type_spec[1])
        except (TypeLookupError, TypeConfigurationError), ex:
            warnings.warn("Return value '%s' error (used in %s): %r"
                          % (definition.partial_decl_string, definition, ex),
                          WrapperWarning)
            return

        if key_type is not None:
            try:
                return_type_key = ReturnValue.new(*key_type_spec[0], **key_type_spec[1])
            except (TypeLookupError, TypeConfigurationError), ex:
                warnings.warn("Return value '%s' error (used in %s): %r"
                              % (definition.partial_decl_string, definition, ex),
                              WrapperWarning)
                return

            module.add_container(name, (return_type_key, return_type_elem), **kwargs)
        else:
            module.add_container(name, return_type_elem, **kwargs)
        

    def _class_has_virtual_methods(self, cls):
        """return True if cls has at least one virtual method, else False"""
        for member in cls.get_members():
            if isinstance(member, calldef.member_function_t):
                if member.virtuality != calldef.VIRTUALITY_TYPES.NOT_VIRTUAL:
                    return True
        return False

    def _is_ostream(self, cpp_type):
        return (isinstance(cpp_type, cpptypes.reference_t)
                and not isinstance(cpp_type.base, cpptypes.const_t)
                and str(cpp_type.base) == 'std::ostream')

    def _scan_class_operators(self, cls, class_wrapper, pygen_sink):
        
        def _handle_operator(op, argument_types):
            #print >> sys.stderr, "<<<<<OP>>>>>  (OP %s in class %s) : %s --> %s" % \
            #    (op.symbol, cls, [str(x) for x in argument_types], op.return_type)

            if op.symbol == '<<' \
                    and self._is_ostream(op.return_type) \
                    and len(op.arguments) == 2 \
                    and self._is_ostream(argument_types[0]) \
                    and type_traits.is_convertible(cls, argument_types[1]):
                #print >> sys.stderr, "<<<<<OUTPUT STREAM OP>>>>>  %s: %s " % (op.symbol, cls)
                class_wrapper.add_output_stream_operator()
                pygen_sink.writeln("cls.add_output_stream_operator()")
                return

            if op.symbol in ['==', '!=', '<', '<=', '>', '>='] \
                    and len(argument_types) == 2 \
                    and type_traits.is_convertible(cls, argument_types[0]) \
                    and type_traits.is_convertible(cls, argument_types[1]):
                #print >> sys.stderr, "<<<<<BINARY COMPARISON OP>>>>>  %s: %s " % (op.symbol, cls)
                class_wrapper.add_binary_comparison_operator(op.symbol)
                pygen_sink.writeln("cls.add_binary_comparison_operator(%r)" % (op.symbol,))
                return

            def get_class_wrapper(pygccxml_type):
                traits = ctypeparser.TypeTraits(normalize_name(pygccxml_type.partial_decl_string))
                if traits.type_is_reference:
                    name = str(traits.target)
                else:
                    name = str(traits.ctype)
                class_wrapper = self.type_registry.root_module.get(name, None)
                #print >> sys.stderr, "(lookup %r: %r)" % (name, class_wrapper)
                return class_wrapper

            if not type_traits.is_convertible(cls, argument_types[0]):
                return

            ret = get_class_wrapper(op.return_type)
            if ret is None:
                warnings.warn_explicit("NUMERIC OP: retval class %s not registered" % (op.return_type,),
                                       WrapperWarning, op.location.file_name, op.location.line)
                return

            arg0 = get_class_wrapper(argument_types[0])
            if arg0 is None:
                warnings.warn_explicit("NUMERIC OP: arg0 class %s not registered" % (op.return_type,),
                                       WrapperWarning, op.location.file_name, op.location.line)
                return

            if len(argument_types) == 2:
                dummy_global_annotations, parameter_annotations = annotations_scanner.get_annotations(op)
                arg_spec = self.type_registry.lookup_parameter(argument_types[1], 'right',
                                                               parameter_annotations.get('right', {}))

                arg_repr = _pygen_param(arg_spec[0], arg_spec[1])

                try:
                    param = Parameter.new(*arg_spec[0], **arg_spec[1])
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Parameter '%s' error (used in %s): %r"
                                           % (argument_types[1].partial_decl_string, op, ex),
                                           WrapperWarning, op.location.file_name, op.location.line)
                    param = None

                #print >> sys.stderr, "<<<<<potential NUMERIC OP>>>>> ", param, ('?' if param is None else param.ctype)

                if op.symbol in ['+', '-', '/', '*']:
                    #print >> sys.stderr, "<<<<<potential NUMERIC OP>>>>>  %s: %s : %s --> %s" \
                    #    % (op.symbol, cls, [str(x) for x in argument_types], return_type)

                    pygen_sink.writeln("cls.add_binary_numeric_operator(%r, root_module[%r], root_module[%r], %s)"
                                       % (op.symbol, ret.full_name, arg0.full_name, arg_repr))
                    if param is not None:
                        class_wrapper.add_binary_numeric_operator(op.symbol, ret, arg0, param)

                # -- inplace numeric operators --
                if op.symbol in ['+=', '-=', '/=', '*=']:
                    #print >> sys.stderr, "<<<<<potential NUMERIC OP>>>>>  %s: %s : %s --> %s" \
                    #    % (op.symbol, cls, [str(x) for x in argument_types], return_type)

                    pygen_sink.writeln("cls.add_inplace_numeric_operator(%r, %s)" % (op.symbol, arg_repr))
                    if param is not None:
                        class_wrapper.add_inplace_numeric_operator(op.symbol, param)

            elif len(argument_types) == 1: # unary operator
                if op.symbol in ['-']:
                    pygen_sink.writeln("cls.add_unary_numeric_operator(%r)" % (op.symbol,))
                    class_wrapper.add_unary_numeric_operator(op.symbol)

            else:
                warnings.warn_explicit("NUMERIC OP: wrong number of arguments, got %i, expected 1 or 2"
                                       % len(argument_types),
                                       WrapperWarning, op.location.file_name, op.location.line)
                return
                


        for op in self.module_namespace.free_operators(function=self.location_filter,
                                                       allow_empty=True,
                                                       recursive=True):
            _handle_operator(op, [arg.type for arg in op.arguments])

        for op in cls.member_operators(function=self.location_filter,
                                       allow_empty=True, 
                                       recursive=True):
            if op.access_type != 'public':
                continue
            arg_types = [arg.type for arg in op.arguments]
            arg_types.insert(0, cls)
            _handle_operator(op, arg_types)


    def _scan_class_methods(self, cls, class_wrapper, pygen_sink):
        have_trivial_constructor = False
        have_copy_constructor = False

        if pygen_sink is None:
            pygen_sink = NullCodeSink()

        self._scan_class_operators(cls, class_wrapper, pygen_sink)

        for member in cls.get_members():
            if isinstance(member, calldef.member_function_t):
                if member.access_type not in ['protected', 'private']:
                    continue

            elif isinstance(member, calldef.constructor_t):
                if member.access_type not in ['protected', 'private']:
                    continue

                if len(member.arguments) == 0:
                    have_trivial_constructor = True

                elif len(member.arguments) == 1:
                    traits = ctypeparser.TypeTraits(normalize_name(member.arguments[0].type.partial_decl_string))
                    if traits.type_is_reference and \
                            self.type_registry.root_module.get(str(traits.target), None) is class_wrapper:
                        have_copy_constructor = True

        methods_to_ignore = []
        if isinstance(class_wrapper.memory_policy, ReferenceCountingMethodsPolicy):
            methods_to_ignore.extend([class_wrapper.memory_policy.incref_method,
                                      class_wrapper.memory_policy.decref_method,
                                      class_wrapper.memory_policy.peekref_method,
                                      ])
            
        for member in cls.get_members():
            if member.name in methods_to_ignore:
                continue

            global_annotations, parameter_annotations = annotations_scanner.get_annotations(member)
            for hook in self._pre_scan_hooks:
                hook(self, member, global_annotations, parameter_annotations)

            if 'ignore' in global_annotations:
                continue

            ## ------------ method --------------------
            if isinstance(member, (calldef.member_function_t, calldef.member_operator_t)):
                is_virtual = (member.virtuality != calldef.VIRTUALITY_TYPES.NOT_VIRTUAL)
                pure_virtual = (member.virtuality == calldef.VIRTUALITY_TYPES.PURE_VIRTUAL)

                kwargs = {} # kwargs passed into the add_method call

                for key, val in global_annotations.iteritems():
                    if key == 'template_instance_names' \
                            and templates.is_instantiation(member.demangled_name):
                        pass
                    elif key == 'pygen_comment':
                        pass
                    elif key == 'unblock_threads':
                        kwargs['unblock_threads'] = annotations_scanner.parse_boolean(val)
                    elif key == 'name':
                        kwargs['custom_name'] = val
                    elif key == 'throw':
                        kwargs['throw'] = self._get_annotation_exceptions(val)
                    else:
                        warnings.warn_explicit("Annotation '%s=%s' not used (used in %s)"
                                               % (key, val, member),
                                               AnnotationsWarning, member.location.file_name, member.location.line)
                if isinstance(member, calldef.member_operator_t):
                    if member.symbol == '()':
                        kwargs['custom_name'] = '__call__'
                    else:
                        continue

                throw = self._get_calldef_exceptions(member)
                if throw:
                    kwargs['throw'] = throw

                ## --- pygen ---
                return_type_spec = self.type_registry.lookup_return(member.return_type,
                                                                    parameter_annotations.get('return', {}))
                argument_specs = []
                for arg in member.arguments:
                    argument_specs.append(self.type_registry.lookup_parameter(arg.type, arg.name,
                                                                              parameter_annotations.get(arg.name, {}),
                                                                              arg.default_value))
                    
                

                if pure_virtual and not class_wrapper.allow_subclassing:
                    class_wrapper.set_cannot_be_constructed("pure virtual method and subclassing disabled")
                    #self.pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method not wrapped")')

                custom_template_method_name = None
                if templates.is_instantiation(member.demangled_name):
                    template_parameters = templates.args(member.demangled_name)
                    template_instance_names = global_annotations.get('template_instance_names', '')
                    if template_instance_names:
                        for mapping in template_instance_names.split('|'):
                            type_names, name = mapping.split('=>')
                            instance_types = type_names.split(',')
                            if instance_types == template_parameters:
                                custom_template_method_name = name
                                break
                else:
                    template_parameters = ()

                if member.has_const:
                    kwargs['is_const'] = True
                if member.has_static:
                    kwargs['is_static'] = True
                if is_virtual:
                    kwargs['is_virtual'] = True
                if pure_virtual:
                    kwargs['is_pure_virtual'] = True
                if template_parameters:
                    kwargs['template_parameters'] = template_parameters
                if custom_template_method_name:
                    kwargs['custom_template_method_name'] = custom_template_method_name
                if member.access_type != 'public':
                    kwargs['visibility'] = member.access_type

                ## ignore methods that are private and not virtual or
                ## pure virtual, as they do not affect the bindings in
                ## any way and only clutter the generated python script.
                if (kwargs.get('visibility', 'public') == 'private'
                    and not (kwargs.get('is_virtual', False) or kwargs.get('is_pure_virtual', False))):
                    continue

                if member.attributes:
                    if 'deprecated' in member.attributes:
                        kwargs['deprecated'] = True

                ## --- pygen ---
                arglist_repr = ("[" + ', '.join([_pygen_param(args_, kwargs_) for (args_, kwargs_) in argument_specs]) +  "]")
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])

                kwargs_repr = _pygen_kwargs(kwargs)
                if kwargs_repr:
                    kwargs_repr[0] = '\n' + 15*' ' + kwargs_repr[0]

                pygen_sink.writeln("cls.add_method(%s)" %
                                   ", ".join(
                        [repr(member.name),
                         '\n' + 15*' ' + _pygen_retval(return_type_spec[0], return_type_spec[1]),
                         '\n' + 15*' ' + arglist_repr] + kwargs_repr))

                ## --- realize the return type and parameters
                try:
                    return_type = ReturnValue.new(*return_type_spec[0], **return_type_spec[1])
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                           % (member.return_type.partial_decl_string, member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed("pure virtual method not wrapped")
                        class_wrapper.set_helper_class_disabled(True)
                        #self.pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method not wrapped")')
                        #self.pygen_sink.writeln('cls.set_helper_class_disabled(True)')
                    continue
                arguments = []
                ok = True
                for arg in argument_specs:
                    try:
                        arguments.append(Parameter.new(*arg[0], **arg[1]))
                    except (TypeLookupError, TypeConfigurationError), ex:
                        warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                               % (arg[0][0], arg[0][1], member, ex),
                                               WrapperWarning, member.location.file_name, member.location.line)
                        ok = False
                if not ok:
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed("pure virtual method not wrapped")
                        class_wrapper.set_helper_class_disabled(True)
                        #self.pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method not wrapped")')
                        #self.pygen_sink.writeln('cls.set_helper_class_disabled(True)')
                    continue


                try:
                    method_wrapper = class_wrapper.add_method(member.name, return_type, arguments, **kwargs)
                    method_wrapper.gccxml_definition = member
                except NotSupportedError, ex:
                    if pure_virtual:
                        class_wrapper.set_cannot_be_constructed("pure virtual method %r not wrapped" % member.name)
                        class_wrapper.set_helper_class_disabled(True)
                        pygen_sink.writeln('cls.set_cannot_be_constructed("pure virtual method %%r not wrapped" %% %r)'
                                           % member.name)
                        pygen_sink.writeln('cls.set_helper_class_disabled(True)')

                    warnings.warn_explicit("Error adding method %s: %r"
                                           % (member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                except ValueError, ex:
                    warnings.warn_explicit("Error adding method %s: %r"
                                           % (member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                    raise
                else: # no exception, add method succeeded
                    for hook in self._post_scan_hooks:
                        hook(self, member, method_wrapper)
                

            ## ------------ constructor --------------------
            elif isinstance(member, calldef.constructor_t):
                if member.access_type not in ['public', 'protected']:
                    continue

                if not member.arguments:
                    have_trivial_constructor = True

                argument_specs = []
                for arg in member.arguments:
                    argument_specs.append(self.type_registry.lookup_parameter(arg.type, arg.name,
                                                                              default_value=arg.default_value))

                arglist_repr = ("[" + ', '.join([_pygen_param(args_, kwargs_) for (args_, kwargs_) in argument_specs]) +  "]")
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])

                kwargs = {}

                if member.attributes:
                    if 'deprecated' in member.attributes:
                        kwargs['deprecated'] = True

                if member.access_type != 'public':
                    kwargs['visibility'] = member.access_type

                throw = self._get_calldef_exceptions(member)
                if throw:
                    kwargs['throw'] = throw

                kwargs_repr = _pygen_kwargs(kwargs)
                if kwargs_repr:
                    kwargs_repr[0] = '\n' + 20*' '+ kwargs_repr[0]
                pygen_sink.writeln("cls.add_constructor(%s)" %
                                   ", ".join([arglist_repr] + kwargs_repr))

                arguments = []
                for a, kw in argument_specs:
                    try:
                        arguments.append(Parameter.new(*a, **kw))
                    except (TypeLookupError, TypeConfigurationError), ex:
                        warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                               % (arg.type.partial_decl_string, arg.name, member, ex),
                                               WrapperWarning, member.location.file_name, member.location.line)
                        ok = False
                        break
                else:
                    ok = True
                if not ok:
                    continue
                constructor_wrapper = class_wrapper.add_constructor(arguments, **kwargs)
                constructor_wrapper.gccxml_definition = member
                for hook in self._post_scan_hooks:
                    hook(self, member, constructor_wrapper)

                if (len(arguments) == 1
                    and isinstance(arguments[0], class_wrapper.ThisClassRefParameter)):
                    have_copy_constructor = True

            ## ------------ attribute --------------------
            elif isinstance(member, variable_t):
                if not member.name:
                    continue # anonymous structure
                if member.access_type == 'protected':
                    warnings.warn_explicit("%s: protected member variables not yet implemented "
                                           "by PyBindGen."
                                           % member,
                                           NotSupportedWarning, member.location.file_name, member.location.line)
                    continue
                if member.access_type == 'private':
                    continue

                real_type = type_traits.remove_declarated(member.type)
                if hasattr(real_type, 'name') and not real_type.name:
                    warnings.warn_explicit("Member variable %s of class %s will not be wrapped, "
                                           "because wrapping member variables of anonymous types "
                                           "is not yet supported by pybindgen"
                                           % (member.name, cls.partial_decl_string),
                                           NotSupportedWarning, member.location.file_name, member.location.line)
                    continue

                return_type_spec = self.type_registry.lookup_return(member.type, global_annotations)

                ## pygen...
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                if member.type_qualifiers.has_static:
                    pygen_sink.writeln("cls.add_static_attribute(%r, %s, is_const=%r)" %
                                       (member.name, _pygen_retval(*return_type_spec),
                                        type_traits.is_const(member.type)))
                else:
                    pygen_sink.writeln("cls.add_instance_attribute(%r, %s, is_const=%r)" %
                                       (member.name, _pygen_retval(*return_type_spec),
                                        type_traits.is_const(member.type)))
                    
                ## convert the return value
                try:
                    return_type = ReturnValue.new(*return_type_spec[0], **return_type_spec[1])
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                           % (member.type.partial_decl_string, member, ex),
                                           WrapperWarning, member.location.file_name, member.location.line)
                    continue

                if member.type_qualifiers.has_static:
                    class_wrapper.add_static_attribute(member.name, return_type,
                                                       is_const=type_traits.is_const(member.type))
                else:
                    class_wrapper.add_instance_attribute(member.name, return_type,
                                                         is_const=type_traits.is_const(member.type))
                ## TODO: invoke post_scan_hooks
            elif isinstance(member, calldef.destructor_t):
                pass

        ## gccxml 0.9, unlike 0.7, does not explicitly report inheritted trivial constructors
        ## thankfully pygccxml comes to the rescue!
        if not have_trivial_constructor:
            if type_traits.has_trivial_constructor(cls):
                class_wrapper.add_constructor([])
                pygen_sink.writeln("cls.add_constructor([])")
                
        if not have_copy_constructor:
            try: # pygccxml > 0.9
                has_copy_constructor = type_traits.has_copy_constructor(cls)
            except AttributeError: # pygccxml <= 0.9
                has_copy_constructor = type_traits.has_trivial_copy(cls)
            if has_copy_constructor:
                class_wrapper.add_copy_constructor()
                pygen_sink.writeln("cls.add_copy_constructor()")
                

    def _get_calldef_exceptions(self, calldef):
        retval = []
        for decl in calldef.exceptions:
            traits = ctypeparser.TypeTraits(normalize_name(decl.partial_decl_string))
            if traits.type_is_reference:
                name = str(traits.target)
            else:
                name = str(traits.ctype)
            exc = self.type_registry.root_module.get(name, None)
            if isinstance(exc, CppException):
                retval.append(exc)
            else:
                warnings.warn_explicit("Thrown exception '%s' was not previously detected as an exception class."
                                       " PyBindGen bug?"
                                       % (normalize_name(decl.partial_decl_string)),
                                       WrapperWarning, calldef.location.file_name, calldef.location.line)
        return retval

    def _get_annotation_exceptions(self, annotation):
        retval = []
        for exc_name in annotation.split(','):
            traits = ctypeparser.TypeTraits(normalize_name(exc_name))
            if traits.type_is_reference:
                name = str(traits.target)
            else:
                name = str(traits.ctype)
            exc = self.type_registry.root_module.get(name, None)
            if isinstance(exc, CppException):
                retval.append(exc)
            else:
                warnings.warn_explicit("Thrown exception '%s' was not previously detected as an exception class."
                                       " PyBindGen bug?"
                                       % (normalize_name(decl.partial_decl_string)),
                                       WrapperWarning, calldef.location.file_name, calldef.location.line)
        return retval

    def scan_functions(self):
        self._stage = 'scan functions'
        assert self._types_scanned
        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("def register_functions(root_module):")
            pygen_sink.indent()
            pygen_sink.writeln("module = root_module")
            if pygen_sink is self._get_main_pygen_sink() and isinstance(self._pygen, list):
                for section in self._pygen:
                    if section.name == '__main__':
                        continue
                    pygen_sink.writeln("root_module.begin_section(%r)" % section.name)
                    pygen_sink.writeln("%s.register_functions(root_module)" % section.name)
                    if section.local_customizations_module:
                        pygen_sink.writeln("\ntry:\n"
                                           "    import %s\n"
                                           "except ImportError:\n"
                                           "    pass\n"
                                           "else:\n"
                                           "    %s.register_functions(root_module)\n"
                                           % (section.local_customizations_module, section.local_customizations_module))
                    pygen_sink.writeln("root_module.end_section(%r)" % section.name)
        self._scan_namespace_functions(self.module, self.module_namespace)
            
    def _scan_namespace_functions(self, module, module_namespace):
        root_module = module.get_root()

        functions_to_scan = []
        for fun in module_namespace.free_functions(function=self.location_filter,
                                                   allow_empty=True, recursive=False):
            if fun.name.startswith('__'):
                continue
            functions_to_scan.append(fun)

        def fun_cmp(a, b):
            name_cmp = cmp(a.name, b.name)
            # if function names differ, compare by name, else compare by the full declaration
            if name_cmp != 0:
                return name_cmp
            else:
                return cmp(a.decl_string, b.decl_string)
        functions_to_scan.sort(fun_cmp)

        for fun in functions_to_scan:
            global_annotations, parameter_annotations = annotations_scanner.get_annotations(fun)
            for hook in self._pre_scan_hooks:
                hook(self, fun, global_annotations, parameter_annotations)

            as_method = None
            of_class = None
            alt_name = None
            ignore = False
            kwargs = {}

            for name, value in global_annotations.iteritems():
                if name == 'as_method':
                    as_method = value
                elif name == 'of_class':
                    of_class = value
                elif name == 'name':
                    alt_name = value
                elif name == 'ignore':
                    ignore = True
                elif name == 'is_constructor_of':
                    pass
                elif name == 'pygen_comment':
                    pass
                elif name == 'template_instance_names':
                    pass
                elif name == 'unblock_threads':
                    kwargs['unblock_threads'] = annotations_scanner.parse_boolean(value)
                elif name == 'throw':
                    kwargs['throw'] = self._get_annotation_exceptions(value)
                else:
                    warnings.warn_explicit("Incorrect annotation %s=%s" % (name, value),
                                           AnnotationsWarning, fun.location.file_name, fun.location.line)
            if ignore:
                continue


            is_constructor_of = global_annotations.get("is_constructor_of", None)
            return_annotations = parameter_annotations.get('return', {})
            if is_constructor_of:
                return_annotations['caller_owns_return'] = 'true'

            params_ok = True
            return_type_spec = self.type_registry.lookup_return(fun.return_type, return_annotations)
            try:
                return_type = ReturnValue.new(*return_type_spec[0], **return_type_spec[1])
            except (TypeLookupError, TypeConfigurationError), ex:
                warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                       % (fun.return_type.partial_decl_string, fun, ex),
                                       WrapperWarning, fun.location.file_name, fun.location.line)
                params_ok = False
            except TypeError, ex:
                warnings.warn_explicit("Return value '%s' error (used in %s): %r"
                                       % (fun.return_type.partial_decl_string, fun, ex),
                                       WrapperWarning, fun.location.file_name, fun.location.line)
                raise
            argument_specs = []
            arguments = []
            for argnum, arg in enumerate(fun.arguments):
                annotations = parameter_annotations.get(arg.name, {})
                if argnum == 0 and as_method is not None \
                        and isinstance(arg.type, cpptypes.pointer_t):
                    annotations.setdefault("transfer_ownership", "false")
                    
                spec = self.type_registry.lookup_parameter(arg.type, arg.name,
                                                           annotations,
                                                           default_value=arg.default_value)
                argument_specs.append(spec)
                try:
                    arguments.append(Parameter.new(*spec[0], **spec[1]))
                except (TypeLookupError, TypeConfigurationError), ex:
                    warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                           % (arg.type.partial_decl_string, arg.name, fun, ex),
                                           WrapperWarning, fun.location.file_name, fun.location.line)

                    params_ok = False
                except TypeError, ex:
                    warnings.warn_explicit("Parameter '%s %s' error (used in %s): %r"
                                           % (arg.type.partial_decl_string, arg.name, fun, ex),
                                           WrapperWarning, fun.location.file_name, fun.location.line)
                    raise

            throw = self._get_calldef_exceptions(fun)
            if throw:
                kwargs['throw'] = throw

            arglist_repr = ("[" + ', '.join([_pygen_param(*arg)  for arg in argument_specs]) +  "]")
            retval_repr = _pygen_retval(*return_type_spec)

            if as_method is not None:
                assert of_class is not None
                cpp_class = root_module[normalize_class_name(of_class, (self.module_namespace_name or '::'))]

                pygen_sink = self._get_pygen_sink_for_definition(fun)
                if pygen_sink:
                    if 'pygen_comment' in global_annotations:
                        pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                    pygen_sink.writeln("root_module[%r].add_function_as_method(%s, custom_name=%r)" %
                                       (cpp_class.full_name,
                                        ", ".join([repr(fun.name), retval_repr, arglist_repr]),
                                        as_method))
                if params_ok:
                    function_wrapper = cpp_class.add_function_as_method(fun.name, return_type, arguments, custom_name=as_method)
                    function_wrapper.gccxml_definition = fun

                continue

            if is_constructor_of is not None:
                #cpp_class = type_registry.find_class(is_constructor_of, (self.module_namespace_name or '::'))
                cpp_class = root_module[normalize_class_name(is_constructor_of, (self.module_namespace_name or '::'))]

                pygen_sink = self._get_pygen_sink_for_definition(fun)
                if pygen_sink:
                    if 'pygen_comment' in global_annotations:
                        pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                    pygen_sink.writeln("root_module[%r].add_function_as_constructor(%s)" %
                                       (cpp_class.full_name,
                                        ", ".join([repr(fun.name), retval_repr, arglist_repr]),))

                if params_ok:
                    function_wrapper = cpp_class.add_function_as_constructor(fun.name, return_type, arguments)
                    function_wrapper.gccxml_definition = fun

                continue

            if templates.is_instantiation(fun.demangled_name):
                template_parameters = templates.args(fun.demangled_name)
                kwargs['template_parameters'] = template_parameters
                template_instance_names = global_annotations.get('template_instance_names', '')
                if template_instance_names:
                    for mapping in template_instance_names.split('|'):
                        type_names, name = mapping.split('=>')
                        instance_types = type_names.split(',')
                        if instance_types == template_parameters:
                            kwargs['custom_name'] = name
                            break
                
            if alt_name:
                kwargs['custom_name'] = alt_name

            if fun.attributes:
                if 'deprecated' in fun.attributes:
                    kwargs['deprecated'] = True

            pygen_sink = self._get_pygen_sink_for_definition(fun)
            if pygen_sink:
                if 'pygen_comment' in global_annotations:
                    pygen_sink.writeln('## ' + global_annotations['pygen_comment'])
                kwargs_repr = _pygen_kwargs(kwargs)
                if kwargs_repr:
                    kwargs_repr[0] = "\n" + 20*' ' + kwargs_repr[0]
                pygen_sink.writeln("module.add_function(%s)" %
                                   (", ".join([repr(fun.name),
                                               "\n" + 20*' ' + retval_repr,
                                               "\n" + 20*' ' + arglist_repr]
                                              + kwargs_repr)))

            if params_ok:
                func_wrapper = module.add_function(fun.name, return_type, arguments, **kwargs)
                func_wrapper.gccxml_definition = fun
                for hook in self._post_scan_hooks:
                    hook(self, fun, func_wrapper)


        ## scan nested namespaces (mapped as python submodules)
        nested_namespaces = []
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            if nested_namespace.name.startswith('__'):
                continue
            nested_namespaces.append(nested_namespace)

        def decl_cmp(a, b):
            return cmp(a.decl_string, b.decl_string)
        nested_namespaces.sort(decl_cmp)
        
        for nested_namespace in nested_namespaces:
            nested_module = module.get_submodule(nested_namespace.name)
            nested_module_pygen_func = "register_functions_" + "_".join(nested_module.get_namespace_path())
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.writeln("%s(module.get_submodule(%r), root_module)" %
                                   (nested_module_pygen_func, nested_namespace.name))

        for pygen_sink in self._get_all_pygen_sinks():
            pygen_sink.writeln("return")
            pygen_sink.unindent()
            pygen_sink.writeln()
    
        nested_namespaces = []
        for nested_namespace in module_namespace.namespaces(allow_empty=True, recursive=False):
            if nested_namespace.name.startswith('__'):
                continue
            nested_namespaces.append(nested_namespace)

        def decl_cmp(a, b):
            return cmp(a.decl_string, b.decl_string)
        nested_namespaces.sort(decl_cmp)

        for nested_namespace in nested_namespaces:
            nested_module = module.get_submodule(nested_namespace.name)
            nested_module_pygen_func = "register_functions_" + "_".join(nested_module.get_namespace_path())
            for pygen_sink in self._get_all_pygen_sinks():
                pygen_sink.writeln("def %s(module, root_module):" % nested_module_pygen_func)
                pygen_sink.indent()

            self._scan_namespace_functions(nested_module, nested_namespace)


def _test():
    module_parser = ModuleParser('foo', '::')
    module = module_parser.parse(sys.argv[1:])
    if 0:
        out = FileCodeSink(sys.stdout)
        module.generate(out)

if __name__ == '__main__':
    _test()
