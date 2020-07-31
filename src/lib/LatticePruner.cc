/*
 LatticePruner.cpp 

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
using namespace std;
#include "include/LatticePruner.h"


LatticePruner::LatticePruner( ){
  //Default constructor
}

LatticePruner::LatticePruner( LabelData _penalties, TropicalWeight _beam, int _nbest, bool _fb, bool _penalize ) {
  penalties = _penalties;
  penalize  = _penalize;
  beam      = _beam;
  nbest     = _nbest;
  fb        = _fb;
}

LatticePruner::LatticePruner( TropicalWeight _beam, int _nbest, bool _fb ) {
  //TODO
  beam     = _beam;
  nbest    = _nbest;
  fb       = _fb;
  penalize = false;
}

void LatticePruner::prune_fst( VectorFst<StdArc>* fst ){
  /*
    Apply several optional pruning heuristics to the lattice.
  */
  if( penalize==true )
    _penalize_arcs( fst );

  if( fb==true )
    _forward_backward( fst );

  if( nbest==1 ){
    //If N=1 then all the remaining stuff is a waste of time.
    //This is because the pruning heuristics are all computed
    // *relative* to the 1-best hypothesis.  
    //This is in contrast LMBR and arc penalization.
    *fst = _nbest_prune( fst );
    return;
  }


  if( beam.Value() != LogWeight::Zero() )
    Prune( fst, beam );

  if( nbest > 1 )
    *fst = _nbest_prune( fst );

  return;
}

VectorFst<StdArc> LatticePruner::_nbest_prune( VectorFst<StdArc>* fst ){
  /* 
     This is just a destructive wrapper for the OpenFst ShortestPath 
     implementation.  I wish they'd implement desctructive versions of
     all the algos in the library...
  */
  VectorFst<StdArc> sfst;

  ShortestPath( *fst, &sfst, nbest );  

  return sfst;
}

void LatticePruner::_forward_backward( VectorFst<StdArc>* fst ){
  /*
    OpenFst-based implementation of forward-backward lattice pruning based on,
       Sixtus and Ortmanns, "HIGH QUALITY WORD GRAPHS USING FORWARD-BACKWARD PRUNING", 1999

    Note-to-self: It seems to give consistent WER and PER improvements so I guess I 
     got the implementation right, but it seems like maybe it was too easy.
  */
  //Setup
  VectorFst<LogArc>* pfst = new VectorFst<LogArc>();
  VectorFst<LogArc>* lfst = new VectorFst<LogArc>();
  vector<LogWeight>  alpha, beta;

  Map(*fst, lfst, StdToLogMapper());

  //Normalize so that subsequent operations don't go crazy
  Push<LogArc, REWEIGHT_TO_FINAL>(*lfst, pfst, kPushWeights);
  for( StateIterator<VectorFst<LogArc> > siter(*pfst); !siter.Done(); siter.Next() ){
    size_t i = siter.Value();
    if( pfst->Final(i)!=LogArc::Weight::Zero() ){
      pfst->SetFinal(i,LogArc::Weight::One());
    }
  }

  //Compute Forward and Backward probabilities
  ShortestDistance( *pfst, &alpha );
  ShortestDistance( *pfst, &beta, true );

  //Compute arc posteriors.  This is the same as the Expectation step.
  for( StateIterator<VectorFst<LogArc> > siter(*pfst); !siter.Done(); siter.Next() ){
    LogArc::StateId q = siter.Value();
    for( MutableArcIterator<VectorFst<LogArc> > aiter(pfst,q); !aiter.Done(); aiter.Next() ){
      LogArc    arc   = aiter.Value();
      LogWeight gamma = Divide(Times(Times(alpha[q], arc.weight), beta[arc.nextstate]), beta[0]);

      if( gamma.Value()==gamma.Value() ){
        arc.weight = gamma;
        aiter.SetValue(arc);
      }
    }
  }

  Map(*pfst, fst, LogToStdMapper()); 

  delete lfst;
  delete pfst;
  return;
}

void LatticePruner::_penalize_arcs( VectorFst<StdArc>* fst ){

  for( StateIterator<VectorFst<StdArc> > siter(*fst); !siter.Done(); siter.Next() ){
    StdArc::StateId q = siter.Value();
    for( MutableArcIterator<VectorFst<StdArc> > aiter(fst,q); !aiter.Done(); aiter.Next() ){
      StdArc     arc = aiter.Value();
      LabelDatum* ld = &penalties[arc.ilabel];

      if( ld->lhs>1 && ld->rhs>1 ){
        arc.weight = 999; 
      }else{
        arc.weight = arc.weight.Value() * ld->max;
      }
      if( arc.weight == LogWeight::Zero() )
        arc.weight = 999;
      if( arc.weight != arc.weight )
        arc.weight = 999;
      aiter.SetValue(arc);
    }
  }

  return;
}

