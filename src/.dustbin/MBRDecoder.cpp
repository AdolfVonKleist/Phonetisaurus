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
#include "MBRDecoder.hpp"

MBRDecoder::MBRDecoder( ){
  //Default constructor
}

MBRDecoder::MBRDecoder( int _order, VectorFst<LogArc>* _lattice, float _alpha, vector<float> _thetas ){
  /*
    Preferred class constructor
  */
  order   = _order;
  syms    = new SymbolTable("syms");
  sigmaID = 1;
  rhoID   = 2;
  alpha   = _alpha;
  thetas  = _thetas;
  
  syms->AddSymbol("<eps>");
  syms->AddSymbol("<sigma>");
  syms->AddSymbol("<rho>");
  syms->AddSymbol("<phi>");
  for( unsigned int i=0; i<_lattice->InputSymbols()->NumSymbols(); i++ )
    syms->AddSymbol(_lattice->InputSymbols()->Find(i));
  Relabel(_lattice, syms, syms);
  lattice = new VectorFst<LogArc>();
  std_lattice = new VectorFst<StdArc>();

  _alpha_normalize(_lattice);

  ngrams.resize(order);
  
  for( int i=0; i<order; i++ ){
    mappers.push_back(new VectorFst<LogArc>() );
    pathcounters.push_back(new VectorFst<LogArc>() );
    latticeNs.push_back(new VectorFst<LogArc>() );
    omegas.push_back(new VectorFst<LogArc>());
  }
}

void MBRDecoder::build_decoder( ){
  /*
    Helper function that will build all required MBR decoder components.
    This includes the following:
       * Unique lattice Ngram sets
       * Ngram Context-Dependency transducers
       * Ngram path-counting automata
       * Integrated MBR decoder cores
  */
  //cout << "Map lattice and building counters.." << endl;
  Map(*lattice, std_lattice, LogToStdMapper());  
  *std_lattice = count_ngrams( std_lattice, order );
  //cout << "Finished counts WFST..." << endl;

  //Step 1. Extract all unique Ngrams up to 'order'
  //cout << "Extract ngrams..." << endl;
  extract_ngrams( std_lattice->Start(), vector<int>() );

  //Step 2. Construct N-gram CD FSTs from the result of 1.
  //cout << "Build ngram cd fsts..." << endl;
  build_ngram_cd_fsts( );

  //Step 3. Construct Psi pathcounter FSTs from the result of 1.
  //cout << "Build right pathcounters.." << endl;
  build_right_pathcounters( );

  //Step 4. Construct the decoders from the results of Steps 2. and 3.
  //cout << "build decoders..." << endl;
  build_decoders( );

  //Step 5. Finally find the shortest path through the decoder cascade
  //cout << "finally decode" << endl;
  decode( );

  return;
}

void MBRDecoder::decode( ){
  //First map the lattice weights to \Theta_{0}
  for( StateIterator<VectorFst<LogArc> > siter(*lattice); !siter.Done(); siter.Next() ){
    size_t i = siter.Value();
    for( MutableArcIterator<VectorFst<LogArc> > aiter(lattice,i); !aiter.Done(); aiter.Next() ){
      LogArc arc = aiter.Value();
      arc.weight = thetas[0];
      aiter.SetValue(arc);
    }
  }
  //lattice->SetInputSymbols(syms);
  //lattice->SetOutputSymbols(syms);
  //lattice->Write("normed-lattice.fst");
  //cout << "Start decoder compose" << endl;
  ArcSort(lattice, OLabelCompare<LogArc>());
  Compose(*lattice, *mappers[0], omegas[0]);
  Project(omegas[0],PROJECT_INPUT);
  ArcSort(omegas[0], OLabelCompare<LogArc>());
  //mappers[0]->Write("wmapper-0.fst");
  for( int i=1; i<order; i++ ){
    //cout << "decoder compose Order (" << i << ")" << endl;
    Compose(*omegas[i-1], *mappers[i], omegas[i]);
    Project(omegas[i],PROJECT_INPUT);
    ArcSort(omegas[i],OLabelCompare<LogArc>());
    //mappers[i]->Write("wmapper-"+to_string(i)+".fst");
    //omegas[i]->Write("omega-"+to_string(i)+".fst");
  }
  /*
  for( StateIterator<VectorFst<LogArc> > siter(*omegas[order-1]); !siter.Done(); siter.Next() ){
    size_t i = siter.Value();
    for( MutableArcIterator<VectorFst<LogArc> > aiter(omegas[order-1],i); !aiter.Done(); aiter.Next() ){
      LogArc arc = aiter.Value();
      arc.weight = arc.weight.Value() * -1.;
      aiter.SetValue(arc);
    }
  }
  */
  //omegas[order-1]->Write("omega-final.fst");
  //cout << "Finished decoding composition" << endl;
  return;
}

