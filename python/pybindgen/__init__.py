
from typehandlers.base import ReturnValue, Parameter
from module import Module
from function import Function
from typehandlers.codesink import CodeSink, FileCodeSink
from cppclass import CppMethod, CppClass, CppConstructor
from enum import Enum
from utils import write_preamble, param, retval
import version

import logging
#logging.basicConfig(level=logging.DEBUG)
del logging
