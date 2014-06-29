# rnnlm-module.py
#
# Copyright (c) [2014-], Yandex, LLC
# Author: jorono@yandex-team.ru (Josef Robert Novak)
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted #provided that the following conditions
#   are met:
#
#   * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above
#   copyright notice, this list of #conditions and the following
#   disclaimer in the documentation and/or other materials provided
#   with the distribution.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#   FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
#   COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
#   INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#   (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#   SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
#   HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
#   STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#   ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
#   OF THE POSSIBILITY OF SUCH DAMAGE.
#
#
# \file
# Python bindings for RnnLM.  These only correspond
# to basic evaluation functions, not training. By default
# the evaluations utilizes the -independent convention from
# the original rnnlm tool.  This is all we are interested in
# for G2P evaluations.
# Specifically this is the generator code for pybindgen.
import pybindgen
from pybindgen import param, retval
import sys

mod = pybindgen.Module ('RnnLM')
mod.add_container ('std::vector<std::string>', 'std::string', 'vector')
mod.add_container ('std::vector<double>', 'double', 'vector')
struct = mod.add_struct ('UttResult')
struct.add_constructor ([])
struct.add_instance_attribute ('sent_prob', 'double')
struct.add_instance_attribute ('word_probs', 'std::vector<double>')
struct.add_instance_attribute ('words', 'std::vector<std::string>')

mod.add_include ('"RnnLMPy.h"')
klass = mod.add_class ('RnnLMPy')
klass.add_constructor ([
        param ('std::string', 'rnnlm_file')
])
klass.add_method (
     'EvaluateSentence', retval ('UttResult'),
     [param ('std::vector<std::string>', 'words')]
    )

mod.generate (sys.stdout)
