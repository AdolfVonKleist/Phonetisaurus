/*
 PhonetisaurusE2F.hpp 

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
#ifndef PHONETISAURUSE2F_H
#define PHONETISAURUSE2F_H
#include <fst/fstlib.h>
using namespace fst;

class PhonetisaurusE2F {
    /*
      Generate an FSA/FST representation of an
      input word, based on a variety of user supplied
      configuration parameters
    */

public:
  string    skip;
  string    tie;
  bool      allow_ins;
  //bool      fsa_phi;
  int       verbose;
  map<vector<string>, size_t>*    iclusters;
  map<size_t, vector<string> >*   oclusters;
  map<size_t, vector<size_t> >*   i2omap;
  VectorFst<StdArc>*    loop;
  VectorFst<StdArc>     ifilter;
  VectorFst<StdArc>     ofilter;
  VectorFst<StdArc>     word;
  const SymbolTable*    isyms;
  const SymbolTable*    osyms;
        
  PhonetisaurusE2F( );
        
  PhonetisaurusE2F( const EncodeTable<StdArc>& table, int _verbose, bool _allow_ins, 
		    const SymbolTable* _isyms, const SymbolTable* _osyms
		    );

  PhonetisaurusE2F( int _verbose, bool _allow_ins, 
		    const SymbolTable* _isyms, const SymbolTable* _osyms
		    );

  void entry_to_fsa_w( vector<string>* tokens );

  void entry_to_fsa_m( vector<string>* tokens );

  void entry_to_fst_w( vector<string>* tokens );

  void entry_to_fst_m( vector<string>* tokens );

  void _entry_to_skip_fsa( vector<string>* tokens );

  //void _make_fsa_phi_filter( );

private:
  void _make_loop( );
  void _make_ifilter( );
  void _load_iclusters( );
  void _make_loop_and_iomap( const EncodeTable<StdArc>& table );
};

#endif // PHONETISAURUSE2F_H //
