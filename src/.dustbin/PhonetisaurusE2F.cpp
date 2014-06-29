/*
 *  Phonetisaurus.cpp 
 *  
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
#include "PhonetisaurusE2F.hpp"

PhonetisaurusE2F::PhonetisaurusE2F( ) {
    //Default constructor
}

PhonetisaurusE2F::PhonetisaurusE2F( int _verbose, bool _allow_ins,
				    const SymbolTable* _isyms, const SymbolTable* _osyms
				    ){
  /* 
     This version can only use the FSA-based approaches
       entry_to_fsa_w()
       entry_to_fsa_m()
  */
  verbose   = _verbose;
  allow_ins = _allow_ins;
  //Have to make a copy in case we encode the model
  isyms = _isyms;
  osyms = _osyms;
  iclusters = new map<vector<string>, size_t>();
  oclusters = new map<size_t, vector<string> >();
  i2omap    = new map<size_t, vector<size_t> >();
  tie  = isyms->Find(1); //The separator symbol is reserved for index 1
  skip = isyms->Find(2); //The del/ins character is reserved for index 2
  
  _load_iclusters( );
  _make_ifilter( );

}

PhonetisaurusE2F::PhonetisaurusE2F( const EncodeTable<StdArc>& table, int _verbose, bool _allow_ins,
				    const SymbolTable* _isyms, const SymbolTable* _osyms
				    ){
  /* 
     This version can both the FSA and FST-based approaches via the Encode table.
       entry_to_fsa_w()
       entry_to_fsa_m()
       entry_to_fst_w()
       entry_to_fst_m()
  */
  verbose   = _verbose;
  allow_ins = _allow_ins;
  //fsa_phi   = _fsa_phi;
  //Have to make a copy in case we encode the model
  isyms = _isyms;
  osyms = _osyms;
  iclusters = new map<vector<string>, size_t>();
  oclusters = new map<size_t, vector<string> >();
  i2omap    = new map<size_t, vector<size_t> >();
  tie  = isyms->Find(1); //The separator symbol is reserved for index 1
  skip = isyms->Find(2); //The del/ins character is reserved for index 2
  
  _load_iclusters( );
  _make_ifilter( );
  _make_loop_and_iomap( table );

}

void PhonetisaurusE2F::entry_to_fsa_w( vector<string>* tokens ){
  /*
    Convert an input grapheme sequence to an equivalent
    Finite-State Machine.
  */

  //Build a linear FSA representing the input
  _entry_to_skip_fsa( tokens );

  //Add any multi-grapheme arcs
  word = VectorFst<StdArc>(ComposeFst<StdArc>(word,ifilter));
  Project(&word, PROJECT_OUTPUT);

  //Now optimize the result
  RmEpsilon(&word);
  ArcSort(&word,OLabelCompare<StdArc>());

  return;
}

void PhonetisaurusE2F::entry_to_fst_w( vector<string>* tokens ){
  /*
    Convert an input grapheme sequence to an equivalent
    Finite-State Machine.
  */

  //Build a linear FSA representing the input
  _entry_to_skip_fsa( tokens );

  //Add any multi-grapheme arcs
  word = VectorFst<StdArc>(ComposeFst<StdArc>(word,ifilter));
  Project(&word, PROJECT_OUTPUT);

  //Now optimize the result
  ArcSort(&word,OLabelCompare<StdArc>());
  RmEpsilon(&word);
  word = VectorFst<StdArc>(ComposeFst<StdArc>(word,*loop));
  return;
}
             
//STEP 1: Create a linear FSA with skip loops
void PhonetisaurusE2F::_entry_to_skip_fsa( vector<string>* tokens ){
  word = VectorFst<StdArc>();
  word.AddState();
  word.SetStart(0);

  size_t i=0;
  for( i=0; i<tokens->size(); i++){
    word.AddState();
    string ch = tokens->at(i);
    word.AddArc( i, 
		 StdArc( 
			isyms->Find(ch), 
			isyms->Find(ch), 
			StdArc::Weight::One(), i+1 
			 )
		 );
    //If phoneme insertions are to be allowed
    if( allow_ins==true )
      word.AddArc( i, StdArc( 2, 2, StdArc::Weight::One(), i ) );
  }

  if( allow_ins==true )
    word.AddArc( i, StdArc( 2, 2, StdArc::Weight::One(), i ) );
  word.SetFinal( i, StdArc::Weight::One() );
  ArcSort(&word,OLabelCompare<StdArc>());
  return;
}

