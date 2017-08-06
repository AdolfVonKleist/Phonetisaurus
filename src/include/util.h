#ifndef SRC_INCLUDE_UTIL_H_
#define SRC_INCLUDE_UTIL_H_
/*
 Copyright (c) [2012-], Josef Robert Novak
 All rights reserved.

 Redistribution and use in source and binary forms, with or without
  modification, are permitted #provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.
  * Redistributions in binary form must reproduce the above
    copyright notice, this list of #conditions and the following
    disclaimer in the documentation and/or other materials provided
    with the distribution.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
 INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
 OF THE POSSIBILITY OF SUCH DAMAGE.
*
*/
#include <fst/fstlib.h>
#include <utf8.h>
#include <unordered_map>
#include <string>
#include <vector>
#ifdef __MACH__
#include <mach/clock.h>
#include <mach/mach.h>
#endif
using namespace fst;

typedef struct LabelDatum {int max, tot, lhs, rhs; bool lhsE, rhsE;} LabelDatum;
typedef unordered_map<LogArc::Label, LabelDatum> LabelData;

string vec2str (vector<string> vec, string sep);

string itoas (int i);

vector<string> tokenize_utf8_string (string* utf8_string, string* delimiter);

vector<string> tokenize_entry (string* testword, string* sep,
                               SymbolTable* syms);

vector<int> tokenize2ints (string* word, string* sep, const SymbolTable* syms);

timespec get_time( );

timespec diff (timespec start, timespec end);

void PhonetisaurusSetFlags (const char* usage, int* argc, char*** argv,
                            bool remove_flags);

void LoadWordList (const std::string& filename,
                   std::vector<std::string>* corpus);

void Split (const std::string& s, char delim, std::vector<std::string>& elems);

#endif  // SRC_INCLUDE_UTIL_H_