void MBRDecoder::_alpha_normalize( VectorFst<LogArc>* _lattice ){
  for( StateIterator<VectorFst<LogArc> > siter(*_lattice); !siter.Done(); siter.Next() ){
    size_t i = siter.Value();
    for( MutableArcIterator<VectorFst<LogArc> > aiter(_lattice, i); !aiter.Done(); aiter.Next() ){
      LogArc arc = aiter.Value();
      arc.weight = arc.weight.Value() * alpha;
      aiter.SetValue(arc);
    }
  }

  Push<LogArc, REWEIGHT_TO_FINAL>(*_lattice, lattice, kPushWeights);
  
  for( StateIterator<VectorFst<LogArc> > siter(*lattice); !siter.Done(); siter.Next() ){
    size_t i = siter.Value();
    if( lattice->Final(i)!=LogArc::Weight::Zero() ){
      lattice->SetFinal(i,LogArc::Weight::One());
    }
  }

  return;
}

void MBRDecoder::build_decoders( ){
  /*
    Construct the order-N lattices from the order-N
    context-dependency WFSTs and the raw input lattice.
  */
  ArcSort(lattice, OLabelCompare<LogArc>());
  lattice->SetInputSymbols(syms);
  lattice->SetOutputSymbols(syms);

  for( int i=0; i<order; i++ ){
    //cout << "  Setup..." << i << endl;
    ArcSort(mappers[i], ILabelCompare<LogArc>());
    mappers[i]->SetInputSymbols(syms);
    mappers[i]->SetOutputSymbols(syms);

    //
    //---Generate the order-N lattice---
    //
    //cout << "Lattice mapper compose..." << endl;
    Compose(*lattice, *mappers[i], latticeNs[i]);
    Project(latticeNs[i], PROJECT_OUTPUT);
    RmEpsilon(latticeNs[i]);
    string fname = "lattice-" + to_string(i) + ".fst";
    //latticeNs[i]->SetInputSymbols(syms);
    //latticeNs[i]->SetOutputSymbols(syms);
    //latticeNs[i]->Write(fname);

    //
    //---Compute the path-posterior N-gram probabilities---
    //
    pathcounters[i]->SetInputSymbols(syms);
    pathcounters[i]->SetOutputSymbols(syms);
    
    //cout << "  counting paths..." << endl;
    ArcSort( pathcounters[i], ILabelCompare<LogArc>() );
    ArcSort( latticeNs[i],    OLabelCompare<LogArc>() );
    countPaths( pathcounters[i], latticeNs[i], i );
  }
  //syms->WriteText("finalsyms.syms");
  return;
}


