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
#include "PhonetisaurusOmega.hpp"

PhonetisaurusOmega::PhonetisaurusOmega( ) {
    //Default constructor
}

PhonetisaurusOmega::PhonetisaurusOmega( const char* _g2pmodel_file, string _decoder_type,
					bool _logopt, int _beam, int _nbest, bool _lmbr, 
					int _order, float _alpha, float _prec, 
					float _ratio, int _verbose, bool _allow_ins, float _thresh
					){

  g2pmodel = VectorFst<StdArc>::Read( _g2pmodel_file );
  if(g2pmodel == NULL) return;

  //Initialize
  decoder_type = _decoder_type;
  logopt    = _logopt;
  allow_ins = _allow_ins;
  lmbr      = _lmbr;
  beam      = _beam;
  nbest     = _nbest;
  order     = _order;
  alpha     = _alpha;
  prec      = _prec;
  ratio     = _ratio;
  thresh    = _thresh;
  verbose   = _verbose;

  //Have to make a copy in case we encode the model
  isyms = *g2pmodel->InputSymbols();
  osyms = *g2pmodel->OutputSymbols();

  tie  = isyms.Find(1); //The separator  symbol is reserved for index 1
  skip = isyms.Find(2); //The del/ins character is reserved for index 2
  encoder = new EncodeMapper<StdArc>(kEncodeLabels, ENCODE);

  if( decoder_type.compare("fst_phi")==0 ){
    cerr << "Preparing model for 'fst_phi' style decoding." << endl;
    _phi_ify( );
    Encode(g2pmodel, encoder);
    e2f = new PhonetisaurusE2F(encoder->table(), 0, allow_ins, &isyms, &osyms);
  }else if( decoder_type.compare("fsa_phi")==0 ){
    cerr << "Preparing model for 'fsa_phi' style decoding." << endl;
    _phiify_fst( g2pmodel );
    _phi_ify( );
    e2f = new PhonetisaurusE2F(0, allow_ins, &isyms, &osyms);
  }else if( decoder_type.compare("fsa_eps")==0 ){
    cerr << "Using 'fsa_eps' approach.  No model modifications required." << endl;
    e2f = new PhonetisaurusE2F(0, allow_ins, &isyms, &osyms);
  }else{
    cerr << "--decoder_type must be 'fst_phi', 'fsa_phi' or 'fsa_eps'" << endl;
    exit(0);
  }
  ArcSort( g2pmodel, ILabelCompare<StdArc>() );
}

VectorFst<StdArc> PhonetisaurusOmega::phoneticize( vector<string>* tokens, bool _project ){
  /*                                                                       
    Compose with phi (failure) transitions.                                
  */

  //Convert the token sequence into an appropriate FSM
  e2f->word = VectorFst<StdArc>();
  
  if( decoder_type.compare("fst_phi")==0 ){
    //ORIGINAL VERSION
    //If using failure transitions we have to encode the result
    e2f->entry_to_fst_m( tokens );
  }else{
    e2f->entry_to_fsa_m( tokens );
  }

  decode( );

  //This will modify the pronunciation lattice, finally
  // applying the 'logopt', 'nbest' and 'decoder-type' 
  // parameters to return a final, topologically sorted,
  // acyclic pronunciation lattice
  if( _project==true ){
    _extract_hypotheses( tokens );
    word.SetInputSymbols(&osyms);
    word.SetOutputSymbols(&osyms);
  }else{
    //Used by perplexity tool
    VectorFst<StdArc>* shortest = new VectorFst<StdArc>();
    ShortestPath( word, shortest, nbest );
    word = *shortest;
    delete shortest;
    word.SetInputSymbols(&isyms);
    word.SetOutputSymbols(&osyms);
  }
  return word;
}

