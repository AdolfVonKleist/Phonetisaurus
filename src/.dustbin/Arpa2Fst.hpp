/*
 Arpa2Fst.hpp

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
#ifndef ARPA2FST_H
#define ARPA2FST_H
/*
 *  LanguageModel.hpp
 *  openPhone-proj
 *
 *  Created by Joe Novak on 11/02/18.
 *  Copyright 2011 __MyCompanyName__. All rights reserved.
 *
 */
#include <float.h>
#include <fst/fstlib.h>
#include "util.hpp"
using namespace fst;

class Arpa2OpenFST {
	/*
	 Convert an arbitrary ARPA format N-gram language model of 
	 order N to an equivalent OpenFST-based WFST.
	 
	 -- Back-off weights are handled as normal epsilon-arcs
	 
	 -- Any 'missing' back-offs are automatically set to '0.0'
	 however the actual value should be semiring dependent.
	 
	 -- Completely missing lower-order N-grams will be ignored.  
	 In some interpolated models this seems to occasionally lead to 
	 non-coaccessible states.  Other possible options might be to
	 -*- Generate the missing N-grams (but this seems wrong)
	 -*- Force the higher-order N-gram to sentence-end
	 
	 -- In this simple implementation the names for the symbols tables 
	 are fixed to 'ssyms', 'isyms', and 'osyms'.  The default epsilon
	 symbol is '<eps>' but can be set to whatever the user prefers.
	 */  
	
public: 
  ifstream   arpa_lm_fp;
  string     arpa_lm_file;
  string     line;
  size_t     max_order;
  size_t     current_order;

  //default values set
  string     eps;      //epsilon symbol
  string     split;    //split delimiter for multi-tokens
  string     phi;      //phi symbol (not currently used)
  string     start;    //start tag
  string     sb;       //sentence begin tag
  string     se;       //sentence end tag
  string     delim;    //delimiter separating input/output syms in G2P ARPA file
  string     null_sep; //graphemic null

  //FST stuff
  VectorFst<StdArc>  arpafst;
  SymbolTable*   ssyms;
  SymbolTable*   isyms;
  SymbolTable*   osyms;
	
	
  Arpa2OpenFST( );
  
  Arpa2OpenFST ( string arpa_lm, string _eps, string _phi, string _split,
		 string _start, string _sb, string _se, string _delim, string _null_sep );
	
  double log10_2tropical( double val );
	
  void make_arc( string istate, string ostate, string isym, string osym, double weight );
	
  string join( vector<string> &tokens, string sep, int start, int end );
	
  void generateFST ( );
	
};

#endif // ARPA2FST_H //

