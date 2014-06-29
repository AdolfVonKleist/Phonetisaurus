/*
 FstPathFinder.cpp

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
#include "FstPathFinder.h"

FstPathFinder::FstPathFinder ( ) {
  //By default we'll just skip <eps>
  skip.insert(0);
  band = 999999;
}

FstPathFinder::FstPathFinder( set<int> _skip, unsigned int _band ){
  skip  = _skip;
  band  = _band;
}

void FstPathFinder::extract_all_paths( const VectorFst<StdArc>& ifst ){
  vector<int> path;
  //Extract the paths
  _extract_paths( ifst, ifst.Start(), path, LogWeight::One() );
  //Now resort them in case the order has changed
  ////This actually seems to make the results WORSE not better
  ////Maybe because we aren't normalizing the lattice?
  //// CHECK IT LATER
  ////sort(paths.begin(), paths.end(), pathdata_pred());
  return;
}

void FstPathFinder::_extract_paths( const VectorFst<StdArc>& ifst, StdArc::StateId id, 
				    vector<int>& path, LogWeight cost ){

  if( ifst.Final(id) != TropicalWeight::Zero() ){
    cost = Times(cost, ifst.Final(id).Value());
    //We will almost always have unique nbest<10 so this is actually pretty efficient
    bool equals = false;
    for( unsigned int i=0; i<paths.size(); i++ ){
      //If the path is redundant, sum the probability mass
      if( equal( path.begin(), path.end(), paths[i].path.begin() ) ){
	////This actually seems to make the results WORSE not better
	////Maybe because we aren't normalizing the lattice?
	//// CHECK IT LATER
	////paths[i].cost = Plus(paths[i].cost, cost);
	equals = true;
      }
    }

    //If this is a new path, add it to the vector
    if( equals==false )
      paths.push_back( PathData(path, cost) );
    //Now clear the path and terminate the recursion
    path.clear();
    return;
  }


  for( ArcIterator<VectorFst<StdArc> > aiter(ifst,id); !aiter.Done(); aiter.Next() ) {
    const StdArc& arc = aiter.Value();
    if( skip.count(arc.ilabel)==0 )
      path.push_back(arc.ilabel);
    if( paths.size()<=band )
      _extract_paths( ifst, arc.nextstate, path, Times(cost, arc.weight.Value()) );
  }

}