void MBRDecoder::countPaths( VectorFst<LogArc>* Psi, VectorFst<LogArc>* latticeN, int i ){
  /*
    Begin cascaded matcher stuff
    NOTE: Order and precedence matter!!!
  */

  //Sigma (any) matcher
  SM* sm = new SM( *Psi, MATCH_INPUT, sigmaID );
  //Rho (remaining) matcher
  RM* rm = new RM( *Psi, MATCH_INPUT, rhoID, MATCHER_REWRITE_AUTO, sm );

  ComposeFstOptions<LogArc, RM> opts;
  opts.gc_limit = 0;
  opts.matcher1 = new RM(*latticeN, MATCH_NONE,  kNoLabel);
  opts.matcher2 = rm;
  //End cascaded matcher stuff

  //Cast to normal VectorFst
  VectorFst<LogArc> result(ComposeFst<LogArc>(*latticeN, *Psi, opts));
  //cout << "Connecting..." << endl;
  //Connect(&result);
  //cout << "done.." << endl;
  //MODIFIED FORWARD IMPL
  UF posteriors;
  posteriors.set_empty_key(NULL);
  //cout << "Top sorting..." << endl;
  TopSort(&result);
  vector<LogArc::Weight> alphas(result.NumStates()+1,LogArc::Weight::Zero());
  alphas[0] = LogArc::Weight::One();
  vector<int> agrams(result.NumStates()+1);
  agrams[0] = 0;
  //cout << "Computing mod forward..." << endl;
  for( StateIterator<VectorFst<LogArc> > siter(result); !siter.Done(); siter.Next() ){
    size_t q = siter.Value();
    for( ArcIterator<VectorFst<LogArc> > aiter(result,q); !aiter.Done(); aiter.Next() ){
      LogArc arc = aiter.Value();
      alphas[arc.nextstate] = Plus(alphas[arc.nextstate],Times(alphas[q],arc.weight));
      if( arc.olabel==0 ){
	agrams[arc.nextstate] = agrams[q];
      }else{
	agrams[arc.nextstate] = arc.olabel;
	posteriors.insert(UF::value_type(arc.olabel,LogArc::Weight::Zero()));
      }
    }
  }
  for( StateIterator<VectorFst<LogArc> > siter(result); !siter.Done(); siter.Next() ){
    size_t q = siter.Value();
    if( result.Final(q)!=LogArc::Weight::Zero() ){
      LogArc::Weight w = Times(alphas[q],result.Final(q));
      //cout << "q: " << q << "  u[q]: " << syms->Find(agrams[q])
      //   << "  a[q]: " << alphas[q] << "  F[q]: " << result.Final(q)
      //   << "  a[q]xF[q]: " << w << endl;
      posteriors[agrams[q]] = Plus(posteriors[agrams[q]],w);
    }
  }
  //cout << "done with mod forward..." << endl;
  //for( UF::iterator p=posteriors.begin(); p!=posteriors.end(); p++ )
  //  cout << "u: " << syms->Find(p->first) << "  p(u|E): " << p->second << endl;
    
  //END MODIFIED FORWARD IMPL

  /*
  //Delete unconnected states and arcs
  //cout << "   Connect" << endl;
  //cout << "   Project" << endl;
  //Project output labels
  Project(&result, PROJECT_OUTPUT);

  //Remove epsilon arcs
  //cout << "   RmEpsilon" << endl;
  RmEpsilon(&result);

  //Determinize and minimize the result
  VectorFst<LogArc> detResult;
  //cout << "   Determinizing" << endl;
  Determinize( result, &detResult );
  //cout << "   Minimizing" << endl;
  Minimize( &detResult );
  string fname = "post-"+to_string(i)+".fst";
  //detResult.SetInputSymbols(syms);
  //detResult.SetOutputSymbols(syms);
  //detResult.Write(fname);
  //Now set the arc weights for the decoding transducer, which is just the 
  //order-N mapping transducer where the Psi weights have been applied 
  //to all the arcs.
  */

  for( StateIterator<VectorFst<LogArc> > siter(*mappers[i]); !siter.Done(); siter.Next() ){
    size_t id = siter.Value();
    for( MutableArcIterator<VectorFst<LogArc> > aiter(mappers[i],id); !aiter.Done(); aiter.Next() ){
      LogArc arc = aiter.Value();

      if( arc.olabel != 0 ){
	arc.weight = abs(posteriors[arc.olabel].Value())<0.000976562 ? thetas[i+1] : posteriors[arc.olabel].Value()*thetas[i+1];
	//cout << "V-weight: " << syms->Find(arc.olabel) << ": " << arc.weight << endl;
	aiter.SetValue(arc);
      }

      /*  
      for( ArcIterator<VectorFst<LogArc> > viter(detResult,0); !viter.Done(); viter.Next() ){
	const LogArc& varc = viter.Value();
	if( arc.olabel == varc.ilabel ){
	  arc.weight = varc.weight.Value()==0 ? thetas[i+1] : varc.weight.Value() * thetas[i+1];
	  cout << "T-weight: " << syms->Find(arc.olabel) << ": " << arc.weight << endl;
	}
      }
      */
    }
  }
  string fname = "wmapper-"+to_string(i)+".fst";
  //mappers[i]->Write(fname);
  //Project(mappers[i], PROJECT_INPUT);

  ArcSort( mappers[i], ILabelCompare<LogArc>() );

  //lattice->SetInputSymbols(syms);
  //lattice->SetOutputSymbols(syms);
  //lattice->Write("normed-lattice.fst");

  return;
}


