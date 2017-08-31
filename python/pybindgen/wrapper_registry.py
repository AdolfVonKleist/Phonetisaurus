"""
The class that generates code to keep track of existing python
wrappers for a given root class.
"""

from typehandlers.base import NotSupportedError


class WrapperRegistry(object):
    """
    Abstract base class for wrapepr registries.
    """

    def __init__(self, base_name):
        self.base_name = base_name

    def generate_forward_declarations(self, code_sink, module):
        raise NotImplementedError

    def generate(self, code_sink, module, import_from_module):
        raise NotImplementedError

    def write_register_new_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        raise NotImplementedError
        
    def write_lookup_wrapper(self, code_block, wrapper_type, wrapper_lvalue, object_rvalue):
        raise NotImplementedError

    def write_unregister_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        raise NotImplementedError

    
class NullWrapperRegistry(WrapperRegistry):
    """
    A 'null' wrapper registry class.  It produces no code, and does
    not guarantee that more than one wrapper cannot be created for
    each object.  Use this class to disable wrapper registries entirely.
    """

    def __init__(self, base_name):
        super(NullWrapperRegistry, self).__init__(base_name)

    def generate_forward_declarations(self, code_sink, module, import_from_module):
        pass

    def generate(self, code_sink, module):
        pass
    def generate_import(self, code_sink, module, import_from_module):
        pass

    def write_register_new_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        pass
        
    def write_lookup_wrapper(self, code_block, wrapper_type, wrapper_lvalue, object_rvalue):
        raise NotSupportedError

    def write_unregister_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        pass


class StdMapWrapperRegistry(WrapperRegistry):
    """
    A wrapper registry that uses std::map as implementation.  Do not
    use this if generating pure C wrapping code, else the code will
    not compile.
    """


    def __init__(self, base_name):
        super(StdMapWrapperRegistry, self).__init__(base_name)
        self.map_name = "%s_wrapper_registry" % base_name

    def generate_forward_declarations(self, code_sink, module, import_from_module):
        module.add_include("<map>")
        module.add_include("<iostream>")
        #code_sink.writeln("#include <map>")
        #code_sink.writeln("#include <iostream>")
        if import_from_module:
            code_sink.writeln("extern std::map<void*, PyObject*> *_%s;" % self.map_name)
            code_sink.writeln("#define %s (*_%s)" % (self.map_name, self.map_name))
        else:
            code_sink.writeln("extern std::map<void*, PyObject*> %s;" % self.map_name)

    def generate(self, code_sink, module):
        code_sink.writeln("std::map<void*, PyObject*> %s;" % self.map_name)
        # register the map in the module namespace
        module.after_init.write_code("PyModule_AddObject(m, (char *) \"_%s\", PyCObject_FromVoidPtr(&%s, NULL));"
                                     % (self.map_name, self.map_name))

    def generate_import(self, code_sink, code_block, module_pyobj_var):
        code_sink.writeln("std::map<void*, PyObject*> *_%s;" % self.map_name)
        code_block.write_code("PyObject *_cobj = PyObject_GetAttrString(%s, (char*) \"_%s\");"
                              % (module_pyobj_var, self.map_name))
        code_block.write_code("if (_cobj == NULL) {\n"
                              "    _%(MAP)s = NULL;\n"
                              "    PyErr_Clear();\n"
                              "} else {\n"
                              "    _%(MAP)s = reinterpret_cast< std::map<void*, PyObject*> *> (PyCObject_AsVoidPtr (_cobj));\n"
                              "    Py_DECREF(_cobj);\n"
                              "}"
                              % dict(MAP=self.map_name))

    def write_register_new_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        code_block.write_code("%s[(void *) %s] = (PyObject *) %s;" % (self.map_name, object_rvalue, wrapper_lvalue))
        #code_block.write_code('std::cerr << "Register Wrapper: obj=" <<(void *) %s << ", wrapper=" << %s << std::endl;'
        #                      % (object_rvalue, wrapper_lvalue))
        
    def write_lookup_wrapper(self, code_block, wrapper_type, wrapper_lvalue, object_rvalue):
        iterator = code_block.declare_variable("std::map<void*, PyObject*>::const_iterator", "wrapper_lookup_iter")
        #code_block.write_code('std::cerr << "Lookup Wrapper: obj=" <<(void *) %s << " map size: " << %s.size() << std::endl;'
        #                      % (object_rvalue, self.map_name))
        code_block.write_code("%s = %s.find((void *) %s);" % (iterator, self.map_name, object_rvalue))
        code_block.write_code("if (%(ITER)s == %(MAP)s.end()) {\n"
                              "    %(WRAPPER)s = NULL;\n"
                              "} else {\n"
                              "    %(WRAPPER)s = (%(TYPE)s *) %(ITER)s->second;\n"
                              "    Py_INCREF(%(WRAPPER)s);\n"
                              "}\n"
                              % dict(ITER=iterator, MAP=self.map_name, WRAPPER=wrapper_lvalue, TYPE=wrapper_type))
        
    def write_unregister_wrapper(self, code_block, wrapper_lvalue, object_rvalue):
        #code_block.write_code('std::cerr << "Erase Wrapper: obj=" <<(void *) %s << std::endl;'
        #                      % (object_rvalue))
        iterator = code_block.declare_variable("std::map<void*, PyObject*>::iterator", "wrapper_lookup_iter")
        code_block.write_code("%(ITER)s = %(MAP)s.find((void *) %(WRAPPER)s->obj);\n"
                              "if (%(ITER)s != %(MAP)s.end()) {\n"
                              "    %(MAP)s.erase(%(ITER)s);\n"
                              "}\n"
                              % dict(ITER=iterator, MAP=self.map_name, WRAPPER=wrapper_lvalue))