//STEP 2: Create a filter, which adds multi-token links and skip support
void PhonetisaurusE2F::_make_ifilter( ){
  /*
    Create a filter FST.  This will map arcs in the linear 
    input FSA to longer clusters wherever appropriate. A more
    advanced version can be used to also place restrictions on
    how many phoneme insertions to allow, or how to penalize them.
  */
  ifilter.AddState();
  ifilter.SetStart(0);
  for( size_t j=2; j<isyms->NumSymbols(); j++ ){
    ifilter.AddArc( 0, StdArc( j, j, StdArc::Weight::One(), 0 ) );
  }

  typedef map<vector<string>, size_t>::iterator cl_iter;
  size_t k = 1;
  for( cl_iter it=iclusters->begin(); it != iclusters->end(); it++){
    ifilter.AddState();
    ifilter.AddArc( 0, StdArc( isyms->Find(it->first.at(0)), it->second, StdArc::Weight::One(), k ) );
    ifilter.AddArc( k, StdArc( isyms->Find(it->first.at(1)), 0, StdArc::Weight::One(), 0 ) );
    k++;
  }
  ifilter.SetFinal( 0, StdArc::Weight::One() );

  return;
}

void PhonetisaurusE2F::_load_iclusters( ){
  /*
    Compute the set of 'clustered' graphemes learned during 
    the alignment process. This information is encoded in
    the input symbols table.
  */

  for( size_t i = 2; i < isyms->NumSymbols(); i++ ){
    string sym = isyms->Find( i );
    if( sym.find(tie) != string::npos ){
      char* tmpstring = (char *)sym.c_str();
      char* p = strtok(tmpstring, tie.c_str());
      vector<string> cluster;
      while (p) {
        cluster.push_back(p);
        p = strtok(NULL, tie.c_str());
      }
            
      iclusters->insert(pair<vector<string>, size_t>(cluster, i));
    }
  }
  return;
}

void PhonetisaurusE2F::entry_to_fsa_m( vector<string>* tokens ){
  /*
    Convert an input word into an equivalent FSA.  In this case the 
    entire process is achieved via a 'mechanical' algorithm rather than 
    a series of atomic WFST-based operations.  
  */
    
  word.AddState();
  word.SetStart(0);

  //Build the basic FSA
  size_t i=0;    
  for( i=0; i<tokens->size(); i++){
    word.AddState();
    string ch = tokens->at(i);
    word.AddArc( i, StdArc( isyms->Find(ch), isyms->Find(ch), 0, i+1 ));
    if( allow_ins==true )
      word.AddArc( i, StdArc( 2, 2, StdArc::Weight::One(), i ) );
  } 
  if( allow_ins==true )
    word.AddArc( i, StdArc( 2, 2, StdArc::Weight::One(), i ) );
   
  //Add any cluster arcs
  map<vector<string>,size_t>::iterator it_i;
  for( it_i=iclusters->begin(); it_i!=iclusters->end(); it_i++ ){
    vector<string>::iterator it_j;
    vector<string>::iterator start = tokens->begin();
    vector<string> cluster = (*it_i).first;
    while( it_j != tokens->end() ){
      it_j = search( start, tokens->end(), cluster.begin(), cluster.end() );
      if( it_j != tokens->end() ){
	word.AddArc( it_j-tokens->begin(), StdArc( 
						  (*it_i).second,                     //input symbol
						  (*it_i).second,                     //output symbol
						  0,                                  //weight
						  it_j-tokens->begin()+cluster.size()   //destination state
						   ) );
	start = it_j+cluster.size();
      }
    }
  }    

  word.SetFinal( i, StdArc::Weight::One() );

  return;
}