void MBRDecoder::build_right_pathcounters( ){
  for( unsigned int i=0; i<ngrams.size(); i++ ){
    set<vector<int> >::iterator ait;
    pathcounters[i]->AddState();
    pathcounters[i]->SetStart(0);
    pathcounters[i]->AddArc(0, LogArc( 1, 0, LogArc::Weight::One(), 0 ) );
    for( ait=ngrams[i].begin(); ait!=ngrams[i].end(); ait++ ){
      int rhoid   = pathcounters[i]->AddState();
      int final   = pathcounters[i]->AddState();
      int ngramid = syms->Find(_vec_to_string(&(*ait)));
      pathcounters[i]->AddArc( 0, LogArc( ngramid, ngramid, LogArc::Weight::One(), rhoid ) );
      pathcounters[i]->SetFinal(rhoid, LogArc::Weight::One());
      pathcounters[i]->AddArc( rhoid, LogArc( 2, 0, LogArc::Weight::One(), rhoid ) );
      pathcounters[i]->AddArc( rhoid, LogArc( ngramid, 0, LogArc::Weight::One(), final ) );
    }
    string fstname = "rpathcounter-" + to_string(i) + ".fst";
    pathcounters[i]->SetInputSymbols(syms);
    pathcounters[i]->SetOutputSymbols(syms);
    //pathcounters[i]->Write(fstname);
  }
  return;
}

void MBRDecoder::build_left_pathcounters( ){
  for( unsigned int i=0; i<ngrams.size(); i++ ){
    set<vector<int> >::iterator ait;
    pathcounters[i]->AddState();
    pathcounters[i]->SetStart(0);
    int final = pathcounters[i]->AddState();
    for( ait=ngrams[i].begin(); ait!=ngrams[i].end(); ait++ ){
      int rhoid   = pathcounters[i]->AddState();
      int ngramid = syms->Find(_vec_to_string(&(*ait)));
      pathcounters[i]->AddArc( 0, LogArc( 0, 0, LogArc::Weight::One(), rhoid ) );
      pathcounters[i]->AddArc( rhoid, LogArc( 2, 0, LogArc::Weight::One(), rhoid ) );
      pathcounters[i]->AddArc( rhoid, LogArc( ngramid, ngramid, LogArc::Weight::One(), final ) );
    }
    pathcounters[i]->AddArc( final, LogArc( 1, 0, LogArc::Weight::One(), final ) );

    string fstname = "lpathcounter-" + to_string(i) + ".fst";
    pathcounters[i]->SetInputSymbols(syms);
    pathcounters[i]->SetOutputSymbols(syms);
    //pathcounters[i]->Write(fstname);
  }
  return;
}

