/*
 PhonetisaurusOmega.hpp 

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
#ifndef PHONETISAURUSOMEGA_H
#define PHONETISAURUSOMEGA_H
#include <fst/fstlib.h>
#include "LatticePruner.hpp"
#include "MBRDecoder.hpp"
#include "PhonetisaurusE2F.hpp"
using namespace fst;
typedef PhiMatcher<SortedMatcher<Fst<StdArc> > > PM;

class PhonetisaurusOmega {
    /*
     Load a G2P/P2G model and generate pronunciation/spelling
     hypotheses for input items.
    */

public:
  string    skip;
  string    tie;
  string    decoder_type;
  bool      logopt;
  bool      lmbr;
  bool      allow_ins;
  int       beam;
  int       nbest;
  int       verbose;
  set<int>  skipSeqs;
  int       order;
  float     alpha;
  float     prec;
  float     ratio;
  float     thresh;
  PhonetisaurusE2F* e2f;
  vector<float> thetas;
  map<vector<string>, size_t>   clusters;
  map<size_t, vector<string> >   oclusters;
  EncodeMapper<StdArc>* encoder;
  VectorFst<StdArc>*    g2pmodel;
  VectorFst<StdArc>*    loop;
  VectorFst<StdArc>     filter;
  VectorFst<StdArc>     ofilter;
  VectorFst<StdArc>     word;
  SymbolTable           isyms;
  SymbolTable           osyms;
        
  PhonetisaurusOmega( );
        
  PhonetisaurusOmega( const char* _g2pmodel_file, string _decoder_type, 
		      bool _logopt, int _beam, int _nbest, bool _lmbr, 
		      int _order, float _alpha, float _prec, 
		      float _ratio, int _verbose, bool _allow_ins, float _thresh );

  VectorFst<StdArc> phoneticize( vector<string>* tokens, bool _project=true );
  VectorFst<StdArc>* decode( );

private:
  void _extract_hypotheses( vector<string>* tokens );
  int  _compute_thetas( int wlen );

  //FSA-based phi-compatible composition modifications
  void _phiify_fst( VectorFst<StdArc>* fst );
  void _add_arcs( VectorFst<StdArc>* fst, size_t orig_st, size_t st, pair<size_t,size_t> p, double cost);
  void _get_gp( VectorFst<StdArc>* fst, map<size_t, set<size_t> >* gp );
  //Alternative phi-ify method
  void _phi_ify( );
  StdArc::Weight _get_final_bow( StdArc::StateId st );
};

#endif // PHONETISAURUSOMEGA_H //
