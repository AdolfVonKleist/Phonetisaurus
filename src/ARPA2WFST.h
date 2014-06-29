/*
 ARPA2WFST.hpp

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
#ifndef ARPA2WFST_H
#define ARPA2WFST_H
#include <float.h>
#include <fst/fstlib.h>
#include "util.h"
using namespace fst;

class ARPA2WFST {
  /*
      Transform a statistical language model in ARPA format
      to an equivalent Weighted Finite-State Acceptor.
      This implementation adopts the Google format for the output
      WFSA.  This differs from previous implementations in several ways:

       Start-state and <s> arcs:
       * There are no explicit sentence-begin (<s>) arcs
       * There is a single <s> start-state.

       Final-state and </s> arcs:
       * There are no explicit sentence-end (</s>) arcs
       * There is no explicit </s> state
       * NGrams ending in </s> are designated as final
            states, and any probability is assigned 
            to the final weight of said state.
  */  
	
public: 
  ifstream   arpa_lm_fp;
  string     arpa_lm_file;
  string     line;
  size_t     max_order;
  size_t     current_order;

  //Default values
  string     eps;      //epsilon symbol
  string     sb;       //sentence begin tag
  string     se;       //sentence end tag
  string     split;    //delimiter separating input/output syms in G2P ARPA file
  string     skip;     //graphemic null
  string     tie;      //tie for clusters

  //WFST stuff
  VectorFst<StdArc>  arpafst;
  SymbolTable*   ssyms;
  SymbolTable*   isyms;
  SymbolTable*   osyms;
	
  ARPA2WFST( );
  
  ARPA2WFST ( string _lm, string _eps, string _sb, string _se, string _split, string _skip, string _tie );
	
  void arpa_to_wfst ( );

private:
  double log10_2tropical( double val );
	
  void _make_arc( string istate, string ostate, string isym, double weight );

  void _make_final( string fstate, double weight );

  string _join( vector<string>::iterator start, vector<string>::iterator end );

  void _patch_ilabels( );
};

#endif // ARPA2WFST_H //