void MBRDecoder::build_ngram_cd_fsts( ){
  /*
    Parent function to build the individual order-N Ngram
    context-dependency transducers.
  */
  for( unsigned int i=0; i<ngrams.size(); i++ ){
    //Build the Ngram trees from the Ngram sets
    //cout << "starting cd...: " << i << endl;
    mappers[i]->AddState();
    mappers[i]->SetStart(0);
    set<vector<int> >::iterator it;
    for( unsigned int j=0; j<=i; j++ ){
      for( it=ngrams[j].begin(); it!=ngrams[j].end(); it++ ){
	vector<int> ngram = (*it);
	//cout << "adding ngram..." << endl;
	add_ngram( mappers[i], mappers[i]->Start(), ngram, &(*it), (j==i ? true : false) );
      }
    }
    //cout << "finished cd.." << endl;
    //Next, connect the final states based on the allowable 
    // transitions found in the original input word lattice.
    connect_ngram_cd_fst( mappers[i], i );
    //cout << "finished connect" << endl;
    string fstname = "mapper-cd-"+to_string(i)+".fst";
    mappers[i]->SetInputSymbols(syms);
    mappers[i]->SetOutputSymbols(syms);
    //mappers[i]->Write(fstname);
  }
  return;
}

void MBRDecoder::connect_ngram_cd_fst( VectorFst<LogArc>* mapper, int i ){
  for( set<vector<int> >::iterator ait=ngrams[i].begin(); ait!=ngrams[i].end(); ait++ ){
    vector<int> ngram = (*ait);
    //cout << "trying to get an arc..." << endl;
    LogArc iarc = _get_arc( mapper, mapper->Start(), ngram  );
    ngram.erase(ngram.begin());
    for( set<vector<int> >::iterator bit=ngrams[0].begin(); bit!=ngrams[0].end(); bit++ ){
      string label = _vec_to_string(&ngram) + syms->Find(bit->at(0));
      if( syms->Find(label)!=SymbolTable::kNoSymbol ){
	ngram.push_back(bit->at(0));
	//cout << "get that arc!" << endl;
	LogArc oarc = _get_arc( mapper, mapper->Start(), ngram );
	//cout << "Trying to add oarc: " << iarc.nextstate << " " << syms->Find(oarc.ilabel) << ":" << syms->Find(oarc.olabel) << " " << oarc.nextstate << endl;
	if( oarc.weight != LogArc::Weight::Zero() )
	  mapper->AddArc( iarc.nextstate, LogArc( oarc.ilabel, oarc.olabel, LogArc::Weight::One(), oarc.nextstate ) );
	//cout << "added" << endl;
	ngram.pop_back();
	//cout << "popped" << endl;
      }
    }
  }

  return;
}

LogArc MBRDecoder::_get_arc( VectorFst<LogArc>* mapper, int i, vector<int> ngram ){
  //We are ASS-U-ME-ing there is a match.  
  //This will break if I fucked up somewhere else (highly likely).
  if( ngram.size()==1 ){
    //cout << "really a match?" << endl;
    for( ArcIterator<VectorFst<LogArc> > aiter(*mapper,i); !aiter.Done(); aiter.Next() ){
      LogArc arc = aiter.Value();
      //cout << "looking" << endl;
      if( arc.ilabel==ngram[0] ){
	//cout << "found a match!" << endl;
	return arc;
      }
    }
    //maybe we didn't find a match. this means there is an issue withh the algo
    return LogArc( 0, 0, LogArc::Weight::Zero(), 1 );
  }
	
  if( ngram.size()>1 ){
    //cout << "searching..." << endl;
    for( ArcIterator<VectorFst<LogArc> > aiter(*mapper,i); !aiter.Done(); aiter.Next() ){
      LogArc arc = aiter.Value();
      //cout << "found" << endl;
      if( arc.ilabel==ngram[0] ){
	ngram.erase(ngram.begin());
	return _get_arc( mapper, arc.nextstate, ngram );
      }
    }
  }
  //This should never be reached... just to temporarily
  // satisfy -Wall...
  //return LogArc( 0, 0, LogArc::Weight::Zero(), 1 );
}

string MBRDecoder::_vec_to_string( const vector<int>* vec ){
  /*
    Convenience function for converting a pointer to a vector
    of ints to a string based on the input symbol table.
    Mainly used for constructing the Ngram CD transducers.
  */
  string label = "";
  for( unsigned int i=0; i<vec->size(); i++ )
    label += syms->Find(vec->at(i));
  return label;
}