VectorFst<StdArc>* PhonetisaurusOmega::decode( ){
  /*
    Abstracting the decode process so we can potentially modify the 
    e2f->word somewhere else.  Generalizes to the needs of the perplexity tool.
    Still not happy with the way it looks though...
  */

  if( decoder_type.compare("fst_phi")==0 ){
    //ORIGINAL VERSION
    //If using failure transitions we have to encode the result
    Encode(&e2f->word, encoder);
    ComposeFstOptions<StdArc, PM> opts;
    opts.gc_limit = 0;
    opts.matcher1 = new PM(e2f->word, MATCH_NONE, kNoLabel);
    //The encoder will map the backoff <eps>:<eps> pair to ID=1
    opts.matcher2 = new PM(*g2pmodel,   MATCH_INPUT, 1);
    word = VectorFst<StdArc>(ComposeFst<StdArc>(e2f->word, *g2pmodel, opts));
    //Now decode back to input-output symbols
    Decode(&word, *encoder);
    word.SetOutputSymbols(&osyms);
  }else if( decoder_type.compare("fsa_phi")==0 ){
    //FSA modded version
    e2f->word.SetOutputSymbols(g2pmodel->InputSymbols());
    ComposeFstOptions<StdArc, PM> opts;
    opts.gc_limit = 0;
    opts.matcher1 = new PM(e2f->word, MATCH_NONE, kNoLabel);
    opts.matcher2 = new PM(*g2pmodel,   MATCH_INPUT, 0);
    word = VectorFst<StdArc>(ComposeFst<StdArc>(e2f->word, *g2pmodel, opts));
  }else{
    //Normal epsilon version
    e2f->word.SetOutputSymbols(g2pmodel->InputSymbols());
    word = VectorFst<StdArc>(ComposeFst<StdArc>( e2f->word, *g2pmodel ));
  }
  return &word;
}

void PhonetisaurusOmega::_extract_hypotheses( vector<string>* tokens ){
  //word = VectorFst<StdArc>(ComposeFst<StdArc>(word,ofilter));
  Project(&word, PROJECT_OUTPUT);
  //RmEpsilon(&word);
  if( logopt==true ){
    VectorFst<LogArc>* lword = new VectorFst<LogArc>();
    Map(word, lword, StdToLogMapper());
    *lword = VectorFst<LogArc>(DeterminizeFst<LogArc>(*lword));
    RmEpsilon(lword);
    if( lmbr==true ){
      if( beam != -1 ){
	VectorFst<StdArc>* tword = new VectorFst<StdArc>();
	Map(*lword, tword, LogToStdMapper());
	VectorFst<StdArc>* sword = new VectorFst<StdArc>();
	ShortestPath(*tword, sword, beam);
	Map(*sword, lword, StdToLogMapper());
	delete tword;
	delete sword;
      }
    
      int N = _compute_thetas( tokens->size() );
      RmEpsilon(lword);
      *lword = VectorFst<LogArc>(DeterminizeFst<LogArc>(*lword));
      Minimize(lword);
      VectorFst<LogArc>* fword = new VectorFst<LogArc>();
      Map(*lword, fword, SuperFinalMapper<LogArc>());
      fword->SetInputSymbols(&osyms);
      fword->SetOutputSymbols(&osyms);
      MBRDecoder mbrdecoder( N, fword, alpha, thetas );
      cout << "Trying to decode..." << endl;
      mbrdecoder.build_decoder( );
      cout << "Finishing up..." << endl;
      Map(*mbrdecoder.omegas[N-1], &word, LogToStdMapper());
      //word.Write("mbrword.fst");
      osyms = *word.InputSymbols();
      delete fword;
    }else{
      Map(*lword, &word, LogToStdMapper());
    }
    delete lword;
  }


  if( nbest>1 ){
    LatticePruner pruner( thresh , nbest, false );
    pruner.prune_fst(&word);
  }

  VectorFst<StdArc>* shortest = new VectorFst<StdArc>();
  ShortestPath( word, shortest, nbest );
  word = *shortest;
  delete shortest;

  return;
}

int PhonetisaurusOmega::_compute_thetas( int wlen ){
  /*
    Theta values are computed on a per-word basis
    We scale the maximum order by the length of the input word.
    Higher MBR N-gram orders favor longer pronunciation hypotheses.
    Thus a high N-gram order coupled with a short word will
    favor longer pronunciations with more insertions.

      p=.63, r=.48
      p=.85, r=.72
    .918
    Compute the N-gram Theta factors for the
    model.  These are a function of,
      N:  The maximum N-gram order
      T:  The total number of 1-gram tokens 
      p:  The 1-gram precision
      r:  A constant ratio
       
    1) T may be selected arbitrarily.
    2) Default values are selected from Tromble 2008
  */
  thetas.clear();
  float T = 10.0;
  int N   = min( wlen+1, order );
  //cout << "N: " << N << endl;
  //Theta0 is basically an insertion penalty
  // -1/T
  thetas.push_back( -1/T );
  for( int n=1; n<=order; n++ )
    thetas.push_back( 1.0/((N*T*prec) * (pow(ratio,(n-1)))) );
  return N;
}


