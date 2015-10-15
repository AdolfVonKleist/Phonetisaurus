#ifndef FSTPATHFINDER_H
#define FSTPATHFINDER_H
/*
 FstPathFinder.hpp 

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
using namespace fst;

struct PathData{
  vector<int> path;
  LogWeight   cost;
  PathData( vector<int> p, LogWeight c ) : path(p), cost(c) {}
};

struct pathdata_pred {
  bool operator()(const PathData &item1, const PathData &item2) {
    return item1.cost.Value() < item2.cost.Value();
  }
};

class FstPathFinder{
  /*
    Simple path-finder class.  Suitable for traversing the result of ShortestPath().
    Performs a sum over redundant paths utilizing the log semiring.

    This allows us to avoid log-semiring determinization of the lattice, which can
     often be very costly, while still achieving the same result: 
     costs for identical paths are summed.
    
  */

public:
  unsigned int band;   //The 'band' parameter is basically a secondary
                   // pruning heuristic.  It will stop traversining
                   // the N-best lattice as soon as paths.size()>band
                   //NOTE: if we have 4 hypotheses:  
                   //    (b,.3), (a,.2), (c,.17), (a,.15) 
                   // then band=3 would cause (a,.15) to be ignored
                   // and its cost would not be added to the total for 
                   // 'a'.  The resulting list would not take account
                   // of all the actual evidence.  Use with caution!

  set<int> skip;   //Ignore/skip these tokens.
                   //Typically includes <eps> and insertion/deletion
                   //Ensures that paths like:
                   //  'a b <eps> c'
                   //  'a <eps> b c'
                   //  '<ins> a <del> b c'
                   //  'a b c'
                   //Are all considered the same.
  vector<PathData> paths;

  FstPathFinder( ); 
  FstPathFinder( set<int> _skip, unsigned int _band=999999 );

  void extract_all_paths( const VectorFst<StdArc>& ifst );

private:
  void _extract_paths( const VectorFst<StdArc>& ifst, StdArc::StateId id, vector<int>& path, LogWeight cost );

};

#endif //FSTPATHFINDER_H