void MBRDecoder::add_ngram( VectorFst<LogArc>* mapper, int state, vector<int> ngram, const vector<int>* lab, bool olab ){
  /*
    Recursively add Ngrams to the order-N ngram tree.  This forms the basis for
    the order-N lattice-Ngram context-dependency transducer.
  
    The recursion is basically the same as the 'extract_ngrams' function, the 
    salient difference being that in this case we are *adding* Ngrams to a 
    partially developed, deterministic tree, while in 'extract_ngrams' we are
    ...extracting Ngrams from a complete lattice.

    This could also be achieved by building the order-N counting transducer, 
    then removing lattice weights, composing with the input lattice and optimizing
    using the Tropical semiring throughout:
            Det( RmEps( Proj_o( L * Counter ) ) )

    In practice I think this will tend to be a lot slower, especially for larger 
    lattices, but I need to analyze it properly to prove that this is the case.

    This could *also* be achieved by building linear string FSTs for each Ngram,
    then computing,
      Det( Union( [s_1, ..., s_R] ) )
    but the determinization and union operations are a little bit annoying to use.
  */
  bool found_ngram = false;

  //Try to find the next label in the current Ngram.  If we don't find it, we will 
  // add it to the Ngram tree.
  //cout << "ADD NGRAM" << endl;
  if( ngram.size()==0 ) return;
  for( ArcIterator<VectorFst<LogArc> > aiter(*mapper,state); !aiter.Done(); aiter.Next() ){
    const LogArc arc = aiter.Value();
    //cout << "final size: " << ngram.size() << endl;
    if( arc.ilabel==ngram[0] ){
      found_ngram = true;
      //cout << "true" << endl;
      ngram.erase(ngram.begin());
      add_ngram( mapper, arc.nextstate, ngram, lab, olab );
    }
  }

  //If no matching arc was found for the current Ngram word, add a new arc to the WFST.
  if( found_ngram==false ){
    int sid = mapper->AddState();
    //If we only have one word/token left in the Ngram vector, then this is a final state.
    //At this point we will also index the arc so that we know which final nodes need 
    // extra arcs based on our available Ngram histories.
    //cout << "false adding.." << endl;
    if( ngram.size()==1 ){
      if( olab==true )
	mapper->AddArc( state, LogArc( ngram[0], syms->AddSymbol(_vec_to_string(lab)), LogArc::Weight::One(), sid ) );
      else
	mapper->AddArc( state, LogArc( ngram[0], 0, LogArc::Weight::One(), sid ) );
      mapper->SetFinal( sid, LogArc::Weight::One() );
    //If we have more than one remaining token in the Ngram vector, add a new arc and 
    // continue recursively calling 'add_ngram'.  This is not a final state.
    }else if( ngram.size()>1 ){
      //cout << "false keep going" << endl;
      mapper->AddArc( state, LogArc( ngram[0], 0, LogArc::Weight::One(), sid ) );
      //All states except the start state are final states.  
      //Strictly speaking, this violates the idea of real context-dependency
      // because for N-gram order > 1 this means that paths of length < order
      // will still be mapped - albeit to epsilon.  This is necessary for the 
      // decoding procedure however, as we need to project the input back for 
      // each iteration.  This means that if we do NOT add these final states
      // any paths of length < order will be discarded prior to finishing.
      //Hopefully that makes sense.
      mapper->SetFinal( sid, LogArc::Weight::One() );
      ngram.erase(ngram.begin());
      add_ngram( mapper, sid, ngram, lab, olab );
    }
  }
  
  return;
}