void PhonetisaurusOmega::_get_gp( VectorFst<StdArc>* fst, map<size_t, set<size_t> >* gp ){
  /*
    Compute the set of G<->P correspondences
  */
  for( StateIterator<VectorFst<StdArc> > siter(*fst); !siter.Done(); siter.Next() ){
    size_t st = siter.Value();
    for( ArcIterator<VectorFst<StdArc> > aiter(*fst, st); !aiter.Done(); aiter.Next() ){
      const StdArc arc = aiter.Value();
      if( arc.ilabel==0 )
        continue;

      if( gp->find(arc.ilabel)==gp->end() ){
        set<size_t> o;
        o.insert(arc.olabel);
        gp->insert(pair<size_t, set<size_t> >(arc.ilabel, o));
      }else{
        (*gp)[arc.ilabel].insert(arc.olabel);
      }
    }
  }

  return;
}

void PhonetisaurusOmega::_add_arcs( VectorFst<StdArc>* fst, size_t orig_st, size_t st, pair<size_t,size_t> p, double cost){
  size_t phi_id;
  double phi_cost;
  for( ArcIterator<VectorFst<StdArc> > aiter(*fst, st); !aiter.Done(); aiter.Next() ){
    const StdArc& arc = aiter.Value();
    if( arc.ilabel==0 ){
      phi_id = arc.nextstate;
      phi_cost = cost + arc.weight.Value();
      continue;
    }

    if( p.first==arc.ilabel && p.second==arc.olabel ){
      StdArc::Weight w = cost + arc.weight.Value();
      fst->AddArc( orig_st, StdArc( p.first, p.second, w, arc.nextstate ) );
      return;
    }
  }

  return _add_arcs( fst, orig_st, phi_id, p, phi_cost );
}

void PhonetisaurusOmega::_phiify_fst( VectorFst<StdArc>* fst ){
  /*
    Modify the WFST-based joint ngram model to make it compatible with phi-based 
    composition using FSA-based representation of the input word.  This requires 
    adding a number of new transitions, and significantly increases the size of the 
    input model.
  */
  map<size_t, set<size_t> > gp;
  _get_gp( fst, &gp );

  for( StateIterator<VectorFst<StdArc> > siter(*fst); !siter.Done(); siter.Next() ){
    size_t st = siter.Value();
    map<size_t, set<size_t> > ids;
    size_t phi_id;
    double phi_cost;
    for( ArcIterator<VectorFst<StdArc> > aiter(*fst, st); !aiter.Done(); aiter.Next() ){
      StdArc arc = aiter.Value();
      if( arc.ilabel==0 ){
        phi_id = arc.nextstate;
        phi_cost = arc.weight.Value();
        continue;
      }

      if( ids.find(arc.ilabel)==ids.end() ){
        set<size_t> o;
        o.insert(arc.olabel);
        ids.insert(pair<size_t, set<size_t> >(arc.ilabel,o));
      }else{
        ids[arc.ilabel].insert(arc.olabel);
      }
    }

    for( map<size_t, set<size_t> >::iterator it=ids.begin(); it!=ids.end(); it++ ){
      set<size_t> result;
      set_difference( 
                     gp[(*it).first].begin(), gp[(*it).first].end(),
                     (*it).second.begin(), (*it).second.end(),
                     inserter(result, result.end())
                      );

      for( set<size_t>::iterator jt=result.begin(); jt!=result.end(); jt++ ){
        pair<size_t,size_t> p((*it).first, *jt);
        _add_arcs( fst, st, phi_id, p, phi_cost );
      }

    }

  }

  return;
}


/*  PHI-IFY ALTERNATIVE */
void PhonetisaurusOmega::_phi_ify( ){
  for( StateIterator<VectorFst<StdArc> > siter(*g2pmodel); !siter.Done(); 
       siter.Next() ){
    StdArc::StateId st = siter.Value();
    if( g2pmodel->Final(st)==StdArc::Weight::Zero() ){
      _get_final_bow( st );
    }
  }
}
    
StdArc::Weight PhonetisaurusOmega::_get_final_bow( StdArc::StateId st ){
  if( g2pmodel->Final(st) != StdArc::Weight::Zero() )
    return g2pmodel->Final(st);

  for( ArcIterator<VectorFst<StdArc> > aiter(*g2pmodel,st); 
       !aiter.Done(); 
       aiter.Next() ){
    StdArc arc = aiter.Value();
    //Assume there is never more than 1 <eps> transition
    if( arc.ilabel == 0 ){
      StdArc::Weight w = Times(arc.weight, _get_final_bow(arc.nextstate));
      g2pmodel->SetFinal(st, w);
      return w;
    }
  }

  //Should never reach this place
  return StdArc::Weight::Zero();
}