void PhonetisaurusE2F::entry_to_fst_m( vector<string>* tokens ){
  /*
    Convert an input word into an equivalent FST.  In this case the 
    entire process is achieved via a 'mechanical' algorithm rather than 
    a series of atomic WFST-based operations.  
  */
    
  word.AddState();
  word.SetStart(0);

  //Build the basic FST
  size_t i=0;    
  for( i=0; i<tokens->size(); i++){
    word.AddState();
    size_t il = isyms->Find(tokens->at(i));
    for( size_t j=0; j<(*i2omap)[il].size(); j++ )
      word.AddArc( i, StdArc( il, (*i2omap)[il][j], StdArc::Weight::One(), i+1 ));
    if( allow_ins==true )
      for( size_t j=0; j<(*i2omap)[2].size(); j++ )
	word.AddArc( i, StdArc( 2, (*i2omap)[2][j], StdArc::Weight::One(), i ) );
  }
  if( allow_ins==true )
    for( size_t j=0; j<(*i2omap)[2].size(); j++ )
      word.AddArc( i, StdArc( 2, (*i2omap)[2][j], StdArc::Weight::One(), i ) );
    
  //Add any cluster arcs
  map<vector<string>,size_t>::iterator it_i;
  for( it_i=iclusters->begin(); it_i!=iclusters->end(); it_i++ ){
    vector<string>::iterator it_j;
    vector<string>::iterator start = tokens->begin();
    vector<string> cluster = (*it_i).first;
    while( it_j != tokens->end() ){
      it_j = search( start, tokens->end(), cluster.begin(), cluster.end() );
      if( it_j != tokens->end() ){
	for( size_t j=0; j<(*i2omap)[(*it_i).second].size(); j++ )
	  word.AddArc( it_j-tokens->begin(), StdArc( 
						    (*it_i).second,                     //input symbol
						    (*i2omap)[(*it_i).second][j],                     //output symbol
						    0,                                  //weight
						    it_j-tokens->begin()+cluster.size()   //destination state
						     ) );
	start = it_j+cluster.size();
      }
    }
  }    

  word.SetFinal( i, StdArc::Weight::One() );

  return;
}

/*
void PhonetisaurusE2F::_make_fsa_phi_filter( int phi_id ){
  
    Generate a composition filter suitable for correct
    phi-composition with an FSA style input.
    This is based on the suggestion from Prof. Brian Roark.
  
  VectorFst<StdArc> phifilter;
  phifilter.AddState();
  phifilter.SetStart(0);
  int st;

  map<size_t,vector<size_t> >::iterator it_i;
  int count = 0;
  for( it_i=i2omap->begin(); it_i!=i2omap->end(); it_i++ ){
      st = phifilter.AddState();
      size_t i = (*it_i).first;
      phifilter.AddArc( 0, StdArc( phi_id, phi_id, StdArc::Weight::One(), st ) );
      phifilter.AddArc( 0, StdArc(  i, 0, StdArc::Weight::One(), st ) );
      for( size_t j=0; j<(*it_i).second.size(); j++ ){
	size_t o = (*it_i).second[j];
	phifilter.AddArc( st, StdArc( 0, o, StdArc::Weight::One(), 0 ) );
      }
      count++;
  }
  phifilter.SetFinal(0,StdArc::Weight::One());
  phifilter.SetInputSymbols(isyms);
  phifilter.SetOutputSymbols(osyms);
  phifilter.Write("phifilter.fst");
  return;
}
*/

void PhonetisaurusE2F::_make_loop_and_iomap( const EncodeTable<StdArc>& table ){
  loop = new VectorFst<StdArc>();
  loop->AddState();
  loop->SetStart(0);
  
  if( verbose==true ){
    for( size_t i=1; i<=table.Size(); i++ ){
      const EncodeTable<StdArc>::Tuple *t = table.Decode(i);
      cout << "i=" << i << " in: " << isyms->Find(t->ilabel) << " out: " << osyms->Find(t->olabel) << endl;
    }
  }

  for( size_t i=2; i<=table.Size(); i++ ){
    const EncodeTable<StdArc>::Tuple *t = table.Decode(i);

    if( i2omap->find(t->ilabel)==i2omap->end() ){
      vector<size_t> m;
      m.push_back(t->olabel);
      i2omap->insert(pair<size_t, vector<size_t> >(t->ilabel, m));
      loop->AddArc( 0, StdArc( t->ilabel, t->olabel, StdArc::Weight::One(), 0 ) );
    }else{
      (*i2omap)[t->ilabel].push_back(t->olabel);
      loop->AddArc( 0, StdArc( t->ilabel, t->olabel, StdArc::Weight::One(), 0 ) );
    }
  }
  loop->SetFinal(0, StdArc::Weight::One());
  
  ArcSort(loop, ILabelCompare<StdArc>());
  return;
}