void MBRDecoder::extract_ngrams( int state, vector<int> ngram ){
  /*
    Recursively traverse the input lattice and extract all unique Ngrams of length >= order.
    Effectively the 'ngram' vector functions as a sort of stack with a fixed size <= order.  

    The algorithm begins by pushing the first arc label into the 'ngram' vector, then 
    recursively following the destination state of the arc and repeating this procedure.
    If 'ngram' is non-empty then each 'ngram' of length <= order is added to the set of 
    unique lattice Ngrams.  Arc labels are added to the end, and Ngrams are extracted starting
    from the end of the 'ngram' vector, effectively making this a modified FIFO stack. This
    ensures that the string/sentence-final Ngrams are extracted correctly.

    Finally, whenever pushing a new arc label onto the stack results in the stack size increasing
    to length >= order, the *bottom* label is shifted from the stack.  This ensures that 
    no Ngrams of length > order are extracted.

      Example for a linear automaton:
          Sentence = "a b a b b", Order=3
	  Step 1:  
	     - 'a' is pushed onto 'ngram'
	     * ngram = [ 'a' ]
	     - 'a' is inserted into the 1-gram set
	     * ngram = [ 'a' ]
	  Step 2:  
	     - 'b' is pushed onto 'ngram'
	     * ngram = [ 'a', 'b' ]
	     - 'b' is inserted into the 1-gram set
	     - 'ab' is inserted into the 2-gram set
	     * ngram = [ 'a', 'b' ]
	  Step 3: 
	     - 'a' is pushed onto 'ngram'
	     * ngram = [ 'a', 'b', 'a' ]
	     - 'a' is ignored since it has already been added to the 1-gram set
	     - 'ba' is inserted into the 2-gram set
	     - 'aba' is inserted into the 3-gram set
	     - 'a' is shifted from the bottom of the ngram vector/stack
	     * ngram = [ 'b', 'a' ]
	  Step 4:
	     - 'b' is pushed onto 'ngram'
	     * ngram = [ 'b', 'a', 'b' ]
	     - 'b' is ignored since it has already been added to the 1-gram set
	     - 'ab' is ignored since it has already been added to the 2-gram set
	     - 'bab' is inserted into the 3-gram set
	     - 'b' is shifted from the bottom of the ngram vector/stack
	     * ngram = [ 'a', 'b' ]
	  Step 5:
	     - 'b' is pushed onto 'ngram'
	     * ngram = [ 'a', 'b', 'b' ]
	     - 'b' is ignored since it has already been added to the 1-gram set
	     - 'bb' is inserted into the 2-gram set
	     - 'abb' is inserted into the 3-gram set
	     - 'a' is shifted from the bottom of the ngram vector/stack
	     * ngram = [ 'b', 'b' ]

	   +-+ Algorithm terminates, having collected all unique Ngrams of order<=3
	     { 1:['a','b'], 2:['ab','ba','bb'], 3:['aba','bab',abb'] }

    Although it currently does not, this function could be easily augmented to also accumulate
    counts, which should be *MUCH* more efficient than using the pure WFST-based counting 
    methods.

    The vector of Ngram sets that this function computes is used for two purposes:
          1.)  To subsequently construct order-specific context-dependency 
	       transducers which in turn are used to compile the order-specific 
	       hierarchical MBR decoders for hypothesis lattices
	  2.)  To subsequently construct order-specific path-counting automata which 
	       are utilized to estimate the posterior lattice Ngram probabilities,
	          p( u_{n,i} | \mathcal{E}_{n} )
	       where u_{n,i} refers to a particular Ngram of order 'n' with label 
	       identity 'i', and \mathcal{E}_{n} refers to the order-n lattice.
  */

  //If the ngram vector is non-empty, extract all Ngrams and add them to the 
  // set of unique Ngrams.  Any Ngrams that have already been found will be ignored.
  if( ngram.size()>0 )
    for( int i=ngram.size(); i>=0; i-- )
      for( unsigned int j=i; j<ngram.size(); j++ )
	ngrams[ngram.size()-j-1].insert( vector<int>(ngram.begin()+j, ngram.end()) );

  //If the size of the ngram vector/stack has grown to >= order, then pop the first/lowest
  // item currently in the vector.
  if( ngram.size()>=(unsigned int)order )
    ngram.erase(ngram.begin());

  //Recurse through the entire lattice.  We have to make a copy of 'ngram' before each
  // call or else the ngram contents for states with more than one out-going arc will
  // be incorrect.  I'm pretty sure that despite all this the approach is still loads
  // faster and more memory and space efficient than using standard WFST operations.
  //Nevertheless it would be worth double-checking this at a later date, both analytically
  // and empirically with several of the G2P datasets.  More fodder for the journal...
  for( ArcIterator<VectorFst<StdArc> > aiter(*std_lattice,state); !aiter.Done(); aiter.Next() ) {
    const StdArc& arc = aiter.Value();
    vector<int> n_ngram = ngram;
    n_ngram.push_back(arc.ilabel);
    extract_ngrams( arc.nextstate, n_ngram );
  }

  return;
}

