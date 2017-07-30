import pybindgen
from pybindgen import param, retval
import sys

mod = pybindgen.Module ('Phonetisaurus')
################################################
#PhonetisaurusOmega decoder wrapper
mod.add_include ('"include/PhonetisaurusScript.h"')

#Build up the basic bits for the PathData return object
mod.add_container ('std::vector<int>', 'int', 'vector')
mod.add_container ('std::vector<float>', 'float', 'vector')

#Register the PathDataPy struct
struct = mod.add_struct('PathData')
struct.add_constructor([]) 
struct.add_instance_attribute ('PathWeight', 'float')
struct.add_instance_attribute ('PathWeights', 'std::vector<float>')
struct.add_instance_attribute ('ILabels', 'std::vector<int>')
struct.add_instance_attribute ('OLabels', 'std::vector<int>')
struct.add_instance_attribute ('Uniques', 'std::vector<int>')

#Register the vector<PathData> container
mod.add_container ('std::vector<PathData>', 'PathData', 'vector' )

g2pklass = mod.add_class ('PhonetisaurusScript')
std_exception = mod.add_exception ('exception',
                                   foreign_cpp_namespace='std',
                                   message_rvalue='%(EXC)s.what()')

g2pklass.add_constructor ([param ('std::string', 'model')],
                          throw=[std_exception])

g2pklass.add_method ('Phoneticize', retval ('std::vector<PathData>'),
                    [ param ('std::string', 'word'),
                      param ('int', 'nbest'),
                      param ('int', 'beam'),
                      param ('float', 'threshold'),
                      param ('bool', 'write_fsts'),
                      param ('bool', 'accumulate'),
                      param ('float', 'pmass')
                  ]
                )

# Helper methods for the symbol lookup
g2pklass.add_method ('FindIsym', retval ('std::string'),
                    [param ('int', 'symbol_id')])
g2pklass.add_method ('FindIsym', retval('int'),
                    [param ('std::string', 'symbol')])
g2pklass.add_method ('FindOsym', retval('std::string'),
                    [param ('int', 'symbol_id')])
g2pklass.add_method ('FindOsym', retval('int'),
                    [param ('std::string', 'symbol')])



mod.generate (sys.stdout)