void MBRDecoder::build_mappers( ){
  
  return;
}

void MBRDecoder::build_pathcounters( bool _right ){
  if( _right==true )
    build_right_pathcounters( );
  else
    build_left_pathcounters( );
  return;
}

VectorFst<StdArc> MBRDecoder::count_ngrams( VectorFst<StdArc>* std_lattice, int order ){
  /*
    Build an N-gram counting transducer using sigma transitions and 
    extract N-gram occurences from an arbitrary input std_lattice.
  */
  SymbolTable* syms = new SymbolTable("syms");
  syms->AddSymbol("<eps>");
  syms->AddSymbol("<sigma>");
  for( unsigned int i=0; i<std_lattice->InputSymbols()->NumSymbols(); i++ )
    syms->AddSymbol(std_lattice->InputSymbols()->Find(i));
  Relabel(std_lattice, syms, syms);
  ArcSort(std_lattice,OLabelCompare<StdArc>());
  ArcMap(std_lattice, RmWeightMapper<StdArc>());
  //cout << "rmweights ready to iterate" << endl;
  for( StateIterator<VectorFst<StdArc> > siter(*std_lattice); !siter.Done(); siter.Next() ){
    size_t i = siter.Value();
    if( std_lattice->Final(i)!=StdArc::Weight::Zero() )
      std_lattice->SetFinal(i,StdArc::Weight::One());
  } 
  VectorFst<StdArc>* counter = new VectorFst<StdArc>();
  
  size_t start = counter->AddState();
  counter->SetStart(start);
  counter->AddArc( start, StdArc( 1, 0, StdArc::Weight::One(), start ) );
  //cout << "building counters" << endl;
  for( int i=1; i<=order; i++ ){
    size_t state = counter->AddState();
    for( unsigned int j=4; j<syms->NumSymbols(); j++ ){
      counter->AddArc( i-1, StdArc( j, j, StdArc::Weight::One(), i ) );
      counter->SetFinal( i, StdArc::Weight::One() );
    }
  }
  size_t final = counter->NumStates()-1;
  //cout << "adding final arcs" << endl;
  counter->AddArc( final, StdArc( 1, 0, StdArc::Weight::One(), final ) );
  for( unsigned int i=1; i<final; i++ )
    counter->AddArc( i, StdArc( 1, 0, StdArc::Weight::One(), final ) );
  //counter->SetFinal( final, StdArc::Weight::One() );
  counter->SetInputSymbols(syms);
  counter->SetOutputSymbols(syms);
  //counter->Write("counter-s.fst");
  ArcSort(counter,ILabelCompare<StdArc>());
  SSM* sm = new SSM( *counter, MATCH_INPUT, 1 );
  ComposeFstOptions<StdArc, SSM> opts;
  opts.gc_limit = 0;
  opts.matcher1 = new SSM(*std_lattice, MATCH_NONE,  kNoLabel);
  opts.matcher2 = sm;
  //cout << "ngram count compose " << endl;
  ComposeFst<StdArc> fstc(*std_lattice, *counter, opts);
  VectorFst<StdArc> tmp(fstc);
  Project(&tmp, PROJECT_OUTPUT);
  RmEpsilon(&tmp);
  DeterminizeFst<StdArc> det(tmp);
  VectorFst<StdArc> counts(det);
  Minimize(&counts);
  counts.SetInputSymbols(syms);
  counts.SetOutputSymbols(syms);

  return counts;
}
